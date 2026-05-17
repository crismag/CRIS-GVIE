"""Plugin architecture primitives."""

from .base import BaseConversationPlugin, ConversationPlugin
from .context import ConversationContext, ConversationTurn
from .loader import load_plugin
from .registry import PluginRegistry

__all__ = [
    "BaseConversationPlugin",
    "ConversationContext",
    "ConversationPlugin",
    "ConversationTurn",
    "PluginRegistry",
    "load_plugin",
]
