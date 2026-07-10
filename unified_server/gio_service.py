from __future__ import annotations

from dataclasses import asdict
from difflib import SequenceMatcher
from typing import Any, Iterator

from openai import OpenAI

from unified_server.gio_repository import GioDream, GioMessage, GioSupabaseRepository
from unified_server.settings import get_settings
from unified_server.providers import OPENAI_MODELS, ProviderRegistry
from unified_server.core.prompts import DEFAULT_SYSTEM_PROMPT


class GioService:
    def __init__(self, repository: GioSupabaseRepository | None = None, providers: ProviderRegistry | None = None) -> None:
        self.repository = repository or GioSupabaseRepository()
        self.providers = providers or ProviderRegistry()
        api_key = get_settings().OPENAI_API_KEY
        self.openai_client = OpenAI(api_key=api_key) if api_key else None

    def ensure_schema(self) -> None:
        self.repository.ensure_schema()

    def list_conversations(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in self.repository.list_conversations()]

    def create_conversation(self, title: str = "New Chat") -> dict[str, Any]:
        return asdict(self.repository.create_conversation(title=title))

    def rename_conversation(self, conversation_id: str, title: str) -> dict[str, Any]:
        self._require_conversation(conversation_id)
        cleaned = " ".join((title or "").split()).strip()
        if not cleaned:
            raise ValueError("Title cannot be empty.")
        return asdict(self.repository.update_conversation_title(conversation_id, cleaned))

    def delete_conversation(self, conversation_id: str) -> None:
        self._require_conversation(conversation_id)
        self.repository.delete_conversation(conversation_id)

    def get_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        self._require_conversation(conversation_id)
        return [
            self.serialize_message(item)
            for item in self.repository.get_messages(conversation_id)
            if item.role != "summary"
        ]

    def list_dreams(self, conversation_id: str | None = None) -> list[dict[str, Any]]:
        if conversation_id:
            self._require_conversation(conversation_id)
        return [self.serialize_dream(item) for item in self.repository.list_dreams(conversation_id)]

    def get_dream(self, dream_id: str) -> dict[str, Any]:
        dream = self.repository.get_dream((dream_id or "").strip())
        if not dream:
            raise ValueError("Dream not found.")
        return self.serialize_dream(dream)

    def create_dream(self, conversation_id: str) -> dict[str, Any]:
        self._require_conversation(conversation_id)
        transcript_messages = self.repository.get_messages(conversation_id)
        source_messages = [item for item in transcript_messages if item.role in {"user", "assistant"} and item.content.strip()]
        if len(source_messages) < 4:
            raise ValueError("Dream Mode needs a little more conversation first.")

        latest_summary = self.repository.get_latest_summary(conversation_id)
        selected_messages = self._select_dream_sources(source_messages)
        selected_ids = [item.id for item in selected_messages]
        existing_dreams = self.repository.list_dreams(conversation_id)
        if existing_dreams and existing_dreams[0].source_message_ids == selected_ids:
            raise ValueError("No new material since the latest dream entry.")

        title, content = self._dream_from_sources(conversation_id, selected_messages, latest_summary.content if latest_summary else None)
        dream = self.repository.create_dream(
            conversation_id=conversation_id,
            title=title,
            content=content,
            model=get_settings().GIO_DREAM_MODEL,
            source_message_ids=selected_ids,
            embedding=self._embed(content),
        )
        return self.serialize_dream(dream)

    def list_models(self, provider_name: str | None = None) -> dict[str, Any]:
        models = self._list_openai_models()
        default_model = get_settings().GIO_DEFAULT_MODEL if any(item["id"] == get_settings().GIO_DEFAULT_MODEL for item in models) else (models[0]["id"] if models else get_settings().GIO_DEFAULT_MODEL)
        return {
            "provider": "openai",
            "default_model": default_model,
            "models": models,
        }

    def list_openai_models(self) -> list[dict[str, Any]]:
        return self._list_openai_models()

    def _list_openai_models(self) -> list[dict[str, Any]]:
        if not self.openai_client:
            return [{"id": model, "supports_reasoning": False} for model in OPENAI_MODELS]
        try:
            response = self.openai_client.models.list()
            items = []
            for model in response.data:
                model_id = getattr(model, "id", "")
                if not self._is_supported_gio_model(model_id):
                    continue
                items.append(
                    {
                        "id": model_id,
                        "supports_reasoning": self._supports_reasoning(model_id),
                    }
                )
            unique = {item["id"]: item for item in items}
            return sorted(unique.values(), key=lambda item: item["id"])
        except Exception:
            return [{"id": model, "supports_reasoning": self._supports_reasoning(model)} for model in OPENAI_MODELS]

    def chat_once(
        self,
        conversation_id: str,
        user_text: str,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        provider_name, model, user_message, messages = self._prepare_chat(
            conversation_id=conversation_id,
            user_text=user_text,
            provider_name=provider_name,
            model=model,
        )

        thinking_content = None
        if provider_name == "openai" and self.openai_client:
            assistant_text, thinking_content = self._chat_openai(messages, model)
        else:
            provider = self.providers.get(provider_name)
            assistant_text = provider.chat(messages=messages, model=model)
        if not assistant_text:
            assistant_text = "No response generated."

        assistant_message = self._store_assistant_message(
            conversation_id=conversation_id,
            provider_name=provider_name,
            model=model,
            assistant_text=assistant_text,
            thinking_content=thinking_content,
        )
        return {
            "conversation_id": conversation_id,
            "user_message": self.serialize_message(user_message),
            "message": self.serialize_message(assistant_message),
        }

    def chat_stream(
        self,
        conversation_id: str,
        user_text: str,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        provider_name, model, user_message, messages = self._prepare_chat(
            conversation_id=conversation_id,
            user_text=user_text,
            provider_name=provider_name,
            model=model,
        )
        yield {
            "type": "meta",
            "conversation_id": conversation_id,
            "user_message": self.serialize_message(user_message),
        }

        if provider_name != "openai":
            provider = self.providers.get(provider_name)
            assistant_text = provider.chat(messages=messages, model=model)
            if not assistant_text:
                assistant_text = "No response generated."
            assistant_message = self._store_assistant_message(
                conversation_id=conversation_id,
                provider_name=provider_name,
                model=model,
                assistant_text=assistant_text,
                thinking_content=None,
            )
            yield {
                "type": "done",
                "conversation_id": conversation_id,
                "user_message": self.serialize_message(user_message),
                "message": self.serialize_message(assistant_message),
            }
            return

        if not self.openai_client:
            raise ValueError("OPENAI_API_KEY is not set.")

        assistant_chunks: list[str] = []
        reasoning_chunks: list[str] = []
        with self.openai_client.responses.stream(
            model=model,
            input=messages,
            store=False,
        ) as stream:
            for event in stream:
                event_type = getattr(event, "type", "")
                if event_type == "response.output_text.delta":
                    delta = getattr(event, "delta", "") or ""
                    if delta:
                        assistant_chunks.append(delta)
                        yield {
                            "type": "delta",
                            "delta": delta,
                        }
                elif event_type.startswith("response.reasoning"):
                    delta = getattr(event, "delta", "") or getattr(event, "text", "") or ""
                    if delta:
                        reasoning_chunks.append(delta)

        assistant_text = "".join(assistant_chunks).strip() or "No response generated."
        assistant_message = self._store_assistant_message(
            conversation_id=conversation_id,
            provider_name=provider_name,
            model=model,
            assistant_text=assistant_text,
            thinking_content=self._clean_reasoning_text("".join(reasoning_chunks)),
        )
        yield {
            "type": "done",
            "conversation_id": conversation_id,
            "user_message": self.serialize_message(user_message),
            "message": self.serialize_message(assistant_message),
        }

    def _prepare_chat(
        self,
        conversation_id: str,
        user_text: str,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> tuple[str, str, GioMessage, list[dict[str, str]]]:
        cleaned = user_text.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty.")

        self._require_conversation(conversation_id)
        provider_name = provider_name or get_settings().GIO_DEFAULT_PROVIDER
        model = model or get_settings().GIO_DEFAULT_MODEL
        user_embedding = self._embed(cleaned)
        user_message = self.repository.add_message(
            conversation_id=conversation_id,
            role="user",
            content=cleaned,
            provider=provider_name,
            model=model,
            embedding=user_embedding,
        )

        messages = self._build_prompt_context(conversation_id, user_embedding)
        return provider_name, model, user_message, messages

    def _store_assistant_message(
        self,
        conversation_id: str,
        provider_name: str,
        model: str,
        assistant_text: str,
        thinking_content: str | None,
    ) -> GioMessage:
        assistant_embedding = self._embed(assistant_text)
        assistant_message = self.repository.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_text,
            provider=provider_name,
            model=model,
            thinking_content=thinking_content,
            embedding=assistant_embedding,
        )
        self._maybe_update_rolling_summary(conversation_id)
        return assistant_message

    def _chat_openai(self, messages: list[dict[str, str]], model: str) -> tuple[str, str | None]:
        response = self.openai_client.responses.create(
            model=model,
            input=messages,
            store=False,
        )
        assistant_text = getattr(response, "output_text", "").strip()
        reasoning_content = self._extract_reasoning_from_response(response)
        return assistant_text, reasoning_content

    def _build_prompt_context(
        self,
        conversation_id: str,
        user_embedding: list[float] | None,
    ) -> list[dict[str, str]]:
        all_messages = self.repository.get_messages(conversation_id)
        latest_summary = self.repository.get_latest_summary(conversation_id)
        conversation_messages = [item for item in all_messages if item.role in {"user", "assistant", "system"}]
        recent_messages = conversation_messages[-get_settings().GIO_RECENT_MESSAGES_LIMIT:]

        prompt_messages = [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}]
        if latest_summary and latest_summary.content.strip():
            prompt_messages.append(
                {
                    "role": "system",
                    "content": "Rolling summary of earlier conversation context. Use it as background, but defer to the recent direct messages when they conflict.\n"
                    + latest_summary.content,
                }
            )

        recall_block = self._build_recall_block(conversation_messages, recent_messages, user_embedding)
        if recall_block:
            prompt_messages.append({"role": "system", "content": recall_block})

        prompt_messages.extend({"role": item.role, "content": item.content} for item in recent_messages)
        return prompt_messages

    def _maybe_update_rolling_summary(self, conversation_id: str) -> None:
        all_messages = self.repository.get_messages(conversation_id)
        visible_messages = [item for item in all_messages if item.role in {"user", "assistant", "system"}]
        latest_summary = self.repository.get_latest_summary(conversation_id)
        recent_messages = visible_messages[-get_settings().GIO_RECENT_MESSAGES_LIMIT:]
        recent_ids = {item.id for item in recent_messages}
        force_refresh = self._recent_messages_include_summary_worthy_update(recent_messages)

        if latest_summary:
            candidates = [
                item for item in visible_messages if item.created_at > latest_summary.updated_at and item.id not in recent_ids
            ]
        else:
            candidates = [item for item in visible_messages if item.id not in recent_ids]

        if force_refresh:
            candidate_map = {item.id: item for item in candidates}
            for item in recent_messages:
                candidate_map[item.id] = item
            candidates = sorted(candidate_map.values(), key=lambda item: item.created_at)

        if len(candidates) < get_settings().GIO_SUMMARY_TRIGGER_MESSAGES and not force_refresh:
            return

        summary_text = self._summarize_messages(candidates, latest_summary.content if latest_summary else None)
        if not summary_text:
            return
        if latest_summary and self._summary_equivalent(summary_text, latest_summary.content):
            return

        summary_embedding = self._embed(summary_text)
        self.repository.save_summary(
            conversation_id=conversation_id,
            content=summary_text,
            model=get_settings().GIO_SUMMARY_MODEL,
            embedding=summary_embedding,
        )

    def _summarize_messages(self, messages: list[GioMessage], previous_summary: str | None = None) -> str | None:
        if not self.openai_client or not messages:
            return previous_summary

        transcript_lines = [f"{item.role}: {self._truncate_content(item.content, limit=400)}" for item in messages]
        prompt = [
            "Create a compact rolling summary of the conversation.",
            "Keep durable facts, preferences, goals, decisions, and unresolved tasks.",
            "Drop filler, repetition, and small talk.",
            "Return plain text bullets only.",
            "Avoid repeating bullets that are already captured unless they need correction.",
        ]
        if previous_summary:
            prompt.append("Previous rolling summary:")
            prompt.append(previous_summary)
        prompt.append("New conversation segment:")
        prompt.extend(transcript_lines)

        try:
            response = self.openai_client.responses.create(
                model=get_settings().GIO_SUMMARY_MODEL,
                input=[{"role": "system", "content": "\n".join(prompt)}],
                store=False,
            )
            summary = getattr(response, "output_text", "").strip()
            return summary or previous_summary
        except Exception:
            return previous_summary

    def _build_recall_block(
        self,
        conversation_messages: list[GioMessage],
        recent_messages: list[GioMessage],
        user_embedding: list[float] | None,
    ) -> str | None:
        if not user_embedding:
            return None

        recent_ids = {item.id for item in recent_messages}
        seen_snippets: set[str] = set()
        user_matches: list[str] = []
        assistant_matches: list[str] = []
        scored_candidates: list[tuple[float, GioMessage]] = []

        for item in conversation_messages:
            if item.id in recent_ids:
                continue
            if item.role not in {"user", "assistant"}:
                continue
            if not item.embedding:
                continue
            score = self._cosine_similarity(user_embedding, item.embedding)
            if score >= get_settings().GIO_RECALL_MIN_SCORE:
                scored_candidates.append((score, item))

        if not scored_candidates:
            return None

        scored_candidates.sort(key=lambda pair: pair[0], reverse=True)
        for _, item in scored_candidates:
            snippet = self._truncate_content(item.content)
            fingerprint = snippet.lower()
            if fingerprint in seen_snippets:
                continue
            seen_snippets.add(fingerprint)
            target = user_matches if item.role == "user" else assistant_matches
            target.append(snippet)
            if len(user_matches) + len(assistant_matches) >= get_settings().GIO_RECALL_TOP_K:
                break

        if not user_matches and not assistant_matches:
            return None

        lines = [
            "Relevant earlier context from this same conversation.",
            "Use it only when it genuinely helps answer the current message.",
        ]
        if user_matches:
            lines.append("User-side recalled context:")
            lines.extend(f"- {snippet}" for snippet in user_matches)
        if assistant_matches:
            lines.append("Assistant-side recalled context:")
            lines.extend(f"- {snippet}" for snippet in assistant_matches)
        return "\n".join(lines)

    def _extract_reasoning_from_response(self, response: Any) -> str | None:
        output_items = getattr(response, "output", None) or []
        chunks: list[str] = []
        for item in output_items:
            if getattr(item, "type", "") != "reasoning":
                continue
            summary = getattr(item, "summary", None) or []
            for part in summary:
                text = getattr(part, "text", "") or ""
                if text:
                    chunks.append(text)
        return self._clean_reasoning_text("\n".join(chunks))

    @staticmethod
    def _clean_reasoning_text(text: str | None) -> str | None:
        cleaned = (text or "").strip()
        return cleaned or None

    @staticmethod
    def _recent_messages_include_summary_worthy_update(messages: list[GioMessage]) -> bool:
        if not messages:
            return False
        update_markers = [
            'correction:',
            'actually',
            'instead of',
            'not ',
            'now ',
            'changed to',
            'update:',
        ]
        for item in messages:
            if item.role != 'user':
                continue
            lowered = item.content.lower()
            if any(marker in lowered for marker in update_markers):
                return True
        return False

    @staticmethod
    def _summary_equivalent(left: str, right: str) -> bool:
        normalized_left = "\n".join(line.strip() for line in left.splitlines() if line.strip())
        normalized_right = "\n".join(line.strip() for line in right.splitlines() if line.strip())
        if normalized_left == normalized_right:
            return True
        return SequenceMatcher(None, normalized_left, normalized_right).ratio() >= 0.98

    @staticmethod
    def _truncate_content(content: str, limit: int = 240) -> str:
        cleaned = " ".join(content.split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 3].rstrip() + "..."

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = sum(a * a for a in left) ** 0.5
        right_norm = sum(b * b for b in right) ** 0.5
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _embed(self, text: str) -> list[float] | None:
        if not self.openai_client or not text.strip():
            return None
        try:
            response = self.openai_client.embeddings.create(model=get_settings().OPENAI_EMBEDDING_MODEL, input=text)
            return list(response.data[0].embedding)
        except Exception:
            return None

    @staticmethod
    def serialize_message(message) -> dict[str, Any]:
        payload = asdict(message)
        payload.pop("embedding", None)
        return payload

    @staticmethod
    def serialize_dream(dream: GioDream) -> dict[str, Any]:
        payload = asdict(dream)
        payload.pop("embedding", None)
        return payload

    def _require_conversation(self, conversation_id: str) -> None:
        cleaned = (conversation_id or "").strip()
        if not cleaned:
            raise ValueError("conversation_id is required.")
        if not self.repository.conversation_exists(cleaned):
            raise ValueError("Conversation not found. Start a new chat or refresh the conversation list.")

    @staticmethod
    def _is_supported_gio_model(model_id: str) -> bool:
        lowered = (model_id or '').lower().strip()
        if not lowered.startswith('gpt'):
            return False
        blocked_tokens = [
            'instruct',
            'audio',
            'realtime',
            'search',
            'transcribe',
            'tts',
            'image',
            'codex',
            'chat-latest',
            'pro',
        ]
        if any(token in lowered for token in blocked_tokens):
            return False
        allowed_prefixes = ['gpt-4.1', 'gpt-4o']
        return any(lowered.startswith(prefix) for prefix in allowed_prefixes)

    @staticmethod
    def _supports_reasoning(model_id: str) -> bool:
        lowered = model_id.lower()
        return any(token in lowered for token in ["o1", "o3", "o4", "reasoning"])

    def _select_dream_sources(self, messages: list[GioMessage]) -> list[GioMessage]:
        recent = messages[-min(4, len(messages)):]
        older = messages[:-len(recent)] if len(messages) > len(recent) else []

        selected: list[GioMessage] = []
        seen_ids: set[str] = set()
        for item in recent:
            selected.append(item)
            seen_ids.add(item.id)

        correction_candidates = [item for item in older if self._message_is_correction_like(item)]
        for item in correction_candidates[-2:]:
            if item.id in seen_ids:
                continue
            selected.append(item)
            seen_ids.add(item.id)
            if len(selected) >= get_settings().GIO_DREAM_SOURCE_LIMIT:
                return sorted(selected, key=lambda entry: entry.created_at)

        scored: list[tuple[float, GioMessage]] = []
        for item in older:
            if item.id in seen_ids or not item.embedding:
                continue
            scored.append((self._dream_source_priority(item, older), item))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        for _, item in scored:
            if item.id in seen_ids:
                continue
            selected.append(item)
            seen_ids.add(item.id)
            if len(selected) >= get_settings().GIO_DREAM_SOURCE_LIMIT:
                break
        return sorted(selected, key=lambda item: item.created_at)

    def _dream_from_sources(
        self,
        conversation_id: str,
        messages: list[GioMessage],
        latest_summary: str | None,
    ) -> tuple[str, str]:
        if not self.openai_client:
            raise ValueError("Dream Mode requires OPENAI_API_KEY for now.")

        transcript_lines = [f"{item.role}: {self._truncate_content(item.content, limit=280)}" for item in messages]
        prompt = [
            "You are generating a Dream Mode reflection for a single conversation.",
            "This is not a user-facing reply and not roleplay.",
            "Work only from the supplied evidence.",
            "Extract repeated themes, durable facts, unresolved threads, corrections, and any candidate long-term memories.",
            "Be concrete. Avoid mysticism, filler, and fake feelings.",
            "Return plain text in exactly this shape:",
            "Title: <short title>",
            "",
            "Reflection:",
            "- bullet",
            "- bullet",
            "",
            "Possible lasting memory:",
            "- bullet",
            "- bullet",
            "",
            "Open questions:",
            "- bullet",
            "- bullet",
        ]
        if latest_summary:
            prompt.extend(["", "Latest rolling summary:", latest_summary])
        prompt.extend(["", f"Conversation id: {conversation_id}", "Selected source excerpts:"])
        prompt.extend(transcript_lines)

        response = self.openai_client.responses.create(
            model=get_settings().GIO_DREAM_MODEL,
            input=[{"role": "system", "content": "\n".join(prompt)}],
            store=False,
        )
        raw = getattr(response, "output_text", "").strip()
        if not raw:
            raise ValueError("Dream generation returned no content.")

        title = "Dream Reflection"
        body = raw
        first_line, _, remainder = raw.partition("\n")
        if first_line.lower().startswith("title:"):
            parsed = first_line.split(":", 1)[1].strip()
            title = parsed or title
            body = remainder.strip() or raw
        return title, body

    def _dream_source_priority(self, candidate: GioMessage, pool: list[GioMessage]) -> float:
        score = 0.0
        if self._message_is_correction_like(candidate):
            score += 0.75
        if candidate.role == 'user':
            score += 0.15
        similarity_total = 0.0
        similarity_count = 0
        if candidate.embedding:
            for other in pool:
                if other.id == candidate.id or not other.embedding:
                    continue
                similarity_total += self._cosine_similarity(candidate.embedding, other.embedding)
                similarity_count += 1
        if similarity_count:
            score += similarity_total / similarity_count
        return score

    @staticmethod
    def _message_is_correction_like(message: GioMessage) -> bool:
        return message.role == 'user' and GioService._recent_messages_include_summary_worthy_update([message])
