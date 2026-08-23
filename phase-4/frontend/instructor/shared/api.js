// =========================================================
// Brightpeak Academy — Instructor Portal
// API service layer
// All real endpoints live under /instructor (FastAPI router).
// BP_USE_MOCK is off; mock data kept for reference only.
// =========================================================

const BP_API_BASE  = "http://localhost:8000";
const BP_USE_MOCK  = false;

// ---------------------------------------------------------
// Auth helper
// ---------------------------------------------------------
function _bpAuthHeaders() {
  try {
    const user = JSON.parse(localStorage.getItem("user") || "{}");
    return {
      "Content-Type": "application/json",
      "X-User-Id":   String(user.id   || ""),
      "X-User-Role": String(user.role || "instructor"),
    };
  } catch (e) {
    return { "Content-Type": "application/json" };
  }
}

// ---------------------------------------------------------
// Low-level request helper
// ---------------------------------------------------------
async function bpRequest(path, options = {}) {
  const res = await fetch(`${BP_API_BASE}${path}`, {
    headers: _bpAuthHeaders(),
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err  = new Error(body.detail || `Request failed: ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function bpDelay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// =========================================================
// MOCK DATA — kept for offline dev reference only.
// Never used in production (BP_USE_MOCK = false).
// =========================================================
const BP_MOCK = {
  dashboard: {
    stats: { courses: 4, students: 12, reports: 3, pendingRequests: 2 },
    statusCounts: { reported: 1, underReview: 1, awaitingAppeal: 0, closed: 1 },
    recentCases: [],
    recentRequests: [],
  },
  cases:         [],
  caseDetails:   {},
  courses:       [],
  students:      [],
  assessments:   [],
  courseList:    [],
  studentRoster: [],
  studentDetails: {},
  hitl: { needsAttention: [], awaitingAppeal: [], committeeDecisions: [] },
  requests:       [],
  requestDetails: {},
  agents: [
    { id: "academic-integrity-agent", name: "Academic Integrity Agent",
      description: "Assists with academic integrity workflows and case analysis.", status: "available" },
  ],
};

// =========================================================
// Service functions — all real paths prefixed /instructor
// =========================================================

async function getInstructorDashboard() {
  if (BP_USE_MOCK) { await bpDelay(350); return BP_MOCK.dashboard; }
  return bpRequest("/instructor/dashboard");
}

async function getIntegrityCases({ search = "", status = "all" } = {}) {
  if (BP_USE_MOCK) { await bpDelay(350); return BP_MOCK.cases; }
  const params = new URLSearchParams({ search, status });
  return bpRequest(`/academic-integrity/cases?${params.toString()}`);
}

async function getIntegrityCase(id) {
  if (BP_USE_MOCK) { await bpDelay(300); return BP_MOCK.caseDetails[id] || {}; }
  return bpRequest(`/academic-integrity/cases/${id}`);
}

// Lookup dropdowns — now under /instructor/lookups/*
async function getStudentOptions() {
  if (BP_USE_MOCK) { await bpDelay(150); return BP_MOCK.students; }
  return bpRequest("/instructor/lookups/students");
}
async function getCourseOptions() {
  if (BP_USE_MOCK) { await bpDelay(150); return BP_MOCK.courses; }
  return bpRequest("/instructor/lookups/courses");
}
async function getAssessmentOptions() {
  if (BP_USE_MOCK) { await bpDelay(150); return BP_MOCK.assessments; }
  return bpRequest("/instructor/lookups/assessments");
}

// Case submission — sends numeric IDs, not text names
async function submitIntegrityCase(formData) {
  if (BP_USE_MOCK) {
    await bpDelay(700);
    return { id: String(Math.floor(1000 + Math.random() * 9000)), status: "reported" };
  }
  return bpRequest("/academic-integrity/cases", {
    method: "POST",
    body: JSON.stringify(formData),
  });
}

async function getCourses() {
  if (BP_USE_MOCK) { await bpDelay(350); return BP_MOCK.courseList; }
  return bpRequest("/instructor/courses");
}

async function getCourse(id) {
  if (BP_USE_MOCK) { await bpDelay(300); return BP_MOCK.courseList.find((c) => c.id === id) || {}; }
  return bpRequest(`/instructor/courses/${id}`);
}

async function getStudents({ search = "", course = "all" } = {}) {
  if (BP_USE_MOCK) { await bpDelay(350); return BP_MOCK.studentRoster; }
  const params = new URLSearchParams({ search, course });
  return bpRequest(`/instructor/students?${params.toString()}`);
}

async function getStudent(id) {
  if (BP_USE_MOCK) { await bpDelay(300); return {}; }
  return bpRequest(`/instructor/students/${id}`);
}

async function getRequests({ search = "", status = "all" } = {}) {
  if (BP_USE_MOCK) { await bpDelay(350); return BP_MOCK.requests; }
  const params = new URLSearchParams({ search, status });
  return bpRequest(`/instructor/requests?${params.toString()}`);
}

async function getRequest(id) {
  if (BP_USE_MOCK) { await bpDelay(300); return {}; }
  return bpRequest(`/instructor/requests/${id}`);
}

async function submitRequestDecision(id, action, payload = {}) {
  if (BP_USE_MOCK) {
    await bpDelay(500);
    const status = action === "approve" ? "approved" : action === "reject" ? "rejected" : "info_requested";
    return { id, action, status, ...payload };
  }
  // Backend expects { decision, notes } — map "action" -> "decision"
  return bpRequest(`/instructor/requests/${id}/decision`, {
    method: "POST",
    body: JSON.stringify({ decision: action, notes: payload.notes || null }),
  });
}

async function getHITLCases() {
  if (BP_USE_MOCK) { await bpDelay(350); return BP_MOCK.hitl; }
  // /cases/hitl returns {needsAttention, awaitingAppeal, committeeDecisions}
  // which is the shape hitl.js expects. The bare /cases endpoint returns
  // a flat array (for the integrity list page) — different consumers,
  // different shapes.
  return bpRequest("/academic-integrity/cases/hitl");
}

async function getHITLCase(id) {
  if (BP_USE_MOCK) { await bpDelay(300); return {}; }
  return bpRequest(`/academic-integrity/cases/${id}`);
}

// HITL decision — backend needs { decision, notes } not just { action }
async function submitHITLDecision(id, action, notes = null) {
  if (BP_USE_MOCK) { await bpDelay(500); return { id, action, status: "recorded" }; }
  return bpRequest(`/academic-integrity/cases/${id}/committee-decision`, {
    method: "POST",
    body: JSON.stringify({ decision: action, notes }),
  });
}

async function getAgents() {
  if (BP_USE_MOCK) { await bpDelay(250); return BP_MOCK.agents; }
  return bpRequest("/instructor/agents");
}