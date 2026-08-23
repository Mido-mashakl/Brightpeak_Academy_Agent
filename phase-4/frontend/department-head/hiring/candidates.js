(function () {
  DHNav.mount({ active: "hiring", searchPlaceholder: "Search candidates..." });

  const urlParams = new URLSearchParams(window.location.search);
  let selectedJobId = urlParams.get("job") || "";
  let selectedCandidateId = null;
  let allJobs = [];
  let allCandidates = [];

  init();

  async function init() {
    allJobs = await DHApi.listJobs();
    populateJobFilter();
    document.getElementById("job-filter").addEventListener("change", (e) => {
      selectedJobId = e.target.value;
      renderAll();
    });
    await renderAll();
  }

  function populateJobFilter() {
    const select = document.getElementById("job-filter");
    select.innerHTML =
      `<option value="">All Job Postings</option>` +
      allJobs.map((j) => `<option value="${j.id}" ${j.id === selectedJobId ? "selected" : ""}>${escapeHtml(j.title)}</option>`).join("");
  }

  async function renderAll() {
    allCandidates = await DHApi.listCandidates(selectedJobId || undefined);
    renderStats();
    renderTable();
    renderInsightPanel(null);
  }

  function renderStats() {
    const jobsInScope = selectedJobId ? allJobs.filter((j) => j.id === selectedJobId) : allJobs;
    document.getElementById("stat-jobs").textContent = jobsInScope.length;
    document.getElementById("stat-applications").textContent = allCandidates.length;
    document.getElementById("stat-shortlisted").textContent = allCandidates.filter((c) => c.status === "shortlisted").length;
    document.getElementById("stat-pending").textContent = allCandidates.filter((c) => !c.decision).length;
  }

  function renderTable() {
    const tbody = document.getElementById("candidate-rows");
    const emptyState = document.getElementById("empty-state");
    if (!allCandidates.length) {
      tbody.innerHTML = "";
      emptyState.classList.remove("hidden");
      return;
    }
    emptyState.classList.add("hidden");
    tbody.innerHTML = allCandidates
      .map(
        (c) => `
      <tr data-candidate-id="${c.id}" class="${c.id === selectedCandidateId ? "selected" : ""}">
        <td>
          <div class="flex items-center">
            <span class="avatar-chip">${initials(c.name)}</span>
            <div>
              <div class="text-on-surface font-medium">${escapeHtml(c.name)}</div>
              <div class="text-on-surface-variant text-xs">${escapeHtml(c.university || "")}</div>
            </div>
          </div>
        </td>
        <td>${c.aiScore != null ? `<span class="match-score"><span class="material-symbols-outlined text-sm">bolt</span>${c.aiScore}%</span>` : `<span class="text-on-surface-variant text-xs">${c.status === "parsing" ? "Parsing..." : "N/A"}</span>`}</td>
        <td class="text-on-surface-variant">${c.experienceYears != null ? c.experienceYears + " Years" : "Unknown"}</td>
        <td><span class="status-tag ${c.status}">${statusLabel(c.status)}</span></td>
        <td><span class="material-symbols-outlined text-on-surface-variant">chevron_right</span></td>
      </tr>`
      )
      .join("");

    tbody.querySelectorAll("tr").forEach((row) =>
      row.addEventListener("click", () => {
        selectedCandidateId = row.dataset.candidateId;
        renderTable();
        renderInsightPanel(allCandidates.find((c) => c.id === selectedCandidateId));
      })
    );
  }

  function renderInsightPanel(candidate) {
    const panel = document.getElementById("ai-insight-panel");
    if (!candidate) {
      panel.innerHTML = `
        <div class="text-center text-on-surface-variant p-lg">
          <span class="material-symbols-outlined text-4xl mb-sm block">touch_app</span>
          Select a candidate to view AI insight and record the Department Head decision.
        </div>`;
      return;
    }

    const skillChips = (candidate.skills || []).map((s) => `<span class="insight-skill-chip">${escapeHtml(s)}</span>`).join("") || `<span class="text-on-surface-variant text-xs">No skills parsed</span>`;
    const strengths = (candidate.keyStrengths || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("");

    const decisionSection = candidate.decision
      ? `<div class="decision-made-box">
           <div class="flex items-center gap-xs font-medium"><span class="material-symbols-outlined text-sm">check_circle</span>Department Head Decision Recorded</div>
           <div class="mt-xs text-on-surface">${decisionLabel(candidate.decision.action)}${candidate.decision.note ? " — " + escapeHtml(candidate.decision.note) : ""}</div>
         </div>`
      : `<div class="decision-section">
           <div class="font-label-caps text-label-caps text-on-surface-variant mb-sm">Department Head Decision</div>
           <div class="decision-grid">
             <button class="decision-btn hire" data-decision="hire"><span class="material-symbols-outlined text-sm">check_circle</span>Hire</button>
             <button class="decision-btn reject" data-decision="reject"><span class="material-symbols-outlined text-sm">cancel</span>Reject</button>
             <button class="decision-btn interview" data-decision="interview"><span class="material-symbols-outlined text-sm">event</span>Interview</button>
             <button class="decision-btn rescore" data-decision="rescore"><span class="material-symbols-outlined text-sm">refresh</span>Rescore</button>
           </div>
         </div>`;

    panel.innerHTML = `
      <div class="flex items-center gap-sm mb-md">
        <span class="material-symbols-outlined text-primary">neurology</span>
        <div>
          <div class="font-headline-md text-headline-md text-on-surface">AI Insight</div>
          <div class="text-on-surface-variant text-body-sm">${escapeHtml(candidate.name)} Analysis</div>
        </div>
        ${candidate.aiScore != null ? `<div class="insight-score-ring ml-auto">${candidate.aiScore}</div>` : ""}
      </div>

      <div class="font-label-caps text-label-caps text-on-surface-variant mb-xs">Candidate Profile</div>
      <div class="grid grid-cols-2 gap-md mb-md text-body-sm">
        <div><div class="text-on-surface-variant text-xs mb-1">Education</div><div class="text-on-surface">${escapeHtml(candidate.university || "Unknown")}</div></div>
        <div><div class="text-on-surface-variant text-xs mb-1">Experience</div><div class="text-on-surface">${candidate.experienceYears != null ? candidate.experienceYears + " Years" : "Not provided"}</div></div>
      </div>

      <div class="font-label-caps text-label-caps text-on-surface-variant mb-xs">Top Skills</div>
      <div class="mb-md">${skillChips}</div>

      ${strengths ? `<div class="font-label-caps text-label-caps text-on-surface-variant mb-xs flex items-center gap-xs"><span class="material-symbols-outlined text-sm">verified</span>Key Strengths</div><ul class="list-disc list-inside text-body-sm text-on-surface-variant mb-md">${strengths}</ul>` : ""}

      <div class="font-label-caps text-label-caps text-on-surface-variant mb-xs">AI Recommendation</div>
      <div class="ai-recommendation-box mb-md">
        <div class="text-on-surface font-medium">${escapeHtml(candidate.aiRecommendation || "Not yet scored")}</div>
        <div class="text-on-surface-variant text-xs mt-xs">AI recommendations are advisory only and are never treated as the final decision.</div>
      </div>

      ${decisionSection}
    `;

    panel.querySelectorAll("[data-decision]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        const action = btn.dataset.decision;
        let note = null;
        if (action === "reject" || action === "rescore") {
          note = prompt(`Optional note for this "${action}" decision:`) || null;
        }
        btn.disabled = true;
        try {
          // Real endpoint: POST /hiring/candidates/{candidate_id}/decision
          const updated = await DHApi.submitHiringDecision(candidate.id, action, note);
          showToast(`Decision recorded: ${decisionLabel(action)}.`, "success");
          await renderAll();
          selectedCandidateId = updated.id;
          renderTable();
          renderInsightPanel(updated);
        } catch (err) {
          console.error(err);
          if (err.status === 501) {
            // 'reject' has no corresponding action in the faculty_hiring
            // graph yet (see hiring_router.py) — report this honestly
            // instead of pretending the decision was recorded.
            showToast("Reject isn't supported by the hiring workflow yet.", "error");
          } else if (err.status === 401) {
            showToast(err.message || "Incorrect dept head passcode.", "error");
          } else {
            showToast(err.message || "Could not record the decision.", "error");
          }
          btn.disabled = false;
        }
      })
    );
  }

  function statusLabel(status) {
    const map = { parsing: "Parsing", ai_scored: "AI Scored", shortlisted: "Shortlisted", interview: "Interview", hired: "Hired", rejected: "Rejected", rescore_requested: "Rescore" };
    return map[status] || status;
  }
  function decisionLabel(action) {
    const map = { hire: "Hired", reject: "Rejected", interview: "Interview Requested", rescore: "Rescore Requested" };
    return map[action] || action;
  }
  function initials(name) {
    return (name || "?").split(" ").filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join("");
  }
  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function showToast(message, type) {
    const toast = document.createElement("div");
    toast.className = `toast ${type === "error" ? "error" : ""}`;
    toast.style.cssText = "background:#191c22;border:1px solid rgba(143,214,163,.4);color:#e1e2eb;padding:12px 18px;border-radius:.5rem;font-size:14px;box-shadow:0 4px 20px rgba(0,0,0,.4);margin-top:8px;";
    if (type === "error") toast.style.borderColor = "rgba(255,180,171,.4)";
    toast.textContent = message;
    let root = document.getElementById("toast-root");
    if (!root) {
      root = document.createElement("div");
      root.id = "toast-root";
      root.style.cssText = "position:fixed;bottom:24px;right:24px;z-index:200;";
      document.body.appendChild(root);
    }
    root.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }
})();