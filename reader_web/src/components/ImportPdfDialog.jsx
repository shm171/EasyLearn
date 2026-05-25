import { useState } from "react";
import { FileUp, Loader2, X } from "lucide-react";
import { importLocalMaterial } from "../api/client.js";

export default function ImportPdfDialog({ open, onClose, onImported }) {
  const [courseId, setCourseId] = useState("");
  const [chapterTitle, setChapterTitle] = useState("");
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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
    try {
      const result = await importLocalMaterial({
        courseId: courseId.trim(),
        chapterTitle: chapterTitle.trim(),
        file
      });
      onImported(result.material);
      setCourseId("");
      setChapterTitle("");
      setFile(null);
      onClose();
    } catch (importError) {
      setError(importError.message);
    } finally {
      setLoading(false);
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
