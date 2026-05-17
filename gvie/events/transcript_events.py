"""Structured transcript events for streaming runtime updates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto


class TranscriptEventType(Enum):
    """Kinds of transcript updates emitted by the runtime."""

    PARTIAL_UPDATED = auto()
    PARTIAL_CORRECTED = auto()
    FINALIZED = auto()


@dataclass(slots=True)
class TranscriptEvent:
    """Single transcript update event."""

    event: TranscriptEventType
    text: str
    revision: int
    confidence: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
