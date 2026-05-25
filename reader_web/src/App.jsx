import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BookOpen, FileUp, KeyRound, PanelRightOpen } from "lucide-react";
import {
  askCurrentPage,
  askSelection,
  explainCodeSelection,
  generateQuizFromSelection,
  listMaterials
} from "./api/client.js";
import ApiConfigDialog from "./components/ApiConfigDialog.jsx";
import AiSidePanel from "./components/AiSidePanel.jsx";
import CourseSelector from "./components/CourseSelector.jsx";
import FloatingToolbox from "./components/FloatingToolbox.jsx";
import ImportPdfDialog from "./components/ImportPdfDialog.jsx";
import PdfReader from "./components/PdfReader.jsx";

const emptyPanel = {
  actionLabel: "",
  selectedText: "",
  loading: false,
  error: "",
  result: null,
  progress: null
};

const DEFAULT_ANNOTATION_SETTINGS = {
  enabled: false,
  tool: "pen",
  color: "#ef4444",
  strokeWidth: 4
};

const ANNOTATION_STORAGE_PREFIX = "easylearn.reader.annotations";
const MAX_ANNOTATIONS_PER_PAGE = 500;
const MAX_POINTS_PER_ANNOTATION = 900;

export default function App() {
  const [materials, setMaterials] = useState([]);
  const [materialsLoading, setMaterialsLoading] = useState(false);
  const [materialsError, setMaterialsError] = useState("");
  const [selectedCourseId, setSelectedCourseId] = useState("");
  const [manualCourseId, setManualCourseId] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [numPages, setNumPages] = useState(0);
  const [panel, setPanel] = useState(emptyPanel);
  const [importOpen, setImportOpen] = useState(false);
  const [apiConfigOpen, setApiConfigOpen] = useState(false);
  const [annotationSettings, setAnnotationSettings] = useState(DEFAULT_ANNOTATION_SETTINGS);
  const [annotationsByPage, setAnnotationsByPage] = useState({});
  const [annotationsDirty, setAnnotationsDirty] = useState(false);
  const progressTimerRef = useRef(null);

  const activeCourseId = useMemo(
    () => manualCourseId.trim() || selectedCourseId,
    [manualCourseId, selectedCourseId]
  );
  const activeMaterial = useMemo(
    () => materials.find((material) => material.course_id === activeCourseId) || null,
    [activeCourseId, materials]
  );
  const activeMaterialLabel = activeMaterial?.file_type === "markdown" ? "Markdown" : "PDF";
  const currentPageAnnotations = annotationsByPage[String(currentPage)] || [];

  const goToReaderPage = useCallback(
    (page) => {
      setCurrentPage(clamp(page, 1, numPages || 1));
    },
    [numPages]
  );

  const updateCurrentPageAnnotations = useCallback(
    (nextAnnotations) => {
      setAnnotationsByPage((current) => ({
        ...current,
        [String(currentPage)]: trimPageAnnotations(nextAnnotations)
      }));
      setAnnotationsDirty(true);
    },
    [currentPage]
  );

  const undoCurrentPageAnnotation = useCallback(() => {
    setAnnotationsByPage((current) => {
      const pageKey = String(currentPage);
      const pageAnnotations = current[pageKey] || [];
      if (!pageAnnotations.length) {
        return current;
      }
      setAnnotationsDirty(true);
      return {
        ...current,
        [pageKey]: pageAnnotations.slice(0, -1)
      };
    });
  }, [currentPage]);

  const clearCurrentPageAnnotations = useCallback(() => {
    setAnnotationsByPage((current) => {
      const pageKey = String(currentPage);
      const pageAnnotations = current[pageKey] || [];
      if (!pageAnnotations.length) {
        return current;
      }
      setAnnotationsDirty(true);
      return {
        ...current,
        [pageKey]: []
      };
    });
  }, [currentPage]);

  useEffect(() => {
    refreshMaterials();
  }, []);

  useEffect(() => () => clearProgressTimer(), []);

  useEffect(() => {
    setAnnotationsByPage(readSavedAnnotations(activeCourseId));
    setAnnotationsDirty(false);
  }, [activeCourseId]);

  useEffect(() => {
    function handleAnnotationShortcut(event) {
      if (!activeCourseId || event.repeat || !event.ctrlKey || !event.altKey) {
        return;
      }
      const key = event.key.toLowerCase();
      if (key === "a") {
        event.preventDefault();
        clearCurrentPageAnnotations();
      } else if (key === "z" || key === "backspace") {
        event.preventDefault();
        undoCurrentPageAnnotation();
      }
    }

    window.addEventListener("keydown", handleAnnotationShortcut);
    return () => window.removeEventListener("keydown", handleAnnotationShortcut);
  }, [activeCourseId, clearCurrentPageAnnotations, undoCurrentPageAnnotation]);

  async function refreshMaterials() {
    setMaterialsLoading(true);
    setMaterialsError("");
    try {
      const items = await listMaterials();
      setMaterials(items);
      if (!selectedCourseId && items.length > 0) {
        setSelectedCourseId(items[0].course_id);
      }
    } catch (error) {
      setMaterialsError(error.message);
    } finally {
      setMaterialsLoading(false);
    }
  }

  async function handleImported(material) {
    await refreshMaterials();
    setSelectedCourseId(material.course_id);
    setManualCourseId("");
    setCurrentPage(1);
    setPanel({
      actionLabel: "导入本地资料",
      selectedText: "",
      loading: false,
      error: "",
      result: {
        answer: `已导入并打开：${material.file_name}`,
        source_chunks: [],
        warnings: []
      }
    });
  }

  function clearProgressTimer() {
    if (progressTimerRef.current) {
      window.clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
    }
  }

  function startPanel(actionLabel, selectedText = "", progressKind = "default") {
    clearProgressTimer();
    const profile = progressProfile(progressKind);
    const startedAt = Date.now();
    setPanel({
      actionLabel,
      selectedText,
      loading: true,
      error: "",
      result: null,
      progress: {
        value: profile.start,
        message: profile.stages[0]?.message || "准备处理"
      }
    });
    progressTimerRef.current = window.setInterval(() => {
      setPanel((current) => {
        if (!current.loading) {
          return current;
        }
        const elapsed = Date.now() - startedAt;
        const expected = profile.start + (elapsed / profile.estimateMs) * (profile.ceiling - profile.start);
        const value = Math.min(profile.ceiling, Math.max(current.progress?.value || profile.start, expected));
        return {
          ...current,
          progress: {
            value,
            message: progressMessage(profile, value)
          }
        };
      });
    }, 350);
  }

  function finishPanel(result) {
    clearProgressTimer();
    setPanel((current) => ({
      ...current,
      loading: false,
      error: "",
      result,
      progress: { value: 1, message: "已完成" }
    }));
  }

  function failPanel(error) {
    clearProgressTimer();
    setPanel((current) => ({
      ...current,
      loading: false,
      error,
      result: null,
      progress: { value: 1, message: "处理失败" }
    }));
  }

  function saveAnnotations() {
    if (!activeCourseId) {
      return;
    }
    writeSavedAnnotations(activeCourseId, annotationsByPage);
    setAnnotationsDirty(false);
  }

  async function handleContextAction(action, selectedText) {
    if (!activeCourseId) {
      failPanel("请先选择或输入 course_id。");
      return;
    }

    const basePayload = {
      course_id: activeCourseId,
      selected_text: selectedText,
      page_number: currentPage
    };

    try {
      if (action === "ask_current_page") {
        const question = window.prompt("想问当前页什么？", "这一页主要讲了什么？");
        if (!question) {
          return;
        }
        startPanel("结合当前页问 AI", "", "ask");
        finishPanel(
          await askCurrentPage({
            course_id: activeCourseId,
            page_number: currentPage,
            question
          })
        );
        return;
      }

      if (!selectedText) {
        failPanel("请先选中资料中的文字。");
        return;
      }

      if (action === "explain_code") {
        startPanel("解释选中代码", selectedText, "ask");
        finishPanel(await explainCodeSelection(basePayload));
        return;
      }

      if (action === "generate_quiz") {
        startPanel("根据选中文字生成练习题", selectedText, "quiz");
        finishPanel(await generateQuizFromSelection({ ...basePayload, action: "generate_quiz" }));
        return;
      }

      startPanel(action === "summarize" ? "总结选中文字" : "解释选中文字", selectedText, action);
      finishPanel(await askSelection({ ...basePayload, action }));
    } catch (error) {
      failPanel(error.message);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <BookOpen size={22} />
          <span>EasyLearn 资料阅读器</span>
        </div>
        <button type="button" className="primary-button import-top-button" onClick={() => setImportOpen(true)}>
          <FileUp size={18} />
          <span>导入本地资料</span>
        </button>
        <button type="button" className="secondary-button api-top-button" onClick={() => setApiConfigOpen(true)}>
          <KeyRound size={18} />
          <span>API 配置</span>
        </button>
        <CourseSelector
          materials={materials}
          selectedCourseId={selectedCourseId}
          manualCourseId={manualCourseId}
          loading={materialsLoading}
          error={materialsError}
          onSelect={(value) => {
            setSelectedCourseId(value);
            setManualCourseId("");
          }}
          onManualChange={setManualCourseId}
          onRefresh={refreshMaterials}
        />
        <div className="current-page-pill">
          <PanelRightOpen size={17} />
          <span>
            当前页 {currentPage}
            {numPages ? ` / ${numPages}` : ""}
          </span>
        </div>
      </header>

      <main className="workspace">
        <div className="reader-column">
          <section className="quick-start">
            <div>
              <strong>{activeCourseId ? `正在阅读：${activeCourseId}` : "先导入或选择一个资料"}</strong>
              <span>{numPages ? `${activeMaterialLabel} · 共 ${numPages} 页` : "本地 PDF / Markdown 阅读与 AI 检索"}</span>
            </div>
            <button type="button" className="secondary-button" onClick={() => setImportOpen(true)}>
              <FileUp size={17} />
              <span>导入资料</span>
            </button>
          </section>
          <PdfReader
            courseId={activeCourseId}
            material={activeMaterial}
            currentPage={currentPage}
            annotationSettings={annotationSettings}
            pageAnnotations={currentPageAnnotations}
            onPageChange={setCurrentPage}
            onPageInfo={setNumPages}
            onPageAnnotationsChange={updateCurrentPageAnnotations}
            onContextAction={handleContextAction}
            onImport={() => setImportOpen(true)}
            onRefresh={refreshMaterials}
          />
        </div>
        <AiSidePanel panel={panel} />
      </main>
      <FloatingToolbox
        courseId={activeCourseId}
        currentPage={currentPage}
        totalPages={numPages}
        onPageChange={goToReaderPage}
        onStart={(label, progressKind) => startPanel(label, "", progressKind)}
        onResult={finishPanel}
        onError={failPanel}
        annotationSettings={annotationSettings}
        onAnnotationSettingsChange={setAnnotationSettings}
        annotationCount={currentPageAnnotations.length}
        annotationsDirty={annotationsDirty}
        onUndoAnnotation={undoCurrentPageAnnotation}
        onClearPageAnnotations={clearCurrentPageAnnotations}
        onSaveAnnotations={saveAnnotations}
      />
      <ImportPdfDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={handleImported}
      />
      <ApiConfigDialog open={apiConfigOpen} onClose={() => setApiConfigOpen(false)} />
    </div>
  );
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), Math.max(min, max));
}

