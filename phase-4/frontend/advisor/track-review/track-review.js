document.addEventListener("DOMContentLoaded", async () => {
  bpRenderNav({ active: "track-review", showSearch: false });
  await loadQueue();
});

async function loadQueue() {
  const queueCard = document.getElementById("bp-tr-queue-card");
  const emptyMsg = document.getElementById("bp-tr-empty");
  const body = document.getElementById("bp-tr-queue-body");
  document.getElementById("bp-tr-decision").hidden = true;
  queueCard.hidden = false;

  const items = await bpFetchTrackReviewQueue();

  if (items.length === 0) {
    body.innerHTML = "";
    emptyMsg.hidden = false;
    return;
  }
  emptyMsg.hidden = true;

  body.innerHTML = items
    .map(
      (r) => `
        <tr>
          <td>${r.student}</td>
          <td>${r.recommendedTrack || "—"}</td>
          <td>${r.runnerUpTrack || "—"}</td>
          <td>${typeof r.confidence === "number" ? r.confidence + "%" : "—"}</td>
          <td>
            <button class="bp-btn bp-review-link" data-thread="${r.threadId || ""}" data-rec="${r.id}">
              Review
            </button>
          </td>
        </tr>`
    )
    .join("");

  body.querySelectorAll("[data-thread]").forEach((btn) => {
    btn.addEventListener("click", () => openDecision(btn.dataset.thread, btn.dataset.rec));
  });
}

async function openDecision(threadId, recommendationId) {
  const queueCard = document.getElementById("bp-tr-queue-card");
  const decisionEl = document.getElementById("bp-tr-decision");

  if (!threadId) {
    // Row predates the thread_id write-back (created before this fix was
    // deployed) — nothing to resume against. Surfacing this beats silently
    // failing the graph call below.
    alert(
      `Recommendation #${recommendationId} has no stored thread_id, so its ` +
      `paused graph run can't be resumed. This can happen for rows created ` +
      `before the thread_id write-back existed.`
    );
    return;
  }

  const state = await bpFetchTrackThreadState(threadId);
  if (!state) {
    alert("No active advisor-review interrupt found for this thread — it may have already been decided.");
    return;
  }

  queueCard.hidden = true;
  decisionEl.hidden = false;
  decisionEl.dataset.threadId = threadId;

  document.getElementById("bp-tr-top").textContent =
    `${state.student}: ${state.topTrack}` + (typeof state.topScore === "number" ? ` (${state.topScore}%)` : "");

  document.getElementById("bp-tr-alt").textContent = state.altTrack
    ? `${state.altTrack}` + (typeof state.altScore === "number" ? ` (${state.altScore}%)` : "")
    : "No alternative track available.";

  const concernsEl = document.getElementById("bp-tr-concerns");
  concernsEl.innerHTML = state.concerns.length
    ? state.concerns.map((c) => `<div class="bp-req-row"><span>${c}</span></div>`).join("")
    : `<div class="bp-req-row bp-muted"><span>No concerns flagged.</span></div>`;

  // Only show the actions the graph actually offered for this interrupt.
  document.querySelectorAll('input[name="tr-decision"]').forEach((input) => {
    const opt = input.closest(".bp-decision-opt");
    opt.style.display = state.actions.includes(input.value) ? "" : "none";
    input.checked = false;
  });

  document.getElementById("bp-tr-submit").disabled = true;
  document.getElementById("bp-tr-result").textContent = "";
  document.getElementById("bp-tr-result").className = "bp-decision-result";
  document.getElementById("bp-tr-subject-wrap").hidden = true;
  document.getElementById("bp-tr-subject").value = "";

  bindDecisionForm(threadId, state);
}

function bindDecisionForm(threadId, state) {
  const submitBtn = document.getElementById("bp-tr-submit");
  const subjectWrap = document.getElementById("bp-tr-subject-wrap");
  const subjectInput = document.getElementById("bp-tr-subject");
  const resultEl = document.getElementById("bp-tr-result");
  const backBtn = document.getElementById("bp-tr-back");

  document.querySelectorAll('input[name="tr-decision"]').forEach((input) => {
    input.onchange = () => {
      submitBtn.disabled = false;
      subjectWrap.hidden = input.value !== "request_assessment";
    };
  });

  backBtn.onclick = () => loadQueue();

  submitBtn.onclick = async () => {
    const selected = document.querySelector('input[name="tr-decision"]:checked');
    if (!selected) return;
    const action = selected.value;

    if (action === "choose_other" && !state.altTrack) {
      resultEl.textContent = "No alternative track is available to choose.";
      resultEl.className = "bp-decision-result error";
      return;
    }
    const subject = subjectInput.value.trim();
    if (action === "request_assessment" && !subject) {
      resultEl.textContent = "Enter a subject for the targeted assessment.";
      resultEl.className = "bp-decision-result error";
      return;
    }

    const user = (typeof bpGetCurrentUser === "function" && bpGetCurrentUser()) || { name: "Advisor" };

    submitBtn.disabled = true;
    submitBtn.textContent = "Submitting...";
    resultEl.textContent = "";
    resultEl.className = "bp-decision-result";

    const res = await bpSubmitTrackDecision(threadId, {
      action,
      advisorName: user.name || "Advisor",
      track: action === "choose_other" ? state.altTrack : undefined,
      subject: action === "request_assessment" ? subject : undefined,
    });

    submitBtn.textContent = "Submit Decision";
    submitBtn.disabled = false;

    if (res.ok) {
      resultEl.textContent = "Decision submitted and Track Recommendation Graph updated.";
      resultEl.classList.add("success");
      setTimeout(loadQueue, 900);
    } else {
      resultEl.textContent = res.message || "Decision failed to submit.";
      resultEl.classList.add("error");
    }
  };
}
