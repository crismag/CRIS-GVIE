"""Structured conversation context and turn models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class ConversationTurn:
    """A single conversational turn."""

    turn_id: int
    speaker: str
    text: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConversationContext:
    """Session-scoped context shared between runtime and plugins."""

    session_id: str
    transcript_history: list[ConversationTurn] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    runtime_state: dict[str, Any] = field(default_factory=dict)