function progressProfile(kind) {
  const profiles = {
    ask: {
      start: 0.08,
      ceiling: 0.9,
      estimateMs: 8000,
      stages: [
        { at: 0.08, message: "初始化检索" },
        { at: 0.22, message: "检索相关页面" },
        { at: 0.42, message: "压缩上下文" },
        { at: 0.58, message: "AI 正在回答" },
        { at: 0.82, message: "整理回答结构" }
      ]
    },
    summarize: {
      start: 0.08,
      ceiling: 0.9,
      estimateMs: 9000,
      stages: [
        { at: 0.08, message: "初始化总结任务" },
        { at: 0.24, message: "检索章节重点" },
        { at: 0.42, message: "压缩总结上下文" },
        { at: 0.62, message: "AI 正在总结" },
        { at: 0.84, message: "整理层次结构" }
      ]
    },
    quiz: {
      start: 0.08,
      ceiling: 0.92,
      estimateMs: 11000,
      stages: [
        { at: 0.08, message: "初始化出题任务" },
        { at: 0.22, message: "检索出题依据" },
        { at: 0.40, message: "分配题型和难度" },
        { at: 0.60, message: "AI 正在生成题目" },
        { at: 0.84, message: "解析答题结构" }
      ]
    },
    "key-points": {
      start: 0.08,
      ceiling: 0.9,
      estimateMs: 7500,
      stages: [
        { at: 0.08, message: "初始化重点提取" },
        { at: 0.26, message: "检索关键页面" },
        { at: 0.48, message: "筛选学习重点" },
        { at: 0.70, message: "AI 正在整理" },
        { at: 0.86, message: "压缩结果" }
      ]
    },
    explain: {
      start: 0.10,
      ceiling: 0.88,
      estimateMs: 6500,
      stages: [
        { at: 0.10, message: "读取选中内容" },
        { at: 0.34, message: "补充页面上下文" },
        { at: 0.56, message: "AI 正在解释" },
        { at: 0.80, message: "整理回答结构" }
      ]
    }
  };
  const normalizedKind = kind === "summary" ? "summarize" : kind;
  return profiles[normalizedKind] || profiles.ask;
}

