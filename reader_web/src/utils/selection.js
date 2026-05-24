export function getSelectedText() {
  const selection = window.getSelection();
  return selection ? selection.toString().trim() : "";
}

export function previewText(text, maxLength = 220) {
  if (!text) {
    return "";
  }
  return text.length > maxLength ? `${text.slice(0, maxLength).trim()}...` : text;
}
