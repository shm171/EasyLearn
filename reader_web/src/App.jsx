import { useEffect, useMemo, useRef, useState } from "react";
import { BookOpen, FileUp, GripVertical, KeyRound, MessageSquareText, PanelRightOpen, X } from "lucide-react";
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
import ImportPdfDialog from "./components/ImportPdfDialog.jsx";
import PageRangeTool from "./components/PageRangeTool.jsx";
import PdfReader from "./components/PdfReader.jsx";

const emptyPanel = {
  actionLabel: "",
  selectedText: "",
  loading: false,
  error: "",
  result: null
};

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
  const [rangeOpen, setRangeOpen] = useState(false);
  const [rangePosition, setRangePosition] = useState(() => {
    if (typeof window === "undefined") {
      return { x: 1040, y: 150 };
    }
    return { x: Math.max(20, window.innerWidth - 470), y: 150 };
  });
  const dragState = useRef(null);

  const activeCourseId = useMemo(
    () => manualCourseId.trim() || selectedCourseId,
    [manualCourseId, selectedCourseId]
  );

  useEffect(() => {
    refreshMaterials();
  }, []);

  useEffect(() => {
    if (!rangeOpen || typeof window === "undefined") {
      return;
    }
    setRangePosition((position) => ({
      x: clamp(position.x, 12, window.innerWidth - Math.min(420, window.innerWidth - 24) - 12),
      y: clamp(position.y, 86, window.innerHeight - Math.min(680, window.innerHeight - 110) - 12)
    }));
  }, [rangeOpen]);

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
      actionLabel: "导入本地 PDF",
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

  function startPanel(actionLabel, selectedText = "") {
    setPanel({
      actionLabel,
      selectedText,
      loading: true,
      error: "",
      result: null
    });
  }

  function finishPanel(result) {
    setPanel((current) => ({
      ...current,
      loading: false,
      error: "",
      result
    }));
  }

  function failPanel(error) {
    setPanel((current) => ({
      ...current,
      loading: false,
      error,
      result: null
    }));
  }

  function startFloatingDrag(event, toggleOnClick = false) {
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    dragState.current = {
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      startX: event.clientX,
      startY: event.clientY,
      moved: false,
      toggleOnClick
    };
    window.addEventListener("pointermove", handleFloatingMove);
    window.addEventListener("pointerup", handleFloatingUp, { once: true });
  }

  function handleFloatingMove(event) {
    const state = dragState.current;
    if (!state) {
      return;
    }
    const moved = Math.abs(event.clientX - state.startX) + Math.abs(event.clientY - state.startY) > 6;
    state.moved = state.moved || moved;
    const width = rangeOpen ? 420 : 64;
    const height = rangeOpen ? 520 : 64;
    setRangePosition({
      x: clamp(event.clientX - state.offsetX, 12, window.innerWidth - width - 12),
      y: clamp(event.clientY - state.offsetY, 86, window.innerHeight - height - 12)
    });
  }

  function handleFloatingUp() {
    const state = dragState.current;
    window.removeEventListener("pointermove", handleFloatingMove);
    dragState.current = null;
    if (state?.toggleOnClick && !state.moved) {
      setRangeOpen((open) => !open);
    }
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
        startPanel("结合当前页问 AI");
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
        failPanel("请先选中 PDF 中的文字。");
        return;
      }

      if (action === "explain_code") {
        startPanel("解释选中代码", selectedText);
        finishPanel(await explainCodeSelection(basePayload));
        return;
      }

      if (action === "generate_quiz") {
        startPanel("根据选中文字生成练习题", selectedText);
        finishPanel(await generateQuizFromSelection({ ...basePayload, action: "generate_quiz" }));
        return;
      }

      startPanel(action === "summarize" ? "总结选中文字" : "解释选中文字", selectedText);
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
          <span>EasyLearn PDF 阅读器</span>
        </div>
        <button type="button" className="primary-button import-top-button" onClick={() => setImportOpen(true)}>
          <FileUp size={18} />
          <span>导入本地 PDF</span>
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
              <strong>{activeCourseId ? `正在阅读：${activeCourseId}` : "先导入或选择一个 PDF"}</strong>
              <span>{numPages ? `共 ${numPages} 页` : "本地 PDF 阅读与 AI 检索"}</span>
            </div>
            <button type="button" className="secondary-button" onClick={() => setImportOpen(true)}>
              <FileUp size={17} />
              <span>导入 PDF</span>
            </button>
          </section>
          <PdfReader
            courseId={activeCourseId}
            currentPage={currentPage}
            onPageChange={setCurrentPage}
            onPageInfo={setNumPages}
            onContextAction={handleContextAction}
            onImport={() => setImportOpen(true)}
            onRefresh={refreshMaterials}
          />
        </div>
        <AiSidePanel panel={panel} />
      </main>
      <div
        className={`floating-range${rangeOpen ? " open" : ""}`}
        style={{ left: rangePosition.x, top: rangePosition.y }}
      >
        {rangeOpen ? (
          <section className="floating-range-card">
            <div className="floating-range-head" onPointerDown={(event) => startFloatingDrag(event)}>
              <GripVertical size={18} />
              <div>
                <strong>页面问答</strong>
                <span>拖动这里调整位置</span>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setRangeOpen(false)}
                title="关闭页面问答"
              >
                <X size={17} />
              </button>
            </div>
            <PageRangeTool
              courseId={activeCourseId}
              currentPage={currentPage}
              totalPages={numPages}
              onStart={(label) => startPanel(label)}
              onResult={finishPanel}
              onError={failPanel}
            />
          </section>
        ) : (
          <button
            type="button"
            className="floating-range-button"
            onPointerDown={(event) => startFloatingDrag(event, true)}
            title="页面问答"
          >
            <MessageSquareText size={24} />
            <span>页问</span>
          </button>
        )}
      </div>
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
