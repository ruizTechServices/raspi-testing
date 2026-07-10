from __future__ import annotations

import time
from typing import Any, Callable

import requests


class IntegrationError(Exception):
    """An upstream public API was unreachable or returned an error."""


class CachedHttpClient:
    """GET-with-timeout plus a per-URL TTL cache.

    Every integration proxies a free public API; the cache keeps us polite to
    those services and makes widget refreshes cheap. `session` and `clock` are
    injectable for tests.
    """

    def __init__(
        self,
        ttl_seconds: float,
        *,
        session=None,
        clock: Callable[[], float] = time.time,
        timeout_seconds: float = 10,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._session = session or requests
        self._clock = clock
        self._timeout_seconds = timeout_seconds
        self._cache: dict[tuple, tuple[float, Any]] = {}

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        key = (url, tuple(sorted((params or {}).items())))
        now = self._clock()
        hit = self._cache.get(key)
        if hit and now - hit[0] < self._ttl_seconds:
            return hit[1]

        try:
            response = self._session.get(url, params=params, timeout=self._timeout_seconds)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout as exc:
            raise IntegrationError("Upstream API timed out.") from exc
        except requests.exceptions.ConnectionError as exc:
            raise IntegrationError("Upstream API is unreachable.") from exc
        except requests.exceptions.RequestException as exc:
            raise IntegrationError(f"Upstream API error: {exc}") from exc
        except ValueError as exc:
            raise IntegrationError("Upstream API returned invalid JSON.") from exc

        self._cache[key] = (now, data)
        return data
