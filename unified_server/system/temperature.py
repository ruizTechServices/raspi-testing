from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

PI_TEMPERATURE_CACHE_TTL_SECONDS = 15


def _read_pi_temperature_c() -> float:
    raw = Path("/sys/class/thermal/thermal_zone0/temp").read_text(encoding="utf-8").strip()
    return int(raw) / 1000.0


def _temperature_state(temperature_c: float) -> tuple[str, str]:
    if temperature_c < 55:
        return "cool", "Cool, plenty of thermal headroom."
    if temperature_c < 70:
        return "normal", "Normal operating range for the Pi."
    if temperature_c < 80:
        return "warm", "Warm, but still acceptable under load."
    return "hot", "Hot. Ease sustained load or improve cooling if this persists."


def _build_temperature_payload(
    temperature_c: float,
    fetched_at: float,
    *,
    cached: bool,
    age_seconds: float,
) -> dict[str, object]:
    temperature_f = round((temperature_c * 9 / 5) + 32, 1)
    state, advisory = _temperature_state(temperature_c)
    return {
        "temperature_c": temperature_c,
        "temperature_f": temperature_f,
        "thermal_state": state,
        "advisory": advisory,
        "cached": cached,
        "cache_ttl_seconds": PI_TEMPERATURE_CACHE_TTL_SECONDS,
        "age_seconds": round(age_seconds, 1),
        "fetched_at": fetched_at,
    }


class PiTemperatureMonitor:
    """Reads the Pi CPU temperature with a short-lived cache.

    The cache lives on the instance (one monitor per app), and the reader/clock
    are injectable so tests never touch the real sensor.
    """

    def __init__(
        self,
        read_temp: Callable[[], float] | None = None,
        clock: Callable[[], float] = time.time,
        cache_ttl_seconds: int = PI_TEMPERATURE_CACHE_TTL_SECONDS,
    ) -> None:
        self._read_temp = read_temp
        self._clock = clock
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cached_temperature_c: float | None = None
        self._fetched_at: float | None = None

    def snapshot(self) -> dict[str, object]:
        now = self._clock()
        if self._fetched_at is not None and self._cached_temperature_c is not None:
            age_seconds = now - self._fetched_at
            if age_seconds < self._cache_ttl_seconds:
                return _build_temperature_payload(
                    self._cached_temperature_c,
                    self._fetched_at,
                    cached=True,
                    age_seconds=age_seconds,
                )

        # Resolved at call time so monkeypatching the module function works.
        reader = self._read_temp or _read_pi_temperature_c
        temperature_c = round(reader(), 1)
        self._cached_temperature_c = temperature_c
        self._fetched_at = now
        return _build_temperature_payload(temperature_c, now, cached=False, age_seconds=0.0)
