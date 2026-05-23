from __future__ import annotations

"""Shared UI utilities for Streamlit pages."""

import json
from pathlib import Path
from typing import Any

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEBUG_DIR = PROJECT_ROOT / "debug_outputs"
MATERIALS_DIR = PROJECT_ROOT / "materials"


def to_jsonable(obj: Any) -> Any:
    """Convert Pydantic models and common containers into JSON-safe values."""

    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {key: to_jsonable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(item) for item in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


def save_json_utf8(path: str | Path, data: Any) -> Path:
    """Save JSON using UTF-8 and preserve Chinese text."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(data), file, ensure_ascii=False, indent=2)
    return target


def load_json_utf8(path: str | Path) -> Any:
    """Load JSON using UTF-8."""

    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def show_json_download_button(label: str, data: Any, file_name: str) -> None:
    """Render a UTF-8 JSON download button."""

    content = json.dumps(to_jsonable(data), ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button(label=label, data=content, file_name=file_name, mime="application/json")


def safe_show_exception(error: Exception) -> None:
    """Show a concise error plus expandable technical details."""

    st.error(str(error))
    with st.expander("错误详情"):
        st.exception(error)


def uploaded_json(uploaded_file: Any) -> Any:
    """Read a Streamlit UploadedFile as UTF-8 JSON."""

    return json.loads(uploaded_file.getvalue().decode("utf-8"))


def render_list_or_json(value: Any) -> None:
    """Render lists as bullets and other values as JSON/text."""

    data = to_jsonable(value)
    if isinstance(data, list):
        if not data:
            st.caption("暂无内容")
        for item in data:
            if isinstance(item, (dict, list)):
                st.json(item, expanded=False)
            else:
                st.markdown(f"- {item}")
        return
    if isinstance(data, dict):
        st.json(data, expanded=False)
    elif data:
        st.write(data)
    else:
        st.caption("暂无内容")
