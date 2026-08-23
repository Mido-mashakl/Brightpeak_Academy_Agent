// =========================================================
// Report Academic Integrity Case — multi-step form
//
// The frontend only collects and submits raw incident facts the
// backend actually accepts: student_id, course_id, description
// (assignment_id/similarity_score are optional and not collected
// here). Severity is never selected here — the backend classifies
// it. There is no file-upload endpoint for evidence and no
// assignment/date lookup in the schema, so those fields from the
// old mock form are not shown — see the audit report.
// =========================================================

const BP_STEPS = [
  { key: "student_course", label: "Student & Course" },
  { key: "incident", label: "Incident Details" },
  { key: "review", label: "Review & Submit" },
];

const BP_STATE = {
  step: 0,
  studentId: "",
  courseId: "",
  description: "",
  submitted: false,
};

let BP_OPTIONS = { students: [], courses: [] };

document.addEventListener("DOMContentLoaded", async () => {
  BPLayout.mount({ active: "integrity-report", userName: (window.currentUser && window.currentUser.name) || "Instructor", userRole: "Instructor" });
  document.getElementById("bp-back-icon").innerHTML = BPIcons.arrowLeft;

  try {
    const [students, courses] = await Promise.all([getStudentOptions(), getCourseOptions()]);
    BP_OPTIONS = { students, courses };
  } catch (err) {
    BPToast.error("Unable to load form options. Please try again.");
  }

  renderStepper();
  renderStep();
});

