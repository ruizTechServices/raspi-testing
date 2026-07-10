from __future__ import annotations

from typing import Any

from unified_server.integrations.http import CachedHttpClient
from unified_server.settings import get_settings

COINGECKO_SIMPLE_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"


class CryptoPriceClient:
    """USD spot prices + 24h change from CoinGecko (no API key)."""

    def __init__(self, http: CachedHttpClient | None = None) -> None:
        self.http = http or CachedHttpClient(ttl_seconds=120)

    def prices(self) -> dict[str, Any]:
        coins = get_settings().CRYPTO_COINS
        data = self.http.get_json(
            COINGECKO_SIMPLE_PRICE_URL,
            params={
                "ids": ",".join(coins),
                "vs_currencies": "usd",
                "include_24hr_change": "true",
            },
        )
        prices = []
        for coin in coins:
            entry = data.get(coin)
            if not isinstance(entry, dict):
                continue
            prices.append(
                {
                    "coin": coin,
                    "usd": entry.get("usd"),
                    "change_24h_percent": entry.get("usd_24h_change"),
                }
            )
        return {"prices": prices, "source": "coingecko.com"}
