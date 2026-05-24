import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, FileUp, Minimize2, RefreshCw, Rows3 } from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { getPdfUrl } from "../api/client.js";
import { getSelectedText } from "../utils/selection.js";
import ContextMenu from "./ContextMenu.jsx";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

export default function PdfReader({
  courseId,
  currentPage,
  onPageChange,
  onPageInfo,
  onContextAction,
  onImport,
  onRefresh
}) {
  const [numPages, setNumPages] = useState(0);
  const [loadError, setLoadError] = useState("");
  const [menu, setMenu] = useState(null);

  useEffect(() => {
    setNumPages(0);
    setLoadError("");
    onPageChange(1);
  }, [courseId]);

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
        <strong>还没有打开 PDF</strong>
        <div className="empty-actions">
          <button type="button" className="primary-button" onClick={onImport}>
            <FileUp size={18} />
            <span>导入本地 PDF</span>
          </button>
          <button type="button" className="secondary-button" onClick={onRefresh}>
            <RefreshCw size={18} />
            <span>刷新列表</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <section className="reader-shell">
      <div className="reader-toolbar">
        <button
          type="button"
          className="icon-text-button"
          onClick={() => goToPage(currentPage - 1)}
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
          onClick={() => goToPage(currentPage + 1)}
          disabled={!numPages || currentPage >= numPages}
        >
          <ChevronRight size={18} />
          <span>下一页</span>
        </button>
      </div>

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
            numPages={numPages}
            currentPage={currentPage}
            onPageSelect={goToPage}
          />
          <div className="pdf-stage" onContextMenu={handleContextMenu}>
          <Page
            pageNumber={currentPage}
            width={Math.min(820, Math.max(320, window.innerWidth - 700))}
            renderTextLayer
            renderAnnotationLayer
          />
          {loadError ? <div className="pdf-load-error">{loadError}</div> : null}
          </div>
        </div>
      </Document>

      {menu ? (
        <ContextMenu
          x={menu.x}
          y={menu.y}
          selectedText={menu.selectedText}
          onClose={() => setMenu(null)}
          onAction={(action) => {
            onContextAction(action, menu.selectedText);
            setMenu(null);
          }}
        />
      ) : null}
    </section>
  );
}

function ThumbnailRail({ numPages, currentPage, onPageSelect }) {
  const [expanded, setExpanded] = useState(false);
  const activeRef = useRef(null);
  const pages = expanded ? buildAllPreviewPages(numPages) : buildPreviewPages(numPages, currentPage);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
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
              {shouldRenderThumbnail(page, currentPage, expanded, numPages) ? (
                <Page
                  pageNumber={page}
                  width={104}
                  renderTextLayer={false}
                  renderAnnotationLayer={false}
                  loading={<div className="thumbnail-placeholder">{page}</div>}
                />
              ) : (
                <div className="thumbnail-placeholder compact">{page}</div>
              )}
              <span>第 {page} 页</span>
            </button>
          )
        )}
      </div>
    </aside>
  );
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
