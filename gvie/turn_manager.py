"""Conversational turn state machine — speech start/stop and turn completion."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
from rich.console import Console

from .audio_events import AudioEventType, TurnCompletedPayload
from .silence_detector import SilenceDetector
from .stream_buffer import StreamBuffer
from .vad import VoiceActivityDetector


class TurnManager:
    """Orchestrates the LISTENING → RECORDING → TURN_COMPLETED state machine.

    Each audio chunk received via :meth:`process_chunk` is classified by the
    :class:`~gvie.vad.VoiceActivityDetector`.  When speech is detected the
    manager transitions to RECORDING state, accumulating chunks in a
    :class:`~gvie.stream_buffer.StreamBuffer`.  Once silence exceeds the
    configured timeout (or maximum recording duration is reached), the
    accumulated audio is written to a WAV file in *session_dir* and
    *on_turn_completed* is called with the resulting
    :class:`~gvie.audio_events.TurnCompletedPayload`.

    ``process_chunk`` is designed to be called directly from the sounddevice
    audio callback thread.  It does not block except for the WAV export at
    turn finalization, which is a short numpy/scipy operation.
    """

    def __init__(
        self,
        vad: VoiceActivityDetector,
        silence_detector: SilenceDetector,
        session_dir: Path,
        on_turn_completed: Callable[[TurnCompletedPayload], None],
        console: Console,
        chunk_size: int = 512,
        max_recording_duration: float = 60.0,
    ) -> None:
        self._vad = vad
        self._silence = silence_detector
        self._session_dir = session_dir
        self._on_turn_completed = on_turn_completed
        self._console = console
        self._chunk_size = chunk_size
        self._max_duration = max_recording_duration

        self._recording = False
        self._buffer = StreamBuffer(sample_rate=vad.sample_rate)
        self._turn_id = 0
        self._started_at: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_chunk(self, chunk: np.ndarray) -> None:
        """Classify *chunk* and advance the turn state machine.

        Called from the sounddevice audio thread on every captured frame.
        """
        is_speech = self._vad.is_speech(chunk)

        if not self._recording:
            if is_speech:
                self._start_recording(chunk)
        else:
            self._buffer.append(chunk)
            silence_timeout = self._silence.update(is_speech)
            max_reached = (
                self._buffer.duration_seconds(self._chunk_size) >= self._max_duration
            )
            if silence_timeout or max_reached:
                if silence_timeout:
                    self._emit(AudioEventType.SILENCE_DETECTED)
                self._finalize_turn()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _start_recording(self, first_chunk: np.ndarray) -> None:
        self._turn_id += 1
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._buffer.clear()
        self._silence.reset()
        self._buffer.append(first_chunk)
        self._recording = True
        self._emit(AudioEventType.SPEECH_STARTED)
        self._console.print("[bold yellow][SPEECH_STARTED][/bold yellow]")

    def _finalize_turn(self) -> None:
        self._recording = False
        self._emit(AudioEventType.SPEECH_ENDED)
        self._console.print("[bold yellow][SPEECH_ENDED][/bold yellow]")

        if self._buffer.is_empty():
            return

        wav_path = self._session_dir / f"turn_{self._turn_id:03d}.wav"
        try:
            self._buffer.export_wav(wav_path)
        except RuntimeError:
            return
        finally:
            self._buffer.clear()
            self._silence.reset()

        payload = TurnCompletedPayload(
            turn_id=self._turn_id,
            wav_path=wav_path,
            started_at=self._started_at,
        )
        self._emit(AudioEventType.TURN_COMPLETED)
        self._console.print("[bold green][TURN_COMPLETED][/bold green]")
        self._on_turn_completed(payload)

    def _emit(self, event_type: AudioEventType) -> None:  # noqa: ARG002
        # Placeholder for future event bus / plugin hooks.
        pass
