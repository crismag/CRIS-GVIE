"""Mutable runtime state."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..plugins.context import ConversationTurn


@dataclass(slots=True)
class RuntimeState:
    """Current runtime status and persisted turn history."""

    session_id: str = ""
    active_plugin: str = ""
    current_turn_id: int = 0
    listening: bool = False
    speaking: bool = False
    events: list[object] = field(default_factory=list)
    turns: list[ConversationTurn] = field(default_factory=list)
