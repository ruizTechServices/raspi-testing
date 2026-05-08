from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "chat.db"

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
FLASK_ENV = os.getenv("FLASK_ENV", "development")
APP_RUNNER = os.getenv("APP_RUNNER", "waitress").lower()
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
USE_RELOADER = os.getenv("USE_RELOADER", "false").lower() == "true"
WAITRESS_THREADS = int(os.getenv("WAITRESS_THREADS", "8"))
API_KEY = os.getenv("API_KEY", "")
ALLOWED_ORIGINS = [item.strip() for item in os.getenv("ALLOWED_ORIGINS", "*").split(",") if item.strip()]

DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "openai")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4.1-mini")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")
TWITTER_USER_ID = os.getenv("TWITTER_USER_ID", "")
TWITTER_BASE_URL = os.getenv("TWITTER_BASE_URL", "https://api.twitter.com")
TWITTER_TIMEOUT_SECONDS = int(os.getenv("TWITTER_TIMEOUT_SECONDS", "30"))

SUPABASE_URL = os.getenv("SUPABASE_URL", os.getenv("NEXT_PUBLIC_SUPABASE_URL", ""))
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", ""))
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SERVICE_ROLE_KEY", ""))
GIO_DEFAULT_PROVIDER = os.getenv("GIO_DEFAULT_PROVIDER", "openai")
GIO_DEFAULT_MODEL = os.getenv("GIO_DEFAULT_MODEL", "gpt-4.1-mini")
GIO_CONVERSATIONS_TABLE = os.getenv("GIO_CONVERSATIONS_TABLE", "gio_conversations")
GIO_MESSAGES_TABLE = os.getenv("GIO_MESSAGES_TABLE", "gio_messages")
GIO_SUMMARIES_TABLE = os.getenv("GIO_SUMMARIES_TABLE", "gio_conversation_summaries")
GIO_DREAMS_TABLE = os.getenv("GIO_DREAMS_TABLE", "gio_dream_entries")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
GIO_RECENT_MESSAGES_LIMIT = int(os.getenv("GIO_RECENT_MESSAGES_LIMIT", "12"))
GIO_RECALL_TOP_K = int(os.getenv("GIO_RECALL_TOP_K", "5"))
GIO_RECALL_MIN_SCORE = float(os.getenv("GIO_RECALL_MIN_SCORE", "0.2"))
GIO_SUMMARY_TRIGGER_MESSAGES = int(os.getenv("GIO_SUMMARY_TRIGGER_MESSAGES", "8"))
GIO_SUMMARY_MODEL = os.getenv("GIO_SUMMARY_MODEL", "gpt-4.1-mini")
GIO_DREAM_MODEL = os.getenv("GIO_DREAM_MODEL", GIO_SUMMARY_MODEL)
GIO_DREAM_SOURCE_LIMIT = int(os.getenv("GIO_DREAM_SOURCE_LIMIT", "8"))

ENABLE_MEMORY = os.getenv("ENABLE_MEMORY", "true").lower() == "true"
MEMORY_TOP_K = int(os.getenv("MEMORY_TOP_K", "5"))
