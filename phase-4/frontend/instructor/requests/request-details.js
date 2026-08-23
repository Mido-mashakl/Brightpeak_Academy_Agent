// =========================================================
// Request Details
//
// This is where "Request Details -> HITL" happens: the same
// screen shows the proposed write-op AND the decision panel.
// Approve/Reject only render when the backend's availableActions
// actually includes them — record_grade / update_attendance /
// change_enrollment_status are instructor-owned decisions, but
// we still never assume the buttons; a resolved request just
// shows what was decided and by whom.
// =========================================================

document.addEventListener("DOMContentLoaded", async () => {
  BPLayout.mount({ active: "requests", userName: "Fatma", userRole: "Instructor" });
  document.getElementById("bp-back-icon").innerHTML = BPIcons.arrowLeft;

  const root = document.getElementById("bp-request-root");
  const id = new URLSearchParams(window.location.search).get("id");

  if (!id) {
    root.innerHTML = BPState.error("No request selected.");
    return;
  }

  root.innerHTML = BPState.loading("Loading request...");

  try {
    const r = await getRequest(id);
    root.innerHTML = renderRequest(r);
    wireDecision(r);
  } catch (err) {
    root.innerHTML = BPState.error("Unable to load this request. Please try again.");
  }
});

const BP_ACTION_LABELS = { approve: "Approve", reject: "Reject", request_info: "Request Info" };

function renderRequest(r) {
  return `
    <div class="bp-page-header">
      <div><h1>${BPFormat.requestTypeLabel[r.type] || r.type} Request #${r.id}</h1></div>
      <span>${BPFormat.statusBadge(r.status)}</span>
    </div>

    <div class="bp-detail-grid">
      <div class="bp-detail-stack">
        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Request Information</h2></div>
          <div class="bp-kv"><div class="k">Student</div><div class="v">${r.student}</div></div>
          <div class="bp-kv"><div class="k">Course</div><div class="v">${r.course}</div></div>
          <div class="bp-kv"><div class="k">Submitted</div><div class="v">${r.submittedLabel}</div></div>
        </section>

        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Proposed Change</h2></div>
          <div class="bp-kv"><div class="k">${r.fieldLabel || "Field"} (Current)</div><div class="v">${r.currentValue ?? "—"}</div></div>
          <div class="bp-kv"><div class="k">${r.fieldLabel || "Field"} (Proposed)</div><div class="v" style="color:var(--bp-green)">${r.proposedValue ?? "—"}</div></div>
        </section>

        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Agent Reasoning</h2></div>
          ${r.agentReasoning ? `<div class="bp-ai-reasoning">${r.agentReasoning}</div>` : BPState.empty("No reasoning provided for this request.")}
        </section>
      </div>

      <div class="bp-detail-stack">
        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Evidence</h2></div>
          ${
            r.evidence && r.evidence.length
              ? `<div class="bp-evidence-checklist">
                  ${r.evidence
                    .map(
                      (e) => `
                    <div class="bp-evidence-check-item">
                      <span class="bp-evidence-check-icon">${BPIcons.check}</span>
                      <span>${e}</span>
                    </div>
                  `
                    )
                    .join("")}
                </div>`
              : BPState.empty("No supporting evidence for this request.")
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

function wireDecision(r) {
  const panel = document.getElementById("bp-action-panel");
  const actions = r.availableActions || [];

  if (actions.length === 0) {
    if (r.decision) {
      const label = BP_ACTION_LABELS[r.decision.action] || r.decision.action;
      panel.innerHTML = `
        <div class="bp-kv"><div class="k">Decision</div><div class="v">${label}</div></div>
        <div class="bp-kv"><div class="k">By</div><div class="v">${r.decision.byLabel}</div></div>
        <div class="bp-kv"><div class="k">At</div><div class="v">${r.decision.atLabel}</div></div>
      `;
    } else {
      panel.innerHTML = BPState.empty("This request is currently awaiting another workflow participant.");
    }
    return;
  }

  renderActionButtons();

  function actionClass(a) {
    if (a === "reject") return "bp-btn-danger";
    if (a === "request_info") return "bp-btn-secondary";
    return "bp-btn-primary";
  }

  function renderActionButtons() {
    panel.innerHTML = `
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        ${actions
          .map((a) => `<button class="bp-btn ${actionClass(a)} bp-action-btn" data-action="${a}">${BP_ACTION_LABELS[a] || a}</button>`)
          .join("")}
      </div>
    `;

    panel.querySelectorAll(".bp-action-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (btn.dataset.action === "request_info") {
          renderInfoNoteForm();
        } else {
          submitDecision(btn.dataset.action);
        }
      });
    });
  }

  // "Request Info" needs a note before it can be sent — the instructor
  // says what's missing so the student/agent knows what to provide.
  function renderInfoNoteForm() {
    panel.innerHTML = `
      <div class="bp-field">
        <label>What information do you need?</label>
        <textarea class="bp-textarea" id="bp-info-note" placeholder="e.g. Please attach the medical certificate referenced in this request."></textarea>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <button class="bp-btn bp-btn-secondary" id="bp-info-cancel">Cancel</button>
        <button class="bp-btn bp-btn-primary" id="bp-info-send">Send Request</button>
      </div>
    `;
    document.getElementById("bp-info-cancel").addEventListener("click", renderActionButtons);
    document.getElementById("bp-info-send").addEventListener("click", async () => {
      const note = document.getElementById("bp-info-note").value.trim();
      if (!note) {
        BPToast.error("Please describe what information you need.");
        return;
      }
      document.getElementById("bp-info-send").disabled = true;
      document.getElementById("bp-info-cancel").disabled = true;
      try {
        await submitRequestDecision(r.id, "request_info", { note });
        BPToast.success("Info request sent.");
        setTimeout(() => (window.location.href = "requests.html"), 700);
      } catch (err) {
        BPToast.error("Unable to send this request. Please try again.");
        document.getElementById("bp-info-send").disabled = false;
        document.getElementById("bp-info-cancel").disabled = false;
      }
    });
  }

  async function submitDecision(action) {
    panel.querySelectorAll("button").forEach((b) => (b.disabled = true));
    try {
      await submitRequestDecision(r.id, action);
      BPToast.success(`Decision recorded: ${BP_ACTION_LABELS[action] || action}.`);
      setTimeout(() => (window.location.href = "requests.html"), 700);
    } catch (err) {
      BPToast.error("Unable to submit your decision. Please try again.");
      panel.querySelectorAll("button").forEach((b) => (b.disabled = false));
    }
  }
}
