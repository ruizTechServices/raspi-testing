from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests
from requests_oauthlib import OAuth1


class TwitterClientError(Exception):
    pass


class TwitterClientConfigError(TwitterClientError):
    pass


@dataclass(slots=True)
class TwitterClientConfig:
    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    access_token_secret: str = ""
    bearer_token: str = ""
    user_id: str = ""
    base_url: str = "https://api.twitter.com"
    timeout_seconds: int = 30


class TwitterClient:
    def __init__(self, config: TwitterClientConfig) -> None:
        self.config = config

    def is_configured(self) -> bool:
        return bool(self.config.bearer_token or self._has_oauth1_credentials())

    def get_me(self) -> dict[str, Any]:
        self._ensure_user_context_credentials()
        return self._request(
            "GET",
            "/2/users/me",
            headers={"Content-Type": "application/json"},
            params={"user.fields": "id,name,username,description,profile_image_url,verified"},
        )

    def get_post(self, post_id: str) -> dict[str, Any]:
        self._ensure_user_context_credentials()
        return self._request(
            "GET",
            f"/2/tweets/{post_id}",
            headers={"Content-Type": "application/json"},
            params={"tweet.fields": "created_at,author_id,public_metrics,conversation_id"},
        )

    def get_user_timeline(self, user_id: str, max_results: int = 10) -> dict[str, Any]:
        self._ensure_user_context_credentials()
        return self._request(
            "GET",
            f"/2/users/{user_id}/tweets",
            headers={"Content-Type": "application/json"},
            params={
                "max_results": max(5, min(max_results, 100)),
                "tweet.fields": "created_at,author_id,public_metrics,conversation_id",
            },
        )

    def create_post(self, text: str, reply_to_id: str | None = None, quote_post_id: str | None = None) -> dict[str, Any]:
        self._ensure_write_credentials()
        payload: dict[str, Any] = {"text": text}
        if reply_to_id:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}
        if quote_post_id:
            payload["quote_tweet_id"] = quote_post_id
        return self._request("POST", "/2/tweets", json=payload, headers=self._write_headers())

    def delete_post(self, post_id: str) -> dict[str, Any]:
        self._ensure_write_credentials()
        return self._request("DELETE", f"/2/tweets/{post_id}", headers=self._write_headers())

    def _write_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def _bearer_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.bearer_token}", "Content-Type": "application/json"}

    def _has_oauth1_credentials(self) -> bool:
        return all(
            [
                self.config.api_key,
                self.config.api_secret,
                self.config.access_token,
                self.config.access_token_secret,
            ]
        )

    def _ensure_bearer_token(self, message: str) -> None:
        if not self.config.bearer_token:
            raise TwitterClientConfigError(message)

    def _ensure_user_context_credentials(self) -> None:
        if self._has_oauth1_credentials():
            return
        raise TwitterClientConfigError(
            "Twitter/X user-context endpoints require OAuth 1.0a credentials "
            "(api key, api secret, access token, access token secret)."
        )

    def _ensure_write_credentials(self) -> None:
        if self._has_oauth1_credentials():
            return
        raise TwitterClientConfigError(
            "Twitter/X write operations require OAuth 1.0a credentials "
            "(api key, api secret, access token, access token secret)."
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}{path}"
        auth = None
        if self._has_oauth1_credentials():
            auth = OAuth1(
                self.config.api_key,
                client_secret=self.config.api_secret,
                resource_owner_key=self.config.access_token,
                resource_owner_secret=self.config.access_token_secret,
            )
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json,
            timeout=self.config.timeout_seconds,
            auth=auth,
        )
        if response.status_code >= 400:
            detail = response.text.strip()
            raise TwitterClientError(f"Twitter/X API error ({response.status_code}): {detail}")
        return response.json() if response.content else {"ok": True}
