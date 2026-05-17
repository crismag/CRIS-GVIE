"""Lightweight structured interviewer plugin."""

from __future__ import annotations

from ..plugins.base import BaseConversationPlugin
from ..plugins.context import ConversationContext, ConversationTurn


class InterviewerPlugin(BaseConversationPlugin):
    """Basic interview flow with stage-based follow-up questions."""

    name = "interviewer"

    def __init__(self) -> None:
        self._questions = [
            "What kind of scheduling system do you need?",
            "Who will use it, and what must it support?",
            "What integrations or constraints should I know about?",
            "Anything else I should capture before we wrap up?",
        ]

    async def on_session_start(self, context: ConversationContext) -> None:
        context.runtime_state["interview_stage"] = 0
        context.runtime_state["question_index"] = 0

    async def on_user_turn(
        self, turn: ConversationTurn, context: ConversationContext
    ) -> None:
        context.runtime_state["last_answer"] = turn.text

    async def generate_response(self, context: ConversationContext) -> str:
        index = int(context.runtime_state.get("question_index", 0))
        if index >= len(self._questions):
            return "Thanks, that gives me enough to work with."

        context.runtime_state["question_index"] = index + 1
        context.runtime_state["interview_stage"] = index + 1
        return self._questions[index]

    async def on_response_generated(
        self, response: str, context: ConversationContext
    ) -> None:
        context.runtime_state["last_question"] = response
