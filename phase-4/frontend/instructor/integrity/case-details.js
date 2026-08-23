// =========================================================
// Academic Integrity — Case Details
//
// AI Assessment and Workflow Status are rendered exactly as
// returned by the backend. Nothing here computes severity,
// policy match, or workflow state on the frontend.
// =========================================================

document.addEventListener("DOMContentLoaded", async () => {
  BPLayout.mount({ active: "integrity-all", userName: "Fatma", userRole: "Instructor" });
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
    wireEvidencePreviews(c);
  } catch (err) {
    root.innerHTML = BPState.error("Unable to load this case. Please try again.");
  }
});

function fileIcon(item) {
  return item.type === "image" ? BPIcons.image : BPIcons.file;
}

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
          <div class="bp-kv"><div class="k">Incident Type</div><div class="v">${c.incidentType}</div></div>
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
                      (e, i) => `
                    <div class="bp-evidence-tile" data-index="${i}" style="${e.type === "image" ? "cursor:pointer" : ""}">
                      <div class="bp-file-icon" style="margin:0 auto 8px">${fileIcon(e)}</div>
                      <div class="name">${e.name}</div>
                      <div class="size">${e.size}</div>
                    </div>
                  `
                    )
                    .join("")}
                </div>`
              : BPState.empty("No evidence uploaded for this case.")
          }
        </section>
      </div>

      <div class="bp-detail-stack">
        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>AI Assessment</h2></div>
          ${
            c.aiAssessment
              ? `
            <div class="bp-kv">
              <div class="k">Severity</div>
              <div class="bp-ai-severity">${BPFormat.severityBadge(c.aiAssessment.severity.toLowerCase())}</div>
            </div>
            <div class="bp-kv">
              <div class="k">Policy Match</div>
              <div class="v" style="color:var(--bp-green)">${c.aiAssessment.policyMatchPct}%</div>
              <div class="bp-match-bar"><div class="bp-match-bar-fill" style="width:${c.aiAssessment.policyMatchPct}%"></div></div>
            </div>
            <div class="bp-ai-reasoning">${c.aiAssessment.reasoning}</div>
          `
              : BPState.empty("AI assessment not yet available for this case.")
          }
        </section>

        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Workflow Status</h2></div>
          ${renderTimeline(c.workflow)}
        </section>
      </div>
    </div>
  `;
}

function renderTimeline(workflow) {
  if (!workflow || !workflow.steps) return BPState.empty("Workflow status not available.");
  const currentIndex = workflow.steps.findIndex((s) => s.key === workflow.currentStep);
  return `
    <div class="bp-timeline">
      ${workflow.steps
        .map((s, i) => {
          const state = i < currentIndex ? "done" : i === currentIndex ? "active" : "pending";
          const marker = state === "done" ? BPIcons.check : state === "active" ? "●" : "○";
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

function wireEvidencePreviews(c) {
  document.querySelectorAll(".bp-evidence-tile").forEach((tile) => {
    const item = c.evidence[parseInt(tile.dataset.index, 10)];
    if (item && item.type === "image") {
      tile.addEventListener("click", () => {
        BPToast.info(`Preview for ${item.name} would open here once connected to file storage.`);
      });
    }
  });
}
