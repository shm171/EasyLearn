from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from web_ui.pages import ask_pdf, evaluation, home, ingest_pdf, quiz, summary
from web_ui.state import init_session_state


PAGES = {
    "首页 / 状态检查": home.render,
    "PDF 导入": ingest_pdf.render,
    "PDF 问答": ask_pdf.render,
    "章节总结": summary.render,
    "生成题目": quiz.render,
    "答题与批改": evaluation.render,
}


def main() -> None:
    """Run the Streamlit app."""

    st.set_page_config(page_title="AI 编程学习助手", layout="wide")
    init_session_state()

    st.sidebar.title("AI 编程学习助手")
    selected_page = st.sidebar.radio("页面", list(PAGES), label_visibility="collapsed")
    st.sidebar.caption("本地 Streamlit Web 调试界面")

    PAGES[selected_page]()


if __name__ == "__main__":
    main()
