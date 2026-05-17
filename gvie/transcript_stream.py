"""Live transcript stream management and event emission."""

from dataclasses import asdict
from typing import Callable

from rich.console import Console

from .partial_result_manager import PartialDecision, PartialResultManager
from .transcript_events import TranscriptEvent, TranscriptEventType
from .transcript_state import TranscriptState


class TranscriptStream:
    """Maintains ordered streaming transcript state for a single turn."""

    def __init__(
        self,
        console: Console | None = None,
        on_event: Callable[[TranscriptEvent], None] | None = None,
        partial_result_manager: PartialResultManager | None = None,
    ) -> None:
        self.console = console or Console()
        self.on_event = on_event
        self.state = TranscriptState()
        self.partial_result_manager = partial_result_manager or PartialResultManager()
        self.events: list[TranscriptEvent] = []

    def publish_partial(self, text: str) -> TranscriptEvent | None:
        """Publish a partial transcript update."""
        decision: PartialDecision = self.partial_result_manager.evaluate(text)
        if not decision.emit:
            return None

        self.state.update_partial(decision.text)
        event = TranscriptEvent(
            event=decision.event_type,
            text=self.state.partial_text,
            revision=self.state.revision_id,
            confidence=decision.confidence,
        )
        self._store_event(event)
        return event

    def publish_final(self, text: str) -> TranscriptEvent | None:
        """Finalize the transcript for the active turn."""
        decision = self.partial_result_manager.evaluate(text, finalizing=True)
        if not decision.text:
            return None

        final_text = self.state.finalize(decision.text)
        event = TranscriptEvent(
            event=TranscriptEventType.FINALIZED,
            text=final_text,
            revision=self.state.revision_id,
            confidence=decision.confidence,
        )
        self._store_event(event)
        return event

    def reset(self) -> None:
        """Clear turn-local state."""
        self.state.reset()
        self.partial_result_manager.reset()
        self.events.clear()

    def _store_event(self, event: TranscriptEvent) -> None:
        self.events.append(event)
        if self.on_event is not None:
            self.on_event(event)
        self._render_event(event)

    def _render_event(self, event: TranscriptEvent) -> None:
        prefix = {
            TranscriptEventType.PARTIAL_UPDATED: "[bold cyan][PARTIAL_UPDATED][/bold cyan]",
            TranscriptEventType.PARTIAL_CORRECTED: "[bold yellow][PARTIAL_CORRECTED][/bold yellow]",
            TranscriptEventType.FINALIZED: "[bold green][FINALIZED][/bold green]",
        }[event.event]
        self.console.print(f"{prefix} {event.text}")

    def dump_state(self) -> dict[str, object]:
        """Return a JSON-friendly view of the current transcript state."""
        return asdict(self.state)
