from __future__ import annotations

import json
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
    layout = json.loads(documents[0].metadata["slide_layout"])
    assert layout["width"] == 12192000
    assert layout["height"] == 6858000
    assert any(element["type"] == "text" for element in layout["elements"])


def test_pptx_loader_extracts_positioned_images_and_text(tmp_path) -> None:
    pptx_path = tmp_path / "visual_lesson.pptx"
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\xf8\x0f"
        b"\x00\x01\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    with ZipFile(pptx_path, "w") as archive:
        archive.writestr("ppt/presentation.xml", _presentation_xml())
        archive.writestr("ppt/slides/slide1.xml", _visual_slide_xml())
        archive.writestr("ppt/slides/_rels/slide1.xml.rels", _slide_rels_xml())
        archive.writestr("ppt/media/image1.png", png_bytes)

    document = PptxLoaderManager().load_pptx(str(pptx_path), course_id="visual")[0]
    layout = json.loads(document.metadata["slide_layout"])

    assert layout["width"] == 9144000
    assert layout["height"] == 5143500
    assert any(element["type"] == "image" and element["dataUri"].startswith("data:image/png;base64,") for element in layout["elements"])
    text = next(element for element in layout["elements"] if element["type"] == "text")
    assert text["x"] == 457200
    assert text["paragraphs"][0]["fontSize"] == 32


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


def _presentation_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldSz cx="9144000" cy="5143500" type="screen16x9"/>
</p:presentation>
"""


def _visual_slide_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld>
    <p:spTree>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="2" name="Title"/>
          <p:cNvSpPr/>
          <p:nvPr><p:ph type="title"/></p:nvPr>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm>
            <a:off x="457200" y="342900"/>
            <a:ext cx="4572000" cy="914400"/>
          </a:xfrm>
        </p:spPr>
        <p:txBody>
          <a:p><a:r><a:rPr sz="3200" b="1"><a:solidFill><a:srgbClr val="176B5B"/></a:solidFill></a:rPr><a:t>课程标题</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
      <p:pic>
        <p:nvPicPr>
          <p:cNvPr id="3" name="Picture 1" descr="diagram"/>
          <p:cNvPicPr/>
          <p:nvPr/>
        </p:nvPicPr>
        <p:blipFill><a:blip r:embed="rId1"/></p:blipFill>
        <p:spPr>
          <a:xfrm>
            <a:off x="5486400" y="1143000"/>
            <a:ext cx="1828800" cy="1371600"/>
          </a:xfrm>
        </p:spPr>
      </p:pic>
    </p:spTree>
  </p:cSld>
</p:sld>
"""


def _slide_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
                Target="../media/image1.png"/>
</Relationships>
"""
