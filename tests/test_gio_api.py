from __future__ import annotations

import pytest

from unified_server.app_factory import create_app
from unified_server.razzy_service import RazzyService
from unified_server.service import ChatService
from unified_server.settings import get_settings
from unified_server.twitter_service import TwitterService


@pytest.fixture(autouse=True)
def _gio_api_key(monkeypatch, temp_db):
    monkeypatch.setattr(get_settings(), "API_KEY", "change-me")


class FakeGioService:
    def __init__(self) -> None:
        self.conversations = [{"id": "conv-1", "title": "Chat One", "created_at": "2026-04-29T15:00:00+00:00", "updated_at": "2026-04-29T15:00:00+00:00"}]
        self.messages = {
            "conv-1": [
                {"id": "m1", "conversation_id": "conv-1", "role": "user", "content": "Hello", "provider": "openai", "model": "gpt-4.1-mini", "thinking_content": None, "created_at": "2026-04-29T15:00:00+00:00"}
            ]
        }
        self.dreams = [
            {
                "id": "dream-1",
                "conversation_id": "conv-1",
                "title": "Pattern check",
                "content": "Reflection:\n- User keeps iterating toward a cleaner architecture.",
                "model": "gpt-4.1-mini",
                "source_message_ids": ["m1"],
                "created_at": "2026-04-29T15:03:00+00:00",
                "updated_at": "2026-04-29T15:03:00+00:00",
            }
        ]

    def ensure_schema(self) -> None:
        return None

    def list_models(self, provider_name: str | None = None):
        return {
            "provider": "openai",
            "default_model": "gpt-4.1-mini",
            "models": [{"id": "gpt-4.1-mini", "supports_reasoning": False}],
        }

    def list_openai_models(self):
        return self.list_models()["models"]

    def create_conversation(self, title: str = "New Chat"):
        conversation = {"id": f"conv-{len(self.conversations) + 1}", "title": title, "created_at": "2026-04-29T15:01:00+00:00", "updated_at": "2026-04-29T15:01:00+00:00"}
        self.conversations.insert(0, conversation)
        self.messages[conversation["id"]] = []
        return conversation

    def list_conversations(self):
        return self.conversations

    def conversation_exists(self, conversation_id: str):
        return any(conversation['id'] == conversation_id for conversation in self.conversations)

    def get_messages(self, conversation_id: str):
        if not self.conversation_exists(conversation_id):
            raise ValueError('Conversation not found. Start a new chat or refresh the conversation list.')
        return self.messages.get(conversation_id, [])

    def rename_conversation(self, conversation_id: str, title: str):
        if not title.strip():
            raise ValueError("Title cannot be empty.")
        for conversation in self.conversations:
            if conversation["id"] == conversation_id:
                conversation["title"] = title.strip()
                return conversation
        raise ValueError("Conversation not found. Start a new chat or refresh the conversation list.")

    def delete_conversation(self, conversation_id: str) -> None:
        if not self.conversation_exists(conversation_id):
            raise ValueError('Conversation not found. Start a new chat or refresh the conversation list.')
        self.conversations = [item for item in self.conversations if item["id"] != conversation_id]
        self.messages.pop(conversation_id, None)

    def list_dreams(self, conversation_id: str | None = None):
        if conversation_id and not self.conversation_exists(conversation_id):
            raise ValueError('Conversation not found. Start a new chat or refresh the conversation list.')
        if not conversation_id:
            return self.dreams
        return [dream for dream in self.dreams if dream['conversation_id'] == conversation_id]

    def get_dream(self, dream_id: str):
        for dream in self.dreams:
            if dream['id'] == dream_id:
                return dream
        raise ValueError('Dream not found.')

    def create_dream(self, conversation_id: str):
        if not self.conversation_exists(conversation_id):
            raise ValueError('Conversation not found. Start a new chat or refresh the conversation list.')
        dream = {
            "id": f"dream-{len(self.dreams) + 1}",
            "conversation_id": conversation_id,
            "title": "Fresh Dream",
            "content": "Reflection:\n- Durable thought found.",
            "model": "gpt-4.1-mini",
            "source_message_ids": ["m1"],
            "created_at": "2026-04-29T15:04:00+00:00",
            "updated_at": "2026-04-29T15:04:00+00:00",
        }
        self.dreams.insert(0, dream)
        return dream

    def chat_once(self, conversation_id: str, message: str, provider: str | None = None, model: str | None = None):
        if not self.conversation_exists(conversation_id):
            raise ValueError('Conversation not found. Start a new chat or refresh the conversation list.')
        payload = {
            "conversation_id": conversation_id,
            "user_message": {"id": "u1", "conversation_id": conversation_id, "role": "user", "content": message, "provider": provider or "openai", "model": model or "gpt-4.1-mini", "thinking_content": None, "created_at": "2026-04-29T15:02:00+00:00"},
            "message": {"id": "a1", "conversation_id": conversation_id, "role": "assistant", "content": "Hi there", "provider": provider or "openai", "model": model or "gpt-4.1-mini", "thinking_content": None, "created_at": "2026-04-29T15:02:01+00:00"},
        }
        self.messages.setdefault(conversation_id, []).extend([payload["user_message"], payload["message"]])
        return payload

    def chat_stream(self, conversation_id: str, message: str, provider: str | None = None, model: str | None = None):
        if not self.conversation_exists(conversation_id):
            raise ValueError('Conversation not found. Start a new chat or refresh the conversation list.')
        yield {"type": "meta", "conversation_id": conversation_id, "user_message": {"content": message}}
        yield {"type": "delta", "delta": "Hi"}
        yield {"type": "done", "conversation_id": conversation_id, "message": {"content": "Hi there"}}


