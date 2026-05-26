import { useState } from "react";
import { FileUp, Loader2, X } from "lucide-react";
import { importLocalMaterial } from "../api/client.js";

export default function ImportPdfDialog({ open, onClose, onImported }) {
  const [courseId, setCourseId] = useState("");
  const [chapterTitle, setChapterTitle] = useState("");
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [importProgress, setImportProgress] = useState(null);

  if (!open) {
    return null;
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (!courseId.trim()) {
      setError("请填写 course_id。");
      return;
    }
    if (!file) {
      setError("请选择一个 PDF 或 Markdown 文件。");
      return;
    }

    setLoading(true);
    setImportProgress({ value: 0.04, message: "准备导入资料" });
    const startedAt = Date.now();
    const progressTimer = window.setInterval(() => {
      setImportProgress((current) => {
        const elapsed = Date.now() - startedAt;
        const estimated = Math.min(0.88, 0.36 + (elapsed / 30000) * 0.52);
        const value = Math.max(current?.value || 0.04, estimated);
        return {
          value,
          message: progressMessage(value)
        };
      });
    }, 500);
    try {
      const result = await importLocalMaterial({
        courseId: courseId.trim(),
        chapterTitle: chapterTitle.trim(),
        file,
        onProgress: (nextProgress) => {
          setImportProgress((current) => ({
            value: Math.max(current?.value || 0, nextProgress.value),
            message: nextProgress.message
          }));
        }
      });
      setImportProgress({
        value: 1,
        message:
          result.index_status?.status === "indexing"
            ? "阅读已可用，AI 索引后台构建中"
            : "导入完成"
      });
      await new Promise((resolve) => window.setTimeout(resolve, 450));
      onImported(result.material);
      setCourseId("");
      setChapterTitle("");
      setFile(null);
      onClose();
    } catch (importError) {
      setError(importError.message);
    } finally {
      window.clearInterval(progressTimer);
      setLoading(false);
      setImportProgress(null);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="import-dialog" onSubmit={submit}>
        <div className="dialog-head">
          <div>
            <strong>导入本地资料</strong>
            <span>materials / Chroma</span>
          </div>
          <button type="button" className="icon-button" onClick={onClose} title="关闭">
            <X size={18} />
          </button>
        </div>

        <label>
          course_id
          <input
            value={courseId}
            onChange={(event) => setCourseId(event.target.value)}
            placeholder="python_001"
            autoFocus
          />
        </label>

        <label>
          章节标题
          <input
            value={chapterTitle}
            onChange={(event) => setChapterTitle(event.target.value)}
            placeholder="Python编程从入门到实践"
          />
        </label>

        <label className="file-drop">
          <FileUp size={24} />
          <span>{file ? file.name : "点击选择 PDF / Markdown 文件"}</span>
          <input
            type="file"
            accept="application/pdf,text/markdown,text/plain,.pdf,.md,.markdown"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
        </label>

        {error ? <div className="error-box">{error}</div> : null}

        {importProgress ? (
          <div className="import-progress">
            <div className="import-progress-head">
              <span>{importProgress.message}</span>
              <strong>{Math.round(importProgress.value * 100)}%</strong>
            </div>
            <div className="import-progress-track" role="progressbar" aria-label="资料导入进度" aria-valuenow={Math.round(importProgress.value * 100)}>
              <div style={{ width: `${Math.round(importProgress.value * 100)}%` }} />
            </div>
          </div>
        ) : null}

        <div className="dialog-actions">
          <button type="button" className="secondary-button" onClick={onClose} disabled={loading}>
            取消
          </button>
          <button type="submit" className="primary-button" disabled={loading}>
            {loading ? (
              <>
                <Loader2 size={17} className="spin" />
                <span>正在导入</span>
              </>
            ) : (
              <>
                <FileUp size={17} />
                <span>导入并打开</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

function progressMessage(value) {
  if (value >= 0.78) {
    return "正在启动后台 AI 索引";
  }
  if (value >= 0.56) {
    return "正在切分资料内容";
  }
  if (value >= 0.36) {
    return "正在解析页面文本";
  }
  return "正在上传资料";
}
