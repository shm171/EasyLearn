from __future__ import annotations

from zipfile import ZipFile

import pytest

from ai_core.rag.pptx_loader import PptxLoaderManager


def test_pptx_loader_extracts_slide_text(tmp_path) -> None:
    pptx_path = tmp_path / "lesson.pptx"
    with ZipFile(pptx_path, "w") as archive:
        archive.writestr("ppt/slides/slide1.xml", _slide_xml(["Java 基础", "变量", "循环"]))
        archive.writestr("ppt/slides/slide2.xml", _slide_xml(["JDBC", "连接数据库"]))

    loader = PptxLoaderManager()
    documents = loader.load_pptx(str(pptx_path), course_id="java_ppt", chapter_title="Java")

    assert loader.get_slide_count(str(pptx_path)) == 2
    assert len(documents) == 2
    assert documents[0].metadata["file_type"] == "pptx"
    assert documents[0].metadata["page_number"] == 1
    assert documents[0].metadata["page_title"] == "Java 基础"
    assert "变量" in documents[0].page_content
    assert "连接数据库" in documents[1].page_content


def test_ppt_loader_rejects_legacy_ppt(tmp_path) -> None:
    ppt_path = tmp_path / "legacy.ppt"
    ppt_path.write_bytes(b"not a pptx")

    with pytest.raises(ValueError, match="Legacy .ppt"):
        PptxLoaderManager().load_pptx(str(ppt_path), course_id="old")


def _slide_xml(lines: list[str]) -> str:
    paragraphs = "\n".join(
        f"<a:p><a:r><a:t>{line}</a:t></a:r></a:p>"
        for line in lines
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:sp>
        <p:txBody>
          {paragraphs}
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>
"""