class FakeTwitterClient:
    def is_configured(self) -> bool:
        return True


def build_test_client():
    service = ChatService()
    razzy_service = RazzyService(repository=service.repository, providers=service.providers)
    twitter_service = TwitterService(client=FakeTwitterClient())
    gio_service = FakeGioService()
    app = create_app(service=service, razzy_service=razzy_service, twitter_service=twitter_service, gio_service=gio_service)
    app.config.update(TESTING=True)
    return app.test_client()


def auth_headers():
    return {"X-API-Key": "change-me", "Content-Type": "application/json"}


def test_gio_models_endpoint():
    client = build_test_client()
    response = client.get('/api/gio/models', headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json()['provider'] == 'openai'
    assert response.get_json()['default_model'] == 'gpt-4.1-mini'
    assert response.get_json()['models'][0]['id'] == 'gpt-4.1-mini'


def test_gio_session_and_conversation_listing():
    client = build_test_client()

    session_response = client.post('/api/gio/session', headers=auth_headers(), json={'title': 'Fresh Chat'})
    assert session_response.status_code == 200
    assert session_response.get_json()['title'] == 'Fresh Chat'

    list_response = client.get('/api/gio/conversations', headers=auth_headers())
    assert list_response.status_code == 200
    assert any(item['title'] == 'Fresh Chat' for item in list_response.get_json()['conversations'])


def test_gio_messages_and_chat_endpoint():
    client = build_test_client()

    messages_response = client.get('/api/gio/conversations/conv-1/messages', headers=auth_headers())
    assert messages_response.status_code == 200
    assert messages_response.get_json()['messages'][0]['content'] == 'Hello'

    chat_response = client.post(
        '/api/gio/chat',
        headers=auth_headers(),
        json={'conversation_id': 'conv-1', 'message': 'Ping', 'provider': 'openai', 'model': 'gpt-4.1-mini'},
    )
    assert chat_response.status_code == 200
    assert chat_response.get_json()['message']['content'] == 'Hi there'


def test_gio_stream_endpoint_returns_ndjson_events():
    client = build_test_client()

    response = client.post(
        '/api/gio/chat/stream',
        headers=auth_headers(),
        json={'conversation_id': 'conv-1', 'message': 'Ping', 'provider': 'openai', 'model': 'gpt-4.1-mini'},
    )
    assert response.status_code == 200
    assert response.mimetype == 'application/x-ndjson'
    body = response.get_data(as_text=True)
    assert '"type":"meta"' in body
    assert '"type":"delta"' in body
    assert '"type":"done"' in body


def test_gio_invalid_conversation_returns_clean_error():
    client = build_test_client()

    response = client.post(
        '/api/gio/chat',
        headers=auth_headers(),
        json={'conversation_id': 'missing-conv', 'message': 'Ping', 'provider': 'openai', 'model': 'gpt-4.1-mini'},
    )
    assert response.status_code == 400
    assert 'Conversation not found' in response.get_json()['error']

    messages_response = client.get('/api/gio/conversations/missing-conv/messages', headers=auth_headers())
    assert messages_response.status_code == 400
    assert 'Conversation not found' in messages_response.get_json()['error']


def test_gio_rename_and_delete_endpoints():
    client = build_test_client()

    rename_response = client.patch('/api/gio/conversations/conv-1', headers=auth_headers(), json={'title': 'Renamed Chat'})
    assert rename_response.status_code == 200
    assert rename_response.get_json()['title'] == 'Renamed Chat'

    delete_response = client.delete('/api/gio/conversations/conv-1', headers=auth_headers())
    assert delete_response.status_code == 200
    assert delete_response.get_json()['ok'] is True


def test_gio_dream_endpoints():
    client = build_test_client()

    dreams_response = client.get('/api/gio/dreams', headers=auth_headers())
    assert dreams_response.status_code == 200
    assert dreams_response.get_json()['dreams'][0]['id'] == 'dream-1'

    filtered_response = client.get('/api/gio/dreams?conversation_id=conv-1', headers=auth_headers())
    assert filtered_response.status_code == 200
    assert filtered_response.get_json()['dreams'][0]['conversation_id'] == 'conv-1'

    single_response = client.get('/api/gio/dreams/dream-1', headers=auth_headers())
    assert single_response.status_code == 200
    assert single_response.get_json()['title'] == 'Pattern check'

    create_response = client.post('/api/gio/conversations/conv-1/dream', headers=auth_headers())
    assert create_response.status_code == 201
    assert create_response.get_json()['title'] == 'Fresh Dream'