function goToStep(index) {
  if (index < 0 || index >= BP_STEPS.length) return;
  BP_STATE.step = index;
  renderStepper();
  renderStep();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderStepper() {
  const el = document.getElementById("bp-stepper");
  el.innerHTML = BP_STEPS
    .map((s, i) => {
      const state = i < BP_STATE.step ? "done" : i === BP_STATE.step ? "active" : "pending";
      const line = i < BP_STEPS.length - 1 ? `<div class="bp-step-line"></div>` : "";
      return `<div class="bp-step ${state}"><div class="num">${state === "done" ? BPIcons.check : i + 1}</div><span>${s.label}</span></div>${line}`;
    })
    .join("");
}

function renderStep() {
  const content = document.getElementById("bp-step-content");
  const actions = document.getElementById("bp-form-actions");
  const step = BP_STEPS[BP_STATE.step].key;

  if (BP_STATE.submitted) {
    content.innerHTML = successHtml();
    actions.innerHTML = "";
    return;
  }

  if (step === "student_course") content.innerHTML = stepStudentCourse();
  if (step === "incident") content.innerHTML = stepIncident();
  if (step === "review") content.innerHTML = stepReview();

  wireStepEvents(step);
  renderActions(step);
}

// ---------------------------------------------------------
// Step 1 — Student & Course
// ---------------------------------------------------------
function stepStudentCourse() {
  return `
    <div class="bp-field">
      <label>Student</label>
      <select id="bp-student">
        <option value="">Select student</option>
        ${BP_OPTIONS.students.map((s) => `<option value="${s.id}" ${String(s.id) === String(BP_STATE.studentId) ? "selected" : ""}>${s.name}</option>`).join("")}
      </select>
    </div>
    <div class="bp-field">
      <label>Course</label>
      <select id="bp-course">
        <option value="">Select course</option>
        ${BP_OPTIONS.courses.map((c) => `<option value="${c.id}" ${String(c.id) === String(BP_STATE.courseId) ? "selected" : ""}>${c.name}</option>`).join("")}
      </select>
    </div>
  `;
}

// ---------------------------------------------------------
// Step 2 — Incident Details
// (No severity selector — backend classifies severity. No
// incident-type or date field — no such columns on IntegrityCases;
// the report timestamp is set by the server.)
// ---------------------------------------------------------
function stepIncident() {
  return `
    <div class="bp-field">
      <label>Description</label>
      <textarea class="bp-textarea" id="bp-description" placeholder="Describe what happened...">${BP_STATE.description}</textarea>
      <div class="hint">Provide factual details of the incident. Severity is determined automatically after submission.</div>
    </div>
  `;
}

// ---------------------------------------------------------
// Step 3 — Review & Submit
// ---------------------------------------------------------
function stepReview() {
  const student = BP_OPTIONS.students.find((s) => String(s.id) === String(BP_STATE.studentId));
  const course = BP_OPTIONS.courses.find((c) => String(c.id) === String(BP_STATE.courseId));
  return `
    <div class="bp-summary-grid">
      <div class="bp-summary-item"><div class="k">Student</div><div class="v">${student ? student.name : "—"}</div></div>
      <div class="bp-summary-item"><div class="k">Course</div><div class="v">${course ? course.name : "—"}</div></div>
      <div class="bp-summary-item full"><div class="k">Description</div><div class="v" style="font-weight:400">${BP_STATE.description || "—"}</div></div>
    </div>
  `;
}

function successHtml() {
  return `
    <div class="bp-success-box">
      <div class="bp-success-icon">${BPIcons.checkCircle}</div>
      <h3>Case submitted successfully</h3>
      <p>Your report has been added to the Academic Integrity workflow.</p>
      <div style="display:flex;gap:10px;margin-top:20px">
        <a class="bp-btn bp-btn-secondary" href="integrity.html">View all cases</a>
        <a class="bp-btn bp-btn-primary" href="case-details.html?id=${BP_STATE.submittedId || ""}">Open case</a>
      </div>
    </div>
  `;
}

// ---------------------------------------------------------
// Wiring + validation
// ---------------------------------------------------------
function wireStepEvents(step) {
  if (step === "student_course") {
    document.getElementById("bp-student").addEventListener("change", (e) => (BP_STATE.studentId = e.target.value));
    document.getElementById("bp-course").addEventListener("change", (e) => (BP_STATE.courseId = e.target.value));
  }
  if (step === "incident") {
    document.getElementById("bp-description").addEventListener("input", (e) => (BP_STATE.description = e.target.value));
  }
}

function validateStep(step) {
  if (step === "student_course") {
    if (!BP_STATE.studentId) return "Please select a student.";
    if (!BP_STATE.courseId) return "Please select a course.";
  }
  if (step === "incident") {
    if (!BP_STATE.description.trim()) return "Please describe the incident.";
  }
  return null;
}

function renderActions(step) {
  const actions = document.getElementById("bp-form-actions");
  const isFirst = BP_STATE.step === 0;
  const isLast = BP_STATE.step === BP_STEPS.length - 1;

  actions.innerHTML = `
    ${!isFirst ? `<button type="button" class="bp-btn bp-btn-secondary" id="bp-back-btn">Back</button>` : ""}
    <button type="button" class="bp-btn bp-btn-primary" id="bp-next-btn">${isLast ? "Submit Case" : "Next"}</button>
  `;

  const backBtn = document.getElementById("bp-back-btn");
  if (backBtn) backBtn.addEventListener("click", () => goToStep(BP_STATE.step - 1));

  document.getElementById("bp-next-btn").addEventListener("click", async () => {
    const error = validateStep(step);
    if (error) {
      BPToast.error(error);
      return;
    }
    if (isLast) {
      await submitCase();
    } else {
      goToStep(BP_STATE.step + 1);
    }
  });
}

async function submitCase() {
  const btn = document.getElementById("bp-next-btn");
  btn.disabled = true;
  btn.textContent = "Submitting case...";

  try {
    const payload = {
      student_id: parseInt(BP_STATE.studentId, 10),
      course_id: parseInt(BP_STATE.courseId, 10),
      description: BP_STATE.description,
    };
    const result = await submitIntegrityCase(payload);
    BP_STATE.submitted = true;
    BP_STATE.submittedId = result.case_id;
    renderStep();
  } catch (err) {
    BPToast.error("Unable to submit the case.");
    btn.disabled = false;
    btn.textContent = "Submit Case";
  }
}