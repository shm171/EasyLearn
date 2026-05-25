import { useEffect, useRef, useState } from "react";

const MAX_POINTS_PER_STROKE = 900;
const MAX_ANNOTATIONS_PER_PAGE = 500;

export default function ReaderAnnotationLayer({
  enabled,
  settings,
  annotations,
  onChange
}) {
  const canvasRef = useRef(null);
  const drawingRef = useRef(null);
  const annotationsRef = useRef(annotations);
  const sizeRef = useRef({ width: 0, height: 0 });
  const previewRef = useRef(null);
  const animationFrameRef = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    annotationsRef.current = annotations;
    scheduleDraw();
  }, [annotations]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const surface = canvas?.parentElement;
    if (!surface) {
      return;
    }

    function updateSize() {
      const rect = surface.getBoundingClientRect();
      const nextSize = {
        width: Math.max(1, Math.round(rect.width)),
        height: Math.max(1, Math.round(rect.height))
      };
      sizeRef.current = nextSize;
      setSize(nextSize);
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
      drawCanvas(canvasRef.current, sizeRef.current, annotationsRef.current, previewRef.current);
    });
  }

  function startDrawing(event) {
    if (!enabled || !settings || event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = eventPoint(event, event.currentTarget);
    const operation = createOperation(settings, point);
    drawingRef.current = operation;
    previewRef.current = operation;
    scheduleDraw();
  }

  function continueDrawing(event) {
    const operation = drawingRef.current;
    if (!operation) {
      return;
    }
    event.preventDefault();
    const point = eventPoint(event, event.currentTarget);
    const updated = updateOperation(operation, point);
    drawingRef.current = updated;
    previewRef.current = updated;
    scheduleDraw();
  }

  function finishDrawing(event) {
    const operation = drawingRef.current;
    if (!operation) {
      return;
    }
    event.preventDefault();
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // Pointer capture may already be released after a cancelled pointer.
    }
    drawingRef.current = null;
    previewRef.current = null;
    if (!isMeaningfulOperation(operation)) {
      scheduleDraw();
      return;
    }
    onChange(trimAnnotations([...annotationsRef.current, operation]));
    scheduleDraw();
  }

  return (
    <canvas
      ref={canvasRef}
      className={`annotation-canvas${enabled ? " active" : ""}`}
      aria-label="资料批注画布"
      onPointerDown={startDrawing}
      onPointerMove={continueDrawing}
      onPointerUp={finishDrawing}
      onPointerCancel={finishDrawing}
      onContextMenu={(event) => event.preventDefault()}
    />
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
  [...annotations, previewOperation].filter(Boolean).forEach((operation) => {
    drawOperation(context, operation, size);
  });
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
  const from = toCanvasPoint(start, size);
  const to = toCanvasPoint(end, size);
  context.strokeRect(from.x, from.y, to.x - from.x, to.y - from.y);
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
  return { ...base, start: point, end: point };
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

function isMeaningfulOperation(operation) {
  if (operation.tool === "pen" || operation.tool === "eraser") {
    return operation.points.length > 0;
  }
  return distance(operation.start, operation.end) > 0.004;
}

function distance(left, right) {
  return Math.hypot(left.x - right.x, left.y - right.y);
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function trimAnnotations(annotations) {
  return annotations.slice(-MAX_ANNOTATIONS_PER_PAGE).map((operation) => {
    if ((operation.tool === "pen" || operation.tool === "eraser") && operation.points.length > MAX_POINTS_PER_STROKE) {
      return { ...operation, points: operation.points.slice(-MAX_POINTS_PER_STROKE) };
    }
    return operation;
  });
}
