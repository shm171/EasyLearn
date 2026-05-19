from __future__ import annotations

"""Short-term memory helpers for learning agents."""

from typing import Any


def create_memory_checkpointer() -> Any | None:
    """Create an in-memory LangGraph checkpointer when available."""

    try:
        from langgraph.checkpoint.memory import InMemorySaver
    except ImportError:
        return None
    return InMemorySaver()


