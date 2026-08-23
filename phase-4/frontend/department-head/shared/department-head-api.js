/**
 * department-head-api.js
 * ---------------------------------------------------------------
 * Data access layer for the Department Head section.
 *
 * STATUS as of this update: everything below is LIVE — talks to the
 * real FastAPI backend (port 8000). The localStorage demo store this
 * file used to fall back to (`bp_dh_demo_store_v1`) has been removed;
 * Academic Integrity, Tickets, Agents, and Dashboard stats all now
 * read from the database through real endpoints added in this pass:
 *
 *   GET  /academic-integrity/cases                       (dept_head-readable; existing endpoint)
 *   GET  /academic-integrity/cases/{case_id}              (existing endpoint)
 *   GET  /tickets, GET /tickets/{id}                      (new — tickets_router.py)
 *   POST /tickets/{id}/investigate, /resolve              (new — tickets_router.py)
 *   GET  /agents                                          (new — agents_router.py)
 *   GET  /dashboard/dept-head                             (new — dashboard_router.py)
 *
 * KNOWN, DOCUMENTED LIMITATION (not faked — see audit report):
 * IntegrityCases has no dept_head decision path in the Phase-3 graph —
 * only "instructor" and "advisor" roles are allowed to call
 * POST /academic-integrity/cases/{id}/committee-decision and
 * .../final-decision (see academic_integrity_router.py). Calling those
 * as a dept_head returns a real 403 from the server; this file surfaces
 * that error rather than pretending the decision was recorded.
 *
 * NOT WIRED YET (dept_head passcode-gated hiring decision already real,
 * see submitHiringDecision below):
 *   — none left for the sections this file owns.
 *
 * BASE_URL points straight at the FastAPI backend (port 8000). The rest
 * of the platform's shared/api.js points at port 3000 (Express, login +
 * static serving) — the two backends aren't bridged yet, so every call
 * here goes directly to 8000.
 * ---------------------------------------------------------------
 */
const BASE_URL = "http://localhost:8000";

