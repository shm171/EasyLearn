import {
  ArrowUpRight,
  Eraser,
  Minus,
  Paintbrush,
  Pencil,
  RotateCcw,
  Save,
  Square,
  Trash2
} from "lucide-react";

const toolOptions = [
  { value: "pen", label: "画笔", icon: Pencil },
  { value: "eraser", label: "擦除", icon: Eraser },
  { value: "line", label: "直线", icon: Minus },
  { value: "arrow", label: "箭头", icon: ArrowUpRight },
  { value: "rect", label: "矩形", icon: Square }
];

const colorOptions = ["#ef4444", "#f59e0b", "#176b5b", "#2563eb", "#7c3aed", "#202427"];

export default function ReaderAnnotationTool({
  courseId,
  currentPage,
  settings,
  onSettingsChange,
  annotationCount,
  dirty,
  onUndo,
  onClearPage,
  onSave
}) {
  function updateSettings(patch) {
    onSettingsChange((current) => ({ ...current, ...patch }));
  }

  return (
    <section className="annotation-tool" aria-label="批注工具">
      <div className="annotation-tool-head">
        <div>
          <strong>批注</strong>
          <span>{courseId ? `第 ${currentPage} 页 · ${annotationCount} 条` : "未选择 course_id"}</span>
        </div>
        <label className="annotation-toggle">
          <input
            type="checkbox"
            checked={settings.enabled}
            onChange={(event) => updateSettings({ enabled: event.target.checked })}
          />
          <span>{settings.enabled ? "开启" : "关闭"}</span>
        </label>
      </div>

      <div className="annotation-tool-grid" role="group" aria-label="批注模式">
        {toolOptions.map((option) => {
          const Icon = option.icon;
          return (
            <button
              type="button"
              key={option.value}
              className={settings.tool === option.value ? "active" : ""}
              onClick={() => updateSettings({ tool: option.value, enabled: true })}
              title={option.label}
            >
              <Icon size={16} />
              <span>{option.label}</span>
            </button>
          );
        })}
      </div>

      <label className="annotation-color-field">
        颜色
        <div className="annotation-color-row">
          {colorOptions.map((color) => (
            <button
              type="button"
              key={color}
              className={settings.color.toLowerCase() === color ? "active" : ""}
              style={{ "--swatch-color": color }}
              onClick={() => updateSettings({ color, enabled: true })}
              title={color}
              aria-label={`选择颜色 ${color}`}
            />
          ))}
          <input
            type="color"
            value={settings.color}
            onChange={(event) => updateSettings({ color: event.target.value, enabled: true })}
            title="自定义颜色"
          />
        </div>
      </label>

      <label className="annotation-width-field">
        粗细
        <div>
          <input
            type="range"
            min="1"
            max="20"
            value={settings.strokeWidth}
            onChange={(event) => updateSettings({ strokeWidth: Number(event.target.value), enabled: true })}
          />
          <strong>{settings.strokeWidth}px</strong>
        </div>
      </label>

      <div className="annotation-actions">
        <button type="button" className="secondary-button" onClick={onUndo} disabled={!annotationCount} title="Ctrl+Alt+Z">
          <RotateCcw size={16} />
          <span>回退</span>
        </button>
        <button type="button" className="secondary-button" onClick={onClearPage} disabled={!annotationCount} title="Ctrl+Alt+A">
          <Trash2 size={16} />
          <span>清屏</span>
        </button>
        <button type="button" className="primary-button" onClick={onSave} disabled={!courseId}>
          <Save size={16} />
          <span>保存</span>
        </button>
      </div>

      <div className={`annotation-save-state${dirty ? " dirty" : ""}`}>
        <Paintbrush size={14} />
        <span>{dirty ? "有未保存批注" : "批注已保存"}</span>
      </div>
    </section>
  );
}
