"""Local Piper TTS and playback utilities."""

import subprocess
import tempfile
from pathlib import Path

import numpy as np
from scipy.io import wavfile


class PiperTTS:
    """Converts text to speech with Piper and plays it locally."""

    def __init__(self, model_path: str, config_path: str | None = None) -> None:
        self.model_path = model_path
        self.config_path = config_path

    def speak(self, text: str) -> None:
        """Synthesize and play text audio."""
        if not text.strip():
            return

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = Path(tmp.name)

        command = ["piper", "--model", self.model_path, "--output_file", str(wav_path)]
        if self.config_path:
            command.extend(["--config", self.config_path])

        try:
            subprocess.run(command, input=text, text=True, check=True)
            self._play_wav(wav_path)
        finally:
            wav_path.unlink(missing_ok=True)

    @staticmethod
    def _play_wav(wav_path: Path) -> None:
        """Play a WAV file through default output device."""
        import sounddevice as sd

        sample_rate, data = wavfile.read(wav_path)
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32767.0
        sd.play(data, sample_rate)
        sd.wait()
