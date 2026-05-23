from __future__ import annotations

"""Session-state helpers for the Streamlit Web UI."""

import streamlit as st

from ai_core.service import LearningAIService


DEFAULT_COURSE_ID = "python_001"
DEFAULT_CHAPTER_TITLE = "Python编程从入门到实践"


@st.cache_resource
def get_cached_service() -> LearningAIService:
    """Return one cached LearningAIService for the Streamlit session."""

    service = LearningAIService()
    service.warm_up_async()
    return service


def init_session_state() -> None:
    """Initialize global UI state without overwriting user-generated data."""

    defaults = {
        "service": get_cached_service(),
        "current_course_id": DEFAULT_COURSE_ID,
        "current_chapter_title": DEFAULT_CHAPTER_TITLE,
        "last_ingest_result": None,
        "last_summary": None,
        "last_quiz": None,
        "last_report": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def current_course_id() -> str:
    """Return the active course id."""

    return st.session_state.get("current_course_id", DEFAULT_COURSE_ID)


def current_chapter_title() -> str:
    """Return the active chapter title."""

    return st.session_state.get("current_chapter_title", DEFAULT_CHAPTER_TITLE)
