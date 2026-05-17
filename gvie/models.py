"""Core data models for voice interaction turns."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class TranscriptEntry(BaseModel):
    """Single line in transcript.jsonl (legacy append format)."""

    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    speaker: str
    text: str


class TurnEntry(BaseModel):
    """Rich turn record stored per completed conversational turn."""

    turn_id: int
    speaker: str
    plugin: str | None = None
    audio_file: str | None = None
    text: str
    started_at: str
    ended_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    partial_history: list[str] | None = None
    revision_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeEventEntry(BaseModel):
    """Persisted runtime event record."""

    event_type: str
    session_id: str
    turn_id: int | None = None
    plugin: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
