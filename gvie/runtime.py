"""Voice runtime orchestrator — VAD-driven automatic turn detection."""

import queue
import threading
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from .audio_events import TurnCompletedPayload
from .audio_stream import AudioStream
from .config import RuntimeConfig
from .llm import OllamaClient
from .session import SessionStore
from .silence_detector import SilenceDetector
from .stt import FasterWhisperSTT
from .tts import PiperTTS
from .turn_manager import TurnManager
from .vad import VoiceActivityDetector


class VoiceRuntime:
    """Coordinates automatic VAD-driven record → transcribe → respond → speak loop.

    Runtime flow::

        [LISTENING]
        → user speaks → [SPEECH_STARTED] → [RECORDING]
        → silence detected → [SILENCE_DETECTED] → [TURN_COMPLETED]
        → [TRANSCRIBING] → [GENERATING_RESPONSE] → [SPEAKING]
        → [LISTENING]
    """

    def __init__(self, config: RuntimeConfig | None = None) -> None:
        self.config = config or RuntimeConfig()
        self.console = Console()

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

        vad_cfg = self.config.vad
        self._vad = VoiceActivityDetector(
            threshold=vad_cfg.threshold,
            sample_rate=self.config.audio.sample_rate,
            chunk_size=vad_cfg.chunk_size,
        )
        self._silence_detector = SilenceDetector(
            silence_timeout=vad_cfg.silence_timeout,
            sample_rate=self.config.audio.sample_rate,
            chunk_size=vad_cfg.chunk_size,
        )

        # Queue used to hand completed turns from the audio thread to the
        # main processing loop (None is the sentinel to stop the loop).
        self._turn_queue: queue.Queue[TurnCompletedPayload | None] = queue.Queue()

        # Controls whether new turns are accepted (paused during TTS playback).
        self._paused = threading.Event()

    def run(self) -> None:
        """Start the VAD-driven voice loop.

        Listens continuously.  No key press required.
        Press **Ctrl-C** to exit.
        """
        self.session.start(
            {
                "ollama_model": self.config.ollama.model,
                "whisper_model": self.config.stt.model_size,
                "piper_model": self.config.piper.model_path,
            }
        )
        self.console.print("[bold green]CRIS-GVIE VAD runtime started.[/bold green]")
        self.console.print("Speak naturally.  Press [bold]Ctrl-C[/bold] to exit.\n")

        turn_manager = TurnManager(
            vad=self._vad,
            silence_detector=self._silence_detector,
            session_dir=self.session.session_dir,
            on_turn_completed=self._turn_queue.put,
            console=self.console,
            chunk_size=self.config.vad.chunk_size,
            max_recording_duration=self.config.vad.max_recording_duration,
        )

        audio_stream = AudioStream(
            sample_rate=self.config.audio.sample_rate,
            chunk_size=self.config.vad.chunk_size,
            channels=self.config.audio.channels,
            callback=turn_manager.process_chunk,
        )

        self.console.print("[bold cyan][LISTENING][/bold cyan]")
        audio_stream.start()

        try:
            while True:
                payload = self._turn_queue.get()
                if payload is None:
                    break
                self._process_turn(payload)
                self.console.print("[bold cyan][LISTENING][/bold cyan]")
        except KeyboardInterrupt:
            self.console.print("\nGoodbye.")
        finally:
            audio_stream.stop()

    # ------------------------------------------------------------------
    # Turn processing
    # ------------------------------------------------------------------

    def _process_turn(self, payload: TurnCompletedPayload) -> None:
        """Transcribe, generate response, speak — then resume listening."""
        wav_path: Path = payload.wav_path

        try:
            self.console.print("[bold blue][TRANSCRIBING][/bold blue]")
            user_text = self.stt.transcribe(wav_path)

            if not user_text:
                self.console.print("[yellow]No speech detected in turn.[/yellow]")
                return

            self.console.print(f"[cyan]You:[/cyan] {user_text}")
            ended_at = datetime.now(timezone.utc).isoformat()
            self.session.save_turn(
                turn_id=payload.turn_id,
                speaker="user",
                text=user_text,
                audio_file=str(wav_path.name),
                started_at=payload.started_at,
                ended_at=ended_at,
            )

            self.console.print("[bold blue][GENERATING_RESPONSE][/bold blue]")
            ai_text = self.llm.generate(user_text)
            self.console.print(f"[magenta]AI:[/magenta] {ai_text}")
            self.session.save_turn(
                turn_id=payload.turn_id,
                speaker="assistant",
                text=ai_text,
                started_at=ended_at,
            )

            self.console.print("[bold blue][SPEAKING][/bold blue]")
            self.tts.speak(ai_text)

        except Exception as exc:  # pragma: no cover - runtime safeguard
            self.console.print(f"[red]Runtime error:[/red] {exc}")
