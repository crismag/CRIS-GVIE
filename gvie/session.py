"""Session persistence layer."""

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import TranscriptEntry


class SessionStore:
    """Stores metadata and transcript lines for one runtime session."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.base_dir / f"session_{timestamp}"
        self.transcript_path = self.session_dir / "transcript.jsonl"
        self.metadata_path = self.session_dir / "metadata.json"

    def start(self, metadata: dict[str, str]) -> None:
        """Initialize session directory and metadata."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    def append(self, speaker: str, text: str) -> None:
        """Append one transcript entry to transcript.jsonl."""
        entry = TranscriptEntry(speaker=speaker, text=text)
        with self.transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(entry.model_dump_json() + "\n")
