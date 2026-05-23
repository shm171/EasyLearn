from __future__ import annotations

"""Chapter summary page."""

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


def _display_summary(data: dict) -> None:
    found = False
    for label, key in SUMMARY_SECTIONS:
        if key in data:
            found = True
            st.subheader(label)
            render_list_or_json(data.get(key))
    if not found:
        st.json(data, expanded=True)


def render() -> None:
    """Render the chapter summary page."""

    st.title("章节总结")

    course_id = st.text_input("course_id", value=current_course_id())
    chapter_title = st.text_input("chapter_title", value=current_chapter_title())

    if st.button("生成总结", type="primary"):
        try:
            with st.spinner("正在生成章节总结..."):
                summary = st.session_state.service.summarize_chapter(course_id=course_id, chapter_title=chapter_title)
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
