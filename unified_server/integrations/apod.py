from __future__ import annotations

import html
import json
import logging
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from unified_server.integrations.http import CachedHttpClient, IntegrationError

# NASA moved APOD from apod.nasa.gov to science.nasa.gov in 2026. The old
# api.nasa.gov/planetary/apod endpoint still answers but now returns the same
# placeholder ("NASA Science" plus a logo) for every date, so the picture comes
# from NASA's own feed instead. It needs no API key and has no rate limit.
NASA_APOD_FEED_URL = "https://science.nasa.gov/feed/apod-basic/"
APOD_NAMESPACE = {"apod": "https://science.nasa.gov/apod/"}

# APOD publishes a new picture around midnight US Eastern time.
APOD_TIMEZONE = ZoneInfo("America/New_York")

# After a failed fetch, or one that only had an older picture, wait this long
# before asking NASA again.
RETRY_BACKOFF_SECONDS = 15 * 60

_IMAGE_URL = re.compile(r"\.(?:jpe?g|png|gif|webp)(?:$|[/?])", re.IGNORECASE)
_RENDITION_SUFFIX = re.compile(r"/jcr:content/renditions/.*$")

logger = logging.getLogger(__name__)


def _plain_text(markup: str | None) -> str | None:
    if not markup:
        return None
    text = re.sub(r"<br\s*/?>|</p>|</div>", " ", markup, flags=re.IGNORECASE)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return re.sub(r"\s+", " ", text).strip() or None


class ApodClient:
    """NASA Astronomy Picture of the Day, read from NASA's APOD feed.

    Returns the newest picture in the feed. The last good picture is kept
    (optionally on disk at ``cache_path``) and served, marked ``stale`` once it
    is more than a day old, whenever NASA is slow or down.
    """

    def __init__(
        self,
        http: CachedHttpClient | None = None,
        *,
        cache_path: Path | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        # Short TTL: this class decides when to refetch (see RETRY_BACKOFF_SECONDS).
        self.http = http or CachedHttpClient(ttl_seconds=10 * 60, timeout_seconds=20)
        self._cache_path = cache_path
        self._clock = clock
        self._lock = threading.Lock()
        self._last_good: dict[str, Any] | None = self._load_last_good()
        self._next_attempt_at = 0.0
        self._last_error = "Upstream API is unreachable."

    def picture_of_the_day(self) -> dict[str, Any]:
        with self._lock:
            now = self._clock()
            today = datetime.fromtimestamp(now, APOD_TIMEZONE).date().isoformat()

            if self._last_good and self._last_good.get("date") == today:
                return {**self._last_good, "stale": False}

            if now >= self._next_attempt_at:
                try:
                    picture = self._fetch_newest()
                except IntegrationError as exc:
                    self._last_error = str(exc)
                    self._next_attempt_at = now + RETRY_BACKOFF_SECONDS
                else:
                    self._last_good = picture
                    self._save_last_good(picture)
                    if picture["date"] != today:
                        # Today's picture is not out yet; look again later.
                        self._next_attempt_at = now + RETRY_BACKOFF_SECONDS

            if self._last_good:
                yesterday = (
                    datetime.fromtimestamp(now, APOD_TIMEZONE).date() - timedelta(days=1)
                ).isoformat()
                stale = (self._last_good.get("date") or "") < yesterday
                return {**self._last_good, "stale": stale}
            raise IntegrationError(self._last_error)

    def _fetch_newest(self) -> dict[str, Any]:
        feed = self.http.get_text(NASA_APOD_FEED_URL)
        try:
            root = ET.fromstring(feed)
        except ET.ParseError as exc:
            raise IntegrationError("Upstream feed was not valid XML.") from exc

        newest: dict[str, Any] | None = None
        for item in root.iter("item"):
            picture = self._parse_item(item)
            if picture and (newest is None or picture["date"] > newest["date"]):
                newest = picture
        if newest is None:
            raise IntegrationError("Upstream feed had no picture.")
        return newest

    @staticmethod
    def _parse_item(item: ET.Element) -> dict[str, Any] | None:
        def text(tag: str) -> str | None:
            value = item.findtext(tag, namespaces=APOD_NAMESPACE)
            return value.strip() if value and value.strip() else None

        title, page_url, published = text("title"), text("link"), text("pubDate")
        if not (title and page_url and published):
            return None
        try:
            date = parsedate_to_datetime(published).astimezone(APOD_TIMEZONE).date().isoformat()
        except (TypeError, ValueError):
            return None

        media_url = text("apod:hdurl")
        is_image = bool(media_url and _IMAGE_URL.search(media_url))
        explanation = _plain_text(text("apod:explanation"))
        if explanation:
            explanation = re.sub(r"^Explanation:\s*", "", explanation)
        return {
            "title": title,
            "date": date,
            "explanation": explanation,
            "media_type": "image" if is_image else "video",
            # Images: a 1280px rendition to display and the original to open.
            # Anything else: link to NASA's page for that day.
            "url": media_url if is_image else page_url,
            "hd_url": _RENDITION_SUFFIX.sub("", media_url) if is_image else None,
            "thumbnail_url": None,
            "copyright": _plain_text(text("apod:copyright") or text("apod:credit")),
            "page_url": page_url,
            "source": "science.nasa.gov/apod",
        }

    def _load_last_good(self) -> dict[str, Any] | None:
        if not self._cache_path:
            return None
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) and data.get("date") else None

    def _save_last_good(self, picture: dict[str, Any]) -> None:
        if not self._cache_path:
            return
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(picture), encoding="utf-8")
            os.replace(tmp, self._cache_path)
        except OSError as exc:
            logger.warning("could not save the last good NASA picture: %s", exc)
