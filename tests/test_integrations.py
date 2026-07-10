from __future__ import annotations

import pytest
from flask import Flask

from unified_server.integrations.apod import ApodClient
from unified_server.integrations.crypto import CryptoPriceClient
from unified_server.integrations.currency import CurrencyClient
from unified_server.integrations.http import CachedHttpClient, IntegrationError
from unified_server.integrations.network import PublicIpClient
from unified_server.integrations.weather import WeatherClient
from unified_server.web.integrations import build_integrations_blueprint


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.content = b"{}"

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params})
        return FakeResponse(self.payload)


class FailingHttp:
    def get_json(self, url, params=None):
        raise IntegrationError("Upstream API is unreachable.")


def build_client(**overrides):
    app = Flask(__name__)
    app.register_blueprint(build_integrations_blueprint(**overrides))
    app.config.update(TESTING=True)
    return app.test_client()


def http_with(payload, ttl_seconds: float = 60):
    return CachedHttpClient(ttl_seconds=ttl_seconds, session=FakeSession(payload))


def test_weather_endpoint_returns_snapshot():
    payload = {
        "current": {
            "temperature_2m": 71.4,
            "apparent_temperature": 70.1,
            "relative_humidity_2m": 55,
            "wind_speed_10m": 7.8,
            "weather_code": 2,
        },
        "daily": {
            "time": ["2026-07-10"],
            "temperature_2m_max": [82.0],
            "temperature_2m_min": [66.0],
            "precipitation_probability_max": [20],
            "weather_code": [61],
        },
    }
    client = build_client(weather=WeatherClient(http=http_with(payload)))

    response = client.get("/api/integrations/weather")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["current"]["temperature_f"] == 71.4
    assert body["current"]["conditions"] == "Partly cloudy"
    assert body["daily"][0]["conditions"] == "Slight rain"


def test_weather_endpoint_maps_upstream_failure_to_503():
    client = build_client(weather=WeatherClient(http=FailingHttp()))

    response = client.get("/api/integrations/weather")

    assert response.status_code == 503
    assert "unavailable" in response.get_json()["error"].lower()


def test_public_ip_endpoint():
    client = build_client(network=PublicIpClient(http=http_with({"ip": "203.0.113.7"})))

    response = client.get("/api/integrations/network/public-ip")

    assert response.status_code == 200
    assert response.get_json()["ip"] == "203.0.113.7"


def test_crypto_prices_endpoint():
    payload = {
        "bitcoin": {"usd": 64250.12, "usd_24h_change": -1.4},
        "ethereum": {"usd": 3120.55, "usd_24h_change": 2.1},
    }
    client = build_client(crypto=CryptoPriceClient(http=http_with(payload)))

    response = client.get("/api/integrations/crypto/prices")

    assert response.status_code == 200
    prices = response.get_json()["prices"]
    assert {entry["coin"] for entry in prices} == {"bitcoin", "ethereum"}
    bitcoin = next(entry for entry in prices if entry["coin"] == "bitcoin")
    assert bitcoin["usd"] == 64250.12


def test_currency_convert_endpoint():
    payload = {"amount": 25.0, "base": "USD", "date": "2026-07-09", "rates": {"EUR": 22.83}}
    client = build_client(currency=CurrencyClient(http=http_with(payload)))

    response = client.get("/api/integrations/currency/convert?amount=25&from=usd&to=eur")

    assert response.status_code == 200
    body = response.get_json()
    assert body["from"] == "USD"
    assert body["to"] == "EUR"
    assert body["converted"] == 22.83


@pytest.mark.parametrize(
    "query",
    [
        "amount=25&from=usd&to=usd",   # same currency
        "amount=-5&from=usd&to=eur",   # non-positive amount
        "amount=25&from=usd&to=euros", # bad code
        "from=usd&to=eur",             # missing amount
    ],
)
def test_currency_convert_rejects_bad_params(query):
    client = build_client(currency=CurrencyClient(http=FailingHttp()))

    response = client.get(f"/api/integrations/currency/convert?{query}")

    assert response.status_code == 400


def test_apod_endpoint():
    payload = {
        "title": "The Horsehead Nebula",
        "date": "2026-07-09",
        "explanation": "A dark nebula in Orion.",
        "media_type": "image",
        "url": "https://apod.nasa.gov/apod/image/horsehead.jpg",
        "hdurl": "https://apod.nasa.gov/apod/image/horsehead_hd.jpg",
        "copyright": " Some Astronomer ",
    }
    client = build_client(apod=ApodClient(http=http_with(payload)))

    response = client.get("/api/integrations/apod")

    assert response.status_code == 200
    body = response.get_json()
    assert body["title"] == "The Horsehead Nebula"
    assert body["copyright"] == "Some Astronomer"


def test_cached_http_client_caches_within_ttl():
    session = FakeSession({"ip": "203.0.113.7"})
    fake_now = [1000.0]
    http = CachedHttpClient(ttl_seconds=300, session=session, clock=lambda: fake_now[0])

    first = http.get_json("https://api.ipify.org", params={"format": "json"})
    second = http.get_json("https://api.ipify.org", params={"format": "json"})
    assert first == second
    assert len(session.calls) == 1

    fake_now[0] += 301
    http.get_json("https://api.ipify.org", params={"format": "json"})
    assert len(session.calls) == 2
