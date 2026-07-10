from __future__ import annotations

from dataclasses import asdict
from typing import Any


def serialize_message(message) -> dict[str, Any]:
    payload = asdict(message)
    payload.pop("embedding", None)
    return payload


def serialize_dream(dream) -> dict[str, Any]:
    payload = asdict(dream)
    payload.pop("embedding", None)
    return payload
