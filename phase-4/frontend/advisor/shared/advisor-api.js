/* ============================================================
   Brightpeak Academy — Advisor Portal
   Real API layer — wired to FastAPI backend (port 8000).

   Auth: reads the logged-in user from localStorage("user")
   and forwards X-User-Id / X-User-Role on every request,
   matching the pattern in core/auth.py.
   ============================================================ */

const BP_ADVISOR_BASE = "http://localhost:8000";

// Keys here MUST match CertificateRequests/ScholarshipApplications.status'
// CHECK constraint in db/schema.sql: 'pending' | 'eligible' | 'ineligible' |
// 'needs_review'. This used to list a different, unrelated set of keys
// (review/progress/waiting/... and pending_review/in_progress/approved/
// rejected) that never matched a real row, so BP_STATUS_META[r.status] was
// always undefined and `meta.badgeClass` below threw — which is what made
// the Requests table render empty even once the DB actually had rows.
// The old keys are kept as aliases in case any other graph/table still
// produces them, since aliasing costs nothing and a future mismatch here
// is exactly this bug again.
const BP_STATUS_META = {
  pending:          { label: "Pending",               badgeClass: "status-review" },
  needs_review:     { label: "Needs Review",           badgeClass: "status-review" },
  eligible:         { label: "Eligible",               badgeClass: "status-completed" },
  ineligible:       { label: "Ineligible",             badgeClass: "status-waiting" },

  // aliases for other graphs' status vocabularies, kept for safety
  review:           { label: "Needs Review",          badgeClass: "status-review" },
  progress:         { label: "In Progress",           badgeClass: "status-progress" },
  waiting:          { label: "Waiting for Student",   badgeClass: "status-waiting" },
  completed:        { label: "Completed",             badgeClass: "status-completed" },
  pending_review:   { label: "Needs Review",          badgeClass: "status-review" },
  in_progress:      { label: "In Progress",           badgeClass: "status-progress" },
  approved:         { label: "Completed",             badgeClass: "status-completed" },
  rejected:         { label: "Completed",             badgeClass: "status-completed" },
};

// Fallback so an unrecognized status still renders instead of throwing —
// belt-and-suspenders alongside fixing the keys above.
const BP_STATUS_META_FALLBACK = { label: "Unknown", badgeClass: "status-review" };

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

// status -> a human verdict word for the AI-recommendation card, since the
// DB only stores one status column (no separate "verdict" field).
const _VERDICT_BY_STATUS = {
  eligible:   "Eligible",
  ineligible: "Ineligible",
  needs_review: "Needs Review",
  pending:    "Pending",
};

/** Maps a raw DB row from advisor_router to the shape pages expect.
 *
 * CertificateRequests/ScholarshipApplications (db/schema.sql) only have a
 * single `recommendation` TEXT column — there is no `ai_recommendation`,
 * `confidence`, `reasoning`, `requirements`, or `timeline` column on these
 * tables. Reading those field names off `row` always returned undefined,
 * so aiRecommendation was always null and hitl.js's "No AI analysis
 * available" fallback fired for every request, even ones with a real
 * recommendation. `row.recommendation` is used as the reasoning text below;
 * confidence isn't stored at the row level (it only exists transiently in
 * the graph's human_review interrupt — see bpFetchRequestById, which layers
 * that on top when a live interrupt is open).
 */
