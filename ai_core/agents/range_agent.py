from __future__ import annotations

"""Prompt helpers for page-range and PDF reader AI actions."""

from typing import Any

from ai_core.agents.reading_agent import _extract_response_text


NO_EVIDENCE_IN_RANGE = "当前页码范围内未找到明确依据。"


class RangeLearningAgent:
    """Use a chat model with explicitly bounded PDF context."""

    def __init__(self, model: Any) -> None:
        self.model = model

    def answer_range(
        self,
        course_id: str,
        question: str,
        page_start: int,
        page_end: int,
        context: str,
    ) -> str:
        prompt = f"""你是编程学习资料阅读助手。请只基于给定页码范围内的 PDF 上下文回答。

course_id: {course_id}
允许页码范围: {page_start}-{page_end}
问题: {question}

PDF 上下文:
{context or NO_EVIDENCE_IN_RANGE}

要求:
- 只能使用上述上下文回答，不要编造 PDF 中没有的内容。
- 如果上下文不足，明确说：{NO_EVIDENCE_IN_RANGE}
- 输出必须简洁、有层次：先给“## 结论”，再给“## 要点”，必要时给“## 示例”。
- 要点最多 5 条；能用代码说明时，代码必须放在 ```{_language_hint(question)}``` 代码块中。
- 涉及具体依据时引用页码或 chunk ID。"""
        return self._invoke(prompt)

    def summarize_range(self, course_id: str, page_start: int, page_end: int, context: str) -> str:
        prompt = f"""请只总结指定 PDF 页码范围内的内容。

course_id: {course_id}
允许页码范围: {page_start}-{page_end}

PDF 上下文:
{context or NO_EVIDENCE_IN_RANGE}

要求:
- 只基于上述上下文总结。
- 如果上下文不足，明确说：{NO_EVIDENCE_IN_RANGE}
- 用 Markdown 分成“## 核心内容 / ## 关键概念 / ## 易错点 / ## 复习建议”。
- 每节最多 5 条，避免长段落。"""
        return self._invoke(prompt)

    def key_points_range(self, course_id: str, page_start: int, page_end: int, context: str) -> str:
        prompt = f"""请提取指定 PDF 页码范围内的学习重点。

course_id: {course_id}
允许页码范围: {page_start}-{page_end}

PDF 上下文:
{context or NO_EVIDENCE_IN_RANGE}

要求:
- 只列出上下文中有依据的重点。
- 如果上下文不足，明确说：{NO_EVIDENCE_IN_RANGE}
- 按“## 概念 / ## 语法 / ## 示例 / ## 易错点”组织。
- 每节最多 5 条，句子短。"""
        return self._invoke(prompt)

    def quiz_range(
        self,
        course_id: str,
        page_start: int,
        page_end: int,
        context: str,
        programming_language: str,
        difficulty: str,
        question_types: list[str],
        question_count: int,
    ) -> str:
        prompt = f"""请根据指定 PDF 页码范围生成编程练习题，必须只使用给定上下文。

course_id: {course_id}
允许页码范围: {page_start}-{page_end}
programming_language: {programming_language}
difficulty: {difficulty}
question_types: {question_types}
question_count: {question_count}

PDF 上下文:
{context or NO_EVIDENCE_IN_RANGE}

要求:
- 题目数量必须严格等于 {question_count}。
- 难度必须遵守 {difficulty}。
- 题型只能来自 question_types，可用类型包括 true_false、fill_blank、programming、short_answer。
- 只输出 JSON，不要 Markdown，不要额外解释。
- 顶层字段：quiz_title、questions。
- 每题字段：question_id、question_type、stem、options、code_snippet、answer、explanation、difficulty、reference_chunks。
- true_false 的 options 必须是 ["正确", "错误"]，answer 必须是 "true" 或 "false"。
- fill_blank 的 stem 必须包含 ____，options 用 []。
- programming 必须给出清晰任务，必要时在 code_snippet 放起始代码，answer 放参考代码字符串。
- short_answer 用 [] 作为 options。
- 如果上下文不足，仍输出 JSON，questions 为空，并在 message 中写：{NO_EVIDENCE_IN_RANGE}。"""
        return self._invoke(prompt)

    def selection_action(
        self,
        selected_text: str,
        action: str,
        page_context: str = "",
        question: str | None = None,
    ) -> str:
        if action == "generate_quiz":
            return self._selection_quiz(selected_text, page_context)

        action_instruction = {
            "explain": "解释选中文字：先说它是什么，再说怎么用。",
            "summarize": "总结选中文字：提炼复习要点。",
            "ask": f"回答用户关于选中文字的问题：{question or '请围绕选中文字回答。'}",
            "generate_quiz": "根据选中文字生成 3 道基础练习题，包含答案和解释。",
        }.get(action, "解释选中文字。")
        prompt = f"""你是编程学习 PDF 阅读助手。请快速、分层回答。selected_text 是最高优先级证据。

任务: {action_instruction}

selected_text:
{selected_text}

可选页面上下文:
{page_context or "未提供页面上下文。"}

要求:
- 优先基于 selected_text 回答，页面上下文只能补充解释。
- 如果依据不足，请明确说明不确定。
- 使用 Markdown 小标题，固定结构为“## 结论 / ## 要点 / ## 示例或注意”。
- 总长度控制在 180-300 字；要点最多 5 条。
- 如包含代码，必须放进 ```python``` 代码块。"""
        return self._invoke(prompt)

    def _selection_quiz(self, selected_text: str, page_context: str = "") -> str:
        prompt = f"""请根据 selected_text 生成 3 道适合编程初学者的交互式练习题。

selected_text:
{selected_text}

可选页面上下文:
{page_context or "未提供页面上下文。"}

要求:
- 只输出 JSON，不要 Markdown，不要额外解释。
- 顶层字段：quiz_title、questions。
- questions 必须正好 3 道。
- 题型从 true_false、fill_blank、programming、short_answer 中选择，尽量覆盖不同题型。
- 每题字段：question_id、question_type、stem、options、code_snippet、answer、explanation、difficulty、reference_chunks。
- true_false 的 options 必须是 ["正确", "错误"]，answer 必须是 "true" 或 "false"。
- fill_blank 的 stem 必须包含 ____，options 用 []。
- programming 必须给出清晰任务，必要时在 code_snippet 放起始代码，answer 放参考代码字符串。
- short_answer 用 [] 作为 options。"""
        return self._invoke(prompt)

    def explain_code(
        self,
        selected_text: str,
        programming_language: str,
        page_context: str = "",
    ) -> str:
        prompt = f"""请快速解释选中的 {programming_language} 代码，面向编程初学者。

选中代码:
```{programming_language}
{selected_text}
```

可选页面上下文:
{page_context or "未提供页面上下文。"}

要求:
- 用 Markdown 固定结构：“## 作用 / ## 关键语句 / ## 运行行为 / ## 常见错误”。
- 每节最多 4 条，避免长段落。
- 引用代码时必须使用 ```{programming_language}``` 代码块。
- 不要编造页面上下文中没有的 PDF 内容。"""
        return self._invoke(prompt)

    def _invoke(self, prompt: str) -> str:
        return _extract_response_text(self.model.invoke(prompt)) or NO_EVIDENCE_IN_RANGE


def _language_hint(text: str) -> str:
    lowered = text.lower()
    if "python" in lowered:
        return "python"
    if "javascript" in lowered or "js" in lowered:
        return "javascript"
    if "java" in lowered:
        return "java"
    if "c++" in lowered or "cpp" in lowered:
        return "cpp"
    return "text"
