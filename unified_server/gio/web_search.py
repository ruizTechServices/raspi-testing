from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from unified_server.gio.tooling import GioContextSource
from unified_server.settings import get_settings


class WebSearchConfigurationError(Exception):
    pass


@dataclass(slots=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str


class WebSearchService:
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()

    def search(self, query: str) -> list[GioContextSource]:
        cleaned = (query or "").strip()
        if not cleaned:
            return []

        try:
            results = self._run_provider_search(cleaned)
        except Exception:
            return []

        sources: list[GioContextSource] = []
        for index, item in enumerate(results, start=1):
            snippet = " ".join(item.snippet.split())[:700].strip()
            if not snippet:
                continue
            sources.append(
                GioContextSource(
                    kind="web",
                    label=f"[W{index}]",
                    title=item.title or item.url,
                    source=item.url,
                    url=item.url,
                    snippet=snippet,
                )
            )
        return sources

    def _run_provider_search(self, query: str) -> list[WebSearchResult]:
        settings = get_settings()
        provider = (settings.GIO_WEB_SEARCH_PROVIDER or "tavily").strip().lower()
        if provider == "tavily":
            return self._search_tavily(query)
        if provider == "serper":
            return self._search_serper(query)
        raise WebSearchConfigurationError(f"Unsupported web search provider: {provider}")

    def _search_tavily(self, query: str) -> list[WebSearchResult]:
        settings = get_settings()
        if not settings.TAVILY_API_KEY:
            raise WebSearchConfigurationError("TAVILY_API_KEY is not configured.")
        response = self.session.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": settings.GIO_WEB_SEARCH_MAX_RESULTS,
                "include_answer": False,
                "include_raw_content": False,
            },
            timeout=settings.GIO_WEB_SEARCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            WebSearchResult(
                title=str(item.get("title") or item.get("url") or "Untitled"),
                url=str(item.get("url") or ""),
                snippet=str(item.get("content") or item.get("snippet") or ""),
            )
            for item in payload.get("results", [])
            if item.get("url")
        ]

    def _search_serper(self, query: str) -> list[WebSearchResult]:
        settings = get_settings()
        if not settings.SERPER_API_KEY:
            raise WebSearchConfigurationError("SERPER_API_KEY is not configured.")
        response = self.session.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": settings.SERPER_API_KEY},
            json={"q": query, "num": settings.GIO_WEB_SEARCH_MAX_RESULTS},
            timeout=settings.GIO_WEB_SEARCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        return [
            WebSearchResult(
                title=str(item.get("title") or item.get("link") or "Untitled"),
                url=str(item.get("link") or ""),
                snippet=str(item.get("snippet") or ""),
            )
            for item in payload.get("organic", [])
            if item.get("link")
        ]
