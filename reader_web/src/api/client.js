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

export async function closeMaterial(courseId) {
  return request(`/reader/materials/${encodeURIComponent(courseId)}`, {
    method: "DELETE"
  });
}

export async function getMaterialIndexStatus(courseId) {
  return request(`/reader/materials/${encodeURIComponent(courseId)}/index-status`);
}

export function getPdfUrl(courseId) {
  return `${API_BASE}/reader/pdf/${encodeURIComponent(courseId)}`;
}

export async function getMarkdownPages(courseId) {
  return request(`/reader/markdown/${encodeURIComponent(courseId)}`);
}

export async function getMaterialPages(courseId) {
  return request(`/reader/pages/${encodeURIComponent(courseId)}`);
}

export async function getMarkdownIndex(courseId) {
  return request(`/reader/markdown/${encodeURIComponent(courseId)}/index`);
}

export async function getMaterialPageIndex(courseId) {
  return request(`/reader/pages/${encodeURIComponent(courseId)}/index`);
}

export async function getMarkdownPage(courseId, pageNumber) {
  return request(`/reader/markdown/${encodeURIComponent(courseId)}/pages/${Number(pageNumber)}`);
}

export async function getMaterialPage(courseId, pageNumber) {
  return request(`/reader/pages/${encodeURIComponent(courseId)}/pages/${Number(pageNumber)}`);
}

export async function updateMarkdownPage(courseId, pageNumber, content) {
  return request(`/reader/markdown/${encodeURIComponent(courseId)}/pages/${Number(pageNumber)}`, {
    method: "PUT",
    body: JSON.stringify({ content })
  });
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

export async function importLocalMaterial({ courseId, chapterTitle, file, onProgress }) {
  const formData = new FormData();
  formData.append("course_id", courseId);
  formData.append("chapter_title", chapterTitle || "");
  formData.append("file", file);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/reader/materials/import`);
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || !onProgress) {
        return;
      }
      const uploadRatio = event.loaded / event.total;
      onProgress({
        value: Math.min(0.35, 0.08 + uploadRatio * 0.27),
        message: "正在上传资料"
      });
    };
    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new Error(xhr.responseText || `HTTP ${xhr.status}`));
        return;
      }
      try {
        resolve(JSON.parse(xhr.responseText));
      } catch (error) {
        reject(error);
      }
    };
    xhr.onerror = () => reject(new Error("Network error while importing material."));
    xhr.onabort = () => reject(new Error("Import cancelled."));
    onProgress?.({ value: 0.05, message: "准备上传资料" });
    xhr.send(formData);
  });
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
