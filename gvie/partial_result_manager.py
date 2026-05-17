"""Heuristics for stabilizing streaming partial transcripts."""

from dataclasses import dataclass
from difflib import SequenceMatcher

from .incremental_decoder import merge_transcript_chunks, normalize_transcript
from .transcript_events import TranscriptEventType


@dataclass(slots=True)
class PartialDecision:
    """Outcome of evaluating a candidate transcript fragment."""

    emit: bool
    text: str
    event_type: TranscriptEventType
    confidence: float
    promote_to_final: bool = False


class PartialResultManager:
    """Tracks transcript stability and decides when to emit updates."""

    def __init__(
        self,
        partial_confidence_threshold: float = 0.45,
        final_confidence_threshold: float = 0.75,
        minimum_words: int = 1,
    ) -> None:
        self.partial_confidence_threshold = partial_confidence_threshold
        self.final_confidence_threshold = final_confidence_threshold
        self.minimum_words = minimum_words
        self._last_emitted_text = ""

    @property
    def last_emitted_text(self) -> str:
        """Return the latest text emitted by the manager."""
        return self._last_emitted_text

    def evaluate(
        self,
        candidate: str,
        *,
        finalizing: bool = False,
    ) -> PartialDecision:
        """Evaluate a transcript candidate and decide whether to emit it."""

        candidate = normalize_transcript(candidate)
        if not candidate:
            return PartialDecision(
                emit=False,
                text="",
                event_type=TranscriptEventType.PARTIAL_UPDATED,
                confidence=0.0,
            )

        merged = merge_transcript_chunks(self._last_emitted_text, candidate)
        if not finalizing and merged == self._last_emitted_text:
            return PartialDecision(
                emit=False,
                text=merged,
                event_type=TranscriptEventType.PARTIAL_UPDATED,
                confidence=self._confidence(merged),
            )

        similarity = (
            SequenceMatcher(None, self._last_emitted_text, merged).ratio()
            if self._last_emitted_text
            else 0.0
        )
        confidence = self._confidence(merged, similarity=similarity)
        event_type = (
            TranscriptEventType.FINALIZED
            if finalizing
            else (
                TranscriptEventType.PARTIAL_UPDATED
                if merged.startswith(self._last_emitted_text)
                else TranscriptEventType.PARTIAL_CORRECTED
            )
        )
        emit = finalizing or confidence >= self.partial_confidence_threshold
        if emit:
            self._last_emitted_text = merged

        return PartialDecision(
            emit=emit,
            text=merged,
            event_type=event_type,
            confidence=confidence,
            promote_to_final=finalizing or confidence >= self.final_confidence_threshold,
        )

    def reset(self) -> None:
        """Reset the manager for a new turn."""
        self._last_emitted_text = ""

    def _confidence(self, text: str, similarity: float = 0.0) -> float:
        """Estimate transcript confidence from textual stability."""
        word_score = min(len(text.split()) / max(self.minimum_words, 8), 1.0)
        stability_score = min(similarity, 1.0)
        return round(min(1.0, 0.35 + word_score * 0.4 + stability_score * 0.25), 3)

