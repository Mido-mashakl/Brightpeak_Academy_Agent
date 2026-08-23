// =========================================================
// Brightpeak Academy — shared Graph API client
//
// Talks to the FastAPI backend (phase-4/backend/main.py, port 8000)
// that fronts the Phase-3 state graphs + RAG (hiring, academic
// integrity, advisor, assessment, tracks, teaching).
//
// This is a SEPARATE client from shared/api.js on purpose: api.js
// talks to the Express process (port 3000 — login + static files),
// this one talks to FastAPI (port 8000). The two backends aren't
// bridged (see phase-4/backend/main.py's own comment), so every
// page that calls a graph-backed endpoint should go through here,
// not through BrightPeakAPI.
//
// AUTH: every protected FastAPI route depends on core.auth.require_role,
// which reads X-User-Id / X-User-Role headers (see that file's docstring
// for why headers rather than a shared session). This client attaches
// them automatically from the same localStorage "user" object
// shared/auth.js already manages — pages never need to touch headers
// themselves. Load shared/auth.js BEFORE this file.
// =========================================================

window.BrightPeakGraphAPI = (function () {
  const BASE_URL = "http://localhost:8000";

  function authHeaders() {
    const user = window.BrightPeakAuth ? window.BrightPeakAuth.getUser() : null;
    if (!user) return {};
    return {
      "X-User-Id": String(user.id),
      "X-User-Role": user.role,
    };
  }

  async function request(path, options = {}) {
    const isFormData = options.body instanceof FormData;
    const response = await fetch(BASE_URL + path, {
      ...options,
      headers: {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        ...authHeaders(),
        ...(options.headers || {}),
      },
    });

    let data = null;
    try {
      data = await response.json();
    } catch (e) {
      // No JSON body — fine for some responses.
    }

    if (!response.ok) {
      const message = (data && data.detail) || `Request failed (${response.status})`;
      const err = new Error(typeof message === "string" ? message : JSON.stringify(message));
      err.status = response.status;
      err.body = data;
      throw err;
    }

    return data;
  }

  return {
    get: (path) => request(path, { method: "GET" }),
    post: (path, body) => request(path, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body) }),
    BASE_URL,
  };
})();