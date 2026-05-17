"""Incremental local speech-to-text built on faster-whisper."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import numpy as np
from faster_whisper import WhisperModel

from .partial_result_manager import PartialDecision, PartialResultManager
from .transcript_events import TranscriptEventType


@dataclass(slots=True)
class StreamingTranscriptionResult:
    """A streaming STT update."""

    text: str
    revision: int
    event_type: TranscriptEventType
    confidence: float
    is_final: bool = False


class StreamingSTT:
    """Accumulates audio chunks and incrementally transcribes them."""

    def __init__(
        self,
        model_size: str = "small",
        compute_type: str = "int8",
        sample_rate: int = 16_000,
        chunk_size: int = 512,
        partial_update_interval_ms: int = 250,
        max_stream_buffer_seconds: float = 30.0,
    ) -> None:
        self.model = WhisperModel(model_size, compute_type=compute_type)
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.partial_update_interval_ms = partial_update_interval_ms
        self.max_stream_buffer_seconds = max_stream_buffer_seconds
        self.partial_manager = PartialResultManager()
        self._audio_chunks: list[np.ndarray] = []
        self._chunks_since_emit = 0
        self._revision = 0
        self._partial_update_interval_chunks = max(
            1,
            int(
                round(
                    (partial_update_interval_ms / 1000.0)
                    * sample_rate
                    / chunk_size
                )
            ),
        )
        self._max_buffer_chunks = max(
            1,
            int(round(max_stream_buffer_seconds * sample_rate / chunk_size)),
        )

    def reset(self) -> None:
        """Clear the current audio buffer and transcript state."""
        self._audio_chunks.clear()
        self._chunks_since_emit = 0
        self._revision = 0
        self.partial_manager.reset()

    def append_audio(self, audio_chunk: np.ndarray) -> None:
        """Append a new audio chunk to the rolling stream buffer."""
        chunk = np.asarray(audio_chunk, dtype=np.float32).reshape(-1)
        if chunk.size == 0:
            return

        self._audio_chunks.append(chunk.copy())
        if len(self._audio_chunks) > self._max_buffer_chunks:
            self._audio_chunks = self._audio_chunks[-self._max_buffer_chunks :]

        self._chunks_since_emit += 1

    async def process_chunk(
        self, audio_chunk: np.ndarray
    ) -> StreamingTranscriptionResult | None:
        """Process one audio chunk and emit a partial update when ready."""
        self.append_audio(audio_chunk)
        if self._chunks_since_emit < self._partial_update_interval_chunks:
            return None

        self._chunks_since_emit = 0
        candidate = await asyncio.to_thread(self._transcribe_current_buffer)
        if not candidate:
            return None

        decision = self.partial_manager.evaluate(candidate)
        return self._decision_to_result(decision) if decision.emit else None

    async def finalize(self) -> StreamingTranscriptionResult | None:
        """Force a final transcript update from the current audio buffer."""
        candidate = await asyncio.to_thread(self._transcribe_current_buffer)
        if not candidate:
            self.reset()
            return None

        decision = self.partial_manager.evaluate(candidate, finalizing=True)
        result = self._decision_to_result(decision, is_final=True)
        self.reset()
        return result

    def _transcribe_current_buffer(self) -> str:
        """Run faster-whisper over the accumulated buffer."""
        if not self._audio_chunks:
            return ""

        audio = np.concatenate(self._audio_chunks).astype(np.float32, copy=False)
        segments, _ = self.model.transcribe(audio, vad_filter=False)
        return " ".join(segment.text.strip() for segment in segments).strip()

    def _decision_to_result(
        self,
        decision: PartialDecision,
        *,
        is_final: bool = False,
    ) -> StreamingTranscriptionResult:
        """Convert a partial decision into a typed streaming result."""
        self._revision += 1
        return StreamingTranscriptionResult(
            text=decision.text,
            revision=self._revision,
            event_type=decision.event_type,
            confidence=decision.confidence,
            is_final=is_final or decision.event_type == TranscriptEventType.FINALIZED,
        )

