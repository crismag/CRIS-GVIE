"""Voice runtime orchestrator."""

import tempfile
from pathlib import Path

from rich.console import Console

from .config import RuntimeConfig
from .llm import OllamaClient
from .recorder import AudioRecorder
from .session import SessionStore
from .stt import FasterWhisperSTT
from .tts import PiperTTS


class VoiceRuntime:
    """Coordinates record -> transcribe -> respond -> speak loop."""

    def __init__(self, config: RuntimeConfig | None = None) -> None:
        self.config = config or RuntimeConfig()
        self.console = Console()
        self.recorder = AudioRecorder(
            sample_rate=self.config.audio.sample_rate,
            channels=self.config.audio.channels,
        )
        self.stt = FasterWhisperSTT(
            model_size=self.config.stt.model_size,
            compute_type=self.config.stt.compute_type,
        )
        self.llm = OllamaClient(
            base_url=self.config.ollama.base_url,
            model=self.config.ollama.model,
            timeout_seconds=self.config.ollama.timeout_seconds,
        )
        self.tts = PiperTTS(
            model_path=self.config.piper.model_path,
            config_path=self.config.piper.config_path,
        )
        self.session = SessionStore(base_dir=self.config.sessions.base_dir)

    def run(self) -> None:
        """Run interactive local voice loop."""
        self.session.start(
            {
                "ollama_model": self.config.ollama.model,
                "whisper_model": self.config.stt.model_size,
                "piper_model": self.config.piper.model_path,
            }
        )
        self.console.print("[bold green]CRIS-GVIE runtime started.[/bold green]")

        while True:
            action = input("Press Enter to start recording (or type 'q' to quit): ").strip().lower()
            if action in {"q", "quit", "exit"}:
                self.console.print("Goodbye.")
                break

            input_wav: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    input_wav = Path(tmp.name)

                self.recorder.record_until_enter(input_wav)
                user_text = self.stt.transcribe(input_wav)

                if not user_text:
                    self.console.print("[yellow]No speech detected. Try again.[/yellow]")
                    continue

                self.console.print(f"[cyan]You:[/cyan] {user_text}")
                self.session.append("user", user_text)

                ai_text = self.llm.generate(user_text)
                self.console.print(f"[magenta]AI:[/magenta] {ai_text}")
                self.session.append("assistant", ai_text)

                self.tts.speak(ai_text)
            except KeyboardInterrupt:
                self.console.print("\nInterrupted.")
                break
            except Exception as exc:  # pragma: no cover - runtime safeguard
                self.console.print(f"[red]Runtime error:[/red] {exc}")
            finally:
                if input_wav is not None:
                    input_wav.unlink(missing_ok=True)
