// =========================================================
// HITL — Case Review
//
// Action buttons are rendered strictly from the backend's
// available_actions for this case. Approve/Reject (or any other
// action) is never assumed or hardcoded here.
// =========================================================

document.addEventListener("DOMContentLoaded", async () => {
  BPLayout.mount({ active: "hitl", userName: "Fatma", userRole: "Instructor" });
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

// Matches the real decision vocabulary the graph understands (see
// backend/routers/academic_integrity_router.py's _COMMITTEE_ACTIONS /
// _FINAL_ACTIONS: "uphold" | "dismiss" | "request_more_evidence" |
// "reduce_penalty"). The old approve/reject/confirm labels never matched
// any value the backend actually sends, so every button fell through to
// the `BP_ACTION_LABELS[a] || a` fallback and rendered the raw snake_case
// string instead of a real label.
const BP_ACTION_LABELS = {
  uphold: "Uphold Violation",
  dismiss: "Dismiss Case",
  request_more_evidence: "Request More Evidence",
  reduce_penalty: "Reduce Penalty",
};

function renderReview(c) {
  const d = c.details;
  return `
    <div class="bp-page-header">
      <div><h1>Academic Integrity Case #${c.id}</h1></div>
      <span>${BPFormat.severityBadge(c.severity)}</span>
    </div>

    <div class="bp-detail-grid">
      <div class="bp-detail-stack">
        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Case Information</h2></div>
          <div class="bp-kv"><div class="k">Student</div><div class="v">${c.student}</div></div>
          <div class="bp-kv"><div class="k">Course</div><div class="v">${c.course}</div></div>
          <div class="bp-kv"><div class="k">Workflow Step</div><div class="v">${c.workflowStep}</div></div>
        </section>

        ${
          d
            ? `
        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Incident</h2></div>
          <div class="bp-kv"><div class="k">Incident Type</div><div class="v">${d.incidentType}</div></div>
          <div class="bp-kv"><div class="k">Description</div><div class="bp-desc-box">${d.description}</div></div>
        </section>

        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Evidence</h2></div>
          <div class="bp-evidence-grid">
            ${d.evidence
              .map(
                (e) => `
              <div class="bp-evidence-tile">
                <div class="bp-file-icon" style="margin:0 auto 8px">${e.type === "image" ? BPIcons.image : BPIcons.file}</div>
                <div class="name">${e.name}</div>
                <div class="size">${e.size}</div>
              </div>
            `
              )
              .join("")}
          </div>
        </section>
        `
            : ""
        }
      </div>

      <div class="bp-detail-stack">
        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>AI Assessment</h2></div>
          <div class="bp-kv"><div class="k">Policy Match</div>
            <div class="v" style="color:var(--bp-green)">${c.policyMatchPct}%</div>
            <div class="bp-match-bar"><div class="bp-match-bar-fill" style="width:${c.policyMatchPct}%"></div></div>
          </div>
          ${d && d.aiAssessment ? `<div class="bp-ai-reasoning">${d.aiAssessment.reasoning}</div>` : ""}
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
          // "uphold" confirms the violation — the consequential action for
          // the student, so it gets the danger styling that "reject" used
          // to carry. Everything else (dismissing the case, asking for more
          // evidence, reducing a penalty) is a softer/neutral outcome.
          const styleClass = a === "uphold" ? "bp-btn-danger" : "bp-btn-primary";
          return `<button class="bp-btn ${styleClass} bp-action-btn" data-action="${a}">${BP_ACTION_LABELS[a] || a}</button>`;
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