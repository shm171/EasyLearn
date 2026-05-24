from __future__ import annotations

"""Fast heuristics for validating and reranking retrieved source chunks."""

import re
from dataclasses import dataclass

from ai_core.schemas import SourceChunk


_CLASS_QUERY_HINTS = {
    "class",
    "classes",
    "object",
    "objects",
    "define",
    "definition",
    "structure",
    "method",
    "attribute",
    "__init__",
    "self",
    "\u7c7b",
    "\u5bf9\u8c61",
    "\u5b9a\u4e49",
    "\u7ed3\u6784",
    "\u5c5e\u6027",
    "\u65b9\u6cd5",
    "\u6784\u9020",
}

_ITERATOR_QUERY_HINTS = {
    "iterator",
    "iterators",
    "begin",
    "end",
    "stl",
    "container",
    "containers",
    "vector",
    "list",
    "map",
    "set",
    "\u8fed\u4ee3\u5668",
    "\u5bb9\u5668",
    "\u904d\u5386",
    "\u6307\u9488",
}

_SPECIFIC_TOPIC_HINTS = _CLASS_QUERY_HINTS | _ITERATOR_QUERY_HINTS

_QUESTION_EXPANSIONS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("\u7c7b", "class", "object"),
        (
            "\u521b\u5efa\u548c\u4f7f\u7528\u7c7b \u521b\u5efaDog\u7c7b \u6839\u636e\u7c7b\u521b\u5efa\u5b9e\u4f8b __init__ self \u5c5e\u6027 \u65b9\u6cd5",
            "class __init__ self object method attribute define structure",
            "\u7c7b \u5b9a\u4e49 \u7ed3\u6784 \u5bf9\u8c61 \u5c5e\u6027 \u65b9\u6cd5 self __init__",
        ),
    ),
    (
        ("\u8fed\u4ee3\u5668", "iterator", "iterators"),
        (
            "\u8fed\u4ee3\u5668 iterator STL \u5bb9\u5668 begin end \u904d\u5386 \u6307\u9488",
            "iterator begin end dereference increment STL container vector list map set",
            "\u4f7f\u7528\u8fed\u4ee3\u5668 \u904d\u5386\u5bb9\u5668 \u6307\u5411\u5143\u7d20 ++ *",
        ),
    ),
    (
        ("\u51fd\u6570", "function", "def"),
        (
            "def function parameter return call",
            "\u51fd\u6570 \u5b9a\u4e49 \u53c2\u6570 \u8fd4\u56de\u503c \u8c03\u7528",
        ),
    ),
    (
        ("\u5217\u8868", "list"),
        (
            "list index append remove sort slice",
            "\u5217\u8868 \u7d22\u5f15 \u6dfb\u52a0 \u5220\u9664 \u6392\u5e8f \u5207\u7247",
        ),
    ),
    (
        ("\u5b57\u5178", "dict", "dictionary"),
        (
            "dictionary dict key value item get",
            "\u5b57\u5178 \u952e \u503c \u904d\u5386 \u8bbf\u95ee",
        ),
    ),
)

_NOISE_PATTERNS = (
    "table of contents",
    "contents",
    "copyright",
    "acknowledg",
    "preface",
    "about the author",
    "\u76ee\u5f55",
    "\u7248\u6743",
    "\u81f4\u8c22",
    "\u524d\u8a00",
    "\u4f5c\u8005\u7b80\u4ecb",
)

_CODE_MARKERS = (
    "def ",
    "class ",
    "__init__",
    "self.",
    "return ",
    "import ",
    "for ",
    "while ",
    "if ",
    "elif ",
    "else:",
    ">>>",
)


@dataclass(frozen=True)
class RankedChunk:
    """A source chunk and its heuristic rank."""

    chunk: SourceChunk
    rank: float


