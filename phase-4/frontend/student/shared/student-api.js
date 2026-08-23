// =========================================================
// Brightpeak Academy — Student Portal
// Shared API client for the FastAPI-backed graph pages:
// Assessments, Track Recommendation, Academic Integrity & Appeals.
// Mirrors instructor/shared/api.js's pattern (X-User-Id / X-User-Role
// headers, port 8000) so behavior stays consistent across portals.
// Load AFTER shared/auth.js + student/shared/auth-guard.js.
// =========================================================

const SP_API_BASE = "http://localhost:8000";

function _spAuthHeaders() {
  const user = window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
  return {
    "Content-Type": "application/json",
    "X-User-Id": String(user.id || ""),
    "X-User-Role": String(user.role || "student"),
  };
}

async function spRequest(path, options = {}) {
  const res = await fetch(`${SP_API_BASE}${path}`, {
    headers: _spAuthHeaders(),
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.detail || `Request failed: ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

window.SPApi = {
  BASE_URL: SP_API_BASE,

  // ---- lookups ----
  getMyCourses: () => spRequest("/teaching/courses"),

  // ---- assessments ----
  startAssessment: (body) =>
    spRequest("/assessments/start", { method: "POST", body: JSON.stringify(body) }),
  answerAssessment: (sessionId, studentAnswer) =>
    spRequest(`/assessments/${sessionId}/answer`, {
      method: "POST",
      body: JSON.stringify({ student_answer: studentAnswer }),
    }),
  getAssessmentState: (sessionId) => spRequest(`/assessments/${sessionId}/state`),
  getAssessmentSession: (sessionId) => spRequest(`/assessments/${sessionId}`),
  listAssessmentSessions: () => spRequest(`/assessments`),

  // ---- track recommendation ----
  recommendTrack: () => spRequest("/tracks/recommend", { method: "POST" }),
  listTrackRecommendations: () => spRequest("/tracks/recommendations"),
  getTrackThreadState: (threadId) => spRequest(`/tracks/thread/${threadId}`),
  diagnosticComplete: (threadId) =>
    spRequest(`/tracks/thread/${threadId}/diagnostic-complete`, {
      method: "POST",
      body: JSON.stringify({ completed: true }),
    }),
  targetedAssessmentComplete: (threadId) =>
    spRequest(`/tracks/thread/${threadId}/targeted-assessment-complete`, {
      method: "POST",
      body: JSON.stringify({ completed: true }),
    }),

  // ---- academic integrity / appeals ----
  listMyCases: () => spRequest("/academic-integrity/cases"),
  getCase: (id) => spRequest(`/academic-integrity/cases/${id}`),
  submitAppeal: (id, appealArgument) =>
    spRequest(`/academic-integrity/cases/${id}/appeal`, {
      method: "POST",
      body: JSON.stringify({ appeal_argument: appealArgument }),
    }),
};

// Small shared toast, used by all three new pages.
window.SPToast = {
  el: null,
  show(msg, kind = "info") {
    if (!this.el) {
      this.el = document.createElement("div");
      this.el.className =
        "fixed bottom-6 right-6 z-[100] px-5 py-3 rounded-xl border text-body-sm font-medium shadow-lg backdrop-blur-md transition-all";
      document.body.appendChild(this.el);
    }
    const palette = {
      info: "bg-surface-container-high/90 border-white/10 text-on-surface",
      error: "bg-error-container/90 border-error/30 text-on-error-container",
      success: "bg-emerald-400/10 border-emerald-400/30 text-emerald-300",
    };
    this.el.className = this.el.className.replace(/bg-\S+|border-\S+|text-\S+/g, "").trim();
    this.el.classList.add(...palette[kind].split(" "));
    this.el.textContent = msg;
    this.el.style.opacity = "1";
    clearTimeout(this._t);
    this._t = setTimeout(() => {
      if (this.el) this.el.style.opacity = "0";
    }, 3500);
  },
};