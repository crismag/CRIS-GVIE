"""Session persistence layer."""

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import RuntimeEventEntry, TranscriptEntry, TurnEntry


class SessionStore:
    """Stores metadata and transcript lines for one runtime session."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.base_dir / f"session_{timestamp}"
        self.session_id = self.session_dir.name
        self.transcript_path = self.session_dir / "transcript.jsonl"
        self.events_path = self.session_dir / "events.jsonl"
        self.metadata_path = self.session_dir / "metadata.json"

    def start(self, metadata: dict[str, object]) -> None:
        """Initialize session directory and metadata."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    def append(self, speaker: str, text: str) -> None:
        """Append one transcript entry to transcript.jsonl (legacy helper)."""
        entry = TranscriptEntry(speaker=speaker, text=text)
        with self.transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(entry.model_dump_json() + "\n")

    def save_turn(
        self,
        turn_id: int,
        speaker: str,
        text: str,
        plugin: str | None = None,
        audio_file: str | None = None,
        started_at: str | None = None,
        ended_at: str | None = None,
        partial_history: list[str] | None = None,
        revision_id: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Persist a rich turn record to transcript.jsonl."""
        now = datetime.now(timezone.utc).isoformat()
        entry = TurnEntry(
            turn_id=turn_id,
            speaker=speaker,
            plugin=plugin,
            audio_file=audio_file,
            text=text,
            started_at=started_at or now,
            ended_at=ended_at or now,
            partial_history=partial_history,
            revision_id=revision_id,
            metadata=metadata or {},
        )
        with self.transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(entry.model_dump_json() + "\n")

    def save_event(
        self,
        event_type: str,
        session_id: str,
        turn_id: int | None = None,
        plugin: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        """Persist a runtime event to events.jsonl."""
        entry = RuntimeEventEntry(
            event_type=event_type,
            session_id=session_id,
            turn_id=turn_id,
            plugin=plugin,
            payload=payload or {},
        )
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(entry.model_dump_json() + "\n")
