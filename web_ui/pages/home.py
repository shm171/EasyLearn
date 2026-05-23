from __future__ import annotations

"""Home and environment status page."""

from typing import Any

import pandas as pd
import streamlit as st

from ai_core.config import get_settings
from ai_core.model_factory import get_chat_model, get_embedding_model
from web_ui.ui_utils import safe_show_exception


def _content_from_model_response(response: Any) -> str:
    content = getattr(response, "content", None)
    if content:
        return str(content)
    return str(response)


def render() -> None:
    """Render the home/status page."""

    st.title("AI 编程学习助手")
    st.info("当前阶段：第二阶段，本地 Streamlit Web 调试界面")
    st.write("当前能力：PDF 导入、PDF 问答、章节总结、生成题目、批改评估")
    st.warning("当前限制：只支持普通文本型 PDF，不支持扫描版 PDF，不支持数学可视化，不支持代码图形化调试器")

    settings = get_settings()
    rows = [
        ("AI_PROVIDER", settings.ai_provider),
        ("EMBEDDING_PROVIDER", settings.embedding_provider),
        ("DEEPSEEK_MODEL", settings.deepseek_model),
        ("HUGGINGFACE_EMBEDDING_MODEL", settings.huggingface_embedding_model),
        ("VECTOR_DB_DIR", settings.vector_db_dir),
        ("DEEPSEEK_API_KEY 是否已配置", "已配置" if settings.deepseek_api_key else "未配置"),
    ]
    st.subheader("当前配置")
    st.dataframe(pd.DataFrame(rows, columns=["配置项", "值"]), use_container_width=True, hide_index=True)

    service = st.session_state.get("service")
    if service is not None:
        warm_up_status = service.warm_up_status
        st.subheader("资源预热")
        st.json(warm_up_status, expanded=False)
        if st.button("立即预热检索和模型", use_container_width=True):
            with st.spinner("正在预热检索向量库和聊天模型..."):
                st.json(service.warm_up(), expanded=False)

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("检查环境", use_container_width=True):
            try:
                if settings.ai_provider.lower() == "deepseek" and not settings.deepseek_api_key:
                    st.warning("DEEPSEEK_API_KEY 未配置。")
                else:
                    st.success("环境配置读取成功。")
                st.json(
                    {
                        "ai_provider": settings.ai_provider,
                        "embedding_provider": settings.embedding_provider,
                        "vector_db_dir": settings.vector_db_dir,
                    },
                    expanded=False,
                )
            except Exception as exc:  # pragma: no cover - UI safety net
                safe_show_exception(exc)

    with col2:
        if st.button("测试 DeepSeek 模型", use_container_width=True):
            try:
                with st.spinner("正在测试 DeepSeek 模型..."):
                    model = get_chat_model("deepseek")
                    response = model.invoke("请只回复 OK。")
                st.success("DeepSeek 模型调用成功。")
                st.write(_content_from_model_response(response))
            except Exception as exc:  # pragma: no cover - depends on local env/API
                safe_show_exception(exc)

    with col3:
        if st.button("测试 HuggingFace embedding", use_container_width=True):
            try:
                with st.spinner("正在加载 HuggingFace embedding 并生成测试向量..."):
                    embedding_model = get_embedding_model("huggingface")
                    vector = embedding_model.embed_query("Python 变量")
                st.success(f"HuggingFace embedding 测试成功，向量维度：{len(vector)}")
            except Exception as exc:  # pragma: no cover - depends on local models
                safe_show_exception(exc)


if __name__ == "__main__":
    from web_ui.state import init_session_state

    init_session_state()
    render()
