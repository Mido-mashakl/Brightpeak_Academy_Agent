(async function () {
  const user = DHNav.mount({ active: "dashboard", searchPlaceholder: "Search..." });

  const hour = new Date().getHours();
  const greetingWord = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  document.getElementById("greeting").textContent = `${greetingWord}, ${user.name}.`;

  try {
    const stats = await DHApi.getDashboardStats();
    const urgentCount = stats.integrityCasesAwaitingReview + (stats.openTickets > 10 ? 1 : 0);
    document.getElementById("greeting-sub").textContent =
      `Your AI-powered department command center is fully operational. You have ${urgentCount} urgent item${urgentCount === 1 ? "" : "s"} needing attention today.`;

    renderStats(stats);
    renderHiringOverview(stats.hiring);
    renderIntegrityOverview(stats.integrity);
    renderActivity();
    renderPipeline();
  } catch (err) {
    console.error("[dashboard] failed to load stats", err);
  }

  function statTile({ label, value, icon, iconColor, trend, trendIcon, trendColor, highlight }) {
    return `
      <div class="stat-tile${highlight ? " ai-border-gradient" : ""}">
        <div class="flex justify-between items-start mb-md">
          <div class="font-label-caps text-label-caps text-on-surface-variant">${label}</div>
          <span class="material-symbols-outlined ${iconColor}">${icon}</span>
        </div>
        <div>
          <div class="font-display-lg text-display-lg text-on-surface mb-xs">${value}</div>
          <div class="font-mono-data text-mono-data ${trendColor} flex items-center gap-xs">
            <span class="material-symbols-outlined text-sm">${trendIcon}</span> ${trend}
          </div>
        </div>
      </div>`;
  }

  function renderStats(stats) {
    document.getElementById("stats-row").innerHTML = [
      statTile({ label: "Active Faculty Positions", value: stats.activeFacultyPositions, icon: "work", iconColor: "text-primary/70", trend: "Open postings", trendIcon: "trending_up", trendColor: "text-tertiary-container" }),
      statTile({ label: "Candidates Awaiting Hiring Decision", value: stats.candidatesAwaitingDecision, icon: "people", iconColor: "text-secondary/70", trend: "AI sorted", trendIcon: "auto_awesome", trendColor: "text-secondary", highlight: true }),
      statTile({ label: "Academic Integrity Cases Awaiting Committee Review", value: stats.integrityCasesAwaitingReview, icon: "gavel", iconColor: "text-error/70", trend: "Needs review", trendIcon: "warning", trendColor: "text-error" }),
      statTile({ label: "Open Tickets", value: stats.openTickets, icon: "confirmation_number", iconColor: "text-primary/70", trend: "Across all workflows", trendIcon: "trending_down", trendColor: "text-tertiary-container" })
    ].join("");
  }

  function miniStat(label, value, colorClass) {
    return `<div class="mini-stat"><div class="font-label-caps text-label-caps text-on-surface-variant mb-xs">${label}</div><div class="font-headline-lg text-headline-lg ${colorClass || "text-on-surface"}">${value}</div></div>`;
  }

  function renderHiringOverview(h) {
    document.getElementById("hiring-mini-stats").innerHTML =
      miniStat("Job Postings", h.jobPostings) +
      miniStat("Applications", h.applications) +
      miniStat("Shortlisted", h.shortlisted) +
      miniStat("Pending Decisions", h.pendingDecisions, "text-secondary");
  }

  function renderIntegrityOverview(i) {
    document.getElementById("integrity-mini-stats").innerHTML =
      miniStat("Open Cases", i.openCases) +
      miniStat("Awaiting Review", i.awaitingReview, "text-error") +
      miniStat("Appeals", i.appeals) +
      miniStat("Final Decisions Pending", i.finalDecisionsPending, "text-tertiary-container");
  }

  async function renderActivity() {
    const candidates = await DHApi.listCandidates();
    const recent = candidates.slice(0, 3);
    const dotColors = ["bg-primary", "bg-secondary", "bg-tertiary"];
    document.getElementById("hiring-activity").innerHTML = recent.length
      ? recent
          .map(
            (c, i) => `
        <div class="activity-row">
          <div class="w-2 h-2 rounded-full ${dotColors[i % dotColors.length]}"></div>
          <div class="flex-1">
            <div class="font-body-md text-body-md text-on-surface">${c.name}</div>
            <div class="font-body-sm text-body-sm text-on-surface-variant">${statusLabel(c.status)}</div>
          </div>
          <div class="font-mono-data text-mono-data text-on-surface-variant text-sm">recently</div>
        </div>`
          )
          .join("")
      : `<div class="text-on-surface-variant text-body-sm">No recent hiring activity.</div>`;
  }

  function statusLabel(status) {
    const map = {
      parsing: "Parsing CV",
      ai_scored: "AI Scored",
      shortlisted: "Shortlisted",
      interview: "Interview Scheduled",
      hired: "Hired",
      rejected: "Rejected",
      rescore_requested: "Rescore Requested"
    };
    return map[status] || status;
  }

  async function renderPipeline() {
    const cases = await DHApi.listIntegrityCases();
    const urgent = cases.filter((c) => c.status !== "closed").slice(0, 2);
    document.getElementById("integrity-pipeline").innerHTML = urgent.length
      ? urgent
          .map(
            (c) => `
        <div class="pipeline-row ${c.severity === "severe" || c.severity === "major" ? "urgent" : ""}">
          <div class="flex items-center gap-md">
            <span class="material-symbols-outlined ${c.severity === "severe" || c.severity === "major" ? "text-error" : "text-on-surface-variant"} text-sm">${c.severity === "severe" || c.severity === "major" ? "priority_high" : "pending_actions"}</span>
            <div>
              <div class="font-body-md text-body-md text-on-surface">Case #${c.id}</div>
              <div class="font-body-sm text-body-sm text-on-surface-variant">${c.severity} case — ${statusText(c.status)}</div>
            </div>
          </div>
          <a class="pipeline-btn" href="../hitl/hitl.html?tab=integrity&case=${c.id}">${c.status === "reported" ? "Review" : "Details"}</a>
        </div>`
          )
          .join("")
      : `<div class="text-on-surface-variant text-body-sm">No urgent cases right now.</div>`;
  }

  function statusText(status) {
    const map = { reported: "Review Needed", under_review: "Under Review", awaiting_appeal: "Appeal Hearing Scheduled", closed: "Closed" };
    return map[status] || status;
  }
})();