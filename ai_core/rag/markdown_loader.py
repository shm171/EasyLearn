from __future__ import annotations

"""Markdown loading utilities for reader materials."""

from dataclasses import dataclass
from pathlib import Path
import re

from langchain_core.documents import Document


SUPPORTED_MARKDOWN_SUFFIXES = {".md", ".markdown"}
DEFAULT_MARKDOWN_PAGE_CHARS = 3600


@dataclass(frozen=True)
class MarkdownPage:
    """One virtual reader page extracted from a Markdown document."""

    title: str
    content: str


class MarkdownLoaderManager:
    """Read Markdown learning materials into virtual page documents."""

    def __init__(self, page_max_chars: int = DEFAULT_MARKDOWN_PAGE_CHARS) -> None:
        self.page_max_chars = page_max_chars

    def load_markdown(self, file_path: str, course_id: str, chapter_title: str | None = None) -> list[Document]:
        """Load a Markdown file into virtual pages.

        Markdown has no physical pages, so pages are derived from heading
        sections and clipped to a stable character budget. The generated
        page_number metadata is shared by the reader UI and range retriever.
        """

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Markdown file not found: {file_path}")
        if path.suffix.lower() not in SUPPORTED_MARKDOWN_SUFFIXES:
            raise ValueError("Only .md and .markdown files are supported.")

        text = _read_text_file(path).strip()
        if not text:
            raise ValueError("Markdown file is empty.")

        pages = split_markdown_pages(text, page_max_chars=self.page_max_chars, default_title=path.stem)
        documents: list[Document] = []
        for index, page in enumerate(pages, start=1):
            documents.append(
                Document(
                    page_content=page.content,
                    metadata={
                        "course_id": course_id,
                        "file_path": str(path),
                        "file_name": path.name,
                        "file_type": "markdown",
                        "chapter_title": chapter_title,
                        "page_number": index,
                        "page_title": page.title,
                    },
                )
            )
        return documents


def split_markdown_pages(
    text: str,
    page_max_chars: int = DEFAULT_MARKDOWN_PAGE_CHARS,
    default_title: str = "Markdown",
) -> list[MarkdownPage]:
    """Split Markdown text into stable virtual pages."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    sections = _split_heading_sections(normalized)
    packed_pages: list[str] = []
    current = ""

    for section in sections:
        for piece in _split_oversized_section(section, page_max_chars):
            if not piece:
                continue
            if current and len(current) + len(piece) + 2 > page_max_chars:
                packed_pages.append(current.strip())
                current = piece
            else:
                current = f"{current.rstrip()}\n\n{piece}".strip() if current else piece

    if current.strip():
        packed_pages.append(current.strip())

    return [
        MarkdownPage(title=_extract_page_title(page, default_title, index), content=page)
        for index, page in enumerate(packed_pages, start=1)
    ]


def _read_text_file(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _split_heading_sections(text: str) -> list[str]:
    matches = list(re.finditer(r"(?m)^#{1,3}\s+.+$", text))
    if not matches:
        return _split_by_blank_blocks(text)

    sections: list[str] = []
    if matches[0].start() > 0:
        preface = text[: matches[0].start()].strip()
        if preface:
            sections.append(preface)

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section = text[match.start() : end].strip()
        if section:
            sections.append(section)
    return sections


def _split_oversized_section(section: str, page_max_chars: int) -> list[str]:
    if len(section) <= page_max_chars:
        return [section]

    pieces: list[str] = []
    current = ""
    for block in _split_by_blank_blocks(section):
        if len(block) > page_max_chars:
            if current:
                pieces.append(current.strip())
                current = ""
            pieces.extend(_split_long_block(block, page_max_chars))
            continue
        if current and len(current) + len(block) + 2 > page_max_chars:
            pieces.append(current.strip())
            current = block
        else:
            current = f"{current.rstrip()}\n\n{block}".strip() if current else block
    if current:
        pieces.append(current.strip())
    return pieces


def _split_by_blank_blocks(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def _split_long_block(block: str, page_max_chars: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for line in block.splitlines():
        if len(line) > page_max_chars:
            if current:
                pieces.append(current.rstrip())
                current = ""
            pieces.extend(line[index : index + page_max_chars] for index in range(0, len(line), page_max_chars))
            continue
        if current and len(current) + len(line) + 1 > page_max_chars:
            pieces.append(current.rstrip())
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        pieces.append(current.rstrip())
    return pieces


def _extract_page_title(page: str, default_title: str, index: int) -> str:
    heading = re.search(r"(?m)^#{1,6}\s+(.+?)\s*#*\s*$", page)
    if heading:
        return heading.group(1).strip()
    if index == 1:
        return default_title
    return f"{default_title} {index}"