class SourceQualityValidator:
    """Validate and rerank retrieved chunks without an extra model call."""

    def build_query_variants(self, query: str) -> list[str]:
        """Build a small set of search variants for common programming questions."""

        normalized = _normalize_text(query)
        variants: list[str] = []
        for triggers, expansions in _QUESTION_EXPANSIONS:
            if any(trigger.lower() in normalized for trigger in triggers):
                variants.extend(expansions)
        variants.append(query)

        compact_terms = " ".join(_extract_query_terms(query))
        if compact_terms:
            variants.append(compact_terms)

        return _dedupe_texts(variants, limit=5)

    def rerank(self, chunks: list[SourceChunk], query: str, limit: int) -> list[SourceChunk]:
        """Filter obvious noise, rerank useful chunks, and return at most limit chunks."""

        if not chunks:
            return []

        terms = _extract_query_terms(query)
        ranked = [RankedChunk(chunk=chunk, rank=self._score_chunk(chunk, terms)) for chunk in chunks]
        ranked.sort(key=lambda item: item.rank, reverse=True)

        topic_terms = _specific_topic_terms(terms)
        selected = [
            item.chunk
            for item in ranked
            if item.rank > -2.0
            and not self._is_obvious_noise(item.chunk)
            and (not topic_terms or self._has_topic_signal(item.chunk, topic_terms))
        ]
        if not selected:
            if topic_terms:
                return []
            selected = [item.chunk for item in ranked]
        return selected[:limit]

    def _score_chunk(self, chunk: SourceChunk, terms: list[str]) -> float:
        text = _normalize_text(chunk.content)
        rank = 0.0

        if chunk.score is not None:
            rank -= min(float(chunk.score), 5.0) * 0.25

        for term in terms:
            if term and term.lower() in text:
                rank += 1.2 if term in _CLASS_QUERY_HINTS else 0.8

        class_focused = any(term in _CLASS_QUERY_HINTS for term in terms)
        class_signal = any(
            signal in text
            for signal in (
                "class ",
                "__init__",
                "self.",
                "\u521b\u5efa\u548c\u4f7f\u7528\u7c7b",
                "\u6839\u636e\u7c7b\u521b\u5efa\u5b9e\u4f8b",
                "\u5c5e\u6027",
                "\u65b9\u6cd5",
                "\u7b2c9 \u7ae0 \u7c7b",
                "\u7b2c9\u7ae0 \u7c7b",
            )
        )
        if class_focused and class_signal:
            rank += 2.5
        elif class_focused:
            rank -= 2.0

        iterator_focused = any(term in _ITERATOR_QUERY_HINTS for term in terms)
        iterator_signal = any(
            signal in text
            for signal in (
                "iterator",
                "begin",
                "end",
                "stl",
                "container",
                "vector",
                "\u8fed\u4ee3\u5668",
                "\u5bb9\u5668",
                "\u904d\u5386",
            )
        )
        if iterator_focused and iterator_signal:
            rank += 2.5
        elif iterator_focused:
            rank -= 2.0

        if any(marker in text for marker in _CODE_MARKERS):
            rank += 1.0

        if self._looks_like_toc_or_index(text):
            rank -= 3.0
        if self._is_intro_noise(text):
            rank -= 1.5
        if len(text) < 120:
            rank -= 0.8
        return rank

    def _is_obvious_noise(self, chunk: SourceChunk) -> bool:
        text = _normalize_text(chunk.content)
        return self._looks_like_toc_or_index(text) and not any(marker in text for marker in _CODE_MARKERS)

    def _has_topic_signal(self, chunk: SourceChunk, topic_terms: set[str]) -> bool:
        text = _normalize_text(chunk.content)
        return any(term and term.lower() in text for term in topic_terms)

    def _looks_like_toc_or_index(self, text: str) -> bool:
        if any(pattern in text[:500] for pattern in _NOISE_PATTERNS):
            return True
        if text.count("...") >= 3 or text.count("\u2026") >= 3:
            return True
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 8:
            return False
        short_lines = sum(1 for line in lines if len(line) <= 32)
        numbered_lines = sum(1 for line in lines if re.search(r"(\.{2,}|\s\d{1,4}$|chapter\s+\d+|\u7b2c.+\u7ae0)", line.lower()))
        return short_lines / len(lines) > 0.75 and numbered_lines >= 3

    def _is_intro_noise(self, text: str) -> bool:
        intro_words = ("\u7b80\u4ecb", "\u6982\u8ff0", "overview", "introduction")
        has_intro = any(word in text[:400] for word in intro_words)
        has_learning_signal = any(marker in text for marker in _CODE_MARKERS) or any(term in text for term in _CLASS_QUERY_HINTS)
        return has_intro and not has_learning_signal


def _extract_query_terms(query: str) -> list[str]:
    normalized = _normalize_text(query)
    terms = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", normalized)
    for hint in _CLASS_QUERY_HINTS:
        if hint in normalized:
            terms.append(hint)
    for hint in _ITERATOR_QUERY_HINTS:
        if hint in normalized:
            terms.append(hint)
    for char_term in (
        "\u7c7b",
        "\u5b9a\u4e49",
        "\u7ed3\u6784",
        "\u5c5e\u6027",
        "\u65b9\u6cd5",
        "\u5bf9\u8c61",
        "\u8fed\u4ee3\u5668",
        "\u5bb9\u5668",
        "\u904d\u5386",
    ):
        if char_term in query:
            terms.append(char_term)
    return _dedupe_texts(terms, limit=16)


def _specific_topic_terms(terms: list[str]) -> set[str]:
    return {term for term in terms if term in _SPECIFIC_TOPIC_HINTS}


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def _dedupe_texts(texts: list[str] | tuple[str, ...], limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for text in texts:
        normalized = _normalize_text(str(text))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(str(text))
        if len(result) >= limit:
            break
    return result
