import { useEffect, useRef, useState } from "react";

const MAX_POINTS_PER_STROKE = 900;
const MAX_ANNOTATIONS_PER_PAGE = 500;
const MIN_TEXT_BOX_PX = { width: 120, height: 44 };
const LEGACY_TEXT_BOX = { width: 0.08, height: 0.045 };

export default function ReaderAnnotationLayer({
  enabled,
  settings,
  annotations,
  onChange
}) {
  const canvasRef = useRef(null);
  const drawingRef = useRef(null);
  const movingRef = useRef(null);
  const annotationsRef = useRef(annotations);
  const selectedIdsRef = useRef([]);
  const selectedRectRef = useRef(null);
  const movingPreviewRef = useRef(null);
  const sizeRef = useRef({ width: 0, height: 0 });
  const previewRef = useRef(null);
  const animationFrameRef = useRef(null);
  const moveBoxRef = useRef(null);
  const textAreaRef = useRef(null);
  const textDraftRef = useRef(null);
  const textValueRef = useRef("");
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [selectedIds, setSelectedIds] = useState([]);
  const [textDraft, setTextDraft] = useState(null);
  const [textValue, setTextValue] = useState("");

  useEffect(() => {
    annotationsRef.current = annotations;
    selectedIdsRef.current = selectedIdsRef.current.filter((id) =>
      annotations.some((operation) => operation.id === id)
    );
    if (selectedIdsRef.current.length !== selectedIds.length) {
      setSelectedIds(selectedIdsRef.current);
    }
    if (!selectedIdsRef.current.length && drawingRef.current?.tool !== "selection") {
      selectedRectRef.current = null;
      hideMoveBox();
    }
    scheduleDraw();
  }, [annotations, selectedIds.length]);

  useEffect(() => {
    selectedIdsRef.current = selectedIds;
    if (!selectedIds.length && drawingRef.current?.tool !== "selection") {
      selectedRectRef.current = null;
      hideMoveBox();
    } else if (selectedRectRef.current) {
      showMoveBox(selectedRectRef.current, "selected");
    }
    scheduleDraw();
  }, [selectedIds]);

  useEffect(() => {
    textDraftRef.current = textDraft;
    if (!textDraft) {
      scheduleDraw();
      return undefined;
    }
    const frameId = window.requestAnimationFrame(() => {
      textAreaRef.current?.focus();
    });
    scheduleDraw();
    return () => window.cancelAnimationFrame(frameId);
  }, [textDraft]);

  useEffect(() => {
    textValueRef.current = textValue;
  }, [textValue]);

  useEffect(() => {
    if (settings?.tool !== "move" && selectedIdsRef.current.length) {
      setSelectedIds([]);
      selectedRectRef.current = null;
      hideMoveBox();
    }
  }, [settings?.tool]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const surface = canvas?.parentElement;
    if (!surface) {
      return undefined;
    }

    function updateSize() {
      const rect = surface.getBoundingClientRect();
      const nextSize = {
        width: Math.max(1, Math.round(rect.width)),
        height: Math.max(1, Math.round(rect.height))
      };
      sizeRef.current = nextSize;
      setSize(nextSize);
      if (selectedRectRef.current) {
        showMoveBox(selectedRectRef.current, "selected", nextSize);
      }
      scheduleDraw();
    }

    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(surface);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    sizeRef.current = size;
    scheduleDraw();
    return () => {
      if (animationFrameRef.current) {
        window.cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [size]);

  function scheduleDraw() {
    if (animationFrameRef.current) {
      window.cancelAnimationFrame(animationFrameRef.current);
    }
    animationFrameRef.current = window.requestAnimationFrame(() => {
      animationFrameRef.current = null;
      drawCanvas(
        canvasRef.current,
        sizeRef.current,
        movingPreviewRef.current || annotationsRef.current,
        previewRef.current
      );
    });
  }

  function showMoveBox(rect, mode, nextSize = sizeRef.current) {
    const box = moveBoxRef.current;
    if (!box || !rect || !nextSize.width || !nextSize.height) {
      return;
    }
    const canvasRect = rectToCanvas(rect, nextSize);
    box.dataset.mode = mode;
    box.style.display = "block";
    box.style.transform = `translate3d(${Math.round(canvasRect.x)}px, ${Math.round(canvasRect.y)}px, 0)`;
    box.style.width = `${Math.max(1, Math.round(canvasRect.width))}px`;
    box.style.height = `${Math.max(1, Math.round(canvasRect.height))}px`;
  }

  function hideMoveBox() {
    const box = moveBoxRef.current;
    if (!box) {
      return;
    }
    box.style.display = "none";
  }

  function startDrawing(event) {
    if (!enabled || !settings || event.button !== 0 || textDraftRef.current) {
      return;
    }
    event.preventDefault();
    const point = eventPoint(event, event.currentTarget);

    if (settings.tool === "move") {
      startMoveInteraction(event, point);
      return;
    }

    capturePointer(event);
    const operation = createOperation(settings, point);
    drawingRef.current = operation;
    previewRef.current = operation;
    scheduleDraw();
  }

  function startMoveInteraction(event, point) {
    const selectedBounds = getSelectionBounds(annotationsRef.current, selectedIdsRef.current);
    const selectionRect = selectedRectRef.current || selectedBounds;
    if (selectedBounds && selectionRect && pointInRect(point, inflateRect(selectionRect, 0.01))) {
      capturePointer(event);
      movingRef.current = {
        startPoint: point,
        ids: selectedIdsRef.current,
        idSet: new Set(selectedIdsRef.current),
        bounds: unionRects(selectedBounds, selectionRect),
        selectionRect,
        lastSelectionRect: selectionRect,
        originalAnnotations: annotationsRef.current,
        lastAnnotations: annotationsRef.current
      };
      return;
    }

    capturePointer(event);
    const selection = {
      id: "selection-preview",
      tool: "selection",
      start: point,
      end: point,
      color: "#176b5b",
      width: 2
    };
    setSelectedIds([]);
    selectedRectRef.current = null;
    hideMoveBox();
    drawingRef.current = selection;
    previewRef.current = null;
    showMoveBox(rectFromPoints(point, point), "selecting");
  }

  function continueDrawing(event) {
    const point = eventPoint(event, event.currentTarget);
    const moving = movingRef.current;
    if (moving) {
      event.preventDefault();
      const delta = constrainedDelta(moving.bounds, point.x - moving.startPoint.x, point.y - moving.startPoint.y);
      const translated = moving.originalAnnotations.map((operation) =>
        moving.idSet.has(operation.id) ? translateOperation(operation, delta.x, delta.y) : operation
      );
      const translatedRect = translateRect(moving.selectionRect, delta.x, delta.y);
      moving.lastSelectionRect = translatedRect;
      moving.lastAnnotations = translated;
      movingPreviewRef.current = translated;
      showMoveBox(translatedRect, "moving");
      scheduleDraw();
      return;
    }

    const operation = drawingRef.current;
    if (!operation) {
      return;
    }
    event.preventDefault();
    const updated = updateOperation(operation, point);
    drawingRef.current = updated;
    if (updated.tool === "selection") {
      showMoveBox(rectFromPoints(updated.start, updated.end), "selecting");
    } else {
      previewRef.current = updated;
      scheduleDraw();
    }
  }

  function finishDrawing(event) {
    if (movingRef.current) {
      finishMoving(event);
      return;
    }

    const operation = drawingRef.current;
    if (!operation) {
      return;
    }
    event.preventDefault();
    releasePointer(event);
    drawingRef.current = null;
    previewRef.current = null;

    if (operation.tool === "selection") {
      finishSelection(operation);
      scheduleDraw();
      return;
    }

    if (!isMeaningfulOperation(operation)) {
      scheduleDraw();
      return;
    }

    if (operation.tool === "text") {
      setTextValue("");
      setTextDraft(normalizeTextOperation(operation, sizeRef.current));
      return;
    }

    onChange(trimAnnotations([...annotationsRef.current, operation]));
    scheduleDraw();
  }

  function finishMoving(event) {
    event.preventDefault();
    releasePointer(event);
    const moving = movingRef.current;
    movingRef.current = null;
    movingPreviewRef.current = null;
    const nextAnnotations = moving?.lastAnnotations || annotationsRef.current;
    selectedRectRef.current = moving?.lastSelectionRect || selectedRectRef.current;
    annotationsRef.current = trimAnnotations(nextAnnotations);
    onChange(annotationsRef.current);
    if (selectedRectRef.current && selectedIdsRef.current.length) {
      showMoveBox(selectedRectRef.current, "selected");
    }
    scheduleDraw();
  }

  function finishSelection(operation) {
    if (!isMeaningfulOperation(operation)) {
      setSelectedIds([]);
      return;
    }
    const selectionRect = rectFromPoints(operation.start, operation.end);
    const nextIds = annotationsRef.current
      .filter((annotation) => {
        const bounds = getOperationBounds(annotation);
        return bounds && rectsIntersect(selectionRect, bounds);
      })
      .map((annotation) => annotation.id);
    selectedRectRef.current = nextIds.length ? selectionRect : null;
    setSelectedIds(nextIds);
    if (nextIds.length) {
      showMoveBox(selectionRect, "selected");
    } else {
      hideMoveBox();
    }
  }

  function commitTextDraft() {
    const draft = textDraftRef.current;
    if (!draft) {
      return;
    }
    const text = textValueRef.current.trim();
    setTextDraft(null);
    setTextValue("");
    if (!text) {
      scheduleDraw();
      return;
    }
    const operation = {
      ...draft,
      text,
      updatedAt: Date.now()
    };
    annotationsRef.current = trimAnnotations([...annotationsRef.current, operation]);
    onChange(annotationsRef.current);
    scheduleDraw();
  }

  function cancelTextDraft() {
    setTextDraft(null);
    setTextValue("");
    scheduleDraw();
  }

  const textInputRect = textDraft ? rectToCss(textDraft, size) : null;
  const activeTool = settings?.tool || "pen";

  return (
    <>
      <canvas
        ref={canvasRef}
        className={`annotation-canvas tool-${activeTool}${enabled ? " active" : ""}`}
        aria-label="资料批注画布"
        onPointerDown={startDrawing}
        onPointerMove={continueDrawing}
        onPointerUp={finishDrawing}
        onPointerCancel={finishDrawing}
        onContextMenu={(event) => event.preventDefault()}
      />
      <div ref={moveBoxRef} className="annotation-move-box" aria-hidden="true" />
      {textDraft && textInputRect ? (
        <textarea
          ref={textAreaRef}
          className="annotation-text-input"
          value={textValue}
          placeholder="输入批注..."
          style={{
            left: `${textInputRect.left}px`,
            top: `${textInputRect.top}px`,
            width: `${textInputRect.width}px`,
            height: `${textInputRect.height}px`,
            color: textDraft.color,
            borderColor: textDraft.color,
            fontSize: `${textDraft.fontSize}px`
          }}
          onBlur={commitTextDraft}
          onChange={(event) => setTextValue(event.target.value)}
          onKeyDown={(event) => {
            event.stopPropagation();
            if (event.key === "Escape") {
              event.preventDefault();
              cancelTextDraft();
            } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
              event.preventDefault();
              commitTextDraft();
            }
          }}
          onPointerDown={(event) => event.stopPropagation()}
        />
      ) : null}
    </>
  );
}

function drawCanvas(canvas, size, annotations, previewOperation) {
  if (!canvas || !size.width || !size.height) {
    return;
  }
  const dpr = window.devicePixelRatio || 1;
  const width = Math.round(size.width * dpr);
  const height = Math.round(size.height * dpr);
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  canvas.style.width = `${size.width}px`;
  canvas.style.height = `${size.height}px`;

  const context = canvas.getContext("2d");
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, size.width, size.height);
  annotations.forEach((operation) => {
    drawOperation(context, operation, size);
  });
  if (previewOperation) {
    drawOperation(context, previewOperation, size);
  }
}

function drawOperation(context, operation, size) {
  context.save();
  context.lineCap = "round";
  context.lineJoin = "round";
  context.globalCompositeOperation = operation.tool === "eraser" ? "destination-out" : "source-over";
  context.strokeStyle = operation.tool === "eraser" ? "#000000" : operation.color;
  context.fillStyle = operation.tool === "eraser" ? "#000000" : operation.color;
  context.lineWidth = operation.tool === "eraser" ? operation.width * 2.4 : operation.width;

  if (operation.tool === "pen" || operation.tool === "eraser") {
    drawStroke(context, operation.points, size);
  } else if (operation.tool === "line") {
    drawLine(context, operation.start, operation.end, size);
  } else if (operation.tool === "rect") {
    drawRect(context, operation.start, operation.end, size);
  } else if (operation.tool === "arrow") {
    drawArrow(context, operation.start, operation.end, size, operation.width);
  } else if (operation.tool === "text") {
    drawText(context, operation, size);
  } else if (operation.tool === "selection") {
    drawDashedRect(context, rectFromPoints(operation.start, operation.end), size, operation.color || "#176b5b");
  }
  context.restore();
}

function drawStroke(context, points, size) {
  if (!points?.length) {
    return;
  }
  const first = toCanvasPoint(points[0], size);
  context.beginPath();
  context.moveTo(first.x, first.y);
  if (points.length === 1) {
    context.lineTo(first.x + 0.1, first.y + 0.1);
  } else {
    for (const point of points.slice(1)) {
      const next = toCanvasPoint(point, size);
      context.lineTo(next.x, next.y);
    }
  }
  context.stroke();
}

function drawLine(context, start, end, size) {
  const from = toCanvasPoint(start, size);
  const to = toCanvasPoint(end, size);
  context.beginPath();
  context.moveTo(from.x, from.y);
  context.lineTo(to.x, to.y);
  context.stroke();
}

function drawRect(context, start, end, size) {
  const rect = rectToCanvas(rectFromPoints(start, end), size);
  context.strokeRect(rect.x, rect.y, rect.width, rect.height);
}

function drawArrow(context, start, end, size, width) {
  drawLine(context, start, end, size);
  const from = toCanvasPoint(start, size);
  const to = toCanvasPoint(end, size);
  const angle = Math.atan2(to.y - from.y, to.x - from.x);
  const headLength = Math.max(12, width * 4);
  context.beginPath();
  context.moveTo(to.x, to.y);
  context.lineTo(to.x - headLength * Math.cos(angle - Math.PI / 6), to.y - headLength * Math.sin(angle - Math.PI / 6));
  context.moveTo(to.x, to.y);
  context.lineTo(to.x - headLength * Math.cos(angle + Math.PI / 6), to.y - headLength * Math.sin(angle + Math.PI / 6));
  context.stroke();
}

function drawText(context, operation, size) {
  if (!operation.start || !operation.end) {
    drawPointText(context, operation, size);
    return;
  }

  const rect = getTextRect(operation);
  if (!rect) {
    return;
  }
  if (!operation.text?.trim()) {
    drawDashedRect(context, rect, size, operation.color);
    return;
  }

  const canvasRect = rectToCanvas(rect, size);
  const fontSize = operation.fontSize || Math.max(14, operation.width * 3 + 10);
  const padding = Math.max(5, operation.width + 2);
  const maxWidth = Math.max(8, canvasRect.width - padding * 2);
  const lineHeight = fontSize * 1.35;

  context.globalCompositeOperation = "source-over";
  context.font = `700 ${fontSize}px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
  context.textBaseline = "top";
  const lines = wrapText(context, operation.text, maxWidth);
  context.save();
  context.beginPath();
  context.rect(canvasRect.x, canvasRect.y, canvasRect.width, canvasRect.height);
  context.clip();
  lines.forEach((line, index) => {
    const x = canvasRect.x + padding;
    const y = canvasRect.y + padding + index * lineHeight;
    if (y + lineHeight > canvasRect.y + canvasRect.height) {
      return;
    }
    context.lineWidth = Math.max(3, operation.width);
    context.strokeStyle = "rgba(255,255,255,0.9)";
    context.strokeText(line, x, y);
    context.fillStyle = operation.color;
    context.fillText(line, x, y);
  });
  context.restore();
}

function drawPointText(context, operation, size) {
  if (!operation.point) {
    return;
  }
  const point = toCanvasPoint(operation.point, size);
  const fontSize = operation.fontSize || Math.max(14, operation.width * 3 + 10);
  const lines = String(operation.text || "").split(/\n/).slice(0, 8);
  context.globalCompositeOperation = "source-over";
  context.font = `700 ${fontSize}px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
  context.textBaseline = "top";
  context.lineWidth = Math.max(3, operation.width);
  lines.forEach((line, index) => {
    const y = point.y + index * fontSize * 1.35;
    context.strokeStyle = "rgba(255,255,255,0.9)";
    context.strokeText(line, point.x, y);
    context.fillStyle = operation.color;
    context.fillText(line, point.x, y);
  });
}

function drawSelectedBounds(context, annotations, selectedIds, size) {
  if (!selectedIds?.length) {
    return;
  }
  const bounds = getSelectionBounds(annotations, selectedIds);
  if (bounds) {
    drawDashedRect(context, bounds, size, "#176b5b", "rgba(23,107,91,0.07)");
  }
}

function drawDashedRect(context, rect, size, color, fill = "rgba(255,255,255,0.18)") {
  const canvasRect = rectToCanvas(rect, size);
  context.save();
  context.globalCompositeOperation = "source-over";
  context.setLineDash([7, 5]);
  context.lineWidth = 2;
  context.strokeStyle = color || "#176b5b";
  context.fillStyle = fill;
  context.fillRect(canvasRect.x, canvasRect.y, canvasRect.width, canvasRect.height);
  context.strokeRect(canvasRect.x, canvasRect.y, canvasRect.width, canvasRect.height);
  context.restore();
}

function eventPoint(event, canvas) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: clamp((event.clientX - rect.left) / Math.max(rect.width, 1), 0, 1),
    y: clamp((event.clientY - rect.top) / Math.max(rect.height, 1), 0, 1)
  };
}

function toCanvasPoint(point, size) {
  return {
    x: point.x * size.width,
    y: point.y * size.height
  };
}

