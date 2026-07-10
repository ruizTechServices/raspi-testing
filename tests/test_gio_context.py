from __future__ import annotations

from types import SimpleNamespace

from unified_server.settings import get_settings
from unified_server.gio_repository import GioConversation, GioDream, GioMessage, GioSummary
from unified_server.gio_service import GioService


class FakeProvider:
    def __init__(self, response_text: str = "refined response") -> None:
        self.response_text = response_text
        self.calls: list[dict] = []

    def chat(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        self.calls.append({"messages": messages, "model": model})
        return self.response_text


class FakeProviderRegistry:
    def __init__(self, provider: FakeProvider) -> None:
        self.provider = provider

    def get(self, name: str):
        return self.provider


class FakeGioRepository:
    def __init__(self) -> None:
        self.messages: list[GioMessage] = []
        self.summary: GioSummary | None = None
        self.dreams: list[GioDream] = []
        self.conversations = {
            "conv-1": GioConversation(
                id="conv-1",
                title="New Chat",
                created_at="2026-04-29T15:00:00+00:00",
                updated_at="2026-04-29T15:00:00+00:00",
            )
        }
        self.counter = 0

    def ensure_schema(self) -> None:
        return None

    def list_conversations(self):
        return list(self.conversations.values())

    def create_conversation(self, title: str = "New Chat") -> GioConversation:
        return self.conversations["conv-1"]

    def conversation_exists(self, conversation_id: str) -> bool:
        return conversation_id in self.conversations

    def get_messages(self, conversation_id: str) -> list[GioMessage]:
        return [item for item in self.messages if item.conversation_id == conversation_id]

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        provider: str | None = None,
        model: str | None = None,
        thinking_content: str | None = None,
        embedding: list[float] | None = None,
    ) -> GioMessage:
        self.counter += 1
        message = GioMessage(
            id=f"msg-{self.counter}",
            conversation_id=conversation_id,
            role=role,
            content=content,
            provider=provider,
            model=model,
            thinking_content=thinking_content,
            embedding=embedding,
            created_at=f"2026-04-29T15:00:{self.counter:02d}+00:00",
        )
        self.messages.append(message)
        return message

    def get_latest_summary(self, conversation_id: str) -> GioSummary | None:
        if self.summary and self.summary.conversation_id == conversation_id:
            return self.summary
        return None

    def save_summary(
        self,
        conversation_id: str,
        content: str,
        model: str | None = None,
        embedding: list[float] | None = None,
    ) -> GioSummary:
        created_at = self.summary.created_at if self.summary else f"2026-04-29T15:00:{self.counter + 1:02d}+00:00"
        updated_at = f"2026-04-29T15:10:{self.counter + 1:02d}+00:00"
        self.summary = GioSummary(
            id=self.summary.id if self.summary else "summary-1",
            conversation_id=conversation_id,
            content=content,
            model=model,
            embedding=embedding,
            created_at=created_at,
            updated_at=updated_at,
        )
        return self.summary

    def list_dreams(self, conversation_id: str | None = None) -> list[GioDream]:
        if conversation_id is None:
            return list(self.dreams)
        return [item for item in self.dreams if item.conversation_id == conversation_id]

    def get_dream(self, dream_id: str) -> GioDream | None:
        for dream in self.dreams:
            if dream.id == dream_id:
                return dream
        return None

    def create_dream(
        self,
        conversation_id: str,
        title: str,
        content: str,
        model: str | None = None,
        source_message_ids: list[str] | None = None,
        embedding: list[float] | None = None,
    ) -> GioDream:
        dream = GioDream(
            id=f"dream-{len(self.dreams) + 1}",
            conversation_id=conversation_id,
            title=title,
            content=content,
            model=model,
            source_message_ids=source_message_ids or [],
            embedding=embedding,
            created_at=f"2026-04-29T16:00:{len(self.dreams) + 1:02d}+00:00",
            updated_at=f"2026-04-29T16:00:{len(self.dreams) + 1:02d}+00:00",
        )
        self.dreams.insert(0, dream)
        return dream


