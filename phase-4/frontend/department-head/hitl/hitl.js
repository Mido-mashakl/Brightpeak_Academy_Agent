(function () {
  DHNav.mount({ active: "hitl", searchPlaceholder: "Search cases..." });

  const params = new URLSearchParams(window.location.search);
  const initialTab = params.get("tab") === "integrity" ? "integrity" : "hiring";
  const focusCaseId = params.get("case");

  let selectedCandidateId = null;
  let selectedCaseId = focusCaseId || null;

  bindTabs();
  activateTab(initialTab);
  loadHiringQueue();
  loadIntegrityQueue();

  /* ---------------- Tabs ---------------- */
  function bindTabs() {
    document.querySelectorAll(".tab-btn").forEach((btn) =>
      btn.addEventListener("click", () => activateTab(btn.dataset.tab))
    );
  }
  function activateTab(tab) {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    document.getElementById("tab-hiring").classList.toggle("hidden", tab !== "hiring");
    document.getElementById("tab-integrity").classList.toggle("hidden", tab !== "integrity");
  }

  /* ================= FACULTY HIRING HITL ================= */
  async function loadHiringQueue() {
    const candidates = await DHApi.listCandidates();
    const queue = candidates.filter((c) => (c.status === "shortlisted" || c.status === "ai_scored") && !c.decision);
    const tbody = document.getElementById("hiring-queue-rows");
    const empty = document.getElementById("hiring-empty");

    if (!queue.length) {
      tbody.innerHTML = "";
      empty.classList.remove("hidden");
      renderHiringDetail(null);
      return;
    }
    empty.classList.add("hidden");

    tbody.innerHTML = queue
      .map(
        (c) => `
      <tr data-id="${c.id}" class="${c.id === selectedCandidateId ? "selected" : ""}">
        <td class="font-medium">${escapeHtml(c.name)}</td>
        <td class="text-on-surface-variant">${escapeHtml(jobTitle(c.jobId))}</td>
        <td>${c.aiScore != null ? c.aiScore + "%" : "—"}</td>
        <td><span class="status-pill under_review">${statusLabel(c.status)}</span></td>
        <td><span class="material-symbols-outlined text-on-surface-variant">chevron_right</span></td>
      </tr>`
      )
      .join("");

    tbody.querySelectorAll("tr").forEach((row) =>
      row.addEventListener("click", () => {
        selectedCandidateId = row.dataset.id;
        loadHiringQueue();
        const candidate = queue.find((c) => c.id === selectedCandidateId);
        renderHiringDetail(candidate);
      })
    );

    if (selectedCandidateId) {
      const c = queue.find((x) => x.id === selectedCandidateId);
      if (c) renderHiringDetail(c);
    }
  }

  const jobsCache = {};
  async function jobTitleAsync(jobId) {
    if (jobsCache[jobId]) return jobsCache[jobId];
    const jobs = await DHApi.listJobs();
    jobs.forEach((j) => (jobsCache[j.id] = j.title));
    return jobsCache[jobId] || "Unknown Position";
  }
  function jobTitle(jobId) { return jobsCache[jobId] || "…"; }
  DHApi.listJobs().then((jobs) => jobs.forEach((j) => (jobsCache[j.id] = j.title)));

  function renderHiringDetail(candidate) {
    const panel = document.getElementById("hiring-detail-panel");
    if (!candidate) {
      panel.innerHTML = `<div class="text-center text-on-surface-variant p-lg"><span class="material-symbols-outlined text-4xl mb-sm block">touch_app</span>Select a candidate to review AI evidence and record the Department Head decision.</div>`;
      return;
    }
    const skillChips = (candidate.skills || []).map((s) => `<span class="policy-chip">${escapeHtml(s)}</span>`).join("") || `<span class="text-on-surface-variant text-xs">No skills parsed</span>`;

    panel.innerHTML = `
      <div class="flex items-center justify-between mb-md">
        <div>
          <div class="font-headline-md text-headline-md text-on-surface">${escapeHtml(candidate.name)}</div>
          <div class="text-on-surface-variant text-body-sm">${escapeHtml(jobTitle(candidate.jobId))}</div>
        </div>
        ${candidate.aiScore != null ? `<div class="insight-score-ring" style="width:48px;height:48px;border-radius:9999px;border:3px solid #d0bcff;display:flex;align-items:center;justify-content:center;font-weight:700;color:#d0bcff;">${candidate.aiScore}</div>` : ""}
      </div>

      <div class="section-title">Qualifications</div>
      <div class="mb-md">${skillChips}</div>

      <div class="section-title">Evidence</div>
      <div class="evidence-row"><span><span class="material-symbols-outlined text-sm align-middle mr-1">description</span>${candidate.fileName || "Parsed CV Document"}</span><span class="material-symbols-outlined text-sm text-on-surface-variant">visibility</span></div>

      <div class="section-title mt-md">AI Recommendation</div>
      <div class="ai-assessment-box mb-md">
        <div class="text-on-surface">${escapeHtml(candidate.aiRecommendation || "Not yet scored")}</div>
        <div class="text-on-surface-variant text-xs mt-xs">Advisory only — never treated as the final decision.</div>
      </div>

      <div class="section-title">Department Head Decision</div>
      <div class="action-btn-row">
        <button class="action-btn" data-decision="hire" style="color:#8fd6a3;border-color:rgba(143,214,163,.35);"><span class="material-symbols-outlined text-sm">check_circle</span>Hire</button>
        <button class="action-btn" data-decision="reject" style="color:#ffb4ab;border-color:rgba(255,180,171,.35);"><span class="material-symbols-outlined text-sm">cancel</span>Reject</button>
        <button class="action-btn primary" data-decision="interview"><span class="material-symbols-outlined text-sm">event</span>Interview</button>
        <button class="action-btn" data-decision="rescore"><span class="material-symbols-outlined text-sm">refresh</span>Rescore</button>
      </div>
    `;

    panel.querySelectorAll("[data-decision]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        try {
          await DHApi.submitHiringDecision(candidate.id, btn.dataset.decision);
          showToast(`Decision recorded for ${candidate.name}.`, "success");
          selectedCandidateId = null;
          await loadHiringQueue();
        } catch (err) {
          console.error(err);
          showToast("Could not record the decision.", "error");
          btn.disabled = false;
        }
      })
    );
  }

  function statusLabel(status) {
    const map = { ai_scored: "AI Scored — Needs Review", shortlisted: "Shortlisted" };
    return map[status] || status;
  }

  /* ================= ACADEMIC INTEGRITY HITL ================= */
  async function loadIntegrityQueue() {
    const cases = await DHApi.listIntegrityCases();
    const tbody = document.getElementById("integrity-queue-rows");
    tbody.innerHTML = cases
      .map(
        (c) => `
      <tr data-id="${c.id}" class="${c.id === selectedCaseId ? "selected" : ""}">
        <td class="font-mono-data">${c.id}</td>
        <td>${escapeHtml(c.student)}</td>
        <td class="text-on-surface-variant">${escapeHtml(c.course)}</td>
        <td class="text-on-surface-variant">${caseTypeFromReport(c)}</td>
        <td><span class="severity-pill ${c.severity}">${c.severity}</span></td>
        <td><span class="status-pill ${c.status}">${integrityStatusLabel(c.status)}</span></td>
      </tr>`
      )
      .join("");

    tbody.querySelectorAll("tr").forEach((row) =>
      row.addEventListener("click", () => {
        selectedCaseId = row.dataset.id;
        loadIntegrityQueue();
        renderIntegrityDetail(cases.find((c) => c.id === selectedCaseId));
      })
    );

    if (selectedCaseId) {
      const found = cases.find((c) => c.id === selectedCaseId);
      if (found) renderIntegrityDetail(found);
    }
  }

  function caseTypeFromReport(c) {
    if (/plagiar/i.test(c.report)) return "Plagiarism";
    if (/generative ai|genai/i.test(c.report)) return "GenAI Use";
    if (/exam|device/i.test(c.report)) return "Exam Fraud";
    return "Academic Integrity";
  }
  function integrityStatusLabel(status) {
    const map = { reported: "Reported", under_review: "Under Review", awaiting_appeal: "Awaiting Appeal", appeal_under_review: "Appeal Under Review", closed: "Closed" };
    return map[status] || status;
  }

  function renderIntegrityDetail(c) {
    const container = document.getElementById("integrity-detail-panel");
    if (!c) {
      container.innerHTML = `<div class="glass-panel rounded-xl p-lg text-center text-on-surface-variant"><span class="material-symbols-outlined text-4xl mb-sm block">touch_app</span>Select a case to view evidence, AI assessment, and record the committee decision.</div>`;
      return;
    }

    const policyChips = (c.policy || []).map((p) => `<span class="policy-chip">${p}</span>`).join("");
    const policySection = policyChips
      ? `<div class="section-title">Relevant Policy Cited</div><div class="mb-md">${policyChips}</div>`
      : "";
    const evidenceRows = (c.evidence || [])
      .map((e) => `<div class="evidence-row"><span><span class="material-symbols-outlined text-sm align-middle mr-1">description</span>${escapeHtml(e)}</span><span class="material-symbols-outlined text-sm text-on-surface-variant">visibility</span></div>`)
      .join("");
    const timelineHtml = (c.timeline || [])
      .map((t) => `<div class="timeline-item"><div class="timeline-dot ${t.state}"></div><div><div class="timeline-label">${escapeHtml(t.label)}</div><div class="timeline-detail">${escapeHtml(t.detail)}</div></div></div>`)
      .join("");

    const decisionBlock = c.decision
      ? `<div class="decision-made-box" style="background:rgba(143,214,163,.08);border:1px solid rgba(143,214,163,.3);border-radius:.5rem;padding:14px 16px;color:#8fd6a3;">
           <div class="flex items-center gap-xs font-medium"><span class="material-symbols-outlined text-sm">check_circle</span>Committee Decision Recorded</div>
           <div class="mt-xs text-on-surface">${integrityActionLabel(c.decision.action)}${c.decision.note ? " — " + escapeHtml(c.decision.note) : ""}</div>
         </div>`
      : c.status === "appeal_under_review"
      ? `<div class="action-btn-row">
           <button class="action-btn primary" data-action="uphold_final"><span class="material-symbols-outlined text-sm">gavel</span>Uphold Ruling</button>
           <button class="action-btn" data-action="reduce_penalty"><span class="material-symbols-outlined text-sm">balance</span>Reduce Penalty</button>
           <button class="action-btn danger" data-action="dismiss_final"><span class="material-symbols-outlined text-sm">close</span>Dismiss on Appeal</button>
         </div>`
      : c.status === "under_review"
      ? `<div class="action-btn-row">
           <button class="action-btn primary" data-action="confirm_finding"><span class="material-symbols-outlined text-sm">gavel</span>Confirm Finding</button>
           <button class="action-btn" data-action="request_evidence"><span class="material-symbols-outlined text-sm">find_in_page</span>Req. Evidence</button>
           <button class="action-btn danger" data-action="dismiss_case"><span class="material-symbols-outlined text-sm">close</span>Dismiss Case</button>
         </div>`
      : `<div class="text-on-surface-variant text-body-sm p-sm">No committee decision is pending — this case is "${integrityStatusLabel(c.status)}".</div>`;

    container.innerHTML = `
      <div class="glass-panel rounded-xl p-lg">
        <div class="flex justify-between items-start mb-sm">
          <div>
            <div class="font-headline-md text-headline-md text-on-surface">Case #${c.id}</div>
            <div class="text-on-surface-variant text-body-sm">${escapeHtml(c.student)} • ${escapeHtml(c.course)}</div>
          </div>
          <span class="severity-pill ${c.severity}">${c.severity}</span>
        </div>
        <div class="border-t border-outline-variant/10 pt-sm mt-sm">
          <div class="section-title">Instructor Report</div>
          <p class="text-on-surface text-body-sm mb-md">${escapeHtml(c.report)} <span class="text-on-surface-variant">— reported by ${escapeHtml(c.instructor)}</span></p>
          ${policySection}
          <div class="section-title">Evidence Summary</div>
          <div>${evidenceRows}</div>
        </div>
      </div>

      <div class="glass-panel rounded-xl p-lg">
        <div class="flex justify-between items-center mb-sm">
          <div class="section-title mb-0 flex items-center gap-xs"><span class="material-symbols-outlined text-sm">neurology</span>AI Assessment (Advisory)</div>
          ${c.aiConfidence != null ? `<div class="confidence-badge">${c.aiConfidence}%</div>` : ""}
        </div>
        <div class="ai-assessment-box">
          <div class="text-on-surface-variant text-xs mb-1">Rationale</div>
          <div class="text-on-surface text-body-sm">${c.aiRationale ? escapeHtml(c.aiRationale) : "Not available for this case yet."}</div>
        </div>
        <div class="text-on-surface-variant text-xs mt-sm">The AI severity assessment (${c.aiSeverity || "unclassified"}) is advisory input only — it is clearly separated from the committee's final decision below.</div>
      </div>

      <div class="glass-panel rounded-xl p-lg">
        <div class="section-title flex items-center gap-xs"><span class="material-symbols-outlined text-sm">balance</span>Committee Decision (Final — Department Head)</div>
        <div class="mb-md">${timelineHtml}</div>
        ${decisionBlock}
      </div>
    `;

    container.querySelectorAll("[data-action]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        const action = btn.dataset.action;
        let note = null;
        if (action !== "confirm_finding") note = prompt(`Optional note for "${integrityActionLabel(action)}":`) || null;
        btn.disabled = true;
        try {
          await DHApi.submitIntegrityDecision(c.id, action, note);
          showToast(`Committee decision recorded: ${integrityActionLabel(action)}.`, "success");
          await loadIntegrityQueue();
        } catch (err) {
          console.error(err);
          // Real, honest error: the Phase-3 graph currently only allows
          // "instructor"/"advisor" roles to record this decision (see
          // academic_integrity_router.py) — a dept_head gets a real 403,
          // shown as-is rather than papered over as a generic failure.
          const message = err.status === 403
            ? "Committee decisions for Academic Integrity currently require an Instructor or Advisor account — Department Head isn't authorized for this step yet."
            : "Could not record the committee decision.";
          showToast(message, "error");
          btn.disabled = false;
        }
      })
    );
  }

  function integrityActionLabel(action) {
    const map = {
      confirm_finding: "Finding Confirmed",
      request_evidence: "Additional Evidence Requested",
      dismiss_case: "Case Dismissed",
      uphold_final: "Ruling Upheld",
      reduce_penalty: "Penalty Reduced",
      dismiss_final: "Dismissed on Appeal",
      // Raw backend decision values (uphold/dismiss/request_more_evidence/
      // reduce_penalty), in case a decision recorded elsewhere is displayed
      // here before this page's own action-label mapping applies.
      uphold: "Finding Upheld",
      dismiss: "Dismissed",
      request_more_evidence: "Additional Evidence Requested",
    };
    return map[action] || action;
  }

  /* ---------------- Utilities ---------------- */
  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function showToast(message, type) {
    let root = document.getElementById("toast-root");
    const toast = document.createElement("div");
    toast.style.cssText = `background:#191c22;border:1px solid ${type === "error" ? "rgba(255,180,171,.4)" : "rgba(143,214,163,.4)"};color:#e1e2eb;padding:12px 18px;border-radius:.5rem;font-size:14px;box-shadow:0 4px 20px rgba(0,0,0,.4);margin-top:8px;`;
    toast.textContent = message;
    root.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }
})();