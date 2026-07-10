from __future__ import annotations

from typing import Any

from unified_server.settings import get_settings
from unified_server.twitter_client import TwitterClient, TwitterClientConfig, TwitterClientConfigError, TwitterClientError


class TwitterService:
    def __init__(self, client: TwitterClient | None = None) -> None:
        settings = get_settings()
        self.client = client or TwitterClient(
            TwitterClientConfig(
                api_key=settings.TWITTER_API_KEY,
                api_secret=settings.TWITTER_API_SECRET,
                access_token=settings.TWITTER_ACCESS_TOKEN,
                access_token_secret=settings.TWITTER_ACCESS_TOKEN_SECRET,
                bearer_token=settings.TWITTER_BEARER_TOKEN,
                user_id=settings.TWITTER_USER_ID,
                base_url=settings.TWITTER_BASE_URL,
                timeout_seconds=settings.TWITTER_TIMEOUT_SECONDS,
            )
        )

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.client.is_configured(),
            "base_url": self.client.config.base_url,
            "user_id": self.client.config.user_id,
            "supports_read": bool(self.client.config.bearer_token),
            "supports_write": self.client.is_configured(),
        }

    def get_me(self) -> dict[str, Any]:
        return self.client.get_me()

    def get_post(self, post_id: str) -> dict[str, Any]:
        self._validate_post_id(post_id)
        return self.client.get_post(post_id)

    def create_post(self, text: str) -> dict[str, Any]:
        self._validate_text(text)
        return self.client.create_post(text=text.strip())

    def delete_post(self, post_id: str) -> dict[str, Any]:
        self._validate_post_id(post_id)
        return self.client.delete_post(post_id)

    def reply_to_post(self, post_id: str, text: str) -> dict[str, Any]:
        self._validate_post_id(post_id)
        self._validate_text(text)
        return self.client.create_post(text=text.strip(), reply_to_id=post_id)

    def quote_post(self, post_id: str, text: str) -> dict[str, Any]:
        self._validate_post_id(post_id)
        self._validate_text(text)
        return self.client.create_post(text=text.strip(), quote_post_id=post_id)

    def get_user_timeline(self, user_id: str | None = None, max_results: int = 10) -> dict[str, Any]:
        target_user_id = (user_id or self.client.config.user_id).strip()
        if not target_user_id:
            raise ValueError("user_id is required.")
        return self.client.get_user_timeline(target_user_id, max_results=max_results)

    @staticmethod
    def _validate_text(text: str) -> None:
        if not text or not text.strip():
            raise ValueError("text is required.")

    @staticmethod
    def _validate_post_id(post_id: str) -> None:
        if not post_id or not post_id.strip():
            raise ValueError("post_id is required.")


__all__ = [
    "TwitterService",
    "TwitterClientError",
    "TwitterClientConfigError",
]
