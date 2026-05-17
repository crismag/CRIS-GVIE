"""Core plugin contract."""

from __future__ import annotations

from typing import Protocol

from .context import ConversationContext, ConversationTurn


class ConversationPlugin(Protocol):
    """Minimal conversational plugin contract."""

    name: str

    async def on_session_start(self, context: ConversationContext) -> None: ...

    async def on_user_turn(
        self, turn: ConversationTurn, context: ConversationContext
    ) -> None: ...

    async def generate_response(self, context: ConversationContext) -> str: ...

    async def on_response_generated(
        self, response: str, context: ConversationContext
    ) -> None: ...

    async def on_session_end(self, context: ConversationContext) -> None: ...


class BaseConversationPlugin:
    """Convenience base class with no-op hook implementations."""

    name = "base"

    async def on_session_start(self, context: ConversationContext) -> None:
        return None

    async def on_user_turn(
        self, turn: ConversationTurn, context: ConversationContext
    ) -> None:
        return None

    async def generate_response(self, context: ConversationContext) -> str:
        return ""

    async def on_response_generated(
        self, response: str, context: ConversationContext
    ) -> None:
        return None

    async def on_session_end(self, context: ConversationContext) -> None:
        return None
