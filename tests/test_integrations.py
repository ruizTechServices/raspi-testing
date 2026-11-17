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


class ScriptedApodHttp:
    """Serves a canned APOD feed; ``feed=None`` behaves like NASA being down."""

    def __init__(self, feed):
        self.feed = feed
        self.calls = 0

    def get_text(self, url, params=None):
        self.calls += 1
        if self.feed is None:
            raise IntegrationError("Upstream API timed out.")
        return self.feed


class FakeClock:
    def __init__(self, year, month, day, hour=12):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        self.now = datetime(year, month, day, hour, tzinfo=ZoneInfo("America/New_York")).timestamp()

    def __call__(self):
        return self.now


def apod_feed(*items):
    """items: (title, 'DD Mon YYYY' publication day, media url)."""
    entries = "".join(
        f"""<item>
          <title>{title}</title>
          <link>https://science.nasa.gov/image-article/{title.lower().replace(' ', '-')}/</link>
          <pubDate>{day} 05:05:00 +0000</pubDate>
          <apod:hdurl>{media}</apod:hdurl>
          <apod:copyright><![CDATA[<a href="https://example.com">Some Astronomer</a>; <br>Processing: <a href="#">A. Person</a>]]></apod:copyright>
          <apod:explanation><![CDATA[<strong>Explanation:</strong> A dark <a href="#">nebula</a> in Orion.]]></apod:explanation>
        </item>"""
        for title, day, media in items
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" ?><rss version="2.0" '
        'xmlns:apod="https://science.nasa.gov/apod/"><channel><title>APOD Basic</title>'
        f"{entries}</channel></rss>"
    )


HORSEHEAD = "https://assets.science.nasa.gov/a/horsehead.jpg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg"


def test_apod_endpoint():
    feed = apod_feed(
        ("Older Picture", "08 Jul 2026", "https://assets.science.nasa.gov/a/older.jpg"),
        ("The Horsehead Nebula", "09 Jul 2026", HORSEHEAD),
    )
    client = build_client(apod=ApodClient(http=ScriptedApodHttp(feed), clock=FakeClock(2026, 7, 9)))

    response = client.get("/api/integrations/apod")

    assert response.status_code == 200
    body = response.get_json()
    assert body["title"] == "The Horsehead Nebula"  # newest item wins, whatever the order
    assert body["date"] == "2026-07-09"
    assert body["media_type"] == "image"
    assert body["url"] == HORSEHEAD
    assert body["hd_url"] == "https://assets.science.nasa.gov/a/horsehead.jpg"
    assert body["copyright"] == "Some Astronomer; Processing: A. Person"
    assert body["explanation"] == "A dark nebula in Orion."
    assert body["stale"] is False


def test_apod_video_day_links_to_the_nasa_page_instead_of_an_image():
    feed = apod_feed(("A Video Day", "09 Jul 2026", "https://www.youtube.com/embed/abc123"))
    apod = ApodClient(http=ScriptedApodHttp(feed), clock=FakeClock(2026, 7, 9))

    body = apod.picture_of_the_day()

    assert body["media_type"] == "video"
    assert body["url"] == "https://science.nasa.gov/image-article/a-video-day/"
    assert body["hd_url"] is None and body["thumbnail_url"] is None


def test_apod_does_not_refetch_once_it_has_todays_picture():
    http = ScriptedApodHttp(apod_feed(("Today", "10 Jul 2026", HORSEHEAD)))
    apod = ApodClient(http=http, clock=FakeClock(2026, 7, 10))

    apod.picture_of_the_day()
    apod.picture_of_the_day()

    assert http.calls == 1


def test_apod_shows_yesterday_until_today_is_published_then_picks_it_up():
    http = ScriptedApodHttp(apod_feed(("Yesterday", "09 Jul 2026", HORSEHEAD)))
    clock = FakeClock(2026, 7, 10, hour=0)
    apod = ApodClient(http=http, clock=clock)

    body = apod.picture_of_the_day()
    apod.picture_of_the_day()

    assert body["title"] == "Yesterday" and body["stale"] is False
    assert http.calls == 1  # the second load waits out the backoff

    http.feed = apod_feed(("Yesterday", "09 Jul 2026", HORSEHEAD), ("Today", "10 Jul 2026", HORSEHEAD))
    clock.now += 16 * 60
    assert apod.picture_of_the_day()["title"] == "Today"


def test_apod_serves_last_good_picture_from_disk_while_nasa_is_down(tmp_path):
    cache_path = tmp_path / "apod_last_good.json"
    working = ScriptedApodHttp(apod_feed(("Saved", "08 Jul 2026", HORSEHEAD)))
    ApodClient(http=working, cache_path=cache_path, clock=FakeClock(2026, 7, 8)).picture_of_the_day()

    down = ScriptedApodHttp(None)
    restarted = ApodClient(http=down, cache_path=cache_path, clock=FakeClock(2026, 7, 10))
    client = build_client(apod=restarted)

    response = client.get("/api/integrations/apod")
    client.get("/api/integrations/apod")

    assert response.status_code == 200
    body = response.get_json()
    assert body["title"] == "Saved" and body["stale"] is True
    assert down.calls == 1  # no hammering during the backoff


def test_apod_endpoint_returns_503_when_nasa_is_down_and_nothing_is_saved():
    client = build_client(apod=ApodClient(http=ScriptedApodHttp(None), clock=FakeClock(2026, 7, 10)))

    response = client.get("/api/integrations/apod")

    assert response.status_code == 503
    assert "timed out" in response.get_json()["error"]


def test_apod_rejects_a_feed_that_is_not_xml():
    apod = ApodClient(http=ScriptedApodHttp("<html>maintenance"), clock=FakeClock(2026, 7, 10))

    with pytest.raises(IntegrationError):
        apod.picture_of_the_day()


def test_cached_http_client_get_text_is_cached():
    class TextSession:
        calls = 0

        def get(self, url, params=None, timeout=None):
            TextSession.calls += 1
            response = FakeResponse({})
            response.text = "<rss/>"
            return response

    http = CachedHttpClient(ttl_seconds=60, session=TextSession())

    assert http.get_text("https://example.com/feed") == "<rss/>"
    assert http.get_text("https://example.com/feed") == "<rss/>"
    assert TextSession.calls == 1


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
