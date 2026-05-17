"""Conversation lifecycle runtime events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any


class RuntimeEventType(Enum):
    """Runtime lifecycle events."""

    SESSION_STARTED = auto()
    SPEECH_STARTED = auto()
    PARTIAL_TRANSCRIPT = auto()
    FINAL_TRANSCRIPT = auto()
    USER_TURN_COMPLETED = auto()
    RESPONSE_GENERATED = auto()
    RESPONSE_SPOKEN = auto()
    SESSION_ENDED = auto()


@dataclass(slots=True)
class RuntimeEvent:
    """Structured runtime event."""

    event_type: RuntimeEventType
    session_id: str
    turn_id: int | None = None
    plugin: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
