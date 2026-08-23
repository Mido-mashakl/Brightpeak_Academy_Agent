// =========================================================
// Brightpeak Academy — Instructor Portal
// API service layer
//
// This file is the ONLY place that should know whether data
// comes from mock fixtures or a real backend. Pages must call
// these functions and never read BP_MOCK directly.
//
// TODO(backend): Replace the request() implementation below
// with the project's real API client (see frontend/shared/api.js
// if one already exists) once Academic Integrity / HITL endpoints
// are available. Do not hardcode endpoint names without confirming
// the project's actual API conventions first.
// =========================================================

const BP_API_BASE = "/api/instructor"; // placeholder base path — align with real API client
const BP_USE_MOCK = true; // flip to false once real endpoints exist

// ---------------------------------------------------------
// Low-level request helper (wire up auth headers / error
// handling to match the project's existing API client)
// ---------------------------------------------------------
async function bpRequest(path, options = {}) {
  const res = await fetch(`${BP_API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...options,
  });
  if (!res.ok) {
    const err = new Error(`Request failed: ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function bpDelay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// =========================================================
// MOCK DATA — isolated. UI-development only. Never used for
// case submission, severity, HITL decisions, or workflow state.
// =========================================================
const BP_MOCK = {
  dashboard: {
    stats: { courses: 4, students: 12, reports: 3, pendingRequests: 2 },
    statusCounts: { reported: 1, underReview: 1, awaitingAppeal: 0, closed: 1 },
    recentCases: [
      { id: "1042", student: "Ahmed Ali", course: "Data Structures", severity: "major", status: "under_review", reportedLabel: "Today, 10:42 AM" },
      { id: "1038", student: "Sara Mohamed", course: "ML Basics", severity: "minor", status: "closed", reportedLabel: "May 12, 09:15 AM" },
      { id: "1035", student: "Omar Hassan", course: "Algorithms", severity: "severe", status: "committee_review", reportedLabel: "May 10, 04:30 PM" },
    ],
    // Recent write-op requests (grade/attendance/enrollment) — a separate
    // feed from Academic Integrity cases; both sit side by side on the
    // dashboard rather than being merged into one list.
    recentRequests: [
      { id: "1024", type: "grade_update", student: "Ahmed Ali", course: "Data Structures", status: "pending", submittedLabel: "2h ago" },
      { id: "1023", type: "attendance_update", student: "Sara Mohamed", course: "ML Basics", status: "pending", submittedLabel: "5h ago" },
      { id: "1020", type: "grade_update", student: "Laila Kamal", course: "Operating Systems", status: "approved", submittedLabel: "Yesterday" },
    ],
  },

  cases: [
    { id: "1042", student: "Ahmed Ali", course: "Data Structures", severity: "major", status: "under_review", reportedLabel: "Today, 10:42 AM" },
    { id: "1038", student: "Sara Mohamed", course: "ML Basics", severity: "minor", status: "closed", reportedLabel: "May 12, 09:15 AM" },
    { id: "1035", student: "Omar Hassan", course: "Algorithms", severity: "severe", status: "committee_review", reportedLabel: "May 10, 04:30 PM" },
  ],

  caseDetails: {
    "1042": {
      id: "1042",
      student: "Ahmed Ali",
      course: "Data Structures",
      reportedBy: "Fatma — Instructor",
      reportedOnLabel: "May 13, 2025 · 10:42 AM",
      status: "under_review",
      incidentType: "Cheating",
      description: "Student was observed using unauthorized notes during the in-class midterm examination.",
      evidence: [
        { name: "exam_submission.pdf", size: "1.2 MB", type: "pdf" },
        { name: "screenshot_1.png", size: "523 KB", type: "image" },
        { name: "photo_1.jpg", size: "1.1 MB", type: "image" },
      ],
      // Rendered as-is. Never computed on the frontend.
      aiAssessment: {
        severity: "MAJOR",
        policyMatchPct: 87,
        reasoning: "The incident matches the academic integrity policy on unauthorized materials usage during assessment. Multiple indicators confirm academic misconduct.",
      },
      workflow: {
        steps: [
          { key: "reported", label: "Case Reported" },
          { key: "evidence_gathered", label: "Evidence Gathered" },
          { key: "severity_analysis", label: "Severity Analysis" },
          { key: "committee_review", label: "Committee Review" },
          { key: "student_appeal", label: "Student Appeal" },
          { key: "final_decision", label: "Final Decision" },
        ],
        currentStep: "severity_analysis",
      },
    },
  },

  courses: ["Data Structures", "ML Basics", "Algorithms", "Operating Systems"],
  students: ["Ahmed Ali", "Sara Mohamed", "Omar Hassan", "Laila Kamal"],
  assessments: ["Midterm Exam", "Final Project", "Assignment 3", "Quiz 2"],

  // ---------------------------------------------------------
  // My Courses — the instructor's own courses. `courses` (above)
  // stays a plain name list for the report-case dropdown; this is
  // the richer object used by the Courses list/detail pages.
  // ---------------------------------------------------------
  courseList: [
    { id: "c1", name: "Data Structures", code: "CS201", term: "Spring 2025", studentsCount: 4, avgGrade: 76, status: "active", description: "Core data structures: lists, trees, graphs, hashing, and complexity analysis." },
    { id: "c2", name: "ML Basics", code: "CS310", term: "Spring 2025", studentsCount: 3, avgGrade: 74, status: "active", description: "Introduction to supervised/unsupervised learning and model evaluation." },
    { id: "c3", name: "Algorithms", code: "CS205", term: "Spring 2025", studentsCount: 3, avgGrade: 81, status: "active", description: "Algorithm design, greedy/DP techniques, and proofs of correctness." },
    { id: "c4", name: "Operating Systems", code: "CS330", term: "Spring 2025", studentsCount: 2, avgGrade: 72, status: "active", description: "Processes, scheduling, memory management, and file systems." },
  ],

  // ---------------------------------------------------------
  // Students — roster rows (one per enrollment) shared by both
  // the Students list page and each course's roster tab.
  // ---------------------------------------------------------
  studentRoster: [
    { id: "s1", name: "Ahmed Ali", courseId: "c1", course: "Data Structures", attendancePct: 92, avgGrade: 85, status: "good_standing" },
    { id: "s2", name: "Youssef Nabil", courseId: "c1", course: "Data Structures", attendancePct: 78, avgGrade: 70, status: "good_standing" },
    { id: "s3", name: "Hana Samir", courseId: "c1", course: "Data Structures", attendancePct: 61, avgGrade: 58, status: "at_risk" },
    { id: "s4", name: "Laila Kamal", courseId: "c1", course: "Data Structures", attendancePct: 95, avgGrade: 91, status: "good_standing" },
    { id: "s5", name: "Sara Mohamed", courseId: "c2", course: "ML Basics", attendancePct: 88, avgGrade: 79, status: "good_standing" },
    { id: "s6", name: "Mona Adel", courseId: "c2", course: "ML Basics", attendancePct: 60, avgGrade: 55, status: "at_risk" },
    { id: "s7", name: "Tarek Aziz", courseId: "c2", course: "ML Basics", attendancePct: 93, avgGrade: 89, status: "good_standing" },
    { id: "s8", name: "Omar Hassan", courseId: "c3", course: "Algorithms", attendancePct: 65, avgGrade: 58, status: "at_risk" },
    { id: "s9", name: "Karim Fathy", courseId: "c3", course: "Algorithms", attendancePct: 90, avgGrade: 88, status: "good_standing" },
    { id: "s10", name: "Rana Gamal", courseId: "c3", course: "Algorithms", attendancePct: 82, avgGrade: 74, status: "good_standing" },
    { id: "s11", name: "Nour Hesham", courseId: "c4", course: "Operating Systems", attendancePct: 84, avgGrade: 76, status: "good_standing" },
    { id: "s12", name: "Mostafa Emad", courseId: "c4", course: "Operating Systems", attendancePct: 55, avgGrade: 48, status: "at_risk" },
  ],

  // Extra profile fields merged in for the Student Details page —
  // kept separate from the roster row so list rendering stays light.
  studentDetails: {
    s1: { email: "ahmed.ali@brightpeak.edu", grades: [{ assignment: "Midterm Exam", score: 82, maxScore: 100 }, { assignment: "Assignment 3", score: 90, maxScore: 100 }, { assignment: "Quiz 2", score: 84, maxScore: 100 }], attendance: { present: 27, absent: 2, excused: 1, totalSessions: 30 } },
    s2: { email: "youssef.nabil@brightpeak.edu", grades: [{ assignment: "Midterm Exam", score: 68, maxScore: 100 }, { assignment: "Assignment 3", score: 74, maxScore: 100 }], attendance: { present: 22, absent: 6, excused: 1, totalSessions: 29 } },
    s3: { email: "hana.samir@brightpeak.edu", grades: [{ assignment: "Midterm Exam", score: 55, maxScore: 100 }, { assignment: "Assignment 3", score: 60, maxScore: 100 }], attendance: { present: 18, absent: 11, excused: 0, totalSessions: 29 } },
    s4: { email: "laila.kamal@brightpeak.edu", grades: [{ assignment: "Midterm Exam", score: 93, maxScore: 100 }, { assignment: "Assignment 3", score: 89, maxScore: 100 }], attendance: { present: 29, absent: 1, excused: 0, totalSessions: 30 } },
    s5: { email: "sara.mohamed@brightpeak.edu", grades: [{ assignment: "Final Project", score: 80, maxScore: 100 }, { assignment: "Quiz 2", score: 78, maxScore: 100 }], attendance: { present: 25, absent: 3, excused: 1, totalSessions: 29 } },
    s6: { email: "mona.adel@brightpeak.edu", grades: [{ assignment: "Final Project", score: 52, maxScore: 100 }, { assignment: "Quiz 2", score: 58, maxScore: 100 }], attendance: { present: 16, absent: 12, excused: 0, totalSessions: 28 } },
    s7: { email: "tarek.aziz@brightpeak.edu", grades: [{ assignment: "Final Project", score: 91, maxScore: 100 }, { assignment: "Quiz 2", score: 87, maxScore: 100 }], attendance: { present: 27, absent: 2, excused: 0, totalSessions: 29 } },
    s8: { email: "omar.hassan@brightpeak.edu", grades: [{ assignment: "Assignment 3", score: 60, maxScore: 100 }, { assignment: "Quiz 2", score: 56, maxScore: 100 }], attendance: { present: 19, absent: 10, excused: 0, totalSessions: 29 } },
    s9: { email: "karim.fathy@brightpeak.edu", grades: [{ assignment: "Assignment 3", score: 90, maxScore: 100 }, { assignment: "Quiz 2", score: 86, maxScore: 100 }], attendance: { present: 26, absent: 3, excused: 0, totalSessions: 29 } },
    s10: { email: "rana.gamal@brightpeak.edu", grades: [{ assignment: "Assignment 3", score: 76, maxScore: 100 }, { assignment: "Quiz 2", score: 72, maxScore: 100 }], attendance: { present: 24, absent: 5, excused: 0, totalSessions: 29 } },
    s11: { email: "nour.hesham@brightpeak.edu", grades: [{ assignment: "Midterm Exam", score: 78, maxScore: 100 }, { assignment: "Final Project", score: 74, maxScore: 100 }], attendance: { present: 23, absent: 4, excused: 1, totalSessions: 28 } },
    s12: { email: "mostafa.emad@brightpeak.edu", grades: [{ assignment: "Midterm Exam", score: 45, maxScore: 100 }, { assignment: "Final Project", score: 51, maxScore: 100 }], attendance: { present: 15, absent: 13, excused: 0, totalSessions: 28 } },
  },

  // NOTE on availableActions / pendingWith:
  // "Committee Review" and "Final Decision" are workflow steps owned by the
  // Academic Integrity Committee / Department Head — not the instructor.
  // The instructor can open and read these cases, but must never be shown
  // Approve/Reject for a decision that isn't theirs to make. availableActions
  // stays [] for both until the backend confirms a HITL node the instructor
  // actually owns; pendingWith drives the "awaiting X" message on the review
  // screen so it's clear WHO the case is with, not just "someone else".
  hitl: {
    needsAttention: [],
    awaitingAppeal: [],
    committeeDecisions: [
      {
        id: "1042", student: "Ahmed Ali", course: "Data Structures", severity: "major",
        workflowStep: "Committee Review", evidenceCount: 4, policyMatchPct: 87,
        availableActions: [], pendingWith: "Academic Integrity Committee",
      },
      {
        id: "1035", student: "Omar Hassan", course: "Algorithms", severity: "severe",
        workflowStep: "Final Decision", evidenceCount: 2, policyMatchPct: 91,
        availableActions: [], pendingWith: "Department Head",
      },
    ],
  },

  // ---------------------------------------------------------
  // Requests — write-operation proposals (record_grade,
  // update_attendance, change_enrollment_status) that the backend
  // holds for human confirmation before they touch the DB. Unlike
  // Academic Integrity's Committee/Dept-Head-owned steps, these
  // ARE the instructor's own decision to make — hence Approve/Reject
  // lives on the request itself, not escalated elsewhere.
  //
  // List rows stay lightweight; full fields (current/proposed value,
  // agent reasoning, evidence) are merged in by getRequest(id), same
  // pattern as getIntegrityCase / getHITLCase above.
  // ---------------------------------------------------------
  requests: [
    { id: "1024", type: "grade_update", student: "Ahmed Ali", course: "Data Structures", status: "pending", submittedLabel: "2h ago" },
    { id: "1023", type: "attendance_update", student: "Sara Mohamed", course: "ML Basics", status: "pending", submittedLabel: "5h ago" },
    { id: "1020", type: "grade_update", student: "Laila Kamal", course: "Operating Systems", status: "approved", submittedLabel: "Yesterday" },
    { id: "1018", type: "enrollment_change", student: "Omar Hassan", course: "Algorithms", status: "rejected", submittedLabel: "May 11" },
  ],

  requestDetails: {
    "1024": {
      fieldLabel: "Grade",
      currentValue: "72",
      proposedValue: "85",
      agentReasoning: "Recalculated from the final exam and project rubric after a grading dispute; the new total reflects corrected rubric weights approved by the department.",
      evidence: ["Student record", "Course record", "Grade history", "Academic policy"],
      availableActions: ["approve", "request_info", "reject"],
      decision: null,
    },
    "1023": {
      fieldLabel: "Attendance",
      currentValue: "Absent — May 18",
      proposedValue: "Present — May 18",
      agentReasoning: "Student submitted a medical certificate for the missed session; agent cross-checked it against the registrar's excused-absence policy.",
      evidence: ["Student record", "Course record", "Attendance log", "Medical certificate"],
      availableActions: ["approve", "request_info", "reject"],
      decision: null,
    },
    "1020": {
      fieldLabel: "Grade",
      currentValue: "78",
      proposedValue: "84",
      agentReasoning: "Extra-credit assignment score added after late submission was approved by the instructor.",
      evidence: ["Student record", "Course record", "Grade history"],
      availableActions: [],
      decision: { action: "approve", byLabel: "Fatma — Instructor", atLabel: "Yesterday, 3:10 PM" },
    },
    "1018": {
      fieldLabel: "Enrollment Status",
      currentValue: "Enrolled",
      proposedValue: "Withdrawn",
      agentReasoning: "Requested withdrawal after add/drop deadline; flagged for instructor confirmation since it falls outside the standard withdrawal window.",
      evidence: ["Student record", "Course record", "Academic policy"],
      availableActions: [],
      decision: { action: "reject", byLabel: "Fatma — Instructor", atLabel: "May 11, 11:20 AM" },
    },
  },

  agents: [
    {
      id: "academic-integrity-agent",
      name: "Academic Integrity Agent",
      description: "Assists with academic integrity workflows and case analysis.",
      status: "available",
    },
  ],
};

// =========================================================
// Service functions
// =========================================================

async function getInstructorDashboard() {
  if (BP_USE_MOCK) {
    await bpDelay(350);
    return BP_MOCK.dashboard;
  }
  return bpRequest("/dashboard");
}

async function getIntegrityCases({ search = "", status = "all" } = {}) {
  if (BP_USE_MOCK) {
    await bpDelay(350);
    let rows = BP_MOCK.cases;
    if (status !== "all") rows = rows.filter((c) => c.status === status);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      rows = rows.filter(
        (c) =>
          c.student.toLowerCase().includes(q) ||
          c.course.toLowerCase().includes(q) ||
          c.id.includes(q)
      );
    }
    return rows;
  }
  const params = new URLSearchParams({ search, status });
  return bpRequest(`/integrity/cases?${params.toString()}`);
}

async function getIntegrityCase(id) {
  if (BP_USE_MOCK) {
    await bpDelay(300);
    const record = BP_MOCK.caseDetails[id];
    if (!record) throw new Error("Case not found");
    return record;
  }
  return bpRequest(`/integrity/cases/${id}`);
}

// Form option lists — kept behind service functions so the real
// endpoints (students/courses/assessments lookup) can be dropped
// in without touching the form page.
async function getStudentOptions() {
  if (BP_USE_MOCK) { await bpDelay(150); return BP_MOCK.students; }
  return bpRequest("/lookups/students");
}
async function getCourseOptions() {
  if (BP_USE_MOCK) { await bpDelay(150); return BP_MOCK.courses; }
  return bpRequest("/lookups/courses");
}
async function getAssessmentOptions() {
  if (BP_USE_MOCK) { await bpDelay(150); return BP_MOCK.assessments; }
  return bpRequest("/lookups/assessments");
}

// Real mutation — never mocked as "successful" beyond UI dev convenience.
// Backend owns severity classification; frontend only submits raw facts.
async function submitIntegrityCase(formData) {
  if (BP_USE_MOCK) {
    await bpDelay(700);
    // Simulated success for UI development only.
    return { id: String(Math.floor(1000 + Math.random() * 9000)), status: "reported" };
  }
  return bpRequest("/integrity/cases", {
    method: "POST",
    body: JSON.stringify(formData),
  });
}

async function getCourses() {
  if (BP_USE_MOCK) {
    await bpDelay(350);
    return BP_MOCK.courseList;
  }
  return bpRequest("/courses");
}

async function getCourse(id) {
  if (BP_USE_MOCK) {
    await bpDelay(300);
    const course = BP_MOCK.courseList.find((c) => c.id === id);
    if (!course) throw new Error("Course not found");
    const roster = BP_MOCK.studentRoster.filter((s) => s.courseId === id);
    return { ...course, roster };
  }
  return bpRequest(`/courses/${id}`);
}

async function getStudents({ search = "", course = "all" } = {}) {
  if (BP_USE_MOCK) {
    await bpDelay(350);
    let rows = BP_MOCK.studentRoster;
    if (course !== "all") rows = rows.filter((s) => s.courseId === course);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      rows = rows.filter((s) => s.name.toLowerCase().includes(q) || s.course.toLowerCase().includes(q));
    }
    return rows;
  }
  const params = new URLSearchParams({ search, course });
  return bpRequest(`/students?${params.toString()}`);
}

async function getStudent(id) {
  if (BP_USE_MOCK) {
    await bpDelay(300);
    const row = BP_MOCK.studentRoster.find((s) => s.id === id);
    if (!row) throw new Error("Student not found");
    const details = BP_MOCK.studentDetails[id] || null;
    return { ...row, ...details };
  }
  return bpRequest(`/students/${id}`);
}

async function getRequests({ search = "", status = "all" } = {}) {
  if (BP_USE_MOCK) {
    await bpDelay(350);
    let rows = BP_MOCK.requests;
    if (status !== "all") rows = rows.filter((r) => r.status === status);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      rows = rows.filter(
        (r) =>
          r.student.toLowerCase().includes(q) ||
          r.course.toLowerCase().includes(q) ||
          r.id.includes(q)
      );
    }
    return rows;
  }
  const params = new URLSearchParams({ search, status });
  return bpRequest(`/requests?${params.toString()}`);
}

async function getRequest(id) {
  if (BP_USE_MOCK) {
    await bpDelay(300);
    const record = BP_MOCK.requests.find((r) => r.id === id);
    if (!record) throw new Error("Request not found");
    const details = BP_MOCK.requestDetails[id] || null;
    return { ...record, ...details };
  }
  return bpRequest(`/requests/${id}`);
}

