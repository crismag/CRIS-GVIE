"""Adapter for a plain local chat workflow."""

from __future__ import annotations

from ..config import RuntimeConfig
from ..examples.simple_chat_plugin import SimpleChatPlugin
from ..plugins.registry import PluginRegistry
from ..runtime.workflow_runtime import WorkflowRuntime


def create_local_chat_runtime(
    config: RuntimeConfig | None = None,
) -> WorkflowRuntime:
    """Create a workflow runtime configured for simple chat."""
    config = config or RuntimeConfig(active_plugin=SimpleChatPlugin.name)
    registry = PluginRegistry()
    registry.register(SimpleChatPlugin.name, SimpleChatPlugin)
    return WorkflowRuntime(config=config, plugin_registry=registry)
