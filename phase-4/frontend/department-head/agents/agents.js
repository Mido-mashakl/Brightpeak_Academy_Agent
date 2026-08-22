(function () {
  DHNav.mount({ active: "agents", searchPlaceholder: "Search agents..." });

  init();

  async function init() {
    const agents = await DHApi.listAgents();
    document.getElementById("agents-grid").innerHTML = agents.map(agentCard).join("");
  }

  function agentCard(agent) {
    const statusClass = agent.status.replace(/\s+/g, "-");
    return `
      <div class="agent-card">
        <div class="flex items-start justify-between">
          <div class="agent-icon-badge"><span class="material-symbols-outlined">${agent.icon}</span></div>
          <div class="flex items-center gap-xs">
            <span class="status-dot ${statusClass}"></span>
            <span class="text-on-surface-variant text-xs">${agent.status}</span>
          </div>
        </div>
        <div>
          <div class="font-headline-md text-headline-md text-on-surface" style="font-size:18px;">${escapeHtml(agent.name)}</div>
          <p class="text-on-surface-variant text-body-sm mt-1">${escapeHtml(agent.description)}</p>
        </div>
        <div>
          <div class="agent-meta-row"><span class="agent-meta-label">Last Activity</span><span class="agent-meta-value">${agent.lastActivity}</span></div>
          <div class="agent-meta-row"><span class="agent-meta-label">Active Workflows</span><span class="agent-meta-value ${agent.status !== "Active" ? "warn" : ""}">${agent.activeWorkflows}</span></div>
        </div>
      </div>`;
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
})();
