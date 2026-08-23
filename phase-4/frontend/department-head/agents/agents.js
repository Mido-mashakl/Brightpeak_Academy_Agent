(function () {
  DHNav.mount({ active: "agents", searchPlaceholder: "Search agents..." });

  // Static, non-application-data icon per graph key — the same kind of
  // fixed UI metadata as a nav icon, not a per-record fact from the DB.
  const ICONS = {
    academic_integrity: "policy",
    adaptive_assessment: "fact_check",
    advisory: "support_agent",
    faculty_hiring: "person_search",
    track_recommendation: "route",
  };

  init();

  async function init() {
    const agents = await DHApi.listAgents();
    document.getElementById("agents-grid").innerHTML = agents.map(agentCard).join("");
  }

  function agentCard(agent) {
    return `
      <div class="agent-card">
        <div class="flex items-start justify-between">
          <div class="agent-icon-badge"><span class="material-symbols-outlined">${ICONS[agent.key] || "hub"}</span></div>
        </div>
        <div>
          <div class="font-headline-md text-headline-md text-on-surface" style="font-size:18px;">${escapeHtml(agent.name)}</div>
          <p class="text-on-surface-variant text-body-sm mt-1">${escapeHtml(agent.description)}</p>
        </div>
        <div>
          <div class="agent-meta-row"><span class="agent-meta-label">Open Items</span><span class="agent-meta-value ${agent.open_items > 0 ? "warn" : ""}">${agent.open_items}</span></div>
        </div>
      </div>`;
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
})();