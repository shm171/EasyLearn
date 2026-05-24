import { AlertCircle, FileText, Loader2 } from "lucide-react";
import { previewText } from "../utils/selection.js";

function renderResult(result) {
  if (!result) {
    return <p className="muted">等待一次阅读器操作或页码范围任务。</p>;
  }
  const mainText = result.answer || result.summary || result.message;
  if (mainText) {
    return <div className="ai-answer">{renderRichText(mainText)}</div>;
  }
  return <pre className="json-block">{JSON.stringify(result, null, 2)}</pre>;
}

function renderRichText(text) {
  const parts = splitCodeBlocks(text);
  return parts.map((part, index) => {
    if (part.type === "code") {
      return (
        <pre className="code-block" key={`${part.type}-${index}`}>
          <code>{part.content}</code>
        </pre>
      );
    }
    return renderTextLines(part.content, index);
  });
}

function splitCodeBlocks(text) {
  const regex = /```([a-zA-Z0-9_+-]*)\n?([\s\S]*?)```/g;
  const parts = [];
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: "text", content: text.slice(lastIndex, match.index) });
    }
    parts.push({ type: "code", language: match[1], content: match[2].trim() });
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push({ type: "text", content: text.slice(lastIndex) });
  }
  return parts.length ? parts : [{ type: "text", content: text }];
}

function renderTextLines(text, keyPrefix) {
  return text
    .split(/\n{2,}/)
    .filter((block) => block.trim())
    .map((block, blockIndex) => {
      const trimmed = block.trim();
      if (/^#{1,4}\s/.test(trimmed)) {
        return (
          <h3 className="ai-heading" key={`h-${keyPrefix}-${blockIndex}`}>
            {trimmed.replace(/^#{1,4}\s/, "")}
          </h3>
        );
      }
      if (/^[-*]\s/m.test(trimmed)) {
        return (
          <ul className="ai-list" key={`ul-${keyPrefix}-${blockIndex}`}>
            {trimmed
              .split("\n")
              .filter((line) => line.trim())
              .map((line, lineIndex) => (
                <li key={`li-${lineIndex}`}>{line.replace(/^[-*]\s*/, "")}</li>
              ))}
          </ul>
        );
      }
      return (
        <p key={`p-${keyPrefix}-${blockIndex}`}>
          {trimmed.split("\n").map((line, lineIndex) => (
            <span key={`line-${lineIndex}`}>
              {line}
              {lineIndex < trimmed.split("\n").length - 1 ? <br /> : null}
            </span>
          ))}
        </p>
      );
    });
}

export default function AiSidePanel({ panel }) {
  const chunks = panel.result?.source_chunks || [];
  const visibleChunks = chunks.slice(0, 6);
  const warnings = panel.result?.warnings || [];

  return (
    <aside className="ai-panel">
      <div className="panel-title">
        <FileText size={18} />
        <span>AI 侧边栏</span>
      </div>

      <div className="panel-section">
        <span className="section-label">当前操作</span>
        <strong>{panel.actionLabel || "无"}</strong>
      </div>

      {panel.selectedText ? (
        <div className="panel-section">
          <span className="section-label">选中文字</span>
          {isLikelyCode(panel.selectedText, panel.actionLabel) ? (
            <pre className="code-block selection-code">
              <code>{previewText(panel.selectedText, 500)}</code>
            </pre>
          ) : (
            <p className="selection-preview">{previewText(panel.selectedText)}</p>
          )}
        </div>
      ) : null}

      <div className="panel-section result-section">
        {panel.loading ? (
          <div className="loading-line">
            <Loader2 size={18} className="spin" />
            <span>AI 正在处理...</span>
          </div>
        ) : null}
        {panel.error ? (
          <div className="error-box">
            <AlertCircle size={18} />
            <span>{panel.error}</span>
          </div>
        ) : null}
        {!panel.loading && !panel.error ? renderResult(panel.result) : null}
      </div>

      {chunks.length ? (
        <div className="panel-section">
          <span className="section-label">来源</span>
          <div className="source-list">
            {visibleChunks.map((chunk) => (
              <div
                className="source-item"
                key={chunk.chunk_id || `${chunk.page_number}-${chunk.content?.slice(0, 10)}`}
                title={chunk.chunk_id || ""}
              >
                <strong>第 {chunk.page_number || "?"} 页</strong>
                <span>{compactChunkId(chunk.chunk_id)}</span>
              </div>
            ))}
            {chunks.length > visibleChunks.length ? (
              <div className="source-more">还有 {chunks.length - visibleChunks.length} 个来源</div>
            ) : null}
          </div>
        </div>
      ) : null}

      {warnings.length ? (
        <div className="panel-section warning-list">
          <span className="section-label">提示</span>
          {warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      ) : null}
    </aside>
  );
}

function isLikelyCode(text, actionLabel) {
  if (actionLabel?.includes("代码")) {
    return true;
  }
  return /[{};=]|\b(def|class|for|while|if|else|return|import|print)\b/.test(text);
}

function compactChunkId(chunkId) {
  if (!chunkId) {
    return "chunk";
  }
  const parts = String(chunkId).split(":").filter(Boolean);
  if (parts.length >= 2) {
    return parts.slice(-2).join(":");
  }
  return chunkId.length > 18 ? `...${chunkId.slice(-18)}` : chunkId;
}
