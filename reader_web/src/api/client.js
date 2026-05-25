const API_BASE = "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

export async function listMaterials() {
  return request("/reader/materials");
}

export async function getMaterial(courseId) {
  return request(`/reader/materials/${encodeURIComponent(courseId)}`);
}

export function getPdfUrl(courseId) {
  return `${API_BASE}/reader/pdf/${encodeURIComponent(courseId)}`;
}

export async function getMarkdownPages(courseId) {
  return request(`/reader/markdown/${encodeURIComponent(courseId)}`);
}

export async function getMarkdownIndex(courseId) {
  return request(`/reader/markdown/${encodeURIComponent(courseId)}/index`);
}

export async function getMarkdownPage(courseId, pageNumber) {
  return request(`/reader/markdown/${encodeURIComponent(courseId)}/pages/${Number(pageNumber)}`);
}

export async function getApiConfig() {
  return request("/reader/api-config");
}

export async function saveApiConfig(payload) {
  return request("/reader/api-config", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function testApiConfig(payload) {
  return request("/reader/api-config/test", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function importLocalPdf({ courseId, chapterTitle, file }) {
  return importLocalMaterial({ courseId, chapterTitle, file });
}

export async function importLocalMaterial({ courseId, chapterTitle, file }) {
  const formData = new FormData();
  formData.append("course_id", courseId);
  formData.append("chapter_title", chapterTitle || "");
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/reader/materials/import`, {
    method: "POST",
    body: formData
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

export async function askCurrentPage(payload) {
  return request("/reader/current-page/ask", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function askSelection(payload) {
  return request("/reader/selection/ask", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function explainCodeSelection(payload) {
  return request("/reader/selection/explain-code", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function generateQuizFromSelection(payload) {
  return request("/reader/selection/generate-quiz", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function askRange(payload) {
  return request("/range/ask", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function summarizeRange(payload) {
  return request("/range/summary", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function generateQuizFromRange(payload) {
  return request("/range/quiz", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function evaluateQuiz(payload) {
  return request("/quizzes/evaluate", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function getKeyPointsFromRange(payload) {
  return request("/range/key-points", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
