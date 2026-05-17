"""Lightweight runtime event routing."""

from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from ..events.conversation_events import RuntimeEvent, RuntimeEventType

EventHandler = Callable[[RuntimeEvent], Any]


class EventRouter:
    """Dispatch runtime events to registered handlers."""

    def __init__(self) -> None:
        self._handlers: dict[RuntimeEventType | None, list[EventHandler]] = defaultdict(list)

    def subscribe(
        self,
        handler: EventHandler,
        event_type: RuntimeEventType | None = None,
    ) -> None:
        """Register a handler for all events or one event type."""
        self._handlers[event_type].append(handler)

    async def dispatch(self, event: RuntimeEvent) -> RuntimeEvent:
        """Send *event* to all matching handlers."""
        for handler in self._handlers.get(None, []):
            await self._maybe_await(handler(event))
        for handler in self._handlers.get(event.event_type, []):
            await self._maybe_await(handler(event))
        return event

    @staticmethod
    async def _maybe_await(result: Any) -> None:
        if inspect.isawaitable(result):
            await result  # pragma: no cover - exercised indirectly
