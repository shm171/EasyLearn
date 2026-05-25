import { useEffect, useRef, useState } from "react";
import { GripVertical, Layers3, MessageSquareText, PanelTop, X } from "lucide-react";
import PageRangeTool from "./PageRangeTool.jsx";
import ReaderPageManager from "./ReaderPageManager.jsx";

export default function FloatingToolbox({
  courseId,
  currentPage,
  totalPages,
  onPageChange,
  onStart,
  onResult,
  onError
}) {
  const [open, setOpen] = useState(false);
  const [activeTool, setActiveTool] = useState("range");
  const [position, setPosition] = useState(() => {
    if (typeof window === "undefined") {
      return { x: 1040, y: 150 };
    }
    return { x: Math.max(20, window.innerWidth - 450), y: 150 };
  });
  const dragState = useRef(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    setPosition((current) => clampToolboxPosition(current, open));
  }, [open]);

  function startDrag(event, toggleOnClick = false) {
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
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleUp, { once: true });
  }

  function handleMove(event) {
    const state = dragState.current;
    if (!state) {
      return;
    }
    state.moved = state.moved || Math.abs(event.clientX - state.startX) + Math.abs(event.clientY - state.startY) > 6;
    const { width, height } = getToolboxSize(open);
    setPosition({
      x: clamp(event.clientX - state.offsetX, 12, window.innerWidth - width - 12),
      y: clamp(event.clientY - state.offsetY, 86, window.innerHeight - height - 12)
    });
  }

  function handleUp() {
    const state = dragState.current;
    window.removeEventListener("pointermove", handleMove);
    dragState.current = null;
    if (state?.toggleOnClick && !state.moved) {
      setOpen((value) => !value);
    }
  }

  return (
    <div className={`floating-toolbox${open ? " open" : ""}`} style={{ left: position.x, top: position.y }}>
      {open ? (
        <section className="toolbox-card">
          <div className="toolbox-head" onPointerDown={(event) => startDrag(event)}>
            <GripVertical size={18} />
            <div>
              <strong>工具箱</strong>
              <span>页问和页面管理</span>
            </div>
            <button type="button" className="icon-button" onClick={() => setOpen(false)} title="关闭工具箱">
              <X size={17} />
            </button>
          </div>
          <div className="toolbox-tabs" role="tablist" aria-label="工具箱">
            <button
              type="button"
              className={activeTool === "range" ? "active" : ""}
              onClick={() => setActiveTool("range")}
              role="tab"
              aria-selected={activeTool === "range"}
            >
              <MessageSquareText size={16} />
              <span>页面问答</span>
            </button>
            <button
              type="button"
              className={activeTool === "manager" ? "active" : ""}
              onClick={() => setActiveTool("manager")}
              role="tab"
              aria-selected={activeTool === "manager"}
            >
              <PanelTop size={16} />
              <span>页面管理</span>
            </button>
          </div>
          <div className={`toolbox-panel ${activeTool}`} key={activeTool}>
            {activeTool === "range" ? (
              <PageRangeTool
                courseId={courseId}
                currentPage={currentPage}
                totalPages={totalPages}
                onStart={onStart}
                onResult={onResult}
                onError={onError}
              />
            ) : (
              <ReaderPageManager
                courseId={courseId}
                currentPage={currentPage}
                totalPages={totalPages}
                onPageChange={onPageChange}
              />
            )}
          </div>
        </section>
      ) : (
        <button
          type="button"
          className="toolbox-button"
          onPointerDown={(event) => startDrag(event, true)}
          title="工具箱"
        >
          <Layers3 size={24} />
          <span>工具</span>
        </button>
      )}
    </div>
  );
}

function clampToolboxPosition(position, open) {
  const { width, height } = getToolboxSize(open);
  return {
    x: clamp(position.x, 12, window.innerWidth - width - 12),
    y: clamp(position.y, 86, window.innerHeight - height - 12)
  };
}

function getToolboxSize(open) {
  if (!open) {
    return { width: 66, height: 66 };
  }
  return {
    width: Math.min(420, Math.max(280, window.innerWidth - 24)),
    height: Math.min(720, Math.max(360, window.innerHeight - 110))
  };
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), Math.max(min, max));
}
