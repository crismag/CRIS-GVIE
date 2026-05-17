"""Tests for the plugin-driven runtime framework."""

from __future__ import annotations

import asyncio
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import numpy as np

if "faster_whisper" not in sys.modules:
    stub = types.ModuleType("faster_whisper")

    class _WhisperModel:  # pragma: no cover - import stub only
        def __init__(self, *args, **kwargs):
            raise RuntimeError("WhisperModel should not be constructed in tests")

    stub.WhisperModel = _WhisperModel
    sys.modules["faster_whisper"] = stub

from gvie.config import RuntimeConfig
from gvie.events.conversation_events import RuntimeEvent, RuntimeEventType
from gvie.plugins.base import BaseConversationPlugin
from gvie.plugins.context import ConversationContext, ConversationTurn
from gvie.plugins.loader import load_plugin
from gvie.plugins.registry import PluginRegistry
from gvie.runtime.event_router import EventRouter
from gvie.runtime.orchestrator import ConversationOrchestrator
from gvie.runtime.workflow_runtime import WorkflowRuntime
from gvie.session import SessionStore


class EchoPlugin(BaseConversationPlugin):
    """Plugin used to exercise runtime orchestration."""

    name = "echo"

    def __init__(self) -> None:
        self.started = False
        self.user_turns: list[str] = []

    async def on_session_start(self, context: ConversationContext) -> None:
        self.started = True
        context.runtime_state["started"] = True

    async def on_user_turn(
        self, turn: ConversationTurn, context: ConversationContext
    ) -> None:
        self.user_turns.append(turn.text)
        context.runtime_state["last_user"] = turn.text

    async def generate_response(self, context: ConversationContext) -> str:
        return f"echo: {context.runtime_state['last_user']}"

    async def on_response_generated(
        self, response: str, context: ConversationContext
    ) -> None:
        context.runtime_state["last_response"] = response


class FakeVAD:
    def is_speech(self, chunk: object) -> bool:  # noqa: ARG002
        return True


class FakeSilenceDetector:
    def __init__(self) -> None:
        self.calls = 0

    def update(self, is_speech: bool) -> bool:  # noqa: ARG002
        self.calls += 1
        return self.calls >= 1

    def reset(self) -> None:
        self.calls = 0


class FakeSTT:
    def __init__(self) -> None:
        self.reset_calls = 0
        self.appended: list[object] = []
        self.processed: list[object] = []

    def reset(self) -> None:
        self.reset_calls += 1
        self.appended.clear()
        self.processed.clear()

    def append_audio(self, chunk: object) -> None:
        self.appended.append(chunk)

    async def process_chunk(self, chunk: object) -> SimpleNamespace:
        self.processed.append(chunk)
        return SimpleNamespace(text="hello world", revision=1, confidence=0.9)

    async def finalize(self) -> SimpleNamespace:
        return SimpleNamespace(text="hello world", revision=2, confidence=1.0)


class FakeTTS:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)


class EventRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatches_sync_and_async_handlers(self) -> None:
        router = EventRouter()
        events: list[str] = []

        def sync_handler(event: RuntimeEvent) -> None:
            events.append(f"sync:{event.event_type.name}")

        async def async_handler(event: RuntimeEvent) -> None:
            events.append(f"async:{event.event_type.name}")

        router.subscribe(sync_handler)
        router.subscribe(async_handler, RuntimeEventType.RESPONSE_GENERATED)

        await router.dispatch(
            RuntimeEvent(event_type=RuntimeEventType.RESPONSE_GENERATED, session_id="s1")
        )

        self.assertEqual(events, ["sync:RESPONSE_GENERATED", "async:RESPONSE_GENERATED"])


class RegistryTests(unittest.TestCase):
    def test_register_and_load_plugin(self) -> None:
        registry = PluginRegistry()
        registry.register(EchoPlugin.name, EchoPlugin)

        plugin = load_plugin(EchoPlugin.name, registry)

        self.assertIsInstance(plugin, EchoPlugin)


