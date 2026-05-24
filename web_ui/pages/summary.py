from __future__ import annotations

"""Chapter summary page."""

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from queue import Empty, Queue
from time import monotonic, sleep
from typing import TypeVar

import streamlit as st

from web_ui.state import current_chapter_title, current_course_id
from web_ui.ui_utils import DEBUG_DIR, render_list_or_json, safe_show_exception, save_json_utf8, show_json_download_button, to_jsonable


SUMMARY_SECTIONS = [
    ("学习目标", "learning_goals"),
    ("核心概念", "key_concepts"),
    ("重要术语", "important_terms"),
    ("代码例子", "code_examples"),
    ("典型题型", "typical_question_types"),
    ("常见错误", "common_mistakes"),
    ("学习建议", "study_suggestions"),
    ("来源", "source_chunks"),
]
ProgressEvent = tuple[float, str]
T = TypeVar("T")


def _display_summary(data: dict) -> None:
    found = False
    for label, key in SUMMARY_SECTIONS:
        if key in data:
            found = True
            st.subheader(label)
            render_list_or_json(data.get(key))
    if not found:
        st.json(data, expanded=True)


def _run_with_progress(task: Callable[[Callable[[float, str], None]], T], fallback_seconds: float = 8.0) -> T:
    progress_events: Queue[ProgressEvent] = Queue()
    progress_bar = st.progress(0.0, text="准备生成章节总结")
    started_at = monotonic()
    current_value = 0.0

    def report(value: float, message: str) -> None:
        progress_events.put((value, message))

    def drain_events() -> None:
        nonlocal current_value
        while True:
            try:
                value, message = progress_events.get_nowait()
            except Empty:
                break
            current_value = max(current_value, min(max(value, 0.0), 1.0))
            progress_bar.progress(current_value, text=message)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future: Future[T] = executor.submit(task, report)
        while not future.done():
            drain_events()
            elapsed = monotonic() - started_at
            target_value = min(0.88, 0.08 + (elapsed / fallback_seconds) * 0.72)
            if target_value > current_value + 0.015:
                current_value = target_value
                progress_bar.progress(current_value, text="模型正在生成章节总结")
            sleep(0.1)
        drain_events()
        try:
            result = future.result()
        except Exception:
            progress_bar.progress(1.0, text="生成失败")
            raise

    progress_bar.progress(1.0, text="章节总结完成")
    return result


def render() -> None:
    """Render the chapter summary page."""

    st.title("章节总结")

    course_id = st.text_input("course_id", value=current_course_id())
    chapter_title = st.text_input("chapter_title", value=current_chapter_title())

    if st.button("生成总结", type="primary"):
        try:
            service = st.session_state.service

            def summarize(report: Callable[[float, str], None]):
                return service.summarize_chapter(
                    course_id=course_id,
                    chapter_title=chapter_title,
                    progress_callback=report,
                )

            summary = _run_with_progress(summarize)
            data = to_jsonable(summary)
            st.session_state.last_summary = summary
            st.session_state.current_course_id = course_id
            st.session_state.current_chapter_title = chapter_title
            save_json_utf8(DEBUG_DIR / "summary_web.json", data)
            st.success("章节总结已生成。")
        except Exception as exc:  # pragma: no cover - depends on local vector/model env
            safe_show_exception(exc)

    if st.session_state.get("last_summary") is not None:
        data = to_jsonable(st.session_state.last_summary)
        _display_summary(data)
        show_json_download_button("下载 summary_web.json", data, "summary_web.json")


if __name__ == "__main__":
    from web_ui.state import init_session_state

    init_session_state()
    render()
