import { RefreshCw } from "lucide-react";

export default function CourseSelector({
  materials,
  selectedCourseId,
  manualCourseId,
  loading,
  error,
  onSelect,
  onManualChange,
  onRefresh
}) {
  return (
    <div className="course-selector">
      <label>
        已导入 PDF
        <select
          value={selectedCourseId}
          onChange={(event) => onSelect(event.target.value)}
          disabled={loading || materials.length === 0}
        >
          {materials.length === 0 ? (
            <option value="">暂无注册 PDF</option>
          ) : (
            materials.map((material) => (
              <option key={material.course_id} value={material.course_id}>
                {material.course_id} · {material.file_name}
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
      {error ? <span className="toolbar-error">{error}</span> : null}
    </div>
  );
}