function _normalizeRequest(row) {
  const typeLabel = row.request_type === "certificate" ? "Certificate" : "Scholarship";
  const statusRaw = row.status || "pending";
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
    aiRecommendation: row.recommendation
      ? { verdict: _VERDICT_BY_STATUS[statusRaw] || "Needs Review", confidence: null, reasoning: row.recommendation }
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
        // Merge graph state if present. The human_review interrupt payload
        // (state_graph/advisory/hitl.py's human_review_node) carries
        // {request_id, student_id, request_type, requirement_checks,
        // confidence, recommendation} — NOT ai_recommendation/reasoning/
        // requirements, which don't exist on this payload and always read
        // as undefined here. This is the live, real-time version of the
        // same data _normalizeRequest reads off the DB row; when a human_review
        // interrupt is actually open we prefer it since it has a real
        // confidence score the DB row never stores.
        if (data.graph_state) {
          norm._graphState = data.graph_state;
          if (data.graph_state._interrupt && data.graph_state._interrupt[0]) {
            const iv = data.graph_state._interrupt[0];
            if (iv.recommendation) norm.aiRecommendation = {
              verdict:    _VERDICT_BY_STATUS[norm.status] || "Needs Review",
              confidence: typeof iv.confidence === "number" ? Math.round(iv.confidence * 100) : null,
              reasoning:  iv.recommendation || "",
            };
            if (iv.requirement_checks) norm.requirements = iv.requirement_checks.map((c) => ({
              label: c.requirement,
              value: c.satisfied === true ? "Satisfied" : c.satisfied === false ? "Not satisfied" : "Pending",
            }));
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

/* ============================================================
   Real-time advisor notifications (SSE)

   GET /advisor/notifications/stream pushes a "needs_review" event the
   instant a certificate/scholarship request reaches human_review_node's
   interrupt() (state_graph/advisory/hitl.py) — i.e. the moment
   status='needs_review' is written, so a request an advisor needs to act
   on shows up within seconds instead of waiting for a manual refresh.

   EventSource can't send the usual X-User-Id/X-User-Role headers, so the
   advisor's id/role go as query params instead (see advisor_router.py's
   /notifications/stream + core/auth.py's verify_user_query for the
   server-side check and its trade-off).
   ============================================================ */

/**
 * Opens the SSE connection and calls onNeedsReview(payload) for every
 * "needs_review" event. Returns the EventSource so the caller can .close()
 * it (e.g. on page unload), though pages that stay open for the session
 * can just leave it running — EventSource reconnects on its own if the
 * connection drops.
 */
function bpSubscribeAdvisorNotifications(onNeedsReview) {
  let user;
  try {
    user = JSON.parse(localStorage.getItem("user") || "{}");
  } catch (e) {
    user = {};
  }
  if (!user.id) return null; // not logged in yet — nothing to subscribe as

  const url = `${BP_ADVISOR_BASE}/advisor/notifications/stream?user_id=${encodeURIComponent(user.id)}&role=advisor`;
  const es = new EventSource(url);
  es.addEventListener("needs_review", (e) => {
    try {
      onNeedsReview(JSON.parse(e.data));
    } catch (err) {
      console.error("[AdvisorAPI] bad needs_review payload:", err);
    }
  });
  // EventSource retries the connection itself on error/drop — nothing to
  // do here beyond not letting a console error look like something broke.
  es.onerror = () => {};
  return es;
}

/* ============================================================
   Track Recommendation — Advisor HITL review queue.

   This is a separate graph/table from CertificateRequests/
   ScholarshipApplications above (TrackRecommendations), with its own
   pause point: hitl_node in state_graph/track_recommendation/nodes_hitl.py.
   Previously nothing in the advisor frontend called any /tracks/* endpoint
   at all, so recommendations that reached status='awaiting_advisor' had
   no UI an advisor could act on. thread_id (needed to resume the paused
   graph) is written back onto the row by graph_loader.start_track_recommendation
   right after it's created — see db/schema.sql's TrackRecommendations.thread_id.
   ============================================================ */

/** GET /tracks/recommendations?status=awaiting_advisor — the advisor's
 * Track Recommendation review queue. */
async function bpFetchTrackReviewQueue() {
  const rows = await _apiFetch("/tracks/recommendations?status=awaiting_advisor");
  return rows.map((r) => ({
    id:               String(r.recommendation_id),
    threadId:         r.thread_id,
    studentId:        r.student_id,
    student:          r.student_name || `Student #${r.student_id}`,
    recommendedTrack: r.recommended_track,
    runnerUpTrack:    r.runner_up_track,
    confidence:       typeof r.confidence === "number" ? Math.round(r.confidence * 100) : null,
    status:           r.status,
  }));
}

/** GET /tracks/thread/{thread_id} — the live interrupt payload for one
 * awaiting_advisor row: student name, top/alternative track+score,
 * concerns, and the allowed actions (state_graph/track_recommendation/
 * nodes_hitl.py's hitl_node interrupt() call). */
async function bpFetchTrackThreadState(threadId) {
  const data = await _apiFetch(`/tracks/thread/${threadId}`);
  const iv = (data._interrupt && data._interrupt[0]) || null;
  if (!iv) return null;
  return {
    student:      iv.student,
    topTrack:     iv.top_recommendation ? iv.top_recommendation.track : null,
    topScore:     iv.top_recommendation ? iv.top_recommendation.score : null,
    altTrack:     iv.alternative ? iv.alternative.track : null,
    altScore:     iv.alternative ? iv.alternative.score : null,
    concerns:     iv.concerns || [],
    actions:      iv.actions || ["approve", "choose_other", "request_assessment"],
  };
}

/**
 * POST /tracks/thread/{thread_id}/advisor-decision
 * Resumes the Track Recommendation graph's hitl_node interrupt.
 * action: "approve" | "choose_other" | "request_assessment"
 * track:   required when action === "choose_other"
 * subject: required when action === "request_assessment"
 */
async function bpSubmitTrackDecision(threadId, { action, advisorName, track, subject }) {
  try {
    const body = { action, advisor_name: advisorName };
    if (track)   body.track   = track;
    if (subject) body.subject = subject;
    const data = await _apiFetch(`/tracks/thread/${threadId}/advisor-decision`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    return { ok: true, ...data };
  } catch (err) {
    console.error("[AdvisorAPI] bpSubmitTrackDecision failed:", err.message);
    return { ok: false, message: err.message };
  }
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
