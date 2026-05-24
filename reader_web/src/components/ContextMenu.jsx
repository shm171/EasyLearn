import { BookOpenText, Code2, FileQuestion, HelpCircle, ListChecks } from "lucide-react";

const selectionActions = [
  { id: "explain", label: "解释选中文字", icon: BookOpenText },
  { id: "summarize", label: "总结选中文字", icon: ListChecks },
  { id: "explain_code", label: "解释选中代码", icon: Code2 },
  { id: "generate_quiz", label: "根据选中文字生成练习题", icon: FileQuestion }
];

export default function ContextMenu({ x, y, selectedText, onAction, onClose }) {
  const hasSelection = Boolean(selectedText);
  const actions = hasSelection ? selectionActions : [];

  return (
    <div className="context-backdrop" onClick={onClose}>
      <div
        className="context-menu"
        style={{ left: x, top: y }}
        onClick={(event) => event.stopPropagation()}
      >
        {actions.map((action) => {
          const Icon = action.icon;
          return (
            <button key={action.id} type="button" onClick={() => onAction(action.id)}>
              <Icon size={16} />
              <span>{action.label}</span>
            </button>
          );
        })}
        <button type="button" onClick={() => onAction("ask_current_page")}>
          <HelpCircle size={16} />
          <span>结合当前页问 AI</span>
        </button>
      </div>
    </div>
  );
}
