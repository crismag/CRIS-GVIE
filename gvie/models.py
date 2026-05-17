"""Core data models for voice interaction turns."""

from datetime import datetime, timezone

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
    audio_file: str | None = None
    text: str
    started_at: str
    ended_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    partial_history: list[str] | None = None
    revision_id: int | None = None
