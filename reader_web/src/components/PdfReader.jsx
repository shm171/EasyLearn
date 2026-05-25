import { useEffect, useRef, useState } from "react";
import {
  Bookmark,
  BookmarkPlus,
  ChevronLeft,
  ChevronRight,
  FileUp,
  Flag,
  Home,
  Minimize2,
  RefreshCw,
  Rows3,
  Search
} from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { getPdfUrl } from "../api/client.js";
import { getSelectedText } from "../utils/selection.js";
import ContextMenu from "./ContextMenu.jsx";

const READER_MARKS_STORAGE_PREFIX = "easylearn.reader.nav";
const MAX_BOOKMARKS = 30;

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
  const [readerMarks, setReaderMarks] = useState(createEmptyReaderMarks);
  const [bodyPageInput, setBodyPageInput] = useState("");

  useEffect(() => {
    setNumPages(0);
    setLoadError("");
    setReaderMarks(loadReaderMarks(courseId));
    setBodyPageInput("");
    onPageChange(1);
    onPageInfo(0);
  }, [courseId]);

  function goToPage(nextPage) {
    const bounded = Math.min(Math.max(nextPage, 1), numPages || 1);
    onPageChange(bounded);
  }

  useEffect(() => {
    if (!courseId || !numPages) {
      return;
    }
    setReaderMarks((current) => {
      const next = sanitizeReaderMarks(current, numPages);
      if (readerMarksEqual(current, next)) {
        return current;
      }
      saveReaderMarks(courseId, next);
      return next;
    });
  }, [courseId, numPages]);

  useEffect(() => {
    function handleReaderShortcut(event) {
      if (event.defaultPrevented || isEditableShortcutTarget(event.target)) {
        return;
      }

      if (
        event.key === "Tab" &&
        !event.shiftKey &&
        !event.altKey &&
        !event.ctrlKey &&
        !event.metaKey &&
        readerMarks.bodyStartPage
      ) {
        event.preventDefault();
        goToPage(readerMarks.bodyStartPage);
        return;
      }

      if (
        event.altKey &&
        !event.ctrlKey &&
        !event.metaKey &&
        /^[1-9]$/.test(event.key)
      ) {
        const bookmark = readerMarks.bookmarks[Number(event.key) - 1];
        if (bookmark) {
          event.preventDefault();
          goToPage(bookmark.page);
        }
      }
    }

    window.addEventListener("keydown", handleReaderShortcut);
    return () => window.removeEventListener("keydown", handleReaderShortcut);
  }, [readerMarks, numPages]);

  function updateReaderMarks(updater) {
    if (!courseId) {
      return;
    }
    setReaderMarks((current) => {
      const next = sanitizeReaderMarks(updater(current), numPages);
      saveReaderMarks(courseId, next);
      return next;
    });
  }

  function markCurrentAsBodyStart() {
    updateReaderMarks((current) => ({
      ...current,
      bodyStartPage: currentPage
    }));
    setBodyPageInput("1");
  }

  function jumpToBodyStart() {
    if (readerMarks.bodyStartPage) {
      goToPage(readerMarks.bodyStartPage);
    }
  }

  function jumpToBodyPage() {
    const bodyPage = Number(bodyPageInput);
    if (!readerMarks.bodyStartPage || !Number.isInteger(bodyPage) || bodyPage < 1) {
      return;
    }
    goToPage(readerMarks.bodyStartPage + bodyPage - 1);
  }

  function addCurrentPageBookmark() {
    updateReaderMarks((current) => addBookmark(current, currentPage));
  }

  function jumpToBookmark(bookmarkId) {
    const bookmark = readerMarks.bookmarks.find((item) => item.id === bookmarkId);
    if (bookmark) {
      goToPage(bookmark.page);
    }
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
            readerMarks={readerMarks}
            bodyPageInput={bodyPageInput}
            onBodyPageInputChange={setBodyPageInput}
            onMarkBodyStart={markCurrentAsBodyStart}
            onJumpBodyStart={jumpToBodyStart}
            onJumpBodyPage={jumpToBodyPage}
            onAddBookmark={addCurrentPageBookmark}
            onJumpBookmark={jumpToBookmark}
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
    </section>
  );
}

function ThumbnailRail({
  numPages,
  currentPage,
  onPageSelect,
  readerMarks,
  bodyPageInput,
  onBodyPageInputChange,
  onMarkBodyStart,
  onJumpBodyStart,
  onJumpBodyPage,
  onAddBookmark,
  onJumpBookmark
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
      <ReaderNavPanel
        numPages={numPages}
        currentPage={currentPage}
        readerMarks={readerMarks}
        bodyPageInput={bodyPageInput}
        onBodyPageInputChange={onBodyPageInputChange}
        onMarkBodyStart={onMarkBodyStart}
        onJumpBodyStart={onJumpBodyStart}
        onJumpBodyPage={onJumpBodyPage}
        onAddBookmark={onAddBookmark}
        onJumpBookmark={onJumpBookmark}
      />
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

function ReaderNavPanel({
  numPages,
  currentPage,
  readerMarks,
  bodyPageInput,
  onBodyPageInputChange,
  onMarkBodyStart,
  onJumpBodyStart,
  onJumpBodyPage,
  onAddBookmark,
  onJumpBookmark
}) {
  const bodyStartPage = readerMarks.bodyStartPage;
  const bodyMaxPage = bodyStartPage ? Math.max(1, numPages - bodyStartPage + 1) : 0;
  const currentBodyPage = bodyStartPage ? currentPage - bodyStartPage + 1 : null;
  const currentBodyLabel = bodyStartPage
    ? currentBodyPage >= 1
      ? `正文第 ${currentBodyPage} 页`
      : `正文前 ${Math.abs(currentBodyPage) + 1} 页`
    : "未标记正文首页";
  const bookmarks = readerMarks.bookmarks;

  return (
    <section className="reader-nav-card" aria-label="正文页码与书签">
      <div className="reader-nav-head">
        <strong>正文 / 书签</strong>
        <small>{bodyStartPage ? `正文首页：第 ${bodyStartPage} 页 · ${currentBodyLabel}` : currentBodyLabel}</small>
      </div>
      <div className="reader-nav-actions">
        <button
          type="button"
          className="reader-nav-button primary"
          onClick={onMarkBodyStart}
          title="标记当前页面为正文第一页"
        >
          <Flag size={14} />
          <span>标为正文首页</span>
        </button>
        <button
          type="button"
          className="reader-nav-button"
          onClick={onJumpBodyStart}
          disabled={!bodyStartPage}
          title="跳转正文第一页，快捷键 Tab"
        >
          <Home size={14} />
          <span>回正文首页</span>
        </button>
      </div>
      <form
        className="body-jump-form"
        onSubmit={(event) => {
          event.preventDefault();
          onJumpBodyPage();
        }}
      >
        <input
          value={bodyPageInput}
          inputMode="numeric"
          pattern="[0-9]*"
          placeholder={bodyStartPage ? "正文页" : "先标正文"}
          aria-label="输入正文页码"
          disabled={!bodyStartPage}
          onChange={(event) => onBodyPageInputChange(cleanNumericInput(event.target.value))}
        />
        <button
          type="submit"
          disabled={!bodyStartPage || !bodyPageInput}
          title={bodyStartPage ? `跳转正文页码，范围 1-${bodyMaxPage}` : "请先标记正文首页"}
        >
          <Search size={14} />
          <span>跳</span>
        </button>
      </form>
      <button
        type="button"
        className="reader-nav-button"
        onClick={onAddBookmark}
        title="添加当前页面为书签"
      >
        <BookmarkPlus size={14} />
        <span>添加书签</span>
      </button>
      <label className="bookmark-select-label">
        <Bookmark size={13} />
        <select
          value=""
          aria-label="跳转到指定书签"
          disabled={bookmarks.length === 0}
          onChange={(event) => onJumpBookmark(event.target.value)}
        >
          <option value="">{bookmarks.length ? "跳转书签" : "暂无书签"}</option>
          {bookmarks.map((bookmark, index) => (
            <option key={bookmark.id} value={bookmark.id}>
              {index + 1}. 第 {bookmark.page} 页{formatBodyPage(bookmark.page, bodyStartPage)}
            </option>
          ))}
        </select>
      </label>
      <div className="reader-shortcuts" title="Tab 跳转正文第一页；Alt + 数字 1-9 跳转对应书签">
        Tab 回正文 · Alt+1-9 书签
      </div>
    </section>
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

function createEmptyReaderMarks() {
  return {
    bodyStartPage: null,
    bookmarks: []
  };
}

function loadReaderMarks(courseId) {
  if (!courseId || typeof window === "undefined") {
    return createEmptyReaderMarks();
  }
  try {
    const raw = window.localStorage.getItem(readerMarksStorageKey(courseId));
    if (!raw) {
      return createEmptyReaderMarks();
    }
    return sanitizeReaderMarks(JSON.parse(raw));
  } catch {
    return createEmptyReaderMarks();
  }
}

function saveReaderMarks(courseId, marks) {
  if (!courseId || typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(readerMarksStorageKey(courseId), JSON.stringify(marks));
  } catch {
    // Reading markers are a convenience layer; PDF reading should keep working if storage is unavailable.
  }
}

function readerMarksStorageKey(courseId) {
  return `${READER_MARKS_STORAGE_PREFIX}.${courseId}`;
}

function sanitizeReaderMarks(value, numPages = 0) {
  const maxPage = Number.isInteger(numPages) && numPages > 0 ? numPages : Number.MAX_SAFE_INTEGER;
  const bodyStartPage = normalizePageNumber(value?.bodyStartPage, maxPage);
  const seenPages = new Set();
  const bookmarks = [];

  if (Array.isArray(value?.bookmarks)) {
    for (const [index, bookmark] of value.bookmarks.entries()) {
      const page = normalizePageNumber(bookmark?.page, maxPage);
      if (!page || seenPages.has(page)) {
        continue;
      }
      seenPages.add(page);
      bookmarks.push({
        id: normalizeBookmarkId(bookmark?.id, index, page),
        page,
        createdAt: Number.isFinite(bookmark?.createdAt) ? bookmark.createdAt : index
      });
      if (bookmarks.length >= MAX_BOOKMARKS) {
        break;
      }
    }
  }

  return { bodyStartPage, bookmarks };
}

function normalizePageNumber(value, maxPage) {
  const page = Number(value);
  if (!Number.isInteger(page) || page < 1 || page > maxPage) {
    return null;
  }
  return page;
}

function normalizeBookmarkId(value, index, page) {
  const text = typeof value === "string" ? value.trim() : "";
  return text || `bookmark_${page}_${index}`;
}

function readerMarksEqual(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function addBookmark(marks, page) {
  const bookmarks = marks.bookmarks.filter((bookmark) => bookmark.page !== page);
  const createdAt = Date.now();
  return {
    ...marks,
    bookmarks: [
      ...bookmarks,
      {
        id: `bookmark_${createdAt}_${page}`,
        page,
        createdAt
      }
    ].slice(-MAX_BOOKMARKS)
  };
}

function cleanNumericInput(value) {
  return value.replace(/\D/g, "").slice(0, 5);
}

function formatBodyPage(page, bodyStartPage) {
  if (!bodyStartPage || page < bodyStartPage) {
    return "";
  }
  return ` · 正文 ${page - bodyStartPage + 1}`;
}

function isEditableShortcutTarget(target) {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tagName = target.tagName;
  return (
    target.isContentEditable ||
    tagName === "INPUT" ||
    tagName === "TEXTAREA" ||
    tagName === "SELECT" ||
    Boolean(target.closest(".cm-editor"))
  );
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
