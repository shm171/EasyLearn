import { useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  FileText,
  FileUp,
  Minimize2,
  RefreshCw,
  Rows3
} from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { getMarkdownIndex, getMarkdownPage, getPdfUrl } from "../api/client.js";
import { getSelectedText } from "../utils/selection.js";
import ContextMenu from "./ContextMenu.jsx";
import ReaderAnnotationLayer from "./ReaderAnnotationLayer.jsx";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

export default function PdfReader({
  courseId,
  material,
  currentPage,
  annotationSettings,
  pageAnnotations = [],
  onPageChange,
  onPageInfo,
  onPageAnnotationsChange,
  onContextAction,
  onImport,
  onRefresh
}) {
  const fileType = materialFileType(material);
  const isMarkdown = fileType === "markdown";
  const [numPages, setNumPages] = useState(0);
  const [loadError, setLoadError] = useState("");
  const [menu, setMenu] = useState(null);
  const [markdownPages, setMarkdownPages] = useState([]);
  const [markdownPageCache, setMarkdownPageCache] = useState({});
  const [markdownLoading, setMarkdownLoading] = useState(false);
  const [markdownPageLoading, setMarkdownPageLoading] = useState(false);
  const markdownRequestsRef = useRef(new Map());

  useEffect(() => {
    setNumPages(0);
    setLoadError("");
    setMarkdownPages([]);
    setMarkdownPageCache({});
    setMarkdownLoading(false);
    setMarkdownPageLoading(false);
    markdownRequestsRef.current.clear();
    onPageChange(1);
    onPageInfo(0);
  }, [courseId, fileType]);

  useEffect(() => {
    if (!courseId || !isMarkdown) {
      return;
    }
    let cancelled = false;
    setMarkdownLoading(true);
    setLoadError("");
    getMarkdownIndex(courseId)
      .then((data) => {
        if (cancelled) {
          return;
        }
        const pages = Array.isArray(data.pages) ? data.pages : [];
        const pageCount = Number(data.page_count || pages.length || 0);
        setMarkdownPages(pages);
        setNumPages(pageCount);
        onPageInfo(pageCount);
        if (currentPage > pageCount) {
          onPageChange(pageCount || 1);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setLoadError(error.message);
          onPageInfo(0);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setMarkdownLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [courseId, isMarkdown]);

  useEffect(() => {
    if (!courseId || !isMarkdown || !numPages || markdownPageCache[String(currentPage)]) {
      return;
    }
    let cancelled = false;
    setMarkdownPageLoading(true);
    requestMarkdownPage(markdownRequestsRef, courseId, currentPage)
      .then((page) => {
        if (!cancelled) {
          setMarkdownPageCache((current) => ({ ...current, [String(currentPage)]: page }));
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setLoadError(error.message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setMarkdownPageLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [courseId, currentPage, isMarkdown, markdownPageCache, numPages]);

  useEffect(() => {
    if (!courseId || !isMarkdown || !numPages) {
      return;
    }
    const nearbyPages = [currentPage - 1, currentPage + 1].filter(
      (page) => page >= 1 && page <= numPages && !markdownPageCache[String(page)]
    );
    nearbyPages.forEach((pageNumber) => {
      requestMarkdownPage(markdownRequestsRef, courseId, pageNumber)
        .then((page) => {
          setMarkdownPageCache((current) => {
            if (current[String(pageNumber)]) {
              return current;
            }
            return { ...current, [String(pageNumber)]: page };
          });
        })
        .catch(() => {
          // Nearby prefetch should not interrupt reading the current page.
        });
    });
  }, [courseId, currentPage, isMarkdown, markdownPageCache, numPages]);

  const currentMarkdownPage = markdownPageCache[String(currentPage)] || null;
  const renderedMarkdownPage = useMemo(
    () => (currentMarkdownPage ? renderMarkdown(currentMarkdownPage.content) : null),
    [currentMarkdownPage]
  );

  function goToPage(nextPage) {
    const bounded = Math.min(Math.max(nextPage, 1), numPages || 1);
    onPageChange(bounded);
  }

  function handleLoadSuccess({ numPages: loadedPages }) {
    setNumPages(loadedPages);
    onPageInfo(loadedPages);
    if (currentPage > loadedPages) {
      onPageChange(loadedPages);
    }
  }

  function handleContextMenu(event) {
    event.preventDefault();
    const selectedText = getSelectedText();
    setMenu({
      x: event.clientX,
      y: event.clientY,
      selectedText
    });
  }

  if (!courseId) {
    return (
      <div className="empty-reader">
        <strong>还没有打开资料</strong>
        <div className="empty-actions">
          <button type="button" className="primary-button" onClick={onImport}>
            <FileUp size={18} />
            <span>导入 PDF / Markdown</span>
          </button>
          <button type="button" className="secondary-button" onClick={onRefresh}>
            <RefreshCw size={18} />
            <span>刷新列表</span>
          </button>
        </div>
      </div>
    );
  }

  const shell = isMarkdown ? (
    <section className="reader-shell markdown-reader-shell">
      <ReaderToolbar currentPage={currentPage} numPages={numPages} onPageSelect={goToPage} />
      {markdownLoading ? <div className="pdf-status">正在加载 Markdown...</div> : null}
      {!markdownLoading ? (
        <div className="pdf-body markdown-body">
          <ThumbnailRail
            type="markdown"
            numPages={numPages}
            currentPage={currentPage}
            pagesMeta={markdownPages}
            onPageSelect={goToPage}
          />
          <div className="pdf-stage markdown-stage" onContextMenu={handleContextMenu}>
            {currentMarkdownPage ? (
              <div className="annotation-surface">
                <article className="markdown-page" aria-label={`Markdown 第 ${currentPage} 页`}>
                  {renderedMarkdownPage}
                </article>
                <ReaderAnnotationLayer
                  enabled={Boolean(annotationSettings?.enabled)}
                  settings={annotationSettings}
                  annotations={pageAnnotations}
                  onChange={onPageAnnotationsChange}
                />
              </div>
            ) : markdownPageLoading ? (
              <div className="pdf-status">正在加载当前页...</div>
            ) : (
              <div className="pdf-status">当前页暂无内容</div>
            )}
            {loadError ? <div className="pdf-load-error">{loadError}</div> : null}
          </div>
        </div>
      ) : null}
    </section>
  ) : (
    <section className="reader-shell">
      <ReaderToolbar currentPage={currentPage} numPages={numPages} onPageSelect={goToPage} />
      <Document
        key={courseId}
        file={getPdfUrl(courseId)}
        onLoadSuccess={handleLoadSuccess}
        onLoadError={(error) => setLoadError(error.message)}
        loading={<div className="pdf-status">正在加载 PDF...</div>}
        error={<div className="pdf-status error-text">PDF 加载失败</div>}
      >
        <div className="pdf-body">
          <ThumbnailRail
            type="pdf"
            numPages={numPages}
            currentPage={currentPage}
            onPageSelect={goToPage}
          />
          <div className="pdf-stage" onContextMenu={handleContextMenu}>
            <div className="annotation-surface">
              <Page
                pageNumber={currentPage}
                width={Math.min(820, Math.max(320, window.innerWidth - 700))}
                renderTextLayer
                renderAnnotationLayer
              />
              <ReaderAnnotationLayer
                enabled={Boolean(annotationSettings?.enabled)}
                settings={annotationSettings}
                annotations={pageAnnotations}
                onChange={onPageAnnotationsChange}
              />
            </div>
            {loadError ? <div className="pdf-load-error">{loadError}</div> : null}
          </div>
        </div>
      </Document>
    </section>
  );

  return (
    <>
      {shell}
      {menu ? (
        <ContextMenu
          x={menu.x}
          y={menu.y}
          selectedText={menu.selectedText}
          onClose={() => setMenu(null)}
          onAction={async (action) => {
            if (action === "copy_selection") {
              await copyTextToClipboard(menu.selectedText);
              setMenu(null);
              return;
            }
            onContextAction(action, menu.selectedText);
            setMenu(null);
          }}
        />
      ) : null}
    </>
  );
}

function ReaderToolbar({ currentPage, numPages, onPageSelect }) {
  return (
    <div className="reader-toolbar">
      <div className="reader-page-controls">
        <button
          type="button"
          className="icon-text-button"
          onClick={() => onPageSelect(currentPage - 1)}
          disabled={currentPage <= 1}
        >
          <ChevronLeft size={18} />
          <span>上一页</span>
        </button>
        <div className="page-meter">
          第 {currentPage} 页 / 共 {numPages || "-"} 页
        </div>
        <button
          type="button"
          className="icon-text-button"
          onClick={() => onPageSelect(currentPage + 1)}
          disabled={!numPages || currentPage >= numPages}
        >
          <ChevronRight size={18} />
          <span>下一页</span>
        </button>
      </div>
    </div>
  );
}

function ThumbnailRail({
  type,
  numPages,
  currentPage,
  pagesMeta = [],
  onPageSelect
}) {
  const [expanded, setExpanded] = useState(false);
  const activeRef = useRef(null);
  const pages = expanded ? buildAllPreviewPages(numPages) : buildPreviewPages(numPages, currentPage);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
  }, [currentPage, expanded]);

  if (!numPages) {
    return null;
  }

  return (
    <aside className={`thumbnail-rail${expanded ? " expanded" : ""}`} aria-label="页面预览">
      <div className="thumbnail-head">
        <span>页面预览</span>
        <button
          type="button"
          className="thumbnail-toggle"
          onClick={() => setExpanded((value) => !value)}
          title={expanded ? "收起到当前页附近" : "展开全部页码"}
        >
          {expanded ? <Minimize2 size={15} /> : <Rows3 size={15} />}
          <span>{expanded ? "收起" : "展开"}</span>
        </button>
      </div>
      <div className="thumbnail-list">
        {pages.map((page, index) =>
          page === "gap" ? (
            <div className="thumbnail-gap" key={`gap-${index}`}>...</div>
          ) : (
            <button
              type="button"
              className={`thumbnail-button${page === currentPage ? " active" : ""}`}
              key={page}
              ref={page === currentPage ? activeRef : null}
              onClick={() => onPageSelect(page)}
              title={`跳转到第 ${page} 页`}
            >
              {type === "pdf" ? (
                shouldRenderThumbnail(page, currentPage, expanded, numPages) ? (
                  <Page
                    pageNumber={page}
                    width={104}
                    renderTextLayer={false}
                    renderAnnotationLayer={false}
                    loading={<div className="thumbnail-placeholder">{page}</div>}
                  />
                ) : (
                  <div className="thumbnail-placeholder compact">{page}</div>
                )
              ) : (
                <MarkdownThumbnail page={page} pageMeta={pagesMeta[page - 1]} />
              )}
              <span>第 {page} 页</span>
            </button>
          )
        )}
      </div>
    </aside>
  );
}

function MarkdownThumbnail({ page, pageMeta }) {
  const title = pageMeta?.title || `第 ${page} 页`;
  const preview = pageMeta?.preview || compactMarkdown(pageMeta?.content || "");
  return (
    <div className="markdown-thumbnail">
      <FileText size={17} />
      <strong>{title}</strong>
      <p>{preview || "Markdown"}</p>
    </div>
  );
}

async function loadMarkdownPage(courseId, pageNumber) {
  const data = await getMarkdownPage(courseId, pageNumber);
  return data.page;
}

function requestMarkdownPage(requestsRef, courseId, pageNumber) {
  const key = `${courseId}:${pageNumber}`;
  const existing = requestsRef.current.get(key);
  if (existing) {
    return existing;
  }
  const request = loadMarkdownPage(courseId, pageNumber).finally(() => {
    requestsRef.current.delete(key);
  });
  requestsRef.current.set(key, request);
  return request;
}

function renderMarkdown(content = "") {
  const lines = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
  const elements = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    const fence = line.match(/^\s*```([A-Za-z0-9_+-]*)\s*$/);
    if (fence) {
      const codeLines = [];
      index += 1;
      while (index < lines.length && !/^\s*```\s*$/.test(lines[index])) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }
      elements.push(
        <pre className="markdown-code code-block" key={`code-${elements.length}`}>
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+?)\s*#*\s*$/);
    if (heading) {
      const level = Math.min(heading[1].length, 4);
      const HeadingTag = `h${level}`;
      elements.push(
        <HeadingTag className={`markdown-heading level-${level}`} key={`heading-${elements.length}`}>
          {renderInlineMarkdown(heading[2], `heading-${elements.length}`)}
        </HeadingTag>
      );
      index += 1;
      continue;
    }

    if (isMarkdownTableStart(lines, index)) {
      const tableLines = [];
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
        tableLines.push(lines[index]);
        index += 1;
      }
      elements.push(renderMarkdownTable(tableLines, `table-${elements.length}`));
      continue;
    }

    if (/^\s*>\s?/.test(line)) {
      const quoteLines = [];
      while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
        quoteLines.push(lines[index].replace(/^\s*>\s?/, ""));
        index += 1;
      }
      elements.push(
        <blockquote className="markdown-quote" key={`quote-${elements.length}`}>
          {renderInlineMarkdown(quoteLines.join(" "), `quote-${elements.length}`)}
        </blockquote>
      );
      continue;
    }

    if (/^\s*[-*+]\s+/.test(line)) {
      const items = [];
      while (index < lines.length && /^\s*[-*+]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*[-*+]\s+/, ""));
        index += 1;
      }
      elements.push(
        <ul className="markdown-list" key={`ul-${elements.length}`}>
          {items.map((item, itemIndex) => (
            <li key={`li-${itemIndex}`}>{renderInlineMarkdown(item, `ul-${elements.length}-${itemIndex}`)}</li>
          ))}
        </ul>
      );
      continue;
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      const items = [];
      while (index < lines.length && /^\s*\d+\.\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*\d+\.\s+/, ""));
        index += 1;
      }
      elements.push(
        <ol className="markdown-list" key={`ol-${elements.length}`}>
          {items.map((item, itemIndex) => (
            <li key={`li-${itemIndex}`}>{renderInlineMarkdown(item, `ol-${elements.length}-${itemIndex}`)}</li>
          ))}
        </ol>
      );
      continue;
    }

    const paragraph = [];
    while (index < lines.length && lines[index].trim() && !isSpecialMarkdownLine(lines, index)) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    elements.push(
      <p className="markdown-paragraph" key={`p-${elements.length}`}>
        {renderInlineMarkdown(paragraph.join(" "), `p-${elements.length}`)}
      </p>
    );
  }

  return elements;
}

