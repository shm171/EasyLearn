import { useEffect, useState } from "react";
import { Bookmark, BookmarkPlus, Flag, Home, Search } from "lucide-react";

const READER_MARKS_STORAGE_PREFIX = "easylearn.reader.nav";
const MAX_BOOKMARKS = 30;

export default function ReaderPageManager({ courseId, currentPage, totalPages, onPageChange }) {
  const [readerMarks, setReaderMarks] = useState(createEmptyReaderMarks);
  const [bodyPageInput, setBodyPageInput] = useState("");
  const bodyStartPage = readerMarks.bodyStartPage;
  const bodyMaxPage = bodyStartPage ? Math.max(1, totalPages - bodyStartPage + 1) : 0;
  const currentBodyPage = bodyStartPage ? currentPage - bodyStartPage + 1 : null;
  const currentBodyLabel = bodyStartPage
    ? currentBodyPage >= 1
      ? `正文第 ${currentBodyPage} 页`
      : `正文前 ${Math.abs(currentBodyPage) + 1} 页`
    : "未标记正文首页";

  useEffect(() => {
    setReaderMarks(loadReaderMarks(courseId));
    setBodyPageInput("");
  }, [courseId]);

  useEffect(() => {
    if (!courseId || !totalPages) {
      return;
    }
    setReaderMarks((current) => {
      const next = sanitizeReaderMarks(current, totalPages);
      if (readerMarksEqual(current, next)) {
        return current;
      }
      saveReaderMarks(courseId, next);
      return next;
    });
  }, [courseId, totalPages]);

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
        onPageChange(readerMarks.bodyStartPage);
        return;
      }

      if (event.altKey && !event.ctrlKey && !event.metaKey && /^[1-9]$/.test(event.key)) {
        const bookmark = readerMarks.bookmarks[Number(event.key) - 1];
        if (bookmark) {
          event.preventDefault();
          onPageChange(bookmark.page);
        }
      }
    }

    window.addEventListener("keydown", handleReaderShortcut);
    return () => window.removeEventListener("keydown", handleReaderShortcut);
  }, [readerMarks, onPageChange]);

  function updateReaderMarks(updater) {
    if (!courseId) {
      return;
    }
    setReaderMarks((current) => {
      const next = sanitizeReaderMarks(updater(current), totalPages);
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
    if (bodyStartPage) {
      onPageChange(bodyStartPage);
    }
  }

  function jumpToBodyPage() {
    const bodyPage = Number(bodyPageInput);
    if (!bodyStartPage || !Number.isInteger(bodyPage) || bodyPage < 1) {
      return;
    }
    onPageChange(bodyStartPage + bodyPage - 1);
  }

  function addCurrentPageBookmark() {
    updateReaderMarks((current) => addBookmark(current, currentPage));
  }

  function jumpToBookmark(bookmarkId) {
    const bookmark = readerMarks.bookmarks.find((item) => item.id === bookmarkId);
    if (bookmark) {
      onPageChange(bookmark.page);
    }
  }

  return (
    <section className="reader-page-manager" aria-label="正文页码与书签">
      <div className="reader-manager-head">
        <div>
          <strong>页面管理</strong>
          <span>{bodyStartPage ? `正文首页：第 ${bodyStartPage} 页 · ${currentBodyLabel}` : currentBodyLabel}</span>
        </div>
        <small>Tab 回正文 · Alt+1-9 书签</small>
      </div>
      <div className="manager-action-grid">
        <button type="button" className="reader-nav-button primary" onClick={markCurrentAsBodyStart}>
          <Flag size={14} />
          <span>标为正文首页</span>
        </button>
        <button type="button" className="reader-nav-button" onClick={jumpToBodyStart} disabled={!bodyStartPage}>
          <Home size={14} />
          <span>回正文首页</span>
        </button>
      </div>
      <form
        className="body-jump-form"
        onSubmit={(event) => {
          event.preventDefault();
          jumpToBodyPage();
        }}
      >
        <input
          value={bodyPageInput}
          inputMode="numeric"
          pattern="[0-9]*"
          placeholder={bodyStartPage ? "正文页" : "先标正文"}
          aria-label="输入正文页码"
          disabled={!bodyStartPage}
          onChange={(event) => setBodyPageInput(cleanNumericInput(event.target.value))}
        />
        <button
          type="submit"
          disabled={!bodyStartPage || !bodyPageInput}
          title={bodyStartPage ? `跳转正文页码，范围 1-${bodyMaxPage}` : "请先标记正文首页"}
        >
          <Search size={14} />
          <span>跳转</span>
        </button>
      </form>
      <button type="button" className="reader-nav-button" onClick={addCurrentPageBookmark}>
        <BookmarkPlus size={14} />
        <span>添加当前页为书签</span>
      </button>
      <label className="bookmark-select-label">
        <Bookmark size={14} />
        <select
          value=""
          aria-label="跳转到指定书签"
          disabled={readerMarks.bookmarks.length === 0}
          onChange={(event) => jumpToBookmark(event.target.value)}
        >
          <option value="">{readerMarks.bookmarks.length ? "跳转书签" : "暂无书签"}</option>
          {readerMarks.bookmarks.map((bookmark, index) => (
            <option key={bookmark.id} value={bookmark.id}>
              {index + 1}. 第 {bookmark.page} 页{formatBodyPage(bookmark.page, bodyStartPage)}
            </option>
          ))}
        </select>
      </label>
    </section>
  );
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
    // The reader must keep working even when browser storage is blocked.
  }
}

function readerMarksStorageKey(courseId) {
  return `${READER_MARKS_STORAGE_PREFIX}.${courseId}`;
}

function sanitizeReaderMarks(value, totalPages = 0) {
  const maxPage = Number.isInteger(totalPages) && totalPages > 0 ? totalPages : Number.MAX_SAFE_INTEGER;
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