def test_gio_chat_uses_recent_window_and_semantic_recall(monkeypatch):
    repository = FakeGioRepository()
    repository.add_message("conv-1", "user", "My favorite color is blue.", embedding=[1.0, 0.0])
    repository.add_message("conv-1", "assistant", "Got it, your favorite color is blue.", embedding=[0.9, 0.1])
    repository.add_message("conv-1", "user", "I also like pizza.", embedding=[0.0, 1.0])
    repository.add_message("conv-1", "assistant", "Pizza is noted.", embedding=[0.0, 0.9])

    provider = FakeProvider()
    service = GioService(repository=repository, providers=FakeProviderRegistry(provider))
    service.openai_client = None

    monkeypatch.setattr(get_settings(), "GIO_RECENT_MESSAGES_LIMIT", 2)
    monkeypatch.setattr(get_settings(), "GIO_RECALL_TOP_K", 2)
    monkeypatch.setattr(get_settings(), "GIO_RECALL_MIN_SCORE", 0.2)
    monkeypatch.setattr(service, "_embed", lambda text: [1.0, 0.0] if "favorite color" in text.lower() else [0.5, 0.5])

    service.chat_once("conv-1", "What is my favorite color?", provider_name="openai", model="gpt-4.1-mini")

    sent_messages = provider.calls[0]["messages"]
    assert sent_messages[0]["role"] == "system"
    assert sent_messages[1]["role"] == "system"
    assert "Relevant earlier context" in sent_messages[1]["content"]
    assert "favorite color is blue" in sent_messages[1]["content"].lower()
    assert "pizza is noted" not in sent_messages[1]["content"].lower()
    assert "User-side recalled context" in sent_messages[1]["content"]

    recent_contents = [item["content"] for item in sent_messages[2:]]
    assert recent_contents == ["Pizza is noted.", "What is my favorite color?"]


def test_gio_chat_without_embedding_falls_back_to_recent_messages(monkeypatch):
    repository = FakeGioRepository()
    repository.add_message("conv-1", "user", "Old fact one.", embedding=[1.0, 0.0])
    repository.add_message("conv-1", "assistant", "Old answer one.", embedding=[1.0, 0.0])
    repository.add_message("conv-1", "user", "Recent fact two.", embedding=[0.0, 1.0])

    provider = FakeProvider()
    service = GioService(repository=repository, providers=FakeProviderRegistry(provider))
    service.openai_client = None

    monkeypatch.setattr(get_settings(), "GIO_RECENT_MESSAGES_LIMIT", 2)
    monkeypatch.setattr(service, "_embed", lambda text: None)

    service.chat_once("conv-1", "Newest message", provider_name="openai", model="gpt-4.1-mini")

    sent_messages = provider.calls[0]["messages"]
    assert len(sent_messages) == 3
    assert sent_messages[0]["role"] == "system"
    assert [item["content"] for item in sent_messages[1:]] == ["Recent fact two.", "Newest message"]


def test_gio_chat_includes_latest_rolling_summary(monkeypatch):
    repository = FakeGioRepository()
    repository.save_summary("conv-1", "- User prefers blue.\n- User likes pizza.", model="gpt-4.1-mini")
    repository.add_message("conv-1", "user", "Recent question one.", embedding=[1.0, 0.0])
    repository.add_message("conv-1", "assistant", "Recent answer one.", embedding=[1.0, 0.0])

    provider = FakeProvider()
    service = GioService(repository=repository, providers=FakeProviderRegistry(provider))
    service.openai_client = None

    monkeypatch.setattr(get_settings(), "GIO_RECENT_MESSAGES_LIMIT", 3)
    monkeypatch.setattr(service, "_embed", lambda text: None)

    service.chat_once("conv-1", "Newest message", provider_name="openai", model="gpt-4.1-mini")

    sent_messages = provider.calls[0]["messages"]
    assert sent_messages[1]["role"] == "system"
    assert "Rolling summary of earlier conversation context" in sent_messages[1]["content"]
    assert "User prefers blue" in sent_messages[1]["content"]


