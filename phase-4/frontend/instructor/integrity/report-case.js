// =========================================================
// Report Academic Integrity Case — multi-step form
//
// The frontend only collects and submits raw incident facts.
// Severity is never selected here — the backend classifies it.
// =========================================================

const BP_STEPS = [
  { key: "student_course", label: "Student & Course" },
  { key: "incident", label: "Incident Details" },
  { key: "evidence", label: "Evidence" },
  { key: "review", label: "Review & Submit" },
];

const BP_STATE = {
  step: 0,
  student: "",
  course: "",
  assessment: "",
  incidentType: "Cheating",
  date: "",
  description: "",
  // Evidence metadata only — actual upload wiring belongs to a real
  // file-upload endpoint; this UI stores files client-side for now.
  evidence: [],
  submitted: false,
};

let BP_OPTIONS = { students: [], courses: [], assessments: [] };

document.addEventListener("DOMContentLoaded", async () => {
  BPLayout.mount({ active: "integrity-report", userName: "Fatma", userRole: "Instructor" });
  document.getElementById("bp-back-icon").innerHTML = BPIcons.arrowLeft;

  try {
    const [students, courses, assessments] = await Promise.all([
      getStudentOptions(),
      getCourseOptions(),
      getAssessmentOptions(),
    ]);
    BP_OPTIONS = { students, courses, assessments };
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
      const num = state === "done" ? BPIcons.check : i + 1;
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
  if (step === "evidence") content.innerHTML = stepEvidence();
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
      <div class="bp-input-icon-wrap">
        <input class="bp-input" list="bp-student-list" id="bp-student" placeholder="Search student..." value="${BP_STATE.student}" />
        <datalist id="bp-student-list">
          ${BP_OPTIONS.students.map((s) => `<option value="${s}">`).join("")}
        </datalist>
        <span style="pointer-events:none">${BPIcons.search}</span>
      </div>
    </div>
    <div class="bp-field">
      <label>Course</label>
      <select id="bp-course">
        <option value="">Select course</option>
        ${BP_OPTIONS.courses.map((c) => `<option value="${c}" ${c === BP_STATE.course ? "selected" : ""}>${c}</option>`).join("")}
      </select>
    </div>
    <div class="bp-field">
      <label>Assessment</label>
      <select id="bp-assessment">
        <option value="">Select assignment / exam</option>
        ${BP_OPTIONS.assessments.map((a) => `<option value="${a}" ${a === BP_STATE.assessment ? "selected" : ""}>${a}</option>`).join("")}
      </select>
    </div>
  `;
}

// ---------------------------------------------------------
// Step 2 — Incident Details
// (No severity selector — backend classifies severity.)
// ---------------------------------------------------------
function stepIncident() {
  return `
    <div class="bp-field">
      <label>Incident Type</label>
      <select id="bp-incident-type">
        <option value="Cheating" ${BP_STATE.incidentType === "Cheating" ? "selected" : ""}>Cheating</option>
      </select>
    </div>
    <div class="bp-field">
      <label>Date</label>
      <input class="bp-input" type="date" id="bp-date" value="${BP_STATE.date}" />
    </div>
    <div class="bp-field">
      <label>Description</label>
      <textarea class="bp-textarea" id="bp-description" placeholder="Describe what happened...">${BP_STATE.description}</textarea>
      <div class="hint">Provide factual details of the incident. Severity is determined automatically after submission.</div>
    </div>
  `;
}

// ---------------------------------------------------------
// Step 3 — Evidence
// ---------------------------------------------------------
function stepEvidence() {
  return `
    <div class="bp-field">
      <label>Evidence</label>
      <div class="bp-dropzone" id="bp-dropzone">
        ${BPIcons.upload}
        <div><strong style="color:var(--bp-text)">+ Upload Evidence</strong></div>
        <div class="hint">Drag and drop files here, or click to browse</div>
      </div>
      <input type="file" id="bp-file-input" multiple style="display:none" />
      <div id="bp-file-list"></div>
    </div>
  `;
}

function fileSizeLabel(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function renderFileList() {
  const el = document.getElementById("bp-file-list");
  if (!el) return;
  if (BP_STATE.evidence.length === 0) {
    el.innerHTML = "";
    return;
  }
  el.innerHTML = BP_STATE.evidence
    .map(
      (f, i) => `
      <div class="bp-file-item">
        <div class="bp-file-icon">${f.isImage ? BPIcons.image : BPIcons.file}</div>
        <div class="bp-file-info">
          <div class="bp-file-name">${f.name}</div>
          <div class="bp-file-size">${f.sizeLabel}</div>
        </div>
        <button type="button" class="bp-file-remove" data-index="${i}">${BPIcons.x}</button>
      </div>
    `
    )
    .join("");

  el.querySelectorAll(".bp-file-remove").forEach((btn) => {
    btn.addEventListener("click", () => {
      BP_STATE.evidence.splice(parseInt(btn.dataset.index, 10), 1);
      renderFileList();
    });
  });
}

function addFiles(fileList) {
  Array.from(fileList).forEach((file) => {
    BP_STATE.evidence.push({
      name: file.name,
      sizeLabel: fileSizeLabel(file.size),
      isImage: file.type.startsWith("image/"),
    });
  });
  renderFileList();
}

// ---------------------------------------------------------
// Step 4 — Review & Submit
// ---------------------------------------------------------
function stepReview() {
  return `
    <div class="bp-summary-grid">
      <div class="bp-summary-item"><div class="k">Student</div><div class="v">${BP_STATE.student || "—"}</div></div>
      <div class="bp-summary-item"><div class="k">Course</div><div class="v">${BP_STATE.course || "—"}</div></div>
      <div class="bp-summary-item"><div class="k">Assessment</div><div class="v">${BP_STATE.assessment || "—"}</div></div>
      <div class="bp-summary-item"><div class="k">Incident Type</div><div class="v">${BP_STATE.incidentType || "—"}</div></div>
      <div class="bp-summary-item"><div class="k">Date</div><div class="v">${BP_STATE.date || "—"}</div></div>
      <div class="bp-summary-item full"><div class="k">Description</div><div class="v" style="font-weight:400">${BP_STATE.description || "—"}</div></div>
      <div class="bp-summary-item full">
        <div class="k">Evidence</div>
        ${
          BP_STATE.evidence.length
            ? `<div class="v" style="font-weight:400">${BP_STATE.evidence.map((f) => f.name).join(", ")}</div>`
            : `<div class="v" style="font-weight:400;color:var(--bp-text-faint)">No evidence attached</div>`
        }
      </div>
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
    document.getElementById("bp-student").addEventListener("input", (e) => (BP_STATE.student = e.target.value));
    document.getElementById("bp-course").addEventListener("change", (e) => (BP_STATE.course = e.target.value));
    document.getElementById("bp-assessment").addEventListener("change", (e) => (BP_STATE.assessment = e.target.value));
  }
  if (step === "incident") {
    document.getElementById("bp-incident-type").addEventListener("change", (e) => (BP_STATE.incidentType = e.target.value));
    document.getElementById("bp-date").addEventListener("change", (e) => (BP_STATE.date = e.target.value));
    document.getElementById("bp-description").addEventListener("input", (e) => (BP_STATE.description = e.target.value));
  }
  if (step === "evidence") {
    const dropzone = document.getElementById("bp-dropzone");
    const fileInput = document.getElementById("bp-file-input");
    dropzone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => addFiles(e.target.files));
    ["dragover", "dragleave", "drop"].forEach((evt) =>
      dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropzone.classList.toggle("dragover", evt === "dragover");
      })
    );
    dropzone.addEventListener("drop", (e) => addFiles(e.dataTransfer.files));
    renderFileList();
  }
}

function validateStep(step) {
  if (step === "student_course") {
    if (!BP_STATE.student.trim()) return "Please select a student.";
    if (!BP_STATE.course) return "Please select a course.";
    if (!BP_STATE.assessment) return "Please select an assessment.";
  }
  if (step === "incident") {
    if (!BP_STATE.date) return "Please select the incident date.";
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
      student: BP_STATE.student,
      course: BP_STATE.course,
      assessment: BP_STATE.assessment,
      incidentType: BP_STATE.incidentType,
      date: BP_STATE.date,
      description: BP_STATE.description,
      evidence: BP_STATE.evidence,
    };
    const result = await submitIntegrityCase(payload);
    BP_STATE.submitted = true;
    BP_STATE.submittedId = result.id;
    renderStep();
  } catch (err) {
    BPToast.error("Unable to submit the case.");
    btn.disabled = false;
    btn.textContent = "Submit Case";
  }
}
