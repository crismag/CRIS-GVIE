"""Core data models for voice interaction turns."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class TranscriptEntry(BaseModel):
    """Single line in transcript.jsonl."""

    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    speaker: str
    text: str