function createOperation(settings, point) {
  const base = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    tool: settings.tool,
    color: settings.color,
    width: settings.strokeWidth,
    createdAt: Date.now()
  };
  if (settings.tool === "pen" || settings.tool === "eraser") {
    return { ...base, points: [point] };
  }
  if (settings.tool === "text") {
    return createTextOperation(base, settings, point);
  }
  return { ...base, start: point, end: point };
}

function createTextOperation(base, settings, point) {
  return {
    ...base,
    tool: "text",
    start: point,
    end: point,
    text: "",
    fontSize: Math.max(14, settings.strokeWidth * 2 + 12)
  };
}

function updateOperation(operation, point) {
  if (operation.tool === "pen" || operation.tool === "eraser") {
    const lastPoint = operation.points[operation.points.length - 1];
    if (operation.points.length >= MAX_POINTS_PER_STROKE || distance(lastPoint, point) < 0.002) {
      return operation;
    }
    return { ...operation, points: [...operation.points, point] };
  }
  return { ...operation, end: point };
}

function normalizeTextOperation(operation, size) {
  const minimum = {
    width: clamp(MIN_TEXT_BOX_PX.width / Math.max(size.width, 1), 0.02, 0.36),
    height: clamp(MIN_TEXT_BOX_PX.height / Math.max(size.height, 1), 0.006, 0.16)
  };
  const rect = ensureMinimumRect(rectFromPoints(operation.start, operation.end), minimum);
  return {
    ...operation,
    start: { x: rect.minX, y: rect.minY },
    end: { x: rect.maxX, y: rect.maxY },
    point: undefined
  };
}

