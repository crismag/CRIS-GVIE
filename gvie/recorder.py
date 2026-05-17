"""Audio recording utilities."""

from pathlib import Path

import numpy as np
from scipy.io import wavfile


class AudioRecorder:
    """Records microphone audio into a WAV file."""

    def __init__(self, sample_rate: int = 16_000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels

    def record_until_enter(self, output_wav: Path) -> Path:
        """Record audio until Enter is pressed and write to output_wav."""
        import sounddevice as sd

        print("Recording... press Enter to stop.")
        chunks: list[np.ndarray] = []

        def callback(indata: np.ndarray, frames: int, time: object, status: object) -> None:
            if status:
                print(f"Audio warning: {status}")
            chunks.append(indata.copy())

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=callback,
        ):
            input()

        if not chunks:
            raise RuntimeError("No audio captured from microphone.")

        audio = np.concatenate(chunks, axis=0)
        audio_int16 = np.clip(audio, -1.0, 1.0)
        wavfile.write(output_wav, self.sample_rate, (audio_int16 * 32767).astype(np.int16))
        return output_wav
