/* ============================================================
   Brightpeak Academy — Advisor Portal
   Real API layer — wired to FastAPI backend (port 8000).

   Auth: reads the logged-in user from localStorage("user")
   and forwards X-User-Id / X-User-Role on every request,
   matching the pattern in core/auth.py.
   ============================================================ */

const BP_ADVISOR_BASE = "http://localhost:8000";

const BP_STATUS_META = {
  review:           { label: "Needs Review",          badgeClass: "status-review" },
  progress:         { label: "In Progress",           badgeClass: "status-progress" },
  waiting:          { label: "Waiting for Student",   badgeClass: "status-waiting" },
  completed:        { label: "Completed",             badgeClass: "status-completed" },
  pending_review:   { label: "Needs Review",          badgeClass: "status-review" },
  in_progress:      { label: "In Progress",           badgeClass: "status-progress" },
  approved:         { label: "Completed",             badgeClass: "status-completed" },
  rejected:         { label: "Completed",             badgeClass: "status-completed" },
};

function _authHeaders() {
  try {
    const user = JSON.parse(localStorage.getItem("user") || "{}");
    return {
      "Content-Type": "application/json",
      "X-User-Id":   String(user.id   || ""),
      "X-User-Role": String(user.role || "advisor"),
    };
  } catch (e) {
    return { "Content-Type": "application/json" };
  }
}

async function _apiFetch(path, options = {}) {
  const res = await fetch(BP_ADVISOR_BASE + path, {
    headers: _authHeaders(),
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

/** Maps a raw DB row from advisor_router to the shape pages expect */
function _normalizeRequest(row) {
  const typeLabel = row.request_type === "certificate" ? "Certificate" : "Scholarship";
  const statusRaw = row.status || "pending_review";
  return {
    id:        String(row.request_id),
    _type:     row.request_type,          // "certificate" | "scholarship"
    student:   row.student_name || `Student #${row.student_id}`,
    studentId: row.student_id,
    type:      typeLabel,
    status:    statusRaw,
    priority:  "medium",
    updated:   row.updated_at  || row.created_at || "",
    submitted: row.created_at  || "",
    purpose:   row.purpose     || "",
    aiRecommendation: row.ai_recommendation
      ? { verdict: row.ai_recommendation, confidence: row.confidence || 0, reasoning: row.reasoning || "" }
      : null,
    requirements: row.requirements || [],
    timeline:     row.timeline     || [],
  };
}

/** GET /advisor/requests — advisor's full queue */
async function bpFetchDashboardStats() {
  const rows = await _apiFetch("/advisor/requests");
  const items = rows.map(_normalizeRequest);

  const inProgress   = items.filter(r => ["in_progress",  "progress"].includes(r.status)).length;
  const pendingReview= items.filter(r => ["pending_review","review"].includes(r.status)).length;
  const completed    = items.filter(r => ["approved","rejected","completed"].includes(r.status)).length;

  return {
    total:        items.length,
    inProgress,
    pendingReview,
    completed,
    deltas:       { total: "", inProgress: "", pendingReview: "", completed: "" },
    aiInsights:   { avgEligibilityAccuracy: null, requestsAnalyzed: items.length, recommendationsGenerated: 0 },
    needingAttention: items.filter(r => !["approved","rejected","completed"].includes(r.status)).slice(0, 3),
  };
}

/** GET /advisor/requests with optional type / query filter */
async function bpFetchRequests({ type = "all", query = "" } = {}) {
  const params = new URLSearchParams();
  if (type !== "all") params.set("request_type", type);

  const rows = await _apiFetch(`/advisor/requests?${params}`);
  let items = rows.map(_normalizeRequest);

  if (query) {
    const q = query.toLowerCase();
    items = items.filter(r =>
      r.student.toLowerCase().includes(q) ||
      String(r.id).toLowerCase().includes(q)
    );
  }

  return { items, total: items.length, page: 1, pages: 1 };
}

/** GET /advisor/requests/{type}/{id} */
async function bpFetchRequestById(id) {
  // id may be a plain number string or "certificate-5" style
  // Try certificate first, then scholarship
  for (const reqType of ["certificate", "scholarship"]) {
    try {
      const data = await _apiFetch(`/advisor/requests/${reqType}/${id}`);
      if (data && data.row) {
        const norm = _normalizeRequest({ ...data.row, request_type: reqType });
        // Merge graph state if present
        if (data.graph_state) {
          norm._graphState = data.graph_state;
          if (data.graph_state._interrupt && data.graph_state._interrupt[0]) {
            const iv = data.graph_state._interrupt[0];
            if (iv.ai_recommendation) norm.aiRecommendation = {
              verdict:    iv.ai_recommendation,
              confidence: iv.confidence  || 0,
              reasoning:  iv.reasoning   || "",
            };
            if (iv.requirements) norm.requirements = iv.requirements;
          }
        }
        return norm;
      }
    } catch (e) {
      // not found under this type — try the next
    }
  }
  return null;
}

/** Agents — no backend endpoint yet, return empty list */
async function bpFetchAgents() {
  return [];
}

/**
 * POST /advisor/requests/{id}/decision
 * Resumes the Advisory Graph's human_review interrupt.
 * decision: "approve" | "reject" | "request_more_info"
 */
async function bpSubmitAdvisorDecision(requestId, { decision, notes }) {
  try {
    const data = await _apiFetch(`/advisor/requests/${requestId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, notes: notes || "" }),
    });
    return { ok: true, ...data };
  } catch (err) {
    console.error("[AdvisorAPI] bpSubmitAdvisorDecision failed:", err.message);
    return { ok: false, message: err.message };
  }
}
