from __future__ import annotations

from typing import Any

from unified_server.integrations.http import CachedHttpClient
from unified_server.settings import get_settings

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODE_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def describe_weather_code(code: Any) -> str:
    try:
        return WEATHER_CODE_DESCRIPTIONS.get(int(code), "Unknown conditions")
    except (TypeError, ValueError):
        return "Unknown conditions"


class WeatherClient:
    """Current conditions + 3-day forecast from Open-Meteo (no API key)."""

    def __init__(self, http: CachedHttpClient | None = None) -> None:
        self.http = http or CachedHttpClient(ttl_seconds=600)

    def snapshot(self) -> dict[str, Any]:
        settings = get_settings()
        data = self.http.get_json(
            OPEN_METEO_URL,
            params={
                "latitude": settings.WEATHER_LATITUDE,
                "longitude": settings.WEATHER_LONGITUDE,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "auto",
                "forecast_days": 3,
            },
        )
        current = data.get("current", {})
        daily = data.get("daily", {})
        days = []
        for index, date in enumerate(daily.get("time", [])):
            days.append(
                {
                    "date": date,
                    "high_f": _at(daily.get("temperature_2m_max"), index),
                    "low_f": _at(daily.get("temperature_2m_min"), index),
                    "precipitation_chance": _at(daily.get("precipitation_probability_max"), index),
                    "conditions": describe_weather_code(_at(daily.get("weather_code"), index)),
                }
            )
        return {
            "location": settings.WEATHER_LOCATION_NAME,
            "current": {
                "temperature_f": current.get("temperature_2m"),
                "feels_like_f": current.get("apparent_temperature"),
                "humidity_percent": current.get("relative_humidity_2m"),
                "wind_mph": current.get("wind_speed_10m"),
                "conditions": describe_weather_code(current.get("weather_code")),
            },
            "daily": days,
            "source": "open-meteo.com",
        }


def _at(values, index):
    if isinstance(values, list) and index < len(values):
        return values[index]
    return None
