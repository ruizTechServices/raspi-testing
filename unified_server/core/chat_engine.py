from __future__ import annotations

from typing import Callable

from unified_server.settings import get_settings


def run_chat_turn(
    *,
    repository,
    providers,
    conversation_id: str,
    user_text: str,
    provider_name: str | None,
    model: str | None,
    system_prompt: str,
    build_memory_block: Callable[[], str] | None = None,
) -> dict:
    """Shared chat-turn skeleton for the SQLite-backed chat personalities.

    Stores the user message, assembles system prompt + optional memory block +
    conversation history, calls the provider, stores the assistant reply, and
    returns the API result payload. Callers validate the conversation and text
    beforehand and handle any post-turn side effects (e.g. memory writes).
    """
    settings = get_settings()
    provider_name = provider_name or settings.DEFAULT_PROVIDER
    model = model or settings.DEFAULT_MODEL

    repository.add_message(
        conversation_id=conversation_id,
        role="user",
        content=user_text,
        provider=provider_name,
        model=model,
    )

    messages = [{"role": "system", "content": system_prompt}]
    memory_block = build_memory_block() if build_memory_block else ""
    if memory_block:
        messages.append({"role": "system", "content": memory_block})
    messages.extend(repository.get_messages_for_llm(conversation_id))

    provider = providers.get(provider_name)
    assistant_text = provider.chat(messages=messages, model=model)
    if not assistant_text:
        assistant_text = "No response generated."

    message_id = repository.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_text,
        provider=provider_name,
        model=model,
    )

    return {
        "conversation_id": conversation_id,
        "message": {
            "id": message_id,
            "role": "assistant",
            "content": assistant_text,
            "provider": provider_name,
            "model": model,
        },
    }
