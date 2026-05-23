from __future__ import annotations

"""PDF ingestion page."""

import re
from pathlib import Path

import streamlit as st

from web_ui.state import current_chapter_title, current_course_id
from web_ui.ui_utils import DEBUG_DIR, MATERIALS_DIR, safe_show_exception, save_json_utf8, to_jsonable


def _safe_pdf_name(file_name: str) -> str:
    raw_name = Path(file_name).name
    safe_name = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", raw_name).strip("._")
    if not safe_name:
        safe_name = "uploaded.pdf"
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"
    return safe_name


def _display_ingest_result(result: dict) -> None:
    keys = {
        "course_id": result.get("course_id"),
        "file_path": result.get("file_path"),
        "chapter_title": result.get("chapter_title"),
        "pages / page_count": result.get("pages", result.get("page_count")),
        "chunks / chunk_count": result.get("chunks", result.get("chunk_count")),
        "status": result.get("status", result.get("message")),
    }
    if any(value is not None for value in keys.values()):
        st.table({"字段": list(keys), "值": list(keys.values())})
    else:
        st.json(result, expanded=True)


def render() -> None:
    """Render the PDF ingestion page."""

    st.title("PDF 导入")
    st.info("上传 PDF 后会保存到 materials/，再导入本地 Chroma 向量库。")

    course_id = st.text_input("course_id", value=current_course_id())
    chapter_title = st.text_input("chapter_title", value=current_chapter_title())
    uploaded_file = st.file_uploader("上传 PDF 文件", type=["pdf"])

    selected_path: Path | None = None
    if uploaded_file is not None:
        if not uploaded_file.name.lower().endswith(".pdf"):
            st.error("只允许上传 .pdf 文件。")
        else:
            MATERIALS_DIR.mkdir(parents=True, exist_ok=True)
            selected_path = MATERIALS_DIR / _safe_pdf_name(uploaded_file.name)
            if selected_path.exists():
                st.warning(f"同名文件已存在，将覆盖：{selected_path.name}")
            selected_path.write_bytes(uploaded_file.getbuffer())
            st.success(f"PDF 已保存：{selected_path}")

    existing_pdfs = sorted(MATERIALS_DIR.glob("*.pdf")) if MATERIALS_DIR.exists() else []
    if existing_pdfs:
        options = [""] + [str(path) for path in existing_pdfs]
        chosen = st.selectbox("或选择 materials/ 中已有 PDF", options)
        if chosen:
            selected_path = Path(chosen)

    if st.button("导入 PDF", type="primary"):
        if selected_path is None:
            st.error("请先上传或选择一个 PDF 文件。")
            return
        try:
            with st.spinner("正在读取 PDF 并生成本地向量，请稍等..."):
                result = st.session_state.service.ingest_pdf(
                    course_id=course_id,
                    file_path=str(selected_path),
                    chapter_title=chapter_title,
                )
            data = to_jsonable(result)
            st.session_state.last_ingest_result = result
            st.session_state.current_course_id = course_id
            st.session_state.current_chapter_title = chapter_title
            save_json_utf8(DEBUG_DIR / "ingest_web.json", data)
            st.success("PDF 导入成功。")
            _display_ingest_result(data)
        except Exception as exc:  # pragma: no cover - depends on local PDF/model env
            safe_show_exception(exc)

    if st.session_state.get("last_ingest_result") is not None:
        st.subheader("最近一次导入结果")
        _display_ingest_result(to_jsonable(st.session_state.last_ingest_result))


if __name__ == "__main__":
    from web_ui.state import init_session_state

    init_session_state()
    render()
