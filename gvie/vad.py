"""Voice Activity Detection wrapper around silero-vad."""

import numpy as np


class VoiceActivityDetector:
    """Classifies audio chunks as speech or non-speech using silero-vad.

    The silero-vad model expects exactly *chunk_size* float32 samples at the
    configured *sample_rate*.  Supported sample rates: 8 000 Hz and 16 000 Hz.
    Supported chunk sizes at 16 kHz: 256 or 512 samples.

    Usage::

        vad = VoiceActivityDetector(threshold=0.5, sample_rate=16_000, chunk_size=512)
        if vad.is_speech(audio_chunk):
            ...
    """

    def __init__(
        self,
        threshold: float = 0.5,
        sample_rate: int = 16_000,
        chunk_size: int = 512,
    ) -> None:
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self._model = self._load_model()

    @staticmethod
    def _load_model():  # type: ignore[return]
        """Load silero-vad and return the model object."""
        try:
            from silero_vad import load_silero_vad  # type: ignore[import]

            return load_silero_vad()
        except ImportError as exc:
            raise ImportError(
                "silero-vad is required for VAD support. "
                "Install it with: pip install silero-vad"
            ) from exc

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """Return ``True`` when *audio_chunk* contains speech.

        *audio_chunk* must be a float32 numpy array of exactly *chunk_size*
        samples.  Multi-channel input is flattened to mono automatically.
        """
        import torch  # silero-vad installs torch as a dependency

        samples = audio_chunk.flatten().astype(np.float32)
        tensor = torch.from_numpy(samples)
        prob: float = self._model(tensor, self.sample_rate).item()
        return prob >= self.threshold
