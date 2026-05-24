from __future__ import annotations

"""Shared FastAPI dependencies."""

from functools import lru_cache

from ai_core.service import LearningAIService


@lru_cache(maxsize=1)
def get_learning_service() -> LearningAIService:
    """Return a process-wide service instance."""

    return LearningAIService()
