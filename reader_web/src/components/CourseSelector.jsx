import { RefreshCw, XCircle } from "lucide-react";

export default function CourseSelector({
  materials,
  selectedCourseId,
  manualCourseId,
  loading,
  error,
  onSelect,
  onManualChange,
  onRefresh,
  onCloseSelected
}) {
  return (
    <div className="course-selector">
      <label>
        已导入资料
        <select
          value={selectedCourseId}
          onChange={(event) => onSelect(event.target.value)}
          disabled={loading || materials.length === 0}
        >
          {materials.length === 0 ? (
            <option value="">暂无注册资料</option>
          ) : (
            materials.map((material) => (
              <option key={material.course_id} value={material.course_id}>
                {material.course_id} · {material.file_name} · {materialTypeLabel(material.file_type)}
                {material.index_status === "indexing" ? " · 索引中" : ""}
                {material.index_status === "failed" ? " · 索引失败" : ""}
              </option>
            ))
          )}
        </select>
      </label>
      <label className="manual-course-field">
        手动 course_id
        <input
          value={manualCourseId}
          onChange={(event) => onManualChange(event.target.value)}
          placeholder="python_001"
        />
      </label>
      <button type="button" className="icon-button refresh-button" onClick={onRefresh} title="刷新材料列表">
        <RefreshCw size={18} />
      </button>
      <button
        type="button"
        className="icon-button close-material-button"
        onClick={onCloseSelected}
        disabled={loading || !selectedCourseId}
        title="关闭当前导入资料"
      >
        <XCircle size={18} />
      </button>
      {error ? <span className="toolbar-error">{error}</span> : null}
    </div>
  );
}

function materialTypeLabel(fileType) {
  const normalized = String(fileType || "").toLowerCase();
  if (normalized === "markdown" || normalized === "md") {
    return "Markdown";
  }
  if (normalized === "pptx" || normalized === "pptm" || normalized === "presentation") {
    return "PowerPoint";
  }
  return "PDF";
}
