"""Local speech-to-text integration."""

from pathlib import Path

from faster_whisper import WhisperModel


class FasterWhisperSTT:
    """Wraps faster-whisper for local transcription."""

    def __init__(self, model_size: str = "small", compute_type: str = "int8") -> None:
        self.model = WhisperModel(model_size, compute_type=compute_type)

    def transcribe(self, wav_path: Path) -> str:
        """Transcribe WAV audio and return plain text."""
        segments, _ = self.model.transcribe(str(wav_path))
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return text
