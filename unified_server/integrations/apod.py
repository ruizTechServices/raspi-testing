from __future__ import annotations

from typing import Any

from unified_server.integrations.http import CachedHttpClient
from unified_server.settings import get_settings

NASA_APOD_URL = "https://api.nasa.gov/planetary/apod"


class ApodClient:
    """NASA Astronomy Picture of the Day. Works out of the box with the
    rate-limited DEMO_KEY; set NASA_API_KEY for a free personal key."""

    def __init__(self, http: CachedHttpClient | None = None) -> None:
        self.http = http or CachedHttpClient(ttl_seconds=6 * 3600)

    def picture_of_the_day(self) -> dict[str, Any]:
        data = self.http.get_json(
            NASA_APOD_URL,
            params={"api_key": get_settings().NASA_API_KEY, "thumbs": "true"},
        )
        return {
            "title": data.get("title"),
            "date": data.get("date"),
            "explanation": data.get("explanation"),
            "media_type": data.get("media_type"),
            "url": data.get("url"),
            "hd_url": data.get("hdurl"),
            "thumbnail_url": data.get("thumbnail_url"),
            "copyright": (data.get("copyright") or "").strip() or None,
            "source": "apod.nasa.gov",
        }
