"""Structured audio event types for the VAD runtime."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path


class AudioEventType(Enum):
    """Discrete events emitted during a VAD-driven voice session."""

    SPEECH_STARTED = auto()
    SPEECH_ENDED = auto()
    SILENCE_DETECTED = auto()
    TURN_COMPLETED = auto()


@dataclass
class TurnCompletedPayload:
    """Data attached to a TURN_COMPLETED event."""

    turn_id: int
    wav_path: Path
    started_at: str
    ended_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
