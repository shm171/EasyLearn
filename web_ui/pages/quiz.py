from __future__ import annotations

"""Quiz generation page."""

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from queue import Empty, Queue
from time import monotonic, sleep
from typing import TypeVar

import streamlit as st

from web_ui.state import current_chapter_title, current_course_id
from web_ui.ui_utils import DEBUG_DIR, render_list_or_json, safe_show_exception, save_json_utf8, show_json_download_button, to_jsonable


QUESTION_TYPE_OPTIONS = {
    "true_false": "判断题",
    "fill_blank": "填空题",
    "programming": "程序题",
    "short_answer": "简答题",
}
ProgressEvent = tuple[float, str]
T = TypeVar("T")


def _display_quiz(data: dict) -> None:
    questions = data.get("questions", [])
    if not questions:
        st.json(data, expanded=True)
        return

    for index, question in enumerate(questions, start=1):
        with st.container():
            st.markdown(f"### 题号 {index}: {question.get('question_id', '')}")
            st.write(f"题型：{question.get('question_type', '')}")
            st.write(question.get("stem", ""))
            if question.get("code_snippet"):
                st.code(question["code_snippet"], language=data.get("programming_language", "python"))
            if question.get("options"):
                st.write("选项")
                render_list_or_json(question["options"])
            if question.get("knowledge_points"):
                st.write("知识点")
                render_list_or_json(question["knowledge_points"])
            if question.get("reference_chunks"):
                st.write("来源 chunks")
                render_list_or_json(question["reference_chunks"])
            with st.expander("参考答案与解析"):
                st.write("参考答案")
                st.write(question.get("answer", ""))
                st.write("解析")
                st.write(question.get("explanation", ""))


def _run_with_progress(task: Callable[[Callable[[float, str], None]], T], fallback_seconds: float = 8.0) -> T:
    progress_events: Queue[ProgressEvent] = Queue()
    progress_bar = st.progress(0.0, text="准备生成题目")
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
                progress_bar.progress(current_value, text="模型正在生成题目")
            sleep(0.1)
        drain_events()
        try:
            result = future.result()
        except Exception:
            progress_bar.progress(1.0, text="生成失败")
            raise

    progress_bar.progress(1.0, text="题目生成完成")
    return result


def render() -> None:
    """Render the quiz generation page."""

    st.title("生成题目")

    course_id = st.text_input("course_id", value=current_course_id())
    chapter_title = st.text_input("chapter_title", value=current_chapter_title())
    programming_language = st.text_input("programming_language", value="python")
    difficulty = st.selectbox("difficulty", ["easy", "medium", "hard", "mixed"])
    selected_labels = st.multiselect(
        "question_types",
        options=list(QUESTION_TYPE_OPTIONS),
        default=["true_false", "fill_blank", "programming"],
        format_func=lambda key: f"{key}：{QUESTION_TYPE_OPTIONS[key]}",
    )
    question_count = st.number_input("question_count", min_value=1, max_value=50, value=5, step=1)

    if st.button("生成题目", type="primary"):
        if not selected_labels:
            st.warning("请至少选择一种题型。")
            return
        try:
            service = st.session_state.service

            def generate(report: Callable[[float, str], None]):
                return service.generate_programming_quiz(
                    course_id=course_id,
                    chapter_title=chapter_title,
                    programming_language=programming_language,
                    difficulty=difficulty,
                    question_types=selected_labels,
                    question_count=int(question_count),
                    progress_callback=report,
                )

            quiz = _run_with_progress(generate)
            data = to_jsonable(quiz)
            st.session_state.last_quiz = quiz
            st.session_state.current_course_id = course_id
            st.session_state.current_chapter_title = chapter_title
            save_json_utf8(DEBUG_DIR / "quiz_web.json", data)
            actual_count = len(data.get("questions", []))
            if actual_count != int(question_count):
                st.warning(f"请求题数：{int(question_count)}\n\n实际题数：{actual_count}")
            st.success("题目已生成。")
        except Exception as exc:  # pragma: no cover - depends on local vector/model env
            safe_show_exception(exc)

    if st.session_state.get("last_quiz") is not None:
        data = to_jsonable(st.session_state.last_quiz)
        _display_quiz(data)
        show_json_download_button("下载 quiz_web.json", data, "quiz_web.json")


if __name__ == "__main__":
    from web_ui.state import init_session_state

    init_session_state()
    render()
