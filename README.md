# AI 编程学习平台核心层

这是第一阶段本地 AI 编程学习平台核心层，聚焦 PDF 学习资料读取、RAG 检索、AI 总结、AI 出题、AI 批改、CLI 调试和 FastAPI 预留接口。

## 安装

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

在 `.env` 中填写所选模型 provider 的 API key。

## CLI

```bash
python -m ai_core.cli health
python -m ai_core.cli load-pdf --file-path "./materials/test.pdf"
python -m ai_core.cli ingest --course-id cpp_001 --file-path "./materials/test.pdf" --chapter-title "类和对象"
python -m ai_core.cli search --course-id cpp_001 --query "构造函数是什么？"
python -m ai_core.cli ask --course-id cpp_001 --question "构造函数的作用是什么？" --chapter-title "类和对象"
python -m ai_core.cli summarize --course-id cpp_001 --chapter-title "类和对象"
python -m ai_core.cli quiz --course-id cpp_001 --chapter-title "类和对象" --programming-language cpp --difficulty medium --question-types true_false,fill_blank,programming --question-count 10 --output "./debug_outputs/quiz.json"
python -m ai_core.cli evaluate --quiz-file "./debug_outputs/quiz.json" --answers-file "./debug_outputs/answers.json" --output "./debug_outputs/report.json"
```

## FastAPI

```bash
uvicorn api.main:app --reload
```

打开 `http://127.0.0.1:8000/docs` 调试接口。

## Python 调用

```python
from ai_core.service import LearningAIService

service = LearningAIService()
service.ingest_pdf("cpp_001", "./materials/C++基础.pdf", "类和对象")
summary = service.summarize_chapter("cpp_001", "类和对象")
quiz = service.generate_programming_quiz(
    course_id="cpp_001",
    chapter_title="类和对象",
    programming_language="cpp",
    difficulty="medium",
    question_types=["true_false", "fill_blank", "programming"],
    question_count=10,
)
report = service.evaluate_answers(
    quiz=quiz,
    user_answers=[
        {"question_id": "q1", "answer": "true"},
        {"question_id": "q2", "answer": "构造函数用于对象初始化"},
    ],
)
```

## 阶段边界

当前阶段只支持文本型 PDF，不支持 OCR、GUI、PPT、docx、txt、md 或代码图形化调试器。

