const API_ROOT = "/api";

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_ROOT}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = payload?.error || payload?.detail || {};
    const message = typeof detail === "string" ? detail : detail.message || detail.msg || `Request failed (${response.status})`;
    const fields = Array.isArray(detail.fields) ? ` ${detail.fields.map((item) => `${item.field}: ${item.message}`).join("; ")}` : "";
    throw new Error(`${message}${fields}`);
  }
  return payload;
}

export function postJson(path, body) {
  return apiRequest(path, { method: "POST", body: JSON.stringify(body) });
}
