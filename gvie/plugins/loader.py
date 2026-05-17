"""Plugin loader helpers."""

from __future__ import annotations

from .base import BaseConversationPlugin
from .registry import PluginRegistry


def load_plugin(
    name: str,
    registry: PluginRegistry,
    **kwargs: object,
) -> BaseConversationPlugin:
    """Instantiate a plugin by name from *registry*."""
    return registry.create(name, **kwargs)
