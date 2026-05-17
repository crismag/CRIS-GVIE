"""Adapter for the structured interviewer workflow."""

from __future__ import annotations

from ..config import RuntimeConfig
from ..examples.interviewer_plugin import InterviewerPlugin
from ..plugins.registry import PluginRegistry
from ..runtime.workflow_runtime import WorkflowRuntime


def create_interviewer_runtime(
    config: RuntimeConfig | None = None,
) -> WorkflowRuntime:
    """Create a workflow runtime configured for the interviewer plugin."""
    config = config or RuntimeConfig(active_plugin=InterviewerPlugin.name)
    registry = PluginRegistry()
    registry.register(InterviewerPlugin.name, InterviewerPlugin)
    return WorkflowRuntime(config=config, plugin_registry=registry)
