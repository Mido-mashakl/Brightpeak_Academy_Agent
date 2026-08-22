// =========================================================
// Brightpeak Academy — shared navigation config
// Maps each feature key (from permissions.js) to its label,
// icon, and page path relative to a role's folder. Pages can
// use this to render a sidebar instead of hardcoding links.
// =========================================================

window.BrightPeakNav = (function () {
  // Ordinary per-role screens — paths are relative to the role's
  // own folder (e.g. "instructor/").
  const NAV_ITEMS = {
    dashboard: { label: "Dashboard", icon: "grid_view", path: "dashboard/dashboard.html" },
    "ai-assistant": { label: "AI Assistant", icon: "smart_toy", path: "ai-assistant/assistant.html" },
    agents: { label: "AI Agents", icon: "smart_toy", path: "agents/agents.html" },
    requests: { label: "Requests", icon: "description", path: "requests/requests.html" },
    hitl: { label: "HITL Queue", icon: "fact_check", path: "hitl/hitl.html" },
    tickets: { label: "Tickets", icon: "confirmation_number", path: "tickets/tickets.html" },
    hiring: { label: "Faculty Hiring", icon: "work", path: "hiring/hiring.html" },
  };

  // Privileged, shared (not per-role) screens — paths are relative
  // to the role's own folder too, but climb back out to /shared/.
  const PRIVILEGED_NAV_ITEMS = {
    tools: { label: "MCP Tools", icon: "build", path: "../shared/tools/tools.html" },
    rag: { label: "RAG Documents", icon: "menu_book", path: "../shared/rag/rag.html" },
  };

  // Returns the ordered list of nav items a role is allowed to see,
  // using BrightPeakPermissions if it's loaded on the page.
  function itemsFor(role) {
    const features = window.BrightPeakPermissions
      ? window.BrightPeakPermissions.featuresFor(role)
      : Object.keys(NAV_ITEMS);

    const privileged = window.BrightPeakPermissions
      ? window.BrightPeakPermissions.privilegedFeaturesFor(role)
      : [];

    const ordinary = features
      .filter((key) => NAV_ITEMS[key])
      .map((key) => ({ key, ...NAV_ITEMS[key] }));

    const extra = privileged
      .filter((key) => PRIVILEGED_NAV_ITEMS[key])
      .map((key) => ({ key, ...PRIVILEGED_NAV_ITEMS[key] }));

    return [...ordinary, ...extra];
  }

  return { NAV_ITEMS, PRIVILEGED_NAV_ITEMS, itemsFor };
})();
