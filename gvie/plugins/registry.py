"""Lightweight plugin registration."""

from __future__ import annotations

from typing import TypeVar

from .base import BaseConversationPlugin

PluginT = TypeVar("PluginT", bound=BaseConversationPlugin)


class PluginRegistry:
    """Simple in-memory plugin registry."""

    def __init__(self) -> None:
        self._plugins: dict[str, type[BaseConversationPlugin]] = {}

    def register(
        self, name: str, plugin_cls: type[BaseConversationPlugin]
    ) -> type[BaseConversationPlugin]:
        """Register a plugin class under *name*."""
        self._plugins[name] = plugin_cls
        return plugin_cls

    def get(self, name: str) -> type[BaseConversationPlugin]:
        """Return a registered plugin class."""
        if name not in self._plugins:
            raise KeyError(f"Unknown plugin: {name}")
        return self._plugins[name]

    def create(self, name: str, **kwargs: object) -> BaseConversationPlugin:
        """Instantiate a registered plugin."""
        return self.get(name)(**kwargs)

    def names(self) -> list[str]:
        """Return registered plugin names."""
        return sorted(self._plugins)
