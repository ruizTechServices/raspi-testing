from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from unified_server import config
from unified_server.app_factory import create_app
from unified_server.database import init_db
from unified_server.razzy_service import RazzyService
from unified_server.service import ChatService
from unified_server.twitter_service import TwitterService


class FakeProvider:
    def __init__(self, response_text: str = "fake response") -> None:
        self.response_text = response_text
        self.calls: list[dict] = []

    def chat(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        self.calls.append({"messages": messages, "model": model})
        return self.response_text


class FakeProviderRegistry:
    def __init__(self) -> None:
        self.fake_provider = FakeProvider()

    def get(self, name: str):
        return self.fake_provider

    def list_providers(self) -> list[dict[str, object]]:
        return [
            {"id": "openai", "configured": True},
            {"id": "ollama", "configured": True},
            {"id": "anthropic", "configured": True},
        ]


class FakeTwitterClient:
    def __init__(self) -> None:
        self.created_posts: list[dict[str, str | None]] = []
        self.deleted_posts: list[str] = []

    @property
    def config(self):
        class Config:
            base_url = "https://api.twitter.com"
            user_id = "123456"
            bearer_token = "fake-bearer"
        return Config()

    def is_configured(self) -> bool:
        return True

    def get_me(self) -> dict[str, object]:
        return {"data": {"id": "123456", "name": "Razzy", "username": "razzy"}}

    def get_post(self, post_id: str) -> dict[str, object]:
        return {"data": {"id": post_id, "text": "hello world"}}

    def get_user_timeline(self, user_id: str, max_results: int = 10) -> dict[str, object]:
        return {"data": [{"id": "1", "text": "hello"}], "meta": {"user_id": user_id, "max_results": max_results}}

    def create_post(self, text: str, reply_to_id: str | None = None, quote_post_id: str | None = None) -> dict[str, object]:
        payload = {"text": text, "reply_to_id": reply_to_id, "quote_post_id": quote_post_id}
        self.created_posts.append(payload)
        return {"data": {"id": "999", **payload}}

    def delete_post(self, post_id: str) -> dict[str, object]:
        self.deleted_posts.append(post_id)
        return {"data": {"deleted": True, "id": post_id}}


@pytest.fixture()
def temp_db(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_chat.db"
        monkeypatch.setattr(config, "DB_PATH", db_path)
        init_db()
        yield db_path


@pytest.fixture()
def fake_service(temp_db):
    service = ChatService()
    service.providers = FakeProviderRegistry()
    return service


@pytest.fixture()
def app(fake_service, monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "test-key")
    razzy_service = RazzyService(repository=fake_service.repository, providers=fake_service.providers)
    twitter_service = TwitterService(client=FakeTwitterClient())
    app = create_app(service=fake_service, razzy_service=razzy_service, twitter_service=twitter_service)
    app.config.update(TESTING=True)
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers():
    return {"X-API-Key": "test-key", "Content-Type": "application/json"}
