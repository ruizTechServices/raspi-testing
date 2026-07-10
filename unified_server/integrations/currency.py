from __future__ import annotations

from typing import Any

from unified_server.integrations.http import CachedHttpClient

FRANKFURTER_URL = "https://api.frankfurter.app/latest"


class CurrencyClient:
    """Currency conversion via Frankfurter / ECB reference rates (no API key)."""

    def __init__(self, http: CachedHttpClient | None = None) -> None:
        self.http = http or CachedHttpClient(ttl_seconds=3600)

    def convert(self, amount: float, from_currency: str, to_currency: str) -> dict[str, Any]:
        from_code = _validate_currency_code(from_currency, "from")
        to_code = _validate_currency_code(to_currency, "to")
        if from_code == to_code:
            raise ValueError("'from' and 'to' currencies must differ.")
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("amount must be a positive number.")

        data = self.http.get_json(
            FRANKFURTER_URL,
            params={"amount": amount, "from": from_code, "to": to_code},
        )
        rates = data.get("rates", {})
        converted = rates.get(to_code)
        if converted is None:
            raise ValueError(f"Unsupported currency pair: {from_code} -> {to_code}.")
        return {
            "amount": amount,
            "from": from_code,
            "to": to_code,
            "converted": converted,
            "rate_date": data.get("date"),
            "source": "frankfurter.app (ECB rates)",
        }


def _validate_currency_code(value: str, field: str) -> str:
    code = (value or "").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError(f"'{field}' must be a 3-letter currency code.")
    return code
