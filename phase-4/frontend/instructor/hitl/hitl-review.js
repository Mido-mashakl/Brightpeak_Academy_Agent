// =========================================================
// HITL — Case Review
//
// Action buttons are rendered strictly from the backend's
// available_actions for this case. Approve/Reject (or any other
// action) is never assumed or hardcoded here.
// =========================================================

document.addEventListener("DOMContentLoaded", async () => {
  BPLayout.mount({ active: "hitl", userName: (window.currentUser && window.currentUser.name) || "Instructor", userRole: "Instructor" });
  document.getElementById("bp-back-icon").innerHTML = BPIcons.arrowLeft;

  const root = document.getElementById("bp-review-root");
  const id = new URLSearchParams(window.location.search).get("id");

  if (!id) {
    root.innerHTML = BPState.error("No case selected.");
    return;
  }

  root.innerHTML = BPState.loading("Loading case...");

  try {
    const c = await getHITLCase(id);
    root.innerHTML = renderReview(c);
    wireActions(c);
  } catch (err) {
    root.innerHTML = BPState.error("Unable to load this case. Please try again.");
  }
});

// Real decision values accepted by POST /academic-integrity/cases/{id}/
// committee-decision (see academic_integrity_router.py) — not the old
// mock's generic approve/reject/confirm.
const BP_ACTION_LABELS = {
  uphold: "Uphold Finding",
  dismiss: "Dismiss Case",
  reduce_penalty: "Reduce Penalty",
};

function renderReview(c) {
  return `
    <div class="bp-page-header">
      <div><h1>Academic Integrity Case #${c.id}</h1></div>
      <span>${c.severity ? BPFormat.severityBadge(c.severity) : ""}</span>
    </div>

    <div class="bp-detail-grid">
      <div class="bp-detail-stack">
        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Case Information</h2></div>
          <div class="bp-kv"><div class="k">Student</div><div class="v">${c.student}</div></div>
          <div class="bp-kv"><div class="k">Course</div><div class="v">${c.course}</div></div>
          <div class="bp-kv"><div class="k">Workflow Step</div><div class="v">${c.workflowStep}</div></div>
        </section>

        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Incident</h2></div>
          <div class="bp-kv"><div class="k">Description</div><div class="bp-desc-box">${c.description || "—"}</div></div>
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
              ? `<div class="bp-kv"><div class="k">Severity</div><div class="bp-ai-severity">${BPFormat.severityBadge(c.severity)}</div></div>
                 ${c.severityRationale ? `<div class="bp-ai-reasoning">${c.severityRationale}</div>` : ""}`
              : BPState.empty("AI severity assessment not yet available for this case.")
          }
        </section>

        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Your Decision</h2></div>
          <div id="bp-action-panel"></div>
        </section>
      </div>
    </div>
  `;
}

function wireActions(c) {
  const panel = document.getElementById("bp-action-panel");
  const actions = c.availableActions || [];

  if (actions.length === 0) {
    // c.pendingWith (when the backend provides it) names who actually owns
    // this decision — e.g. the Academic Integrity Committee or Department
    // Head — so the instructor understands why no action is offered here,
    // instead of a vague "someone else is handling this".
    const msg = c.pendingWith
      ? `This case is awaiting a decision from the ${c.pendingWith}. You'll be notified if it's returned to you.`
      : "This case is currently awaiting another workflow participant.";
    panel.innerHTML = BPState.empty(msg);
    return;
  }

  panel.innerHTML = `
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      ${actions
        .map((a) => {
          const isReject = a === "reject";
          return `<button class="bp-btn ${isReject ? "bp-btn-danger" : "bp-btn-primary"} bp-action-btn" data-action="${a}">${BP_ACTION_LABELS[a] || a}</button>`;
        })
        .join("")}
    </div>
  `;

  panel.querySelectorAll(".bp-action-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      panel.querySelectorAll("button").forEach((b) => (b.disabled = true));
      try {
        await submitHITLDecision(c.id, btn.dataset.action);
        BPToast.success(`Decision recorded: ${BP_ACTION_LABELS[btn.dataset.action] || btn.dataset.action}.`);
        setTimeout(() => (window.location.href = "hitl.html"), 700);
      } catch (err) {
        BPToast.error("Unable to submit your decision. Please try again.");
        panel.querySelectorAll("button").forEach((b) => (b.disabled = false));
      }
    });
  });
}