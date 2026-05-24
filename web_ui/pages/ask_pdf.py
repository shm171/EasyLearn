from __future__ import annotations

"""PDF question-answering page."""

from collections.abc import Iterator

import streamlit as st

from ai_core.schemas import PDFQueryResult
from web_ui.state import current_chapter_title, current_course_id
from web_ui.ui_utils import render_list_or_json, safe_show_exception, to_jsonable


def _stream_with_progress(text_stream: Iterator[str], progress_bar) -> Iterator[str]:
    chunk_count = 0
    progress_bar.progress(0.60, text="模型正在生成回答")
    for text in text_stream:
        chunk_count += 1
        if chunk_count % 3 == 0:
            progress_bar.progress(min(0.95, 0.60 + chunk_count * 0.015), text="模型正在生成回答")
        yield text
    progress_bar.progress(1.0, text="回答完成")


def render() -> None:
    """Render the PDF QA page."""

    st.title("PDF 问答")
    st.info("如果检索不到内容，请先到“PDF 导入”页面导入学习资料。")

    course_id = st.text_input("course_id", value=current_course_id())
    chapter_title = st.text_input("chapter_title", value=current_chapter_title())
    question = st.text_area("question", value="Python 中变量的作用是什么？", height=120)

    if st.button("提问", type="primary"):
        if not question.strip():
            st.warning("请输入问题。")
            return
        try:
            progress_bar = st.progress(0.0, text="准备提问")

            def report(value: float, message: str) -> None:
                progress_bar.progress(min(max(value, 0.0), 1.0), text=message)

            streamed_answer = st.session_state.service.stream_pdf_answer(
                course_id=course_id,
                question=question.strip(),
                chapter_title=chapter_title,
                progress_callback=report,
            )

            st.subheader("AI 回答")
            answer_output = st.write_stream(_stream_with_progress(streamed_answer.text_stream, progress_bar))
            if isinstance(answer_output, str):
                answer = answer_output
            elif isinstance(answer_output, list):
                answer = "".join(str(part) for part in answer_output)
            else:
                answer = str(answer_output or "")

            result = PDFQueryResult(
                answer=answer or "资料中未找到明确依据",
                source_chunks=streamed_answer.source_chunks,
            )
            data = to_jsonable(result)
            st.session_state.last_ask_result = data
            st.session_state.current_course_id = course_id
            st.session_state.current_chapter_title = chapter_title

            source_chunks = data.get("source_chunks", []) if isinstance(data, dict) else []
            st.subheader("来源 chunks")
            if source_chunks:
                for index, chunk in enumerate(source_chunks, start=1):
                    title = f"来源 {index}"
                    if chunk.get("page_number") is not None:
                        title += f" · page_number: {chunk.get('page_number')}"
                    with st.expander(title):
                        st.write(chunk.get("content", ""))
                        st.json(chunk, expanded=False)
            else:
                st.warning("资料中未找到明确依据")
        except Exception as exc:  # pragma: no cover - depends on local vector/model env
            safe_show_exception(exc)

    last_result = st.session_state.get("last_ask_result")
    if last_result:
        render_list_or_json(last_result)


if __name__ == "__main__":
    from web_ui.state import init_session_state

    init_session_state()
    render()