def test_gio_chat_rolls_new_summary_when_old_context_grows(monkeypatch):
    repository = FakeGioRepository()
    repository.add_message("conv-1", "user", "Fact one.", embedding=[1.0, 0.0])
    repository.add_message("conv-1", "assistant", "Answer one.", embedding=[1.0, 0.0])
    repository.add_message("conv-1", "user", "Fact two.", embedding=[1.0, 0.0])
    repository.add_message("conv-1", "assistant", "Answer two.", embedding=[1.0, 0.0])

    provider = FakeProvider()
    service = GioService(repository=repository, providers=FakeProviderRegistry(provider))
    service.openai_client = None

    monkeypatch.setattr(get_settings(), "GIO_RECENT_MESSAGES_LIMIT", 2)
    monkeypatch.setattr(get_settings(), "GIO_SUMMARY_TRIGGER_MESSAGES", 2)
    monkeypatch.setattr(service, "_embed", lambda text: None)
    monkeypatch.setattr(service, "_summarize_messages", lambda messages, previous_summary=None: "- Durable summary")

    service.chat_once("conv-1", "Newest message", provider_name="openai", model="gpt-4.1-mini")

    assert repository.summary is not None
    assert repository.summary.content == "- Durable summary"

    visible_messages = service.get_messages("conv-1")
    assert all(item["role"] != "summary" for item in visible_messages)


def test_gio_chat_does_not_churn_duplicate_summary(monkeypatch):
    repository = FakeGioRepository()
    repository.save_summary("conv-1", "- Durable summary", model="gpt-4.1-mini")
    repository.add_message("conv-1", "user", "Fact one.", embedding=[1.0, 0.0])
    repository.add_message("conv-1", "assistant", "Answer one.", embedding=[1.0, 0.0])
    repository.add_message("conv-1", "user", "Fact two.", embedding=[1.0, 0.0])
    repository.add_message("conv-1", "assistant", "Answer two.", embedding=[1.0, 0.0])

    provider = FakeProvider()
    service = GioService(repository=repository, providers=FakeProviderRegistry(provider))
    service.openai_client = None

    monkeypatch.setattr(get_settings(), "GIO_RECENT_MESSAGES_LIMIT", 2)
    monkeypatch.setattr(get_settings(), "GIO_SUMMARY_TRIGGER_MESSAGES", 2)
    monkeypatch.setattr(service, "_embed", lambda text: None)
    monkeypatch.setattr(service, "_summarize_messages", lambda messages, previous_summary=None: "- Durable summary")

    before_updated_at = repository.summary.updated_at
    service.chat_once("conv-1", "Newest message", provider_name="openai", model="gpt-4.1-mini")

    assert repository.summary is not None
    assert repository.summary.updated_at == before_updated_at


def test_gio_chat_refreshes_summary_when_recent_user_message_is_a_correction(monkeypatch):
    repository = FakeGioRepository()
    repository.save_summary("conv-1", "- Secret lighthouse codeword: BLUE SPARROW", model="gpt-4.1-mini")
    repository.add_message("conv-1", "user", "What is my secret lighthouse codeword?", embedding=[1.0, 0.0])
    repository.add_message("conv-1", "assistant", "Your secret lighthouse codeword is BLUE SPARROW.", embedding=[1.0, 0.0])

    provider = FakeProvider(response_text="Got it! Your secret lighthouse codeword is now GREEN FALCON.")
    service = GioService(repository=repository, providers=FakeProviderRegistry(provider))
    service.openai_client = None

    monkeypatch.setattr(get_settings(), "GIO_RECENT_MESSAGES_LIMIT", 2)
    monkeypatch.setattr(get_settings(), "GIO_SUMMARY_TRIGGER_MESSAGES", 8)
    monkeypatch.setattr(service, "_embed", lambda text: None)

    captured = {}

    def fake_summarize(messages, previous_summary=None):
        captured['messages'] = [item.content for item in messages]
        captured['previous_summary'] = previous_summary
        return "- Secret lighthouse codeword: GREEN FALCON"

    monkeypatch.setattr(service, "_summarize_messages", fake_summarize)

    service.chat_once(
        "conv-1",
        "Correction: my secret lighthouse codeword is now GREEN FALCON, not BLUE SPARROW.",
        provider_name="openai",
        model="gpt-4.1-mini",
    )

    assert repository.summary is not None
    assert repository.summary.content == "- Secret lighthouse codeword: GREEN FALCON"
    assert captured['previous_summary'] == "- Secret lighthouse codeword: BLUE SPARROW"
    joined = " \n".join(captured['messages'])
    assert "Correction: my secret lighthouse codeword is now GREEN FALCON, not BLUE SPARROW." in joined
    assert "Got it! Your secret lighthouse codeword is now GREEN FALCON." in joined


