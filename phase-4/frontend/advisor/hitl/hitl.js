document.addEventListener("DOMContentLoaded", async () => {
  bpRenderNav({ active: "hitl", showSearch: false });

  const params = new URLSearchParams(window.location.search);
  const id = params.get("id") || "REQ-1032";

  const req = await bpFetchRequestById(id);
  if (!req || !req.aiRecommendation) {
    document.querySelector(".bp-content").innerHTML = `<p class="bp-muted">No AI analysis available for request ${id}.</p>`;
    return;
  }

  // Backend is not connected — surface this clearly instead of pretending it works.
  document.getElementById("bp-mock-warning").hidden = false;

  const ai = req.aiRecommendation;
  const verdictEl = document.getElementById("bp-ai-verdict");
  verdictEl.textContent = `● ${ai.verdict}`;
  if (ai.verdict.toLowerCase() !== "eligible") verdictEl.classList.add("not-eligible");

  document.getElementById("bp-confidence-pct").textContent = `${ai.confidence}%`;
  document.getElementById("bp-confidence-fill").style.width = `${ai.confidence}%`;
  document.getElementById("bp-ai-reasoning").textContent = ai.reasoning;

  document.getElementById("bp-req-check").innerHTML = (req.requirements || [])
    .map((r) => `<div class="bp-req-row"><span>${r.label}</span><span class="ok">${r.value}</span></div>`)
    .join("");

  const submitBtn = document.getElementById("bp-submit-decision");
  const resultEl = document.getElementById("bp-decision-result");

  document.querySelectorAll('input[name="decision"]').forEach((input) => {
    input.addEventListener("change", () => { submitBtn.disabled = false; });
  });

  submitBtn.addEventListener("click", async () => {
    const selected = document.querySelector('input[name="decision"]:checked');
    if (!selected) return;

    const notes = document.getElementById("bp-decision-notes").value;

    submitBtn.disabled = true;
    submitBtn.textContent = "Submitting...";
    resultEl.textContent = "";
    resultEl.className = "bp-decision-result";

    // ⚠️ This calls the MOCK layer (see advisor-api.js). It intentionally
    // does NOT claim success, because no real Advisory Graph resume
    // endpoint is connected. Replace bpSubmitAdvisorDecision's internals
    // with the real POST once the backend endpoint is identified.
    const res = await bpSubmitAdvisorDecision(req.id, { decision: selected.value, notes });

    submitBtn.textContent = "Submit Decision";
    submitBtn.disabled = false;

    if (res.mocked) {
      resultEl.textContent = "Not saved: no backend endpoint connected yet (see implementation report).";
      resultEl.classList.add("error");
    } else if (res.ok) {
      resultEl.textContent = "Decision submitted and Advisory Graph updated.";
      resultEl.classList.add("success");
    } else {
      resultEl.textContent = "Decision failed to submit.";
      resultEl.classList.add("error");
    }
  });
});