class PersistenceTests(unittest.TestCase):
    def test_session_store_persists_turns_and_events(self) -> None:
        with TemporaryDirectory() as tmp:
            store = SessionStore(base_dir=Path(tmp))
            store.start({"active_plugin": "echo"})
            store.save_turn(
                turn_id=1,
                speaker="user",
                plugin="echo",
                text="hello",
                audio_file="turn_001.wav",
                started_at="2026-01-01T00:00:00+00:00",
                ended_at="2026-01-01T00:00:01+00:00",
                partial_history=["he", "hello"],
            )
            store.save_event(
                event_type="SESSION_STARTED",
                session_id=store.session_id,
                plugin="echo",
                payload={"plugin": "echo"},
            )

            transcript = store.transcript_path.read_text(encoding="utf-8")
            events = store.events_path.read_text(encoding="utf-8")

            self.assertIn('"plugin":"echo"', transcript)
            self.assertIn('"speaker":"user"', transcript)
            self.assertIn('"event_type":"SESSION_STARTED"', events)


class OrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_turn_records_history_and_response(self) -> None:
        with TemporaryDirectory() as tmp:
            store = SessionStore(base_dir=Path(tmp))
            store.start({"active_plugin": "echo"})
            context = ConversationContext(session_id=store.session_id)
            router = EventRouter()
            plugin = EchoPlugin()
            orchestrator = ConversationOrchestrator(
                plugin=plugin,
                plugin_name=plugin.name,
                context=context,
                session_store=store,
                event_router=router,
            )

            await orchestrator.start_session()
            response = await orchestrator.complete_turn(
                turn_id=1,
                text="hello",
                started_at="2026-01-01T00:00:00+00:00",
                ended_at="2026-01-01T00:00:01+00:00",
                audio_file="turn_001.wav",
                partial_history=["hello"],
                revision_id=2,
            )
            await orchestrator.end_session()

            self.assertEqual(response, "echo: hello")
            self.assertEqual(len(context.transcript_history), 2)
            self.assertEqual(plugin.user_turns, ["hello"])
            transcript = store.transcript_path.read_text(encoding="utf-8")
            self.assertIn('"speaker":"assistant"', transcript)
            events = store.events_path.read_text(encoding="utf-8")
            self.assertIn('"event_type":"RESPONSE_GENERATED"', events)
            self.assertIn('"event_type":"SESSION_ENDED"', events)


class WorkflowRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_runtime_processes_audio_turns_with_plugin(self) -> None:
        with TemporaryDirectory() as tmp:
            config = RuntimeConfig(
                active_plugin="echo",
                enable_streaming_transcript=False,
                enable_tts=True,
                session_storage_path=Path(tmp),
            )
            registry = PluginRegistry()
            registry.register(EchoPlugin.name, EchoPlugin)
            fake_stt = FakeSTT()
            fake_tts = FakeTTS()
            fake_vad = FakeVAD()
            fake_silence = FakeSilenceDetector()
            runtime = WorkflowRuntime(
                config=config,
                plugin_registry=registry,
                stt=fake_stt,
                tts=fake_tts,
                vad=fake_vad,
                silence_detector=fake_silence,
            )
            runtime.session.start({"active_plugin": "echo"})
            runtime.context.session_id = runtime.session.session_id
            await runtime.orchestrator.start_session()

            chunk = np.zeros((config.vad.chunk_size, 1), dtype=np.float32)
            await runtime._process_audio_chunk(chunk)
            await runtime._process_audio_chunk(chunk)

            self.assertIn("echo: hello world", fake_tts.spoken)
            transcript = runtime.session.transcript_path.read_text(encoding="utf-8")
            self.assertIn('"speaker":"assistant"', transcript)
            self.assertIn('"speaker":"user"', transcript)
            events = runtime.session.events_path.read_text(encoding="utf-8")
            self.assertIn('"event_type":"SPEECH_STARTED"', events)
            self.assertIn('"event_type":"RESPONSE_SPOKEN"', events)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