def test_gio_supported_model_filter_rejects_instruct_and_accepts_chat_families():
    assert GioService._is_supported_gio_model('gpt-4.1-mini') is True
    assert GioService._is_supported_gio_model('gpt-4o-2024-11-20') is True
    assert GioService._is_supported_gio_model('gpt-3.5-turbo-instruct-0914') is False
    assert GioService._is_supported_gio_model('gpt-4o-audio-preview') is False
    assert GioService._is_supported_gio_model('gpt-5-chat-latest') is False


def test_extract_reasoning_from_response_uses_real_reasoning_blocks():
    service = GioService(repository=FakeGioRepository(), providers=FakeProviderRegistry(FakeProvider()))
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="reasoning",
                summary=[SimpleNamespace(text="Reasoning step one."), SimpleNamespace(text="Reasoning step two.")],
            )
        ]
    )

    reasoning = service._extract_reasoning_from_response(response)

    assert reasoning == "Reasoning step one.\nReasoning step two."


def test_gio_dream_prefers_corrections_and_recent_context(monkeypatch):
    repository = FakeGioRepository()
    repository.add_message("conv-1", "user", "My favorite color used to be blue.", embedding=[1.0, 0.0])
    repository.add_message("conv-1", "assistant", "Noted, blue.", embedding=[0.9, 0.1])
    repository.add_message("conv-1", "user", "Correction: my favorite color is green now, not blue.", embedding=[1.0, 0.0])
    repository.add_message("conv-1", "assistant", "Got it, green now.", embedding=[0.9, 0.1])
    repository.add_message("conv-1", "user", "Also I want a stronger gym routine.", embedding=[0.0, 1.0])
    repository.add_message("conv-1", "assistant", "We can plan that.", embedding=[0.1, 0.9])

    provider = FakeProvider()
    service = GioService(repository=repository, providers=FakeProviderRegistry(provider))
    service.openai_client = object()

    monkeypatch.setattr(get_settings(), "GIO_DREAM_SOURCE_LIMIT", 6)
    monkeypatch.setattr(service, "_embed", lambda text: None)

    captured = {}

    def fake_dream_from_sources(conversation_id, messages, latest_summary):
        captured["source_ids"] = [item.id for item in messages]
        captured["contents"] = [item.content for item in messages]
        return ("Color Shift", "Reflection:\n- test")

    monkeypatch.setattr(service, "_dream_from_sources", fake_dream_from_sources)

    dream = service.create_dream("conv-1")

    assert dream["title"] == "Color Shift"
    joined = "\n".join(captured["contents"])
    assert "Correction: my favorite color is green now, not blue." in joined
    assert "Also I want a stronger gym routine." in joined


def test_gio_dream_rejects_duplicate_snapshot(monkeypatch):
    repository = FakeGioRepository()
    repository.add_message("conv-1", "user", "Topic one.", embedding=[1.0, 0.0])
    repository.add_message("conv-1", "assistant", "Answer one.", embedding=[0.9, 0.1])
    repository.add_message("conv-1", "user", "Topic two.", embedding=[0.0, 1.0])
    repository.add_message("conv-1", "assistant", "Answer two.", embedding=[0.1, 0.9])

    provider = FakeProvider()
    service = GioService(repository=repository, providers=FakeProviderRegistry(provider))
    service.openai_client = object()

    monkeypatch.setattr(service, "_embed", lambda text: None)
    monkeypatch.setattr(service, "_dream_from_sources", lambda *args: ("First Dream", "Reflection:\n- test"))

    first = service.create_dream("conv-1")
    assert first["title"] == "First Dream"

    try:
        service.create_dream("conv-1")
        assert False, "Expected duplicate dream snapshot rejection"
    except ValueError as exc:
        assert "No new material" in str(exc)


def test_extract_reasoning_from_response_returns_none_when_absent():
    service = GioService(repository=FakeGioRepository(), providers=FakeProviderRegistry(FakeProvider()))
    response = SimpleNamespace(output=[SimpleNamespace(type="message")])

    assert service._extract_reasoning_from_response(response) is None
