"""Core plugin-driven voice workflow runtime."""

from __future__ import annotations

import asyncio
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from rich.console import Console

from ..audio_stream import AudioStream
from ..config import RuntimeConfig
from ..events.conversation_events import RuntimeEventType
from ..plugins.context import ConversationContext
from ..plugins.loader import load_plugin
from ..plugins.registry import PluginRegistry
from ..session import SessionStore
from ..silence_detector import SilenceDetector
from ..stream_buffer import StreamBuffer
from ..streaming_stt import StreamingSTT
from ..transcript_stream import TranscriptStream
from ..tts import PiperTTS
from ..vad import VoiceActivityDetector
from .event_router import EventRouter
from .orchestrator import ConversationOrchestrator


class WorkflowRuntime:
    """Coordinates audio capture, transcript flow, plugins, and playback."""

    def __init__(
        self,
        config: RuntimeConfig | None = None,
        *,
        plugin_registry: PluginRegistry | None = None,
        plugin_name: str | None = None,
        stt: StreamingSTT | None = None,
        tts: PiperTTS | None = None,
        console: Console | None = None,
        audio_stream_factory: Callable[..., AudioStream] = AudioStream,
        vad: VoiceActivityDetector | None = None,
        silence_detector: SilenceDetector | None = None,
        session_store: SessionStore | None = None,
        event_router: EventRouter | None = None,
    ) -> None:
        self.config = config or RuntimeConfig()
        self.console = console or Console()
        self.session = session_store or SessionStore(
            base_dir=self.config.session_storage_path
        )
        self.plugin_registry = plugin_registry or PluginRegistry()
        self.plugin_name = plugin_name or self.config.active_plugin
        self.audio_stream_factory = audio_stream_factory
        self._audio_queue: queue.Queue[tuple[object, float] | None] = queue.Queue()
        self._paused = threading.Event()
        self._recording = False
        self._turn_id = 0
        self._started_at: str = ""
        self._current_wav_path: Path | None = None
        self._audio_buffer = StreamBuffer(sample_rate=self.config.audio.sample_rate)
        self._transcript_stream = TranscriptStream(
            console=self.console, on_event=self._on_transcript_event
        )
        self._event_router = event_router or EventRouter()

        self._vad = vad or VoiceActivityDetector(
            threshold=self.config.vad.threshold,
            sample_rate=self.config.audio.sample_rate,
            chunk_size=self.config.vad.chunk_size,
        )
        self._silence_detector = silence_detector or SilenceDetector(
            silence_timeout=self.config.vad.silence_timeout,
            sample_rate=self.config.audio.sample_rate,
            chunk_size=self.config.vad.chunk_size,
        )
        self.stt = stt or StreamingSTT(
            model_size=self.config.stt.model_size,
            compute_type=self.config.stt.compute_type,
            sample_rate=self.config.audio.sample_rate,
            chunk_size=self.config.vad.chunk_size,
        )
        self.tts = tts or (
            PiperTTS(
                model_path=self.config.piper.model_path,
                config_path=self.config.piper.config_path,
            )
            if self.config.enable_tts
            else None
        )
        self.context = ConversationContext(session_id=self.session.session_id)
        self.plugin = load_plugin(self.plugin_name, self.plugin_registry)
        self.orchestrator = ConversationOrchestrator(
            plugin=self.plugin,
            plugin_name=self.plugin_name,
            context=self.context,
            session_store=self.session,
            event_router=self._event_router,
            console=self.console,
        )
        self._event_router.subscribe(self._record_event)

    def run(self) -> None:
        """Run the workflow runtime until interrupted."""
        asyncio.run(self.arun())

    async def arun(self) -> None:
        """Async runtime loop."""
        self.session.start(
            {
                "active_plugin": self.plugin_name,
                "default_ollama_model": self.config.default_ollama_model,
                "ollama_model": self.config.ollama.model,
                "whisper_model": self.config.stt.model_size,
                "piper_model": self.config.piper.model_path,
            }
        )
        self.context.session_id = self.session.session_id
        self.context.metadata.update(
            {
                "active_plugin": self.plugin_name,
                "default_ollama_model": self.config.default_ollama_model,
                "ollama_model": self.config.ollama.model,
                "session_dir": str(self.session.session_dir),
            }
        )
        await self.orchestrator.start_session()
        self.console.print(
            f"[bold green]CRIS-GVIE runtime started with plugin: {self.plugin_name}[/bold green]"
        )
        self.console.print("Speak naturally. Press [bold]Ctrl-C[/bold] to exit.\n")
        self.console.print(f"[bold magenta][PLUGIN: {self.plugin_name}][/bold magenta]")
        self.console.print("[bold cyan][LISTENING][/bold cyan]")

        audio_stream = self.audio_stream_factory(
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
            await self.orchestrator.end_session()

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
                await self._start_turn(chunk)
            return

        self._audio_buffer.append(chunk)
        if self.config.enable_streaming_transcript:
            result = await self.stt.process_chunk(chunk)
            if result is not None:
                self._transcript_stream.publish_partial(result.text)
                await self.orchestrator.register_partial_transcript(
                    result.text, result.revision, result.confidence
                )

        if self._silence_detector.update(is_speech):
            await self._finalize_turn()

    async def _start_turn(self, first_chunk) -> None:
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
        await self.orchestrator.emit(
            RuntimeEventType.SPEECH_STARTED,
            turn_id=self._turn_id,
            payload={"started_at": self._started_at},
        )

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
        assistant_text = await self.orchestrator.complete_turn(
            turn_id=self._turn_id,
            text=final_text,
            started_at=self._started_at,
            ended_at=datetime.now(timezone.utc).isoformat(),
            audio_file=self._current_wav_path.name if self._current_wav_path else None,
            partial_history=self._transcript_stream.state.partial_history,
            revision_id=self._transcript_stream.state.revision_id,
        )

        if not assistant_text:
            self.console.print("[yellow]Plugin returned no response.[/yellow]")
            return

        self.console.print(f"[magenta]ASSISTANT:[/magenta] {assistant_text}")
        if self.tts is None:
            await self.orchestrator.mark_response_spoken(
                turn_id=self._turn_id, response=assistant_text
            )
            self.console.print("[bold cyan][LISTENING][/bold cyan]")
            return

        self.console.print("[bold blue][SPEAKING][/bold blue]")
        self._paused.set()
        try:
            await asyncio.to_thread(self.tts.speak, assistant_text)
        finally:
            self._paused.clear()
            await self.orchestrator.mark_response_spoken(
                turn_id=self._turn_id, response=assistant_text
            )
            self.console.print("[bold cyan][LISTENING][/bold cyan]")

    def _export_turn_audio(self) -> Path | None:
        """Write the buffered turn audio to the session directory."""
        if self._audio_buffer.is_empty():
            return None

        path = self.session.session_dir / f"turn_{self._turn_id:03d}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._audio_buffer.export_wav(path)
        return path

    def _record_event(self, event) -> None:
        """Keep a local copy of routed runtime events."""
        self.context.runtime_state["last_event"] = event.event_type.name

    def _on_transcript_event(self, event) -> None:
        """Bridge transcript events into runtime state."""
        self.context.runtime_state["transcript_revision"] = event.revision


VoiceRuntime = WorkflowRuntime
