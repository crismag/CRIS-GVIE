"""Async streaming runtime for low-latency transcript updates."""

from __future__ import annotations

import asyncio
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from .audio_stream import AudioStream
from .config import RuntimeConfig
from .llm import OllamaClient
from .session import SessionStore
from .silence_detector import SilenceDetector
from .stream_buffer import StreamBuffer
from .streaming_stt import StreamingSTT
from .transcript_stream import TranscriptStream
from .tts import PiperTTS
from .vad import VoiceActivityDetector


class StreamRuntime:
    """Coordinates VAD, streaming STT, transcript updates, and response flow."""

    def __init__(self, config: RuntimeConfig | None = None) -> None:
        self.config = config or RuntimeConfig()
        self.console = Console()
        self.session = SessionStore(base_dir=self.config.sessions.base_dir)

        self.stt = StreamingSTT(
            model_size=self.config.stt.model_size,
            compute_type=self.config.stt.compute_type,
            sample_rate=self.config.audio.sample_rate,
            chunk_size=self.config.vad.chunk_size,
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
        self._audio_queue: queue.Queue[tuple[object, float] | None] = queue.Queue()
        self._paused = threading.Event()
        self._recording = False
        self._turn_id = 0
        self._started_at: str = ""
        self._current_wav_path: Path | None = None
        self._audio_buffer = StreamBuffer(sample_rate=self.config.audio.sample_rate)
        self._transcript_stream = TranscriptStream(console=self.console)

    def run(self) -> None:
        """Run the streaming runtime until interrupted."""
        asyncio.run(self.arun())

    async def arun(self) -> None:
        """Async runtime loop."""
        self.session.start(
            {
                "ollama_model": self.config.ollama.model,
                "whisper_model": self.config.stt.model_size,
                "piper_model": self.config.piper.model_path,
            }
        )
        self.console.print(
            "[bold green]CRIS-GVIE streaming runtime started.[/bold green]"
        )
        self.console.print("Speak naturally. Press [bold]Ctrl-C[/bold] to exit.\n")
        self.console.print("[bold cyan][LISTENING][/bold cyan]")

        audio_stream = AudioStream(
            sample_rate=self.config.audio.sample_rate,
            chunk_size=self.config.vad.chunk_size,
            channels=self.config.audio.channels,
            callback=self._enqueue_audio,
        )
        audio_stream.start()

        try:
            while True:
                payload = await asyncio.to_thread(self._audio_queue.get)
                if payload is None:
                    break

                chunk, _ = payload
                await self._process_audio_chunk(chunk)
        except KeyboardInterrupt:
            self.console.print("\nGoodbye.")
        finally:
            audio_stream.stop()

    def _enqueue_audio(self, chunk) -> None:
        """Push an audio chunk from the callback thread into the async queue."""
        if self._paused.is_set():
            return
        self._audio_queue.put((chunk, datetime.now(timezone.utc).timestamp()))

    async def _process_audio_chunk(self, chunk) -> None:
        """Advance the streaming runtime state machine."""
        is_speech = self._vad.is_speech(chunk)

        if not self._recording:
            if is_speech:
                self._start_turn(chunk)
            return

        self._audio_buffer.append(chunk)
        result = await self.stt.process_chunk(chunk)
        if result is not None:
            self._transcript_stream.publish_partial(result.text)

        if self._silence_detector.update(is_speech):
            await self._finalize_turn()

    def _start_turn(self, first_chunk) -> None:
        """Start a new user turn."""
        self._turn_id += 1
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._recording = True
        self._current_wav_path = None
        self._audio_buffer.clear()
        self._audio_buffer.append(first_chunk)
        self._transcript_stream.reset()
        self.stt.reset()
        self.stt.append_audio(first_chunk)
        self._silence_detector.reset()
        self.console.print("[bold yellow][SPEECH_STARTED][/bold yellow]")

    async def _finalize_turn(self) -> None:
        """Finalize the current turn and generate a response."""
        if not self._recording:
            return

        self._recording = False
        final_result = await self.stt.finalize()
        final_text = (
            final_result.text
            if final_result is not None
            else self._transcript_stream.state.current_text
        )
        if self._transcript_stream.publish_final(final_text) is None and not final_text:
            self.console.print("[yellow]No speech detected in turn.[/yellow]")
            return

        self._current_wav_path = self._export_turn_audio()
        self._persist_user_turn(final_text)

        self.console.print("[bold blue][GENERATING_RESPONSE][/bold blue]")
        ai_text = await asyncio.to_thread(self.llm.generate, final_text)
        self.console.print(f"[magenta]AI:[/magenta] {ai_text}")
        self.session.save_turn(
            turn_id=self._turn_id,
            speaker="assistant",
            text=ai_text,
            started_at=self._started_at,
            ended_at=datetime.now(timezone.utc).isoformat(),
        )

        self.console.print("[bold blue][SPEAKING][/bold blue]")
        self._paused.set()
        try:
            await asyncio.to_thread(self.tts.speak, ai_text)
        finally:
            self._paused.clear()
            self.console.print("[bold cyan][LISTENING][/bold cyan]")

    def _export_turn_audio(self) -> Path | None:
        """Write the buffered turn audio to the session directory."""
        if self._audio_buffer.is_empty():
            return None

        path = self.session.session_dir / f"turn_{self._turn_id:03d}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._audio_buffer.export_wav(path)
        return path

    def _persist_user_turn(self, final_text: str) -> None:
        """Persist the finalized user turn to the session log."""
        self.session.save_turn(
            turn_id=self._turn_id,
            speaker="user",
            text=final_text,
            audio_file=self._current_wav_path.name if self._current_wav_path else None,
            started_at=self._started_at,
            ended_at=datetime.now(timezone.utc).isoformat(),
            partial_history=self._transcript_stream.state.partial_history,
            revision_id=self._transcript_stream.state.revision_id,
        )

VoiceRuntime = StreamRuntime