function renderInlineMarkdown(text, keyPrefix) {
  const tokenRegex = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g;
  const nodes = [];
  let lastIndex = 0;
  let match;

  while ((match = tokenRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith("`")) {
      nodes.push(<code key={`${keyPrefix}-code-${nodes.length}`}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith("**")) {
      nodes.push(<strong key={`${keyPrefix}-strong-${nodes.length}`}>{token.slice(2, -2)}</strong>);
    } else {
      const link = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      const href = safeHref(link?.[2] || "");
      nodes.push(
        href ? (
          <a key={`${keyPrefix}-link-${nodes.length}`} href={href} target="_blank" rel="noreferrer">
            {link?.[1]}
          </a>
        ) : (
          link?.[1] || token
        )
      );
    }
    lastIndex = tokenRegex.lastIndex;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}

function renderMarkdownTable(tableLines, key) {
  const rows = tableLines.filter((line, index) => index !== 1 || !isTableSeparator(line)).map(parseTableRow);
  const [head = [], ...body] = rows;
  return (
    <div className="markdown-table-wrap" key={key}>
      <table className="markdown-table">
        <thead>
          <tr>
            {head.map((cell, index) => (
              <th key={`th-${index}`}>{renderInlineMarkdown(cell, `${key}-th-${index}`)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, rowIndex) => (
            <tr key={`tr-${rowIndex}`}>
              {row.map((cell, cellIndex) => (
                <td key={`td-${cellIndex}`}>{renderInlineMarkdown(cell, `${key}-td-${rowIndex}-${cellIndex}`)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function parseTableRow(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function isMarkdownTableStart(lines, index) {
  return lines[index]?.includes("|") && index + 1 < lines.length && isTableSeparator(lines[index + 1]);
}

function isTableSeparator(line) {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}

function isSpecialMarkdownLine(lines, index) {
  const line = lines[index] || "";
  return (
    /^\s*```/.test(line) ||
    /^#{1,6}\s+/.test(line) ||
    isMarkdownTableStart(lines, index) ||
    /^\s*>\s?/.test(line) ||
    /^\s*[-*+]\s+/.test(line) ||
    /^\s*\d+\.\s+/.test(line)
  );
}

function safeHref(value) {
  if (/^(https?:|mailto:|#)/i.test(value)) {
    return value;
  }
  return "";
}

function compactMarkdown(content) {
  return content
    .replace(/```[\s\S]*?```/g, "代码块")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/[*_`>#|-]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 88);
}

function buildAllPreviewPages(numPages) {
  return Array.from({ length: numPages }, (_, index) => index + 1);
}

function buildPreviewPages(numPages, currentPage) {
  if (!numPages) {
    return [];
  }
  if (numPages <= 24) {
    return Array.from({ length: numPages }, (_, index) => index + 1);
  }

  const visible = new Set([1, numPages]);
  const start = Math.max(1, currentPage - 5);
  const end = Math.min(numPages, currentPage + 5);
  for (let page = start; page <= end; page += 1) {
    visible.add(page);
  }

  const sorted = Array.from(visible).sort((a, b) => a - b);
  const pages = [];
  sorted.forEach((page, index) => {
    if (index > 0 && page - sorted[index - 1] > 1) {
      pages.push("gap");
    }
    pages.push(page);
  });
  return pages;
}

function shouldRenderThumbnail(page, currentPage, expanded, numPages) {
  if (!expanded || numPages <= 40) {
    return true;
  }
  return page === 1 || page === numPages || Math.abs(page - currentPage) <= 3;
}

function materialFileType(material) {
  const fileType = String(material?.file_type || "").toLowerCase();
  if (fileType === "markdown" || fileType === "md") {
    return "markdown";
  }
  const fileName = String(material?.file_name || "").toLowerCase();
  if (fileName.endsWith(".md") || fileName.endsWith(".markdown")) {
    return "markdown";
  }
  return "pdf";
}

async function copyTextToClipboard(text) {
  if (!text) {
    return;
  }
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Fall back to the hidden textarea path below.
    }
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}
