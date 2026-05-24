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

第三阶段新增接口包括：

- `GET /reader/materials`
- `POST /reader/materials/import`
- `GET /reader/pdf/{course_id}`
- `POST /reader/current-page/ask`
- `POST /reader/selection/ask`
- `POST /reader/selection/explain-code`
- `POST /range/ask`
- `POST /range/summary`
- `POST /range/quiz`
- `POST /range/key-points`

## 第二阶段：启动 Streamlit 本地 Web 调试界面

### 1. 激活虚拟环境

```powershell
.\.venv\Scripts\activate
```

### 2. 安装依赖

```powershell
pip install -r requirements.txt
```

### 3. 启动 Web UI

```powershell
streamlit run web_ui/app.py
```

### 4. 浏览器访问

Streamlit 会自动打开浏览器。如果没有自动打开，请根据终端提示访问本地地址。

## 第三阶段：PDF 阅读器 GUI + 页码范围检索器

### 1. 启动后端

```powershell
cd C:\Users\35753\Documents\智能体学习
.\.venv\Scripts\activate
uvicorn api.main:app --reload
```

后端地址：`http://127.0.0.1:8000`

接口文档：`http://127.0.0.1:8000/docs`

### 2. 启动 React 阅读器

```powershell
cd C:\Users\35753\Documents\智能体学习\reader_web
npm install
npm run dev
```

前端地址：`http://127.0.0.1:5173`

### 3. 使用流程

```text
1. 在阅读器顶部点击“导入本地 PDF”，或确认已经导入 PDF，例如 python_001 / materials/1.pdf。
2. 启动 FastAPI 后端。
3. 启动 React 阅读器前端。
4. 在前端选择 python_001，或直接导入后打开。
5. 打开 PDF 后翻页，确认当前页码变化。
6. 选中文字并右键，选择解释、总结、解释代码或生成练习。
7. 使用页码范围工具输入 page_start 和 page_end。
8. 测试范围问答、范围总结、范围出题和提取重点。
```

说明：PDF 阅读器只会根据 `data/materials_registry.json` 中注册的材料读取 `materials/` 目录下的 PDF，避免任意本地路径被前端访问。导入 PDF 成功后，`LearningAIService.ingest_pdf()` 会自动尝试注册该材料。

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

当前阶段只支持文本型 PDF，不支持 OCR、PPT、docx、txt、md、账号系统、云端同步或代码图形化调试器。