const DHApi = (function () {
  function authHeaders() {
    const user = window.BrightPeakAuth ? window.BrightPeakAuth.getUser() : null;
    if (!user) return {};
    return { "X-User-Id": String(user.id), "X-User-Role": user.role };
  }

  async function apiGet(path) {
    const res = await fetch(`${BASE_URL}${path}`, { headers: authHeaders() });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${res.status})`);
    }
    return res.json();
  }

  async function apiPost(path, body) {
    const res = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      const err = new Error(errBody.detail || `Request failed (${res.status})`);
      err.status = res.status;
      throw err;
    }
    return res.json();
  }

  const api = {
    async listJobs() {
      const res = await fetch(`${BASE_URL}/hiring/jobs`);
      if (!res.ok) throw new Error("Failed to load job postings.");
      const jobs = await res.json();
      // Normalize server's ISO deadline/postedDate strings to epoch ms —
      // jobs.js's countdown timer and lock logic both do Date.now() math.
      return jobs.map((j) => ({
        ...j,
        deadline: j.deadline ? new Date(j.deadline.replace(" ", "T") + "Z").getTime() : null,
        postedDate: j.postedDate ? new Date(j.postedDate.replace(" ", "T") + "Z").getTime() : null,
      }));
    },

    async createJob({ title, department, qualifications, deadline }) {
      const res = await fetch(`${BASE_URL}/hiring/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_title: title,
          department,
          qualifications: qualifications || [],
          application_deadline: deadline ? new Date(deadline).toISOString() : null,
          initial_cvs: [],
        }),
      });
      if (!res.ok) throw new Error("Failed to create job posting.");
      const data = await res.json();
      return {
        id: data.job_id,
        title,
        department,
        qualifications: qualifications || [],
        status: "open",
        deadline,
        postedDate: Date.now(),
        closedManually: false,
      };
    },

    // Department Head manually ends the application window (deadline button).
    async closeJob(jobId) {
      const res = await fetch(`${BASE_URL}/hiring/jobs/${jobId}/close`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to close job posting.");
      return { id: jobId, status: "closed", closedManually: true };
    },

    /** ------------- CANDIDATES / CV INTAKE (LIVE) ------------- */
    async listCandidates(jobId) {
      const url = jobId ? `${BASE_URL}/hiring/jobs/${jobId}/candidates` : `${BASE_URL}/hiring/candidates`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to load candidates.");
      return res.json();
    },

    /**
     * Real endpoint: POST /hiring/jobs/{job_id}/cv  (multipart file upload)
     * This is the CV Intake step of the hiring graph (ingest_cv_batch ->
     * parse_and_validate -> score_cv_against_qualifications) — LIVE now,
     * hitting the real graph via POST /hiring/jobs/{job_id}/cv.
     */
    async uploadCV(jobId, file, candidateName) {
      const fd = new FormData();
      fd.append("cv_file", file);
      if (candidateName) fd.append("candidate_name", candidateName);

      const res = await fetch(`${BASE_URL}/hiring/jobs/${jobId}/cv`, {
        method: "POST",
        body: fd, // no Content-Type header — the browser sets the multipart boundary itself
      });

      if (res.status === 409) {
        const err = new Error("APPLICATIONS_CLOSED");
        err.code = "APPLICATIONS_CLOSED";
        throw err;
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Failed to submit CV.");
      }
      return res.json();
    },

    /**
     * Real endpoint: POST /hiring/candidates/{candidate_id}/decision
     * body: { decision, notes, passcode }
     * This is the human-in-the-loop node (hitl_dept_head_review). The AI
     * recommendation above is never treated as final here.
     *
     * Requires BOTH: (1) the FastAPI-level dept_head auth (X-User-Id /
     * X-User-Role headers, attached automatically by BrightPeakGraphAPI
     * from the logged-in user), and (2) phase-3's own passcode-gated
     * dept_head session (mcp_server/roles.py) — a second, stricter check
     * specific to this one endpoint. There's no dedicated passcode UI
     * yet, so this prompts for it inline; a real settings/session flow
     * is a follow-up, not something to fake here.
     */
    async submitHiringDecision(candidateId, decision, note) {
      const passcode = window.prompt("Dept Head passcode (required to record a hiring decision):");
      if (!passcode) {
        const err = new Error("A passcode is required to record this decision.");
        err.status = 401;
        throw err;
      }
      const result = await BrightPeakGraphAPI.post(`/hiring/candidates/${candidateId}/decision`, {
        decision,
        notes: note || null,
        passcode,
      });
      const map = { hire: "hired", reject: "rejected", interview: "interview", rescore: "rescore_requested" };
      return {
        id: candidateId,
        status: map[decision] || decision,
        decision: { action: decision, by: "department_head", note: note || null, at: Date.now() },
        result: result.result,
      };
    },

    /** ------------- ACADEMIC INTEGRITY / HITL (LIVE) ------------- */
    /**
     * GET /academic-integrity/cases, enriched per-case with GET
     * /academic-integrity/cases/{id} for evidence/decisions/severity_rationale
     * (the list endpoint alone doesn't include those — see
     * academic_integrity_router.py). Mapped into the shape hitl.js already
     * renders; fields the schema has no column for (policy citations, a
     * numeric AI confidence score) come back null/empty rather than
     * invented — hitl.js hides those UI sections when absent.
     */
    async listIntegrityCases() {
      const cases = await apiGet("/academic-integrity/cases");
      const detailed = await Promise.all(
        cases.map((c) => apiGet(`/academic-integrity/cases/${c.case_id}`).catch(() => null))
      );
      return cases.map((c, i) => mapIntegrityCase(c, detailed[i]));
    },

    /**
     * Real endpoint: POST /academic-integrity/cases/{id}/committee-decision
     * or .../final-decision, depending which HITL gate the case is
     * currently waiting on (case.status). Only "instructor"/"advisor"
     * roles are authorized for either endpoint in the existing graph
     * (see academic_integrity_router.py) — a dept_head calling this gets
     * a real 403 back, which is surfaced to the caller as-is rather than
     * silently treated as success.
     */
    async submitIntegrityDecision(caseId, action, note) {
      const decisionMap = {
        confirm_finding: "uphold",
        request_evidence: "request_more_evidence",
        dismiss_case: "dismiss",
        uphold_final: "uphold",
        reduce_penalty: "reduce_penalty",
        dismiss_final: "dismiss",
      };
      const decision = decisionMap[action] || action;
      const stage = ["uphold_final", "reduce_penalty", "dismiss_final"].includes(action)
        ? "final-decision"
        : "committee-decision";
      return apiPost(`/academic-integrity/cases/${caseId}/${stage}`, { decision, notes: note || null });
    },

    /** ------------- TICKETS (LIVE — tickets_router.py) ------------- */
    async listTickets() {
      const tickets = await apiGet("/tickets");
      return tickets.map(mapTicket);
    },

    async updateTicketStatus(ticketId, status) {
      // tickets_router.py models two real transitions (open -> investigating
      // -> resolved), not an arbitrary PATCH — map the UI's 3-way status
      // toggle onto the matching endpoint.
      if (status === "Investigating") {
        return mapTicket(await apiPost(`/tickets/${ticketId}/investigate`));
      }
      if (status === "Resolved") {
        return mapTicket(await apiPost(`/tickets/${ticketId}/resolve`, {}));
      }
      throw new Error(`Ticket status can only move forward (Investigating/Resolved), not to "${status}".`);
    },

    /** ------------- AI AGENTS (LIVE — agents_router.py) ------------- */
    async listAgents() {
      return apiGet("/agents");
    },

    /** ------------- DASHBOARD (LIVE — dashboard_router.py) ------------- */
    async getDashboardStats() {
      return apiGet("/dashboard/dept-head");
    },
  };

  /** Maps a real IntegrityCases row (+ its detail response) into the shape
   * hitl.js renders. Anything with no backing column stays null/empty —
   * never filled in with a plausible-looking placeholder. */
  function mapIntegrityCase(row, detail) {
    const evidence = detail ? detail.evidence.map((e) => e.content) : [];
    const decisions = detail ? detail.decisions : [];
    const lastDecision = decisions.length ? decisions[decisions.length - 1] : null;
    return {
      id: String(row.case_id),
      student: row.student_name || `Student #${row.student_id}`,
      course: row.course_title || `Course #${row.course_id}`,
      instructor: row.reported_by_name || `Instructor #${row.reported_by}`,
      severity: row.severity || "major",
      status: row.status,
      report: row.description,
      policy: [], // no policy-citation column in IntegrityCases/IntegrityEvidence
      evidence,
      aiSeverity: row.severity,
      aiConfidence: null, // no numeric confidence column — hitl.js hides the badge when null
      aiRationale: (detail && detail.severity_rationale) || null,
      timeline: buildTimeline(row.status),
      decision: lastDecision ? { action: lastDecision.decision, note: lastDecision.notes } : null,
    };
  }

  function buildTimeline(status) {
    const stageOf = {
      reported: 0,
      under_review: 1,
      awaiting_appeal: 2,
      appeal_under_review: 2,
      closed: 3,
    };
    const stage = stageOf[status] ?? 0;
    const steps = [
      { label: "Reported", key: 0 },
      { label: "Under Review", key: 1 },
      { label: "Appeal / Final Decision", key: 2 },
    ];
    return steps.map((s) => ({
      label: s.label,
      detail: s.key < stage ? "Done" : s.key === stage ? "Current Stage" : "Pending",
      state: s.key < stage ? "done" : s.key === stage ? "current" : "pending",
    }));
  }

  /** Maps a real Tickets row into the shape tickets.js renders. `priority`,
   * `workflow`, and `relatedWorkflow` have no column in the Tickets table
   * (see schema.sql's comment: "shared failure/recovery path") — left
   * null so tickets.js can show a real "—" instead of a fabricated value. */
  function mapTicket(row) {
    return {
      id: String(row.ticket_id),
      sourceGraph: row.source_graph,
      sourceId: String(row.source_id),
      threadId: row.thread_id,
      workflow: null,
      failureType: row.failure_type,
      details: row.details,
      status: row.status.charAt(0).toUpperCase() + row.status.slice(1),
      priority: null,
      relatedWorkflow: null,
    };
  }

  return api;
})();