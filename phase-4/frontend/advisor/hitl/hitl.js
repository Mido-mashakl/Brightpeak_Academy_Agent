document.addEventListener("DOMContentLoaded", async () => {
  bpRenderNav({ active: "hitl", showSearch: false });

  const params = new URLSearchParams(window.location.search);
  const id = params.get("id") || "REQ-1032";

  const req = await bpFetchRequestById(id);
  if (!req || !req.aiRecommendation) {
    document.querySelector(".bp-content").innerHTML = `<p class="bp-muted">No AI analysis available for request ${id}.</p>`;
    return;
  }

  // Backend is now connected — hide the mock warning if it exists.
  const mockWarning = document.getElementById("bp-mock-warning");
  if (mockWarning) mockWarning.hidden = true;

  const ai = req.aiRecommendation;
  const verdictEl = document.getElementById("bp-ai-verdict");
  verdictEl.textContent = `● ${ai.verdict}`;
  if (ai.verdict.toLowerCase() !== "eligible") verdictEl.classList.add("not-eligible");

  // confidence is only known while the graph's human_review interrupt is
  // actually open (see advisor-api.js) — once a request is decided, the
  // DB row has no confidence column to fall back on, so hide the bar
  // rather than showing a fabricated "0%".
  const confWrap = document.querySelector(".bp-confidence-bar-wrap");
  if (typeof ai.confidence === "number") {
    if (confWrap) confWrap.hidden = false;
    document.getElementById("bp-confidence-pct").textContent = `${ai.confidence}%`;
    document.getElementById("bp-confidence-fill").style.width = `${ai.confidence}%`;
  } else if (confWrap) {
    confWrap.hidden = true;
  }
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

    const res = await bpSubmitAdvisorDecision(req.id, { decision: selected.value, notes });

    submitBtn.textContent = "Submit Decision";
    submitBtn.disabled = false;

    if (res.ok) {
      resultEl.textContent = "Decision submitted and Advisory Graph updated.";
      resultEl.classList.add("success");
    } else {
      resultEl.textContent = "Decision failed to submit.";
      resultEl.classList.add("error");
    }
  });
});
