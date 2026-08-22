/* ============================================================
   Brightpeak Academy — Advisor Portal
   Mock data / API layer.

   ⚠️ THIS FILE IS A STAND-IN. No real backend was available to
   inspect when this was built (see report). Every function below
   is written so it can be swapped for a real fetch() call without
   changing any page code — just replace the body.

   Real integration checklist (per implementation brief, section 9):
   - [ ] Find existing Advisor endpoints (list/detail/decision)
   - [ ] Find Advisory Graph entry point + state shape
   - [ ] Find HITL interrupt/resume mechanism
   - [ ] Find accepted decision values (approve/more_info/deny/escalate?)
   - [ ] Find DB fields for advisory requests
   ============================================================ */

const BP_MOCK_REQUESTS = [
  { id: "REQ-1032", student: "Ahmed Mostafa", studentId: "STU-10245", program: "Computer Science", level: "Level 3", type: "Certificate", status: "review", priority: "high", updated: "2h ago", submitted: "May 10, 2025",
    message: "I would like to apply for the Data Science Certificate.",
    notes: "I have completed the core courses and would like to know if I'm eligible.",
    attachments: ["Transcript.pdf"],
    programInfo: { certificate: "Data Science Certificate", plan: "2024 CS Plan", advisor: "Dr. Sarah Johnson" },
    timeline: [
      { label: "Request Submitted", date: "May 10", state: "done" },
      { label: "Data & Eligibility Check", date: "May 10", state: "done" },
      { label: "AI Analysis", date: "May 11", state: "done" },
      { label: "Advisor Review", date: "Current", state: "current" },
      { label: "Final Decision", date: "Pending", state: "pending" },
    ],
    requirements: [
      { label: "Core Courses", value: "12 / 12 Completed", ok: true },
      { label: "GPA Requirement (≥ 3.00)", value: "3.48 / 3.00", ok: true },
      { label: "Credit Hours (≥ 24)", value: "27 / 24", ok: true },
      { label: "Financial Clearance", value: "Clear", ok: true },
    ],
    aiRecommendation: { verdict: "Eligible", confidence: 94,
      reasoning: "Student has completed all required core courses with grade ≥ B. GPA is 3.48 which meets the minimum requirement. No academic holds found." },
  },
  { id: "REQ-1031", student: "Sara Ali", studentId: "STU-10221", program: "Business Administration", level: "Level 4", type: "Scholarship", status: "progress", priority: "medium", updated: "5h ago", submitted: "May 9, 2025" },
  { id: "REQ-1030", student: "Omar Hassan", studentId: "STU-10198", program: "Mechanical Engineering", level: "Level 2", type: "Certificate", status: "waiting", priority: "medium", updated: "1d ago", submitted: "May 8, 2025" },
  { id: "REQ-1029", student: "Lina Khaled", studentId: "STU-10177", program: "Graphic Design", level: "Level 3", type: "Scholarship", status: "progress", priority: "low", updated: "1d ago", submitted: "May 8, 2025" },
  { id: "REQ-1028", student: "Youssef Tarek", studentId: "STU-10156", program: "Computer Science", level: "Level 4", type: "Certificate", status: "review", priority: "high", updated: "2d ago", submitted: "May 7, 2025" },
  { id: "REQ-1027", student: "Nourhan Ali", studentId: "STU-10142", program: "Finance", level: "Level 3", type: "Scholarship", status: "progress", priority: "medium", updated: "2d ago", submitted: "May 6, 2025" },
  { id: "REQ-1026", student: "Hassan Mohamed", studentId: "STU-10119", program: "Architecture", level: "Level 2", type: "Certificate", status: "completed", priority: "low", updated: "3d ago", submitted: "May 5, 2025" },
];

const BP_STATUS_META = {
  review:    { label: "Needs Review",     badgeClass: "status-review" },
  progress:  { label: "In Progress",      badgeClass: "status-progress" },
  waiting:   { label: "Waiting for Student", badgeClass: "status-waiting" },
  completed: { label: "Completed",        badgeClass: "status-completed" },
};

const BP_AGENTS = [
  { key: "advisory_assistant", name: "Advisory Assistant", desc: "Provides academic guidance and general advising support.", accuracy: 92, lastActivity: "2m ago", active: true },
  { key: "eligibility_agent", name: "Eligibility Agent", desc: "Checks eligibility for certificates and scholarships.", accuracy: 94, lastActivity: "3m ago", active: true },
  { key: "policy_search_agent", name: "Policy Search Agent", desc: "Searches policies and academic rules.", accuracy: 90, lastActivity: "1m ago", active: true },
  { key: "plan_generator_agent", name: "Plan Generator Agent", desc: "Generates academic plans and course recommendations.", accuracy: 91, lastActivity: "4m ago", active: true },
];

/** GET /api/advisor/dashboard/stats  (TODO: replace with real endpoint) */
async function bpFetchDashboardStats() {
  return {
    total: BP_MOCK_REQUESTS.length + 21, // decorative — see report
    inProgress: 14,
    pendingReview: 12,
    completed: 18,
    deltas: { total: "+12% vs last week", inProgress: "+3 vs last week", pendingReview: "+2 vs last week", completed: "+8 vs last week" },
    aiInsights: { avgEligibilityAccuracy: 92, requestsAnalyzed: 24, recommendationsGenerated: 16 },
    needingAttention: BP_MOCK_REQUESTS.filter((r) => r.status !== "completed").slice(0, 3),
  };
}

/** GET /api/advisor/requests?query=&type=&status=&page= (TODO: replace with real endpoint) */
async function bpFetchRequests({ type = "all", query = "" } = {}) {
  let items = BP_MOCK_REQUESTS;
  if (type !== "all") items = items.filter((r) => r.type.toLowerCase() === type);
  if (query) items = items.filter((r) => r.student.toLowerCase().includes(query.toLowerCase()) || r.id.toLowerCase().includes(query.toLowerCase()));
  return { items, total: 28, page: 1, pages: 4 };
}

/** GET /api/advisor/requests/:id (TODO: replace with real endpoint) */
async function bpFetchRequestById(id) {
  return BP_MOCK_REQUESTS.find((r) => r.id === id) || null;
}

/** GET /api/advisor/agents (TODO: replace with real endpoint / registry) */
async function bpFetchAgents() {
  return BP_AGENTS;
}

/**
 * POST /api/advisor/requests/:id/decision
 * TODO (critical — see brief section 7):
 * This MUST call the real Advisory Graph resume/decision endpoint.
 * Do not treat this mock resolve() as a real decision. It exists only
 * so the HITL screen has something to call while wired to fake data.
 */
async function bpSubmitAdvisorDecision(requestId, { decision, notes }) {
  console.warn(
    `[MOCK] bpSubmitAdvisorDecision called for ${requestId} with decision="${decision}". ` +
    `No real backend endpoint is connected — this decision is NOT persisted.`
  );
  return { ok: false, mocked: true, message: "No backend endpoint connected yet." };
}
