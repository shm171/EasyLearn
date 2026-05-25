from ai_core.rag.markdown_loader import MarkdownLoaderManager, split_markdown_pages


def test_markdown_loader_creates_virtual_pages(tmp_path) -> None:
    markdown_path = tmp_path / "lesson.md"
    markdown_path.write_text(
        "# Python 基础\n\n"
        "变量用于保存数据。\n\n"
        "## 示例\n\n"
        "```python\n"
        "name = 'Ada'\n"
        "print(name)\n"
        "```\n",
        encoding="utf-8",
    )

    loader = MarkdownLoaderManager(page_max_chars=80)
    documents = loader.load_markdown(str(markdown_path), course_id="python_md", chapter_title="Markdown")

    assert documents
    assert documents[0].metadata["file_type"] == "markdown"
    assert documents[0].metadata["page_number"] == 1
    assert documents[0].metadata["course_id"] == "python_md"


def test_split_markdown_pages_uses_heading_titles() -> None:
    pages = split_markdown_pages("# 第一章\n\n内容\n\n# 第二章\n\n更多内容", page_max_chars=20)

    assert [page.title for page in pages] == ["第一章", "第二章"]
