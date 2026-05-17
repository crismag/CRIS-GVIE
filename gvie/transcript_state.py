"""Mutable transcript state for a single speaker turn."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class TranscriptState:
    """Tracks the current partial and finalized transcript for one turn."""

    partial_text: str = ""
    final_text: str = ""
    revision_id: int = 0
    partial_history: list[str] = field(default_factory=list)

    @property
    def current_text(self) -> str:
        """Return the best available transcript text."""
        return self.final_text or self.partial_text

    def update_partial(self, text: str) -> None:
        """Store a new partial transcript revision."""
        normalized = " ".join(text.split()).strip()
        if not normalized or normalized == self.partial_text:
            return

        self.revision_id += 1
        self.partial_text = normalized
        self.partial_history.append(normalized)

    def finalize(self, text: str | None = None) -> str:
        """Promote the current transcript to final text."""
        if text is not None:
            self.update_partial(text)

        self.final_text = self.partial_text.strip()
        self.partial_text = ""
        self.revision_id += 1
        return self.final_text

    def reset(self) -> None:
        """Clear all turn-local state."""
        self.partial_text = ""
        self.final_text = ""
        self.revision_id = 0
        self.partial_history.clear()

