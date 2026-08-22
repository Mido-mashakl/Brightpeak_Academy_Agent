/**
 * department-head-api.js
 * ---------------------------------------------------------------
 * Data access layer for the Department Head section.
 *
 * STATUS: DEMO / MOCK PERSISTENCE (localStorage).
 * No backend was available to inspect while building this preview,
 * so every function below is a stand-in. Each one is written so the
 * *only* thing that needs to change to go live is the body of the
 * function — callers (jobs.js, candidates.js, hitl.js, tickets.js,
 * agents.js) do not need to change.
 *
 * Known REAL endpoints (from project brief — confirm base URL/auth
 * headers with the existing frontend service layer before wiring up):
 *   POST /hiring/jobs
 *   POST /hiring/jobs/{job_id}/cv
 *   POST /hiring/jobs/{job_id}/close
 *
 * NOT CONFIRMED / LIKELY MISSING (used here as mock only — see
 * README report at bottom of chat for the full list):
 *   GET  /hiring/jobs
 *   GET  /hiring/jobs/{job_id}/candidates
 *   POST /hiring/candidates/{candidate_id}/decision   (hire/reject/interview/rescore)
 *   GET  /hitl/academic-integrity/cases
 *   POST /hitl/academic-integrity/cases/{case_id}/decision
 *   GET  /tickets
 *   PATCH /tickets/{ticket_id}/status
 *   GET  /agents
 * ---------------------------------------------------------------
 */
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
    /** ------------- JOBS ------------- */
    // Real endpoint: GET /hiring/jobs (NOT CONFIRMED to exist yet — mocked)
    async listJobs() {
      await delay();
      return load().jobs;
    },

    // Real endpoint: POST /hiring/jobs
    async createJob({ title, department, qualifications, deadline }) {
      await delay();
      const store = load();
      const job = {
        id: uid("job"),
        title,
        department,
        qualifications: qualifications || [],
        status: "open",
        deadline,
        postedDate: Date.now(),
        closedManually: false
      };
      store.jobs.unshift(job);
      save(store);
      return job;
    },

    // Real endpoint: POST /hiring/jobs/{job_id}/close
    // Department Head manually ends the application window (deadline button).
    async closeJob(jobId) {
      await delay();
      const store = load();
      const job = store.jobs.find((j) => j.id === jobId);
      if (!job) throw new Error("Job not found");
      job.status = "closed";
      job.closedManually = true;
      save(store);
      return job;
    },

    /** ------------- CANDIDATES / CV INTAKE ------------- */
    // Real endpoint: GET /hiring/jobs/{job_id}/candidates (NOT CONFIRMED — mocked)
    async listCandidates(jobId) {
      await delay();
      const store = load();
      return jobId ? store.candidates.filter((c) => c.jobId === jobId) : store.candidates;
    },

    /**
     * Real endpoint: POST /hiring/jobs/{job_id}/cv  (multipart file upload)
     * This is the CV Intake step of the hiring graph (ingest_cv_batch ->
     * parse_and_validate -> score_cv_against_qualifications). Since there
     * is no live parsing/scoring backend in this preview, we simulate the
     * pipeline locally so the deadline-lock UX can be demonstrated end to end.
     */
    async uploadCV(jobId, file, candidateName) {
      const store = load();
      const job = store.jobs.find((j) => j.id === jobId);
      if (!job) throw new Error("Job not found");

      const deadlinePassed = job.deadline && Date.now() > job.deadline;
      if (job.status === "closed" || job.closedManually || deadlinePassed) {
        const err = new Error("APPLICATIONS_CLOSED");
        err.code = "APPLICATIONS_CLOSED";
        throw err;
      }

      await delay(400);
      const candidate = {
        id: uid("cand"),
        jobId,
        name: candidateName || (file && file.name ? file.name.replace(/\.[^/.]+$/, "") : "New Candidate"),
        university: "Pending parse",
        experienceYears: null,
        skills: [],
        teachingExperienceYears: null,
        aiScore: null,
        status: "parsing",
        aiRecommendation: null,
        keyStrengths: [],
        decision: null,
        fileName: file ? file.name : null,
        source: "upload"
      };
      store.candidates.unshift(candidate);
      save(store);

      // Simulate parse_and_validate -> score_cv_against_qualifications
      await delay(900);
      const store2 = load();
      const c = store2.candidates.find((x) => x.id === candidate.id);
      if (c) {
        c.status = "ai_scored";
        c.aiScore = Math.floor(60 + Math.random() * 35);
        c.aiRecommendation = c.aiScore >= 85 ? "Recommended for Interview" : "Below shortlist threshold — review recommended";
        save(store2);
      }
      return candidate;
    },

    /**
     * Real endpoint: POST /hiring/candidates/{candidate_id}/decision
     * body: { decision: "hire" | "reject" | "interview" | "rescore" }
     * This is the human-in-the-loop node (hitl_dept_head_review). The AI
     * recommendation above is never treated as final here.
     */
    async submitHiringDecision(candidateId, decision, note) {
      await delay();
      const store = load();
      const c = store.candidates.find((x) => x.id === candidateId);
      if (!c) throw new Error("Candidate not found");
      const map = { hire: "hired", reject: "rejected", interview: "interview", rescore: "rescore_requested" };
      c.status = map[decision] || c.status;
      c.decision = { action: decision, by: "department_head", note: note || null, at: Date.now() };
      save(store);
      return c;
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
