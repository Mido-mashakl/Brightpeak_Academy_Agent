// Agent icons are real image assets, served from advisor/assets/.
// Plan Generator Agent intentionally uses an inline icon (not an image) —
// the layers-glow.png asset didn't match the design and was removed.
const BP_AGENT_ICONS = {
  advisory_assistant: "../assets/ai-orbit.png.jpeg",
  eligibility_agent: "../assets/eligibility-cube.png",
  policy_search_agent: "../assets/search-glow.png.jpeg",
};

const BP_AGENT_FALLBACK_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2 2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5"/></svg>';

const BP_WORKFLOW_STEPS = [
  { label: "Student\nRequest", icon: "grid" },
  { label: "AI Analysis", icon: "cpu" },
  { label: "Requirements\nCheck", icon: "check" },
  { label: "Policy\nValidation", icon: "search" },
  { label: "Advisor\nReview", icon: "user" },
  { label: "Final\nDecision", icon: "flag" },
];

const BP_WF_ICONS = {
  grid: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
  cpu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 3v3M15 3v3M9 18v3M15 18v3"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 12 2 2 4-4"/><circle cx="12" cy="12" r="9"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>',
  user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/></svg>',
  flag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 22V4"/><path d="M4 4h14l-3 4 3 4H4"/></svg>',
};

document.addEventListener("DOMContentLoaded", async () => {
  bpRenderNav({ active: "agents", showSearch: false });

  // Real GET /agents response: key, name, description, open_items.
  // There is no accuracy / last-activity / active-flag column anywhere
  // in the schema, so those are not rendered — showing them would mean
  // inventing numbers the backend never provided.
  const agents = await bpFetchAgents();

  document.getElementById("bp-agents-grid").innerHTML = agents.length
    ? agents
        .map(
          (a) => `
      <div class="bp-agent-card">
        <div class="bp-agent-icon">
          ${
            BP_AGENT_ICONS[a.key]
              ? `<img src="${BP_AGENT_ICONS[a.key]}" alt="${a.name} icon" onerror="this.style.display='none'" />`
              : `<span class="bp-agent-icon-fallback">${BP_AGENT_FALLBACK_ICON}</span>`
          }
        </div>
        <div class="bp-agent-name">${a.name}</div>
        <div class="bp-agent-desc">${a.description}</div>
        <div class="bp-agent-meta">
          <div><span class="num">${a.open_items}</span>Open Items</div>
        </div>
      </div>`
        )
        .join("")
    : `<p class="bp-muted">No agents found.</p>`;

  document.getElementById("bp-workflow-row").innerHTML = BP_WORKFLOW_STEPS.map(
    (s, i) => `
      <div class="bp-wf-step">
        <div class="bp-wf-icon">${BP_WF_ICONS[s.icon]}</div>
        <div class="bp-wf-label">${s.label.replace("\n", "<br/>")}</div>
      </div>
      ${i < BP_WORKFLOW_STEPS.length - 1 ? '<span class="bp-wf-arrow">→</span>' : ""}`
  ).join("");
});