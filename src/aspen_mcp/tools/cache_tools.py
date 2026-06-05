"""Cache and tool call log MCP tools."""
from __future__ import annotations
from .. import cache


def tool_get_call_log(limit: int = 20) -> list[dict]:
    """Show the most recent tool call history (up to 200 saved)."""
    return cache.get_call_log(limit)


def tool_clear_call_log() -> str:
    """Clear the tool call history log."""
    return cache.clear_call_log()


def tool_get_sensitivity_history() -> list[dict]:
    """Show all saved sensitivity analysis results."""
    return cache.get_sensitivity_history()


def tool_clear_sensitivity_cache() -> str:
    """Clear all cached sensitivity results."""
    return cache.clear_sensitivity()
