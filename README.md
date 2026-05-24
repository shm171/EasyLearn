# EasyLearn 本地 PDF 阅读器

本项目是本地 AI 编程学习助手，当前主要入口是 React PDF 阅读器：导入本地 PDF、边读边问 AI、按页面范围总结/出题。

## 安装

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

也可以直接在阅读器顶部点击“API 配置”填写 DeepSeek API Key，系统会写入本地 `.env`。

## FastAPI

```bash
uvicorn api.main:app --reload
```

打开 `http://127.0.0.1:8000/docs` 调试接口。

第三阶段新增接口包括：

- `GET /reader/materials`
- `POST /reader/materials/import`
- `GET /reader/api-config`
- `POST /reader/api-config`
- `POST /reader/api-config/test`
- `GET /reader/pdf/{course_id}`
- `POST /reader/current-page/ask`
- `POST /reader/selection/ask`
- `POST /reader/selection/explain-code`
- `POST /range/ask`
- `POST /range/summary`
- `POST /range/quiz`
- `POST /range/key-points`

## PDF 阅读器 GUI + 页码范围检索器

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
1. 点击“API 配置”，输入 DeepSeek API Key，保存后测试调用。
2. 点击“导入本地 PDF”，选择 PDF 并填写 course_id。
3. 打开 PDF 后翻页，确认当前页码变化。
4. 选中文字并右键，选择解释、总结、解释代码或生成练习。
5. 点击右侧悬浮“页问”，使用当前页、前后 2 页或全部页范围问答。
```

说明：PDF 阅读器只会根据 `data/materials_registry.json` 中注册的材料读取 `materials/` 目录下的 PDF，避免任意本地路径被前端访问。导入 PDF 成功后，`LearningAIService.ingest_pdf()` 会自动尝试注册该材料。

## 阶段边界

当前阶段只支持文本型 PDF，不支持 OCR、PPT、docx、txt、md、账号系统、云端同步或代码图形化调试器。
