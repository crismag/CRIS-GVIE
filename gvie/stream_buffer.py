"""Thread-safe rolling audio buffer with WAV export."""

import threading
from pathlib import Path

import numpy as np
from scipy.io import wavfile


class StreamBuffer:
    """Accumulates audio chunks from the microphone and exports them as WAV.

    All public methods are thread-safe.
    """

    def __init__(self, sample_rate: int = 16_000) -> None:
        self.sample_rate = sample_rate
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()

    def append(self, chunk: np.ndarray) -> None:
        """Append a float32 audio chunk to the buffer."""
        with self._lock:
            self._chunks.append(chunk.copy())

    def clear(self) -> None:
        """Discard all buffered audio."""
        with self._lock:
            self._chunks.clear()

    def is_empty(self) -> bool:
        """Return True when no audio has been buffered."""
        with self._lock:
            return len(self._chunks) == 0

    def duration_seconds(self, chunk_size: int) -> float:
        """Approximate recording duration based on chunk count."""
        with self._lock:
            return len(self._chunks) * chunk_size / self.sample_rate

    def export_wav(self, path: Path) -> Path:
        """Write buffered audio to *path* as a 16-bit mono WAV file.

        Raises ``RuntimeError`` when the buffer is empty.
        """
        with self._lock:
            if not self._chunks:
                raise RuntimeError("Cannot export empty audio buffer.")
            audio = np.concatenate(self._chunks).flatten()

        audio_clipped = np.clip(audio, -1.0, 1.0)
        audio_int16 = (audio_clipped * 32767).astype(np.int16)
        wavfile.write(str(path), self.sample_rate, audio_int16)
        return path
