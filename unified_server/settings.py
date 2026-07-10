from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() == "true"


def _env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


@dataclass
class Settings:
    """Runtime configuration, loaded once from the environment via from_env().

    Field names intentionally match the legacy unified_server.config constants
    so call sites read as get_settings().<OLD_CONSTANT_NAME>.
    """

    # Server runtime
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    FLASK_ENV: str = "development"
    APP_RUNNER: str = "waitress"
    DEBUG: bool = False
    USE_RELOADER: bool = False
    WAITRESS_THREADS: int = 8
    API_KEY: str = ""
    ALLOWED_ORIGINS: list[str] = field(default_factory=lambda: ["*"])

    # Storage
    DB_PATH: Path = DATA_DIR / "chat.db"

    # Providers
    DEFAULT_PROVIDER: str = "openai"
    DEFAULT_MODEL: str = "gpt-4.1-mini"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "llama3.2:latest"

    # Twitter / X
    TWITTER_API_KEY: str = ""
    TWITTER_API_SECRET: str = ""
    TWITTER_ACCESS_TOKEN: str = ""
    TWITTER_ACCESS_TOKEN_SECRET: str = ""
    TWITTER_BEARER_TOKEN: str = ""
    TWITTER_USER_ID: str = ""
    TWITTER_BASE_URL: str = "https://api.twitter.com"
    TWITTER_TIMEOUT_SECONDS: int = 30

    # Supabase / Gio
    SUPABASE_URL: str = ""
    SUPABASE_PUBLISHABLE_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    GIO_DEFAULT_PROVIDER: str = "openai"
    GIO_DEFAULT_MODEL: str = "gpt-4.1-mini"
    GIO_CONVERSATIONS_TABLE: str = "gio_conversations"
    GIO_MESSAGES_TABLE: str = "gio_messages"
    GIO_SUMMARIES_TABLE: str = "gio_conversation_summaries"
    GIO_DREAMS_TABLE: str = "gio_dream_entries"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    GIO_RECENT_MESSAGES_LIMIT: int = 12
    GIO_RECALL_TOP_K: int = 5
    GIO_RECALL_MIN_SCORE: float = 0.2
    GIO_SUMMARY_TRIGGER_MESSAGES: int = 8
    GIO_SUMMARY_MODEL: str = "gpt-4.1-mini"
    GIO_DREAM_MODEL: str = "gpt-4.1-mini"
    GIO_DREAM_SOURCE_LIMIT: int = 8
    GIO_DREAM_RECALL_ENABLED: bool = True
    GIO_DREAM_RECALL_TOP_K: int = 5
    GIO_DREAM_RECALL_MIN_SCORE: float = 0.25
    GIO_DREAM_RECALL_PROBABILITY: float = 0.25

    # Local memory cells
    ENABLE_MEMORY: bool = True
    MEMORY_TOP_K: int = 5

    # Public-API integrations
    NASA_API_KEY: str = "DEMO_KEY"
    WEATHER_LATITUDE: float = 40.7128
    WEATHER_LONGITUDE: float = -74.0060
    WEATHER_LOCATION_NAME: str = "New York, NY"
    CRYPTO_COINS: list[str] = field(default_factory=lambda: ["bitcoin", "ethereum"])
    CURRENCY_DEFAULT_BASE: str = "USD"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        summary_model = os.getenv("GIO_SUMMARY_MODEL", "gpt-4.1-mini")
        return cls(
            HOST=os.getenv("HOST", "0.0.0.0"),
            PORT=int(os.getenv("PORT", "8000")),
            FLASK_ENV=os.getenv("FLASK_ENV", "development"),
            APP_RUNNER=os.getenv("APP_RUNNER", "waitress").lower(),
            DEBUG=_env_bool("DEBUG"),
            USE_RELOADER=_env_bool("USE_RELOADER"),
            WAITRESS_THREADS=int(os.getenv("WAITRESS_THREADS", "8")),
            API_KEY=os.getenv("API_KEY", ""),
            ALLOWED_ORIGINS=_env_list("ALLOWED_ORIGINS", "*"),
            DB_PATH=DATA_DIR / "chat.db",
            DEFAULT_PROVIDER=os.getenv("DEFAULT_PROVIDER", "openai"),
            DEFAULT_MODEL=os.getenv("DEFAULT_MODEL", "gpt-4.1-mini"),
            OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
            ANTHROPIC_API_KEY=os.getenv("ANTHROPIC_API_KEY", ""),
            OLLAMA_BASE_URL=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            OLLAMA_MODEL=os.getenv("OLLAMA_MODEL", "llama3.2:latest"),
            TWITTER_API_KEY=os.getenv("TWITTER_API_KEY", ""),
            TWITTER_API_SECRET=os.getenv("TWITTER_API_SECRET", ""),
            TWITTER_ACCESS_TOKEN=os.getenv("TWITTER_ACCESS_TOKEN", ""),
            TWITTER_ACCESS_TOKEN_SECRET=os.getenv("TWITTER_ACCESS_TOKEN_SECRET", ""),
            TWITTER_BEARER_TOKEN=os.getenv("TWITTER_BEARER_TOKEN", ""),
            TWITTER_USER_ID=os.getenv("TWITTER_USER_ID", ""),
            TWITTER_BASE_URL=os.getenv("TWITTER_BASE_URL", "https://api.twitter.com"),
            TWITTER_TIMEOUT_SECONDS=int(os.getenv("TWITTER_TIMEOUT_SECONDS", "30")),
            SUPABASE_URL=os.getenv("SUPABASE_URL", os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")),
            SUPABASE_PUBLISHABLE_KEY=os.getenv(
                "SUPABASE_PUBLISHABLE_KEY", os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "")
            ),
            SUPABASE_SERVICE_ROLE_KEY=os.getenv(
                "SUPABASE_SERVICE_ROLE_KEY", os.getenv("SERVICE_ROLE_KEY", "")
            ),
            GIO_DEFAULT_PROVIDER=os.getenv("GIO_DEFAULT_PROVIDER", "openai"),
            GIO_DEFAULT_MODEL=os.getenv("GIO_DEFAULT_MODEL", "gpt-4.1-mini"),
            GIO_CONVERSATIONS_TABLE=os.getenv("GIO_CONVERSATIONS_TABLE", "gio_conversations"),
            GIO_MESSAGES_TABLE=os.getenv("GIO_MESSAGES_TABLE", "gio_messages"),
            GIO_SUMMARIES_TABLE=os.getenv("GIO_SUMMARIES_TABLE", "gio_conversation_summaries"),
            GIO_DREAMS_TABLE=os.getenv("GIO_DREAMS_TABLE", "gio_dream_entries"),
            OPENAI_EMBEDDING_MODEL=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            GIO_RECENT_MESSAGES_LIMIT=int(os.getenv("GIO_RECENT_MESSAGES_LIMIT", "12")),
            GIO_RECALL_TOP_K=int(os.getenv("GIO_RECALL_TOP_K", "5")),
            GIO_RECALL_MIN_SCORE=float(os.getenv("GIO_RECALL_MIN_SCORE", "0.2")),
            GIO_SUMMARY_TRIGGER_MESSAGES=int(os.getenv("GIO_SUMMARY_TRIGGER_MESSAGES", "8")),
            GIO_SUMMARY_MODEL=summary_model,
            GIO_DREAM_MODEL=os.getenv("GIO_DREAM_MODEL", summary_model),
            GIO_DREAM_SOURCE_LIMIT=int(os.getenv("GIO_DREAM_SOURCE_LIMIT", "8")),
            GIO_DREAM_RECALL_ENABLED=_env_bool("GIO_DREAM_RECALL_ENABLED", "true"),
            GIO_DREAM_RECALL_TOP_K=int(os.getenv("GIO_DREAM_RECALL_TOP_K", "5")),
            GIO_DREAM_RECALL_MIN_SCORE=float(os.getenv("GIO_DREAM_RECALL_MIN_SCORE", "0.25")),
            GIO_DREAM_RECALL_PROBABILITY=float(os.getenv("GIO_DREAM_RECALL_PROBABILITY", "0.25")),
            ENABLE_MEMORY=_env_bool("ENABLE_MEMORY", "true"),
            MEMORY_TOP_K=int(os.getenv("MEMORY_TOP_K", "5")),
            NASA_API_KEY=os.getenv("NASA_API_KEY", "DEMO_KEY"),
            WEATHER_LATITUDE=float(os.getenv("WEATHER_LATITUDE", "40.7128")),
            WEATHER_LONGITUDE=float(os.getenv("WEATHER_LONGITUDE", "-74.0060")),
            WEATHER_LOCATION_NAME=os.getenv("WEATHER_LOCATION_NAME", "New York, NY"),
            CRYPTO_COINS=_env_list("CRYPTO_COINS", "bitcoin,ethereum"),
            CURRENCY_DEFAULT_BASE=os.getenv("CURRENCY_DEFAULT_BASE", "USD"),
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def reset_settings() -> None:
    """Discard the cached Settings so the next get_settings() reloads from env."""
    global _settings
    _settings = None