function isMeaningfulOperation(operation) {
  if (operation.tool === "pen" || operation.tool === "eraser") {
    return operation.points.length > 0;
  }
  if (operation.tool === "text") {
    return distance(operation.start, operation.end) > 0.003;
  }
  if (operation.tool === "selection") {
    return distance(operation.start, operation.end) > 0.004;
  }
  return distance(operation.start, operation.end) > 0.004;
}

function getOperationBounds(operation) {
  if (operation.tool === "pen" || operation.tool === "eraser") {
    const points = Array.isArray(operation.points) ? operation.points : [];
    if (!points.length) {
      return null;
    }
    return points.reduce(
      (rect, point) => ({
        minX: Math.min(rect.minX, point.x),
        minY: Math.min(rect.minY, point.y),
        maxX: Math.max(rect.maxX, point.x),
        maxY: Math.max(rect.maxY, point.y)
      }),
      { minX: points[0].x, minY: points[0].y, maxX: points[0].x, maxY: points[0].y }
    );
  }
  if (operation.tool === "text") {
    return getTextRect(operation);
  }
  if (operation.start && operation.end) {
    return rectFromPoints(operation.start, operation.end);
  }
  return null;
}

function getTextRect(operation) {
  if (operation.start && operation.end) {
    return rectFromPoints(operation.start, operation.end);
  }
  if (operation.point) {
    return ensureMinimumRect(
      {
        minX: operation.point.x,
        minY: operation.point.y,
        maxX: operation.point.x + 0.18,
        maxY: operation.point.y + 0.065
      },
      LEGACY_TEXT_BOX
    );
  }
  return null;
}

function getSelectionBounds(annotations, selectedIds) {
  if (!selectedIds?.length) {
    return null;
  }
  const selected = new Set(selectedIds);
  const rects = annotations
    .filter((operation) => selected.has(operation.id))
    .map(getOperationBounds)
    .filter(Boolean);
  if (!rects.length) {
    return null;
  }
  return rects.reduce(
    (bounds, rect) => ({
      minX: Math.min(bounds.minX, rect.minX),
      minY: Math.min(bounds.minY, rect.minY),
      maxX: Math.max(bounds.maxX, rect.maxX),
      maxY: Math.max(bounds.maxY, rect.maxY)
    }),
    rects[0]
  );
}

function constrainedDelta(bounds, dx, dy) {
  return {
    x: clamp(dx, -bounds.minX, 1 - bounds.maxX),
    y: clamp(dy, -bounds.minY, 1 - bounds.maxY)
  };
}

function translateOperation(operation, dx, dy) {
  if (operation.tool === "pen" || operation.tool === "eraser") {
    return {
      ...operation,
      points: (Array.isArray(operation.points) ? operation.points : []).map((point) => translatePoint(point, dx, dy))
    };
  }
  if (operation.start && operation.end) {
    return {
      ...operation,
      start: translatePoint(operation.start, dx, dy),
      end: translatePoint(operation.end, dx, dy)
    };
  }
  if (operation.point) {
    return {
      ...operation,
      point: translatePoint(operation.point, dx, dy)
    };
  }
  return operation;
}

function translatePoint(point, dx, dy) {
  return {
    x: clamp(point.x + dx, 0, 1),
    y: clamp(point.y + dy, 0, 1)
  };
}

