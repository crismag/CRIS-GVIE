"""Conversation orchestration helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from rich.console import Console

from ..events.conversation_events import RuntimeEvent, RuntimeEventType
from ..models import TurnEntry
from ..plugins.base import ConversationPlugin
from ..plugins.context import ConversationContext, ConversationTurn
from ..session import SessionStore
from .event_router import EventRouter
from .runtime_state import RuntimeState


class ConversationOrchestrator:
    """Coordinates plugin lifecycle, persistence, and runtime events."""

    def __init__(
        self,
        *,
        plugin: ConversationPlugin,
        plugin_name: str,
        context: ConversationContext,
        session_store: SessionStore,
        event_router: EventRouter | None = None,
        console: Console | None = None,
    ) -> None:
        self.plugin = plugin
        self.plugin_name = plugin_name
        self.context = context
        self.session_store = session_store
        self.event_router = event_router or EventRouter()
        self.console = console or Console()
        self.state = RuntimeState(
            session_id=context.session_id,
            active_plugin=plugin_name,
        )

    async def start_session(self) -> None:
        """Initialize plugin state and emit a session-started event."""
        self.context.metadata["active_plugin"] = self.plugin_name
        self.context.runtime_state["plugin"] = self.plugin_name
        await self.plugin.on_session_start(self.context)
        await self.emit(
            RuntimeEventType.SESSION_STARTED,
            payload={"plugin": self.plugin_name},
        )

    async def register_partial_transcript(
        self, text: str, revision: int, confidence: float
    ) -> None:
        """Emit a transcript-progress event."""
        await self.emit(
            RuntimeEventType.PARTIAL_TRANSCRIPT,
            payload={"text": text, "revision": revision, "confidence": confidence},
        )

    async def complete_turn(
        self,
        *,
        turn_id: int,
        text: str,
        started_at: str,
        ended_at: str,
        audio_file: str | None = None,
        partial_history: list[str] | None = None,
        revision_id: int | None = None,
    ) -> str:
        """Persist a user turn and generate the plugin response."""
        user_turn = ConversationTurn(
            turn_id=turn_id,
            speaker="user",
            text=text,
            timestamp=datetime.fromisoformat(ended_at),
            metadata={
                "audio_file": audio_file,
                "partial_history": partial_history or [],
                "revision_id": revision_id,
            },
        )
        self.context.transcript_history.append(user_turn)
        self.state.turns.append(user_turn)
        self.state.current_turn_id = turn_id
        await self.plugin.on_user_turn(user_turn, self.context)
        self.session_store.save_turn(
            turn_id=turn_id,
            speaker="user",
            plugin=self.plugin_name,
            text=text,
            audio_file=audio_file,
            started_at=started_at,
            ended_at=ended_at,
            partial_history=partial_history,
            revision_id=revision_id,
            metadata=user_turn.metadata,
        )
        await self.emit(
            RuntimeEventType.FINAL_TRANSCRIPT,
            turn_id=turn_id,
            payload={"text": text, "audio_file": audio_file},
        )
        await self.emit(
            RuntimeEventType.USER_TURN_COMPLETED,
            turn_id=turn_id,
            payload={"text": text},
        )

        response = (await self.plugin.generate_response(self.context)).strip()
        await self.plugin.on_response_generated(response, self.context)

        assistant_turn = ConversationTurn(
            turn_id=turn_id,
            speaker="assistant",
            text=response,
            timestamp=datetime.now(timezone.utc),
            metadata={"plugin": self.plugin_name},
        )
        self.context.transcript_history.append(assistant_turn)
        self.state.turns.append(assistant_turn)
        self.session_store.save_turn(
            turn_id=turn_id,
            speaker="assistant",
            plugin=self.plugin_name,
            text=response,
            started_at=ended_at,
            ended_at=datetime.now(timezone.utc).isoformat(),
            metadata=assistant_turn.metadata,
        )
        await self.emit(
            RuntimeEventType.RESPONSE_GENERATED,
            turn_id=turn_id,
            payload={"text": response},
        )
        return response

    async def mark_response_spoken(
        self, *, turn_id: int, response: str
    ) -> None:
        """Emit an event after TTS playback finishes."""
        await self.emit(
            RuntimeEventType.RESPONSE_SPOKEN,
            turn_id=turn_id,
            payload={"text": response},
        )

    async def end_session(self) -> None:
        """Finalize plugin state and emit a session-ended event."""
        await self.plugin.on_session_end(self.context)
        await self.emit(RuntimeEventType.SESSION_ENDED, payload={})

    async def emit(
        self,
        event_type: RuntimeEventType,
        *,
        turn_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> RuntimeEvent:
        """Create, route, persist, and retain a runtime event."""
        event = RuntimeEvent(
            event_type=event_type,
            session_id=self.context.session_id,
            turn_id=turn_id,
            plugin=self.plugin_name,
            payload=payload or {},
        )
        self.state.events.append(event)
        self.session_store.save_event(
            event_type=event_type.name,
            session_id=self.context.session_id,
            turn_id=turn_id,
            plugin=self.plugin_name,
            payload=payload or {},
        )
        await self.event_router.dispatch(event)
        self._log(event)
        return event

    def _log(self, event: RuntimeEvent) -> None:
        tag = f"[{event.event_type.name}]"
        self.console.print(f"[bold cyan]{tag}[/bold cyan]")
