"""Continuous non-blocking microphone capture using sounddevice."""

from __future__ import annotations

from typing import Callable

import numpy as np


class AudioStream:
    """Streams microphone audio in fixed-size chunks via a callback.

    The *callback* is invoked from sounddevice's internal audio thread with
    each captured chunk as a ``float32`` numpy array of shape
    ``(chunk_size, channels)``.  Keep the callback lightweight — offload heavy
    work to another thread.

    Example::

        def on_chunk(chunk: np.ndarray) -> None:
            process(chunk)

        stream = AudioStream(sample_rate=16_000, chunk_size=512, callback=on_chunk)
        stream.start()
        # ... run until done ...
        stream.stop()
    """

    def __init__(
        self,
        sample_rate: int = 16_000,
        chunk_size: int = 512,
        channels: int = 1,
        callback: Callable[[np.ndarray], None] | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self._callback = callback
        self._stream = None  # type: ignore[assignment]
        self._active = False

    def start(self) -> None:
        """Open the input stream and begin capturing audio."""
        import sounddevice as sd  # local import keeps the module importable without audio hardware

        self._active = True
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            blocksize=self.chunk_size,
            callback=self._on_audio,
        )
        self._stream.start()

    def stop(self) -> None:
        """Stop capturing and release the audio device."""
        self._active = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def _on_audio(
        self,
        indata: np.ndarray,
        frames: int,  # noqa: ARG002
        time: object,  # noqa: ARG002
        status: object,
    ) -> None:
        if status:
            pass  # Audio xruns are non-fatal; silently continue.
        if self._active and self._callback is not None:
            self._callback(indata.copy())
