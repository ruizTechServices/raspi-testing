from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class Conversation:
    id: str
    title: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class ChatMessage:
    id: int
    conversation_id: str
    role: str
    content: str
    provider: Optional[str]
    model: Optional[str]
    created_at: str


@dataclass(slots=True)
class MemoryCell:
    id: int
    conversation_id: str
    cell_type: str
    content: str
    salience: float
    created_at: str
