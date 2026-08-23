/**
 * department-head-api.js
 * ---------------------------------------------------------------
 * Data access layer for the Department Head section.
 *
 * STATUS as of this update:
 *   LIVE  — Jobs + Candidates/CV Intake (this file talks to the real
 *           phase-3 faculty_hiring graph via phase-4/backend/routers/
 *           hiring_router.py, port 8000)
 *   MOCK  — Academic Integrity HITL, Tickets, Agents, Dashboard stats
 *           (still localStorage — no auth/endpoints exist for these yet)
 *
 * LIVE endpoints in use:
 *   GET  /hiring/jobs
 *   GET  /hiring/jobs/{job_id}/candidates
 *   GET  /hiring/candidates                      (no job filter)
 *   POST /hiring/jobs
 *   POST /hiring/jobs/{job_id}/cv                (multipart file upload)
 *   POST /hiring/jobs/{job_id}/close
 *
 * NOT WIRED YET (still mock — need dept_head auth session first, see
 * mcp_server/roles.py + hiring_router.py's bottom note):
 *   POST /hiring/candidates/{candidate_id}/decision   (hire/reject/interview/rescore)
 *   GET  /hitl/academic-integrity/cases
 *   POST /hitl/academic-integrity/cases/{case_id}/decision
 *   GET  /tickets
 *   PATCH /tickets/{ticket_id}/status
 *   GET  /agents
 *
 * BASE_URL points straight at the FastAPI backend (port 8000). The rest
 * of the platform's shared/api.js points at port 3000 (Express, login +
 * static serving) — the two backends aren't bridged yet, so hiring calls
 * go directly to 8000 for now instead of through a shared client.
 * ---------------------------------------------------------------
 */
const BASE_URL = "http://localhost:8000";

const DHApi = (function () {
  const STORE_KEY = "bp_dh_demo_store_v1";

  function seed() {
    const now = Date.now();
    const day = 24 * 60 * 60 * 1000;
    return {
      jobs: [
        {
          id: "job-ds-instructor",
          title: "Data Science Instructor",
          department: "Computer Science",
          qualifications: ["Bachelor's degree", "Python", "Machine Learning", "2+ years experience", "Teaching experience"],
          status: "open", // open | closed
          deadline: now + 2 * day,
          postedDate: now - 5 * day,
          closedManually: false
        },
        {
          id: "job-cs-professor",
          title: "Professor of Computer Science",
          department: "Computer Science",
          qualifications: ["PhD Computer Science", "Machine Learning", "AI Ethics", "Publication record"],
          status: "open",
          deadline: now + 10 * day,
          postedDate: now - 20 * day,
          closedManually: false
        },
        {
          id: "job-math-lecturer",
          title: "Mathematics Lecturer",
          department: "Mathematics",
          qualifications: ["Master's degree", "Statistics", "3+ years teaching"],
          status: "closed",
          deadline: now - 3 * day,
          postedDate: now - 30 * day,
          closedManually: false
        }
      ],
      candidates: [
        {
          id: "cand-elena-jenkins",
          jobId: "job-cs-professor",
          name: "Dr. Elena Jenkins",
          university: "Ph.D. Computer Science, MIT",
          experienceYears: 8,
          skills: ["Machine Learning", "AI Ethics", "Grant Writing"],
          teachingExperienceYears: 5,
          aiScore: 94,
          status: "ai_scored", // parsing | ai_scored | shortlisted | interview | hired | rejected | rescore_requested
          aiRecommendation: "Strongly Recommended for Interview",
          keyStrengths: ["Extensive publication record in top-tier AI ethics journals"],
          decision: null,
          source: "seed"
        },
        {
          id: "cand-sara-ahmed",
          jobId: "job-ds-instructor",
          name: "Sara Ahmed",
          university: "B.Sc. Computer Science",
          experienceYears: 3,
          skills: ["Python", "Machine Learning"],
          teachingExperienceYears: 2,
          aiScore: 95,
          status: "shortlisted",
          aiRecommendation: "Strongly Recommended for Hire",
          keyStrengths: ["Meets all required qualifications", "Strong teaching background"],
          decision: null,
          source: "seed"
        },
        {
          id: "cand-omar-ali",
          jobId: "job-ds-instructor",
          name: "Omar Ali",
          university: "B.Sc. Computer Science",
          experienceYears: 4,
          skills: ["Python", "Machine Learning"],
          teachingExperienceYears: 0,
          aiScore: 82,
          status: "shortlisted",
          aiRecommendation: "Recommended for Interview",
          keyStrengths: ["Strong technical experience"],
          decision: null,
          source: "seed"
        },
        {
          id: "cand-mariam-hassan",
          jobId: "job-ds-instructor",
          name: "Mariam Hassan",
          university: "B.Sc. Computer Science",
          experienceYears: null,
          skills: ["Python", "Machine Learning"],
          teachingExperienceYears: null,
          aiScore: 58,
          status: "ai_scored",
          aiRecommendation: "Incomplete profile — missing experience data. Not auto-ranked.",
          keyStrengths: [],
          decision: null,
          source: "seed"
        }
      ],
      integrityCases: [
        {
          id: "AI-2024-089",
          student: "J. Smith",
          course: "CS301 (Data Structures)",
          instructor: "Dr. R. Patel",
          severity: "Major",
          status: "under_review", // reported | under_review | awaiting_appeal | closed
          report: "Submission for Assignment 4 contains structurally identical code blocks to a known GitHub repository, despite obfuscation attempts.",
          policy: ["ACAD-POL-104", "CS-DEPT-22"],
          evidence: ["Student_Submission.py", "Source_Reference_Repo"],
          aiSeverity: "Major",
          aiConfidence: 92,
          aiRationale: "AST (Abstract Syntax Tree) comparison confirms 87% structural similarity. Variable renaming patterns align with common obfuscation tools. Low probability of independent creation.",
          timeline: [
            { label: "Reported", detail: "Oct 24, 09:12 AM", state: "done" },
            { label: "Under Review", detail: "Current Stage", state: "current" },
            { label: "Final Decision", detail: "Pending", state: "pending" }
          ],
          decision: null
        },
        {
          id: "AI-2024-087",
          student: "M. Johnson",
          course: "ENG102",
          instructor: "Prof. L. Owens",
          severity: "Minor",
          status: "reported",
          report: "Suspected undisclosed use of generative AI tools for a reflective writing assignment.",
          policy: ["ACAD-POL-110"],
          evidence: ["Submission_Draft.docx", "Turnitin_AI_Report.pdf"],
          aiSeverity: "Minor",
          aiConfidence: 61,
          aiRationale: "Stylometric analysis flags moderate deviation from student's writing baseline. Confidence is moderate; recommend committee review before formal charge.",
          timeline: [
            { label: "Reported", detail: "Oct 26, 02:40 PM", state: "current" },
            { label: "Under Review", detail: "Not started", state: "pending" },
            { label: "Final Decision", detail: "Pending", state: "pending" }
          ],
          decision: null
        },
        {
          id: "AI-2024-082",
          student: "A. Williams",
          course: "MATH410",
          instructor: "Dr. K. Nasser",
          severity: "Severe",
          status: "awaiting_appeal",
          report: "Unauthorized notes and a second device were found during a proctored final exam.",
          policy: ["ACAD-POL-104", "EXAM-COND-03"],
          evidence: ["Proctor_Incident_Report.pdf", "Exam_Camera_Still.jpg"],
          aiSeverity: "Severe",
          aiConfidence: 97,
          aiRationale: "Proctoring log flags a device-detection event matching the reported timestamp with 97% confidence. Physical evidence corroborates proctor statement.",
          timeline: [
            { label: "Reported", detail: "Oct 18, 11:05 AM", state: "done" },
            { label: "Under Review", detail: "Completed Oct 20", state: "done" },
            { label: "Student Appeal", detail: "Current Stage", state: "current" },
            { label: "Final Decision", detail: "Pending", state: "pending" }
          ],
          decision: null
        }
      ],
      tickets: [
        {
          id: "TKT-8942",
          sourceGraph: "Faculty Hiring",
          sourceId: "cand-mariam-hassan",
          threadId: "thr-7781",
          workflow: "Dossier Processing",
          failureType: "CV Parsing Anomaly",
          details: "parse_and_validate returned a malformed schema for experience field ('three maybe four years???'). Checkpoint held at parse_and_validate.",
          status: "Open",
          priority: "High",
          relatedWorkflow: "parse_and_validate"
        },
        {
          id: "TKT-8938",
          sourceGraph: "Academic Integrity",
          sourceId: "AI-2024-087",
          threadId: "thr-7765",
          workflow: "Committee Review",
          failureType: "Committee Bias Flag",
          details: "Reviewer assignment heuristic flagged a potential conflict of interest requiring manual reassignment.",
          status: "Investigating",
          priority: "Medium",
          relatedWorkflow: "committee_review"
        },
        {
          id: "TKT-8935",
          sourceGraph: "Advisory",
          sourceId: "adv-4471",
          threadId: "thr-7740",
          workflow: "Student Outreach",
          failureType: "Data Sync Delay",
          details: "Advisory agent outreach queue delayed due to upstream data sync lag. Resolved after retry.",
          status: "Resolved",
          priority: "Low",
          relatedWorkflow: "student_outreach"
        }
      ],
      agents: [
        { id: "agent-hiring", name: "Faculty Hiring Agent", icon: "person_search", description: "Automates initial dossier screening, extracts metadata, and flags anomalies.", status: "Active", lastActivity: "1m ago", activeWorkflows: 14 },
        { id: "agent-integrity", name: "Academic Integrity Agent", icon: "policy", description: "Monitors committee reviews for scoring deviations and potential bias.", status: "Active", lastActivity: "5m ago", activeWorkflows: 3 },
        { id: "agent-advisory", name: "Advisory Agent", icon: "support_agent", description: "Assists students with scheduling and general inquiries.", status: "Degraded Sync", lastActivity: "12m ago", activeWorkflows: 42 },
        { id: "agent-assessment", name: "Assessment Agent", icon: "fact_check", description: "Automated grading and feedback generation for standardized testing.", status: "Active", lastActivity: "1h ago", activeWorkflows: 120 },
        { id: "agent-trackrec", name: "Track Rec Agent", icon: "route", description: "Analyzes student performance to recommend optimal degree tracks.", status: "Active", lastActivity: "2h ago", activeWorkflows: 8 }
      ]
    };
  }

  function load() {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) {
      console.warn("[DHApi] Failed to read demo store, reseeding.", e);
    }
    const fresh = seed();
    save(fresh);
    return fresh;
  }

  function save(store) {
    localStorage.setItem(STORE_KEY, JSON.stringify(store));
  }

  function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms || 250));
  }

  function uid(prefix) {
    return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
  }

  return {
    /** ------------- JOBS (LIVE — wired to phase-4/backend/routers/hiring_router.py) ------------- */
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

    /** ------------- ACADEMIC INTEGRITY / HITL ------------- */
    // Real endpoint: GET /hitl/academic-integrity/cases (NOT CONFIRMED — mocked)
    async listIntegrityCases() {
      await delay();
      return load().integrityCases;
    },

    // Real endpoint: POST /hitl/academic-integrity/cases/{case_id}/decision (NOT CONFIRMED — mocked)
    async submitIntegrityDecision(caseId, action, note) {
      await delay();
      const store = load();
      const c = store.integrityCases.find((x) => x.id === caseId);
      if (!c) throw new Error("Case not found");
      c.decision = { action, by: "department_head", note: note || null, at: Date.now() };
      if (action === "confirm_finding" || action === "dismiss_case") {
        c.status = "closed";
      } else if (action === "request_appeal") {
        c.status = "awaiting_appeal";
      }
      save(store);
      return c;
    },

    /** ------------- TICKETS ------------- */
    // Real endpoint: GET /tickets (NOT CONFIRMED — mocked; reuse existing Tickets DB structure)
    async listTickets() {
      await delay();
      return load().tickets;
    },

    // Real endpoint: PATCH /tickets/{ticket_id}/status (NOT CONFIRMED — mocked)
    async updateTicketStatus(ticketId, status) {
      await delay();
      const store = load();
      const t = store.tickets.find((x) => x.id === ticketId);
      if (!t) throw new Error("Ticket not found");
      t.status = status;
      save(store);
      return t;
    },

    /** ------------- AI AGENTS ------------- */
    // Real endpoint: GET /agents (NOT CONFIRMED — mocked, visual-only per brief)
    async listAgents() {
      await delay();
      return load().agents;
    },

    /** ------------- DASHBOARD ------------- */
    async getDashboardStats() {
      await delay();
      const store = load();
      const openJobs = store.jobs.filter((j) => j.status === "open").length;
      const awaitingDecision = store.candidates.filter((c) => ["shortlisted", "ai_scored"].includes(c.status) && !c.decision).length;
      const integrityAwaiting = store.integrityCases.filter((c) => c.status !== "closed").length;
      const openTickets = store.tickets.filter((t) => t.status !== "Resolved").length;
      return {
        activeFacultyPositions: openJobs,
        candidatesAwaitingDecision: awaitingDecision,
        integrityCasesAwaitingReview: integrityAwaiting,
        openTickets,
        hiring: {
          jobPostings: store.jobs.length,
          applications: store.candidates.length,
          shortlisted: store.candidates.filter((c) => c.status === "shortlisted").length,
          pendingDecisions: awaitingDecision
        },
        integrity: {
          openCases: store.integrityCases.filter((c) => c.status !== "closed").length,
          awaitingReview: store.integrityCases.filter((c) => c.status === "reported").length,
          appeals: store.integrityCases.filter((c) => c.status === "awaiting_appeal").length,
          finalDecisionsPending: store.integrityCases.filter((c) => c.status !== "closed").length
        }
      };
    },

    _debugReset() {
      localStorage.removeItem(STORE_KEY);
    }
  };
})();