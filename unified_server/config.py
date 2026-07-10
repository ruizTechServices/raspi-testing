"""DEPRECATED compatibility shim — use unified_server.settings.get_settings() instead.

Legacy code did `from unified_server.config import X`, which froze values at import
time. This module now delegates attribute access lazily to the Settings singleton.
Scheduled for removal once no callers remain (see TODO.md).
"""

from __future__ import annotations

from unified_server.settings import BASE_DIR, DATA_DIR, get_settings

__all__ = ["BASE_DIR", "DATA_DIR"]


def __getattr__(name: str):
    settings = get_settings()
    if hasattr(settings, name):
        return getattr(settings, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
