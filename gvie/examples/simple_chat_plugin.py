"""Simple conversational plugin backed by Ollama."""

from __future__ import annotations

import asyncio

from ..llm import OllamaClient
from ..plugins.base import BaseConversationPlugin
from ..plugins.context import ConversationContext, ConversationTurn


class SimpleChatPlugin(BaseConversationPlugin):
    """Basic local chat plugin."""

    name = "simple_chat"

    def __init__(
        self,
        client: OllamaClient | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self.client = client
        self.model = model
        self.system_prompt = system_prompt or (
            "You are a concise, helpful local voice assistant."
        )

    async def on_session_start(self, context: ConversationContext) -> None:
        self.model = self.model or context.metadata.get("ollama_model")

    async def on_user_turn(
        self, turn: ConversationTurn, context: ConversationContext
    ) -> None:
        context.runtime_state["last_user_turn"] = turn.text

    async def generate_response(self, context: ConversationContext) -> str:
        prompt = self._build_prompt(context)
        if self.client is None:
            self.client = OllamaClient(
                base_url=context.metadata.get("ollama_base_url", "http://localhost:11434"),
                model=self.model or context.metadata.get("ollama_model", "qwen2.5:14b"),
            )
        return await asyncio.to_thread(self.client.generate, prompt)

    async def on_response_generated(
        self, response: str, context: ConversationContext
    ) -> None:
        context.runtime_state["last_response"] = response

    def _build_prompt(self, context: ConversationContext) -> str:
        history = context.transcript_history[-6:]
        lines = [self.system_prompt, ""]
        for turn in history:
            lines.append(f"{turn.speaker.capitalize()}: {turn.text}")
        lines.append("Assistant:")
        return "\n".join(lines).strip()