function progressMessage(profile, value) {
  let message = profile.stages[0]?.message || "处理中";
  for (const stage of profile.stages) {
    if (value >= stage.at) {
      message = stage.message;
    }
  }
  return message;
}

function readSavedAnnotations(courseId) {
  if (!courseId) {
    return {};
  }
  try {
    const raw = window.localStorage.getItem(annotationStorageKey(courseId));
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw);
    return normalizeAnnotationsByPage(parsed.pages || {});
  } catch {
    return {};
  }
}

function writeSavedAnnotations(courseId, annotationsByPage) {
  try {
    window.localStorage.setItem(
      annotationStorageKey(courseId),
      JSON.stringify({
        version: 1,
        savedAt: new Date().toISOString(),
        pages: normalizeAnnotationsByPage(annotationsByPage)
      })
    );
  } catch {
    // Browser storage can be unavailable; the in-memory annotations still stay usable.
  }
}

function annotationStorageKey(courseId) {
  return `${ANNOTATION_STORAGE_PREFIX}.${courseId}`;
}

function normalizeAnnotationsByPage(value) {
  if (!value || typeof value !== "object") {
    return {};
  }
  return Object.fromEntries(
    Object.entries(value)
      .map(([page, annotations]) => [page, Array.isArray(annotations) ? trimPageAnnotations(annotations) : []])
      .filter(([page]) => Number(page) >= 1)
  );
}

function trimPageAnnotations(annotations) {
  return annotations.slice(-MAX_ANNOTATIONS_PER_PAGE).map((operation) => {
    if (
      (operation.tool === "pen" || operation.tool === "eraser") &&
      Array.isArray(operation.points) &&
      operation.points.length > MAX_POINTS_PER_ANNOTATION
    ) {
      return { ...operation, points: operation.points.slice(-MAX_POINTS_PER_ANNOTATION) };
    }
    return operation;
  });
}
