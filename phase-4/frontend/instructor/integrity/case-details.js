// =========================================================
// Academic Integrity — Case Details
//
// AI Assessment and Workflow Status are rendered exactly as
// returned by the backend. Nothing here computes severity,
// policy match, or workflow state on the frontend.
// =========================================================

document.addEventListener("DOMContentLoaded", async () => {
  BPLayout.mount({ active: "integrity-all", userName: (window.currentUser && window.currentUser.name) || "Instructor", userRole: "Instructor" });
  document.getElementById("bp-back-icon").innerHTML = BPIcons.arrowLeft;

  const root = document.getElementById("bp-case-root");
  const id = new URLSearchParams(window.location.search).get("id");

  if (!id) {
    root.innerHTML = BPState.error("No case selected.");
    return;
  }

  root.innerHTML = BPState.loading("Loading case details...");

  try {
    const c = await getIntegrityCase(id);
    root.innerHTML = renderCase(c);
  } catch (err) {
    root.innerHTML = BPState.error("Unable to load this case. Please try again.");
  }
});

function renderCase(c) {
  return `
    <div class="bp-page-header">
      <div>
        <h1>Academic Integrity Case #${c.id}</h1>
      </div>
      <span>${BPFormat.statusBadge(c.status)}</span>
    </div>

    <div class="bp-detail-grid">
      <div class="bp-detail-stack">
        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Case Information</h2></div>
          <div class="bp-kv"><div class="k">Student</div><div class="v">${c.student}</div></div>
          <div class="bp-kv"><div class="k">Course</div><div class="v">${c.course}</div></div>
          <div class="bp-kv"><div class="k">Reported by</div><div class="v">${c.reportedBy}</div></div>
          <div class="bp-kv"><div class="k">Reported on</div><div class="v">${c.reportedOnLabel}</div></div>
          <div class="bp-kv"><div class="k">Status</div><div class="v">${BPFormat.statusBadge(c.status)}</div></div>
        </section>

        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Incident</h2></div>
          <div class="bp-kv">
            <div class="k">Description</div>
            <div class="bp-desc-box">${c.description}</div>
          </div>
        </section>

        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Evidence</h2></div>
          ${
            c.evidence && c.evidence.length
              ? `<div class="bp-evidence-grid">
                  ${c.evidence
                    .map(
                      (e) => `
                    <div class="bp-evidence-tile">
                      <div class="bp-file-icon" style="margin:0 auto 8px">${BPIcons.file}</div>
                      <div class="name">${e.type}</div>
                      <div class="size">${e.content}</div>
                    </div>
                  `
                    )
                    .join("")}
                </div>`
              : BPState.empty("No evidence recorded for this case.")
          }
        </section>
      </div>

      <div class="bp-detail-stack">
        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>AI Assessment</h2></div>
          ${
            c.severity
              ? `
            <div class="bp-kv">
              <div class="k">Severity</div>
              <div class="bp-ai-severity">${BPFormat.severityBadge(c.severity)}</div>
            </div>
            ${c.severityRationale ? `<div class="bp-ai-reasoning">${c.severityRationale}</div>` : ""}
          `
              : BPState.empty("AI severity assessment not yet available for this case.")
          }
        </section>

        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Workflow Status</h2></div>
          ${renderTimeline(c.status)}
        </section>
      </div>
    </div>
  `;
}

// Derived from the real IntegrityCases.status column (see schema.sql's
// CHECK constraint) — not a fabricated multi-field "workflow" object.
const BP_CASE_STAGES = [
  { key: "reported", label: "Reported" },
  { key: "under_review", label: "Under Review" },
  { key: "awaiting_appeal", label: "Awaiting Appeal" },
  { key: "appeal_under_review", label: "Appeal Under Review" },
  { key: "closed", label: "Closed" },
];

function renderTimeline(status) {
  const currentIndex = BP_CASE_STAGES.findIndex((s) => s.key === status);
  return `
    <div class="bp-timeline">
      ${BP_CASE_STAGES
        .map((s, i) => {
          const state = currentIndex < 0 ? "pending" : i < currentIndex ? "done" : i === currentIndex ? "active" : "pending";
          return `
          <div class="bp-tl-step ${state}">
            <div class="bp-tl-marker">${state === "done" ? BPIcons.check : ""}</div>
            <div class="bp-tl-label">${s.label}</div>
          </div>
        `;
        })
        .join("")}
    </div>
  `;
}