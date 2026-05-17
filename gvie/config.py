"""Runtime configuration models."""

from pathlib import Path

from pydantic import BaseModel, Field


class AudioConfig(BaseModel):
    """Microphone capture settings."""

    sample_rate: int = 16_000
    channels: int = 1


class VADConfig(BaseModel):
    """Voice Activity Detection settings."""

    threshold: float = 0.5
    """Speech probability threshold (0.0–1.0). Lower = more sensitive."""

    silence_timeout: float = 1.5
    """Seconds of consecutive silence required to finalize a turn."""

    chunk_size: int = 512
    """Audio frames per VAD evaluation (must be 256 or 512 at 16 kHz)."""

    max_recording_duration: float = 60.0
    """Hard upper limit on a single recording turn in seconds."""


class STTConfig(BaseModel):
    """Speech-to-text settings."""

    model_size: str = "small"
    compute_type: str = "int8"


class OllamaConfig(BaseModel):
    """Ollama API settings."""

    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:14b"
    timeout_seconds: int = 120


class PiperConfig(BaseModel):
    """Piper text-to-speech settings."""

    model_path: str = "en_US-lessac-medium.onnx"
    config_path: str | None = None


class SessionConfig(BaseModel):
    """Session storage settings."""

    base_dir: Path = Field(default_factory=lambda: Path("sessions"))


class RuntimeConfig(BaseModel):
    """Top-level runtime config."""

    audio: AudioConfig = Field(default_factory=AudioConfig)
    vad: VADConfig = Field(default_factory=VADConfig)
    stt: STTConfig = Field(default_factory=STTConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    piper: PiperConfig = Field(default_factory=PiperConfig)
    sessions: SessionConfig = Field(default_factory=SessionConfig)