function translateRect(rect, dx, dy) {
  return {
    minX: clamp(rect.minX + dx, 0, 1),
    minY: clamp(rect.minY + dy, 0, 1),
    maxX: clamp(rect.maxX + dx, 0, 1),
    maxY: clamp(rect.maxY + dy, 0, 1)
  };
}

function rectFromPoints(start, end) {
  return {
    minX: Math.min(start.x, end.x),
    minY: Math.min(start.y, end.y),
    maxX: Math.max(start.x, end.x),
    maxY: Math.max(start.y, end.y)
  };
}

function rectToCanvas(rect, size) {
  return {
    x: rect.minX * size.width,
    y: rect.minY * size.height,
    width: Math.max(1, (rect.maxX - rect.minX) * size.width),
    height: Math.max(1, (rect.maxY - rect.minY) * size.height)
  };
}

function rectToCss(operation, size) {
  const rect = rectToCanvas(getTextRect(operation), size);
  return {
    left: rect.x,
    top: rect.y,
    width: rect.width,
    height: rect.height
  };
}

function ensureMinimumRect(rect, minimum) {
  let { minX, minY, maxX, maxY } = rect;
  if (maxX - minX < minimum.width) {
    if (minX + minimum.width <= 1) {
      maxX = minX + minimum.width;
    } else {
      minX = Math.max(0, maxX - minimum.width);
    }
  }
  if (maxY - minY < minimum.height) {
    if (minY + minimum.height <= 1) {
      maxY = minY + minimum.height;
    } else {
      minY = Math.max(0, maxY - minimum.height);
    }
  }
  return { minX, minY, maxX, maxY };
}

function inflateRect(rect, amount) {
  return {
    minX: clamp(rect.minX - amount, 0, 1),
    minY: clamp(rect.minY - amount, 0, 1),
    maxX: clamp(rect.maxX + amount, 0, 1),
    maxY: clamp(rect.maxY + amount, 0, 1)
  };
}

function pointInRect(point, rect) {
  return point.x >= rect.minX && point.x <= rect.maxX && point.y >= rect.minY && point.y <= rect.maxY;
}

function rectsIntersect(left, right) {
  return left.minX <= right.maxX && left.maxX >= right.minX && left.minY <= right.maxY && left.maxY >= right.minY;
}

function unionRects(left, right) {
  return {
    minX: Math.min(left.minX, right.minX),
    minY: Math.min(left.minY, right.minY),
    maxX: Math.max(left.maxX, right.maxX),
    maxY: Math.max(left.maxY, right.maxY)
  };
}

function wrapText(context, text, maxWidth) {
  const lines = [];
  String(text || "")
    .split(/\r?\n/)
    .forEach((rawLine) => {
      let current = "";
      for (const character of Array.from(rawLine || " ")) {
        const next = current + character;
        if (current && context.measureText(next).width > maxWidth) {
          lines.push(current);
          current = character;
        } else {
          current = next;
        }
      }
      lines.push(current);
    });
  return lines.slice(0, 20);
}

function capturePointer(event) {
  try {
    event.currentTarget.setPointerCapture(event.pointerId);
  } catch {
    // Pointer capture can be unavailable for synthetic pointer events.
  }
}

function releasePointer(event) {
  try {
    event.currentTarget.releasePointerCapture(event.pointerId);
  } catch {
    // Pointer capture may already be released after a cancelled pointer.
  }
}

function distance(left, right) {
  return Math.hypot(left.x - right.x, left.y - right.y);
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function trimAnnotations(annotations) {
  return annotations.slice(-MAX_ANNOTATIONS_PER_PAGE).map((operation) => {
    if (
      (operation.tool === "pen" || operation.tool === "eraser") &&
      Array.isArray(operation.points) &&
      operation.points.length > MAX_POINTS_PER_STROKE
    ) {
      return { ...operation, points: operation.points.slice(-MAX_POINTS_PER_STROKE) };
    }
    return operation;
  });
}