// Real mutation — backend authorizes/executes record_grade,
// update_attendance, or change_enrollment_status. This is the
// instructor's own decision (unlike Academic Integrity's committee
// steps), so it's submitted directly from the request itself.
async function submitRequestDecision(id, action, payload = {}) {
  if (BP_USE_MOCK) {
    await bpDelay(500);
    const status =
      action === "approve" ? "approved" : action === "reject" ? "rejected" : action === "request_info" ? "info_requested" : "pending";
    return { id, action, status, ...payload };
  }
  return bpRequest(`/requests/${id}/decision`, {
    method: "POST",
    body: JSON.stringify({ action, ...payload }),
  });
}

async function getHITLCases() {
  if (BP_USE_MOCK) {
    await bpDelay(350);
    return BP_MOCK.hitl;
  }
  return bpRequest("/hitl/cases");
}

async function getHITLCase(id) {
  if (BP_USE_MOCK) {
    await bpDelay(300);
    const all = [
      ...BP_MOCK.hitl.needsAttention,
      ...BP_MOCK.hitl.awaitingAppeal,
      ...BP_MOCK.hitl.committeeDecisions,
    ];
    const record = all.find((c) => c.id === id);
    if (!record) throw new Error("HITL case not found");
    // Merge with full case details for the review screen.
    const details = BP_MOCK.caseDetails[id] || null;
    return { ...record, details };
  }
  return bpRequest(`/hitl/cases/${id}`);
}

// Real mutation — backend authorizes/executes the decision.
async function submitHITLDecision(id, action) {
  if (BP_USE_MOCK) {
    await bpDelay(500);
    return { id, action, status: "recorded" };
  }
  return bpRequest(`/hitl/cases/${id}/decision`, {
    method: "POST",
    body: JSON.stringify({ action }),
  });
}

async function getAgents() {
  if (BP_USE_MOCK) {
    await bpDelay(250);
    return BP_MOCK.agents;
  }
  return bpRequest("/agents");
}
