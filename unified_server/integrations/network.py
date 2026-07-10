from __future__ import annotations

from typing import Any

from unified_server.integrations.http import CachedHttpClient

IPIFY_URL = "https://api.ipify.org"


class PublicIpClient:
    """The Pi's public WAN IP via ipify (no API key)."""

    def __init__(self, http: CachedHttpClient | None = None) -> None:
        self.http = http or CachedHttpClient(ttl_seconds=300)

    def public_ip(self) -> dict[str, Any]:
        data = self.http.get_json(IPIFY_URL, params={"format": "json"})
        return {"ip": data.get("ip"), "source": "ipify.org"}
