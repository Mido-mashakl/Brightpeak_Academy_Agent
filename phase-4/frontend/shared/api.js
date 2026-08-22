// =========================================================
// Brightpeak Academy — shared API client
// One place that knows the backend's base URL, so pages never
// hardcode "http://localhost:3000" themselves.
// Load this BEFORE any page script that calls BrightPeakAPI.*
// =========================================================

window.BrightPeakAPI = (function () {
  const BASE_URL = "http://localhost:3000";

  async function request(path, options = {}) {
    const response = await fetch(BASE_URL + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });

    let data = null;
    try {
      data = await response.json();
    } catch (e) {
      // No JSON body (e.g. plain 204) — that's fine.
    }

    if (!response.ok) {
      const message = (data && data.message) || `Request failed (${response.status})`;
      throw new Error(message);
    }

    return data;
  }

  return {
    get: (path) => request(path, { method: "GET" }),
    post: (path, body) => request(path, { method: "POST", body: JSON.stringify(body) }),
    BASE_URL,
  };
})();
