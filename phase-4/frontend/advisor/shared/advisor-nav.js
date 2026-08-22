/* ============================================================
   Brightpeak Academy — Advisor Portal
   Shared sidebar + topbar.

   IMPORTANT (backend integration):
   This currently reads the logged-in advisor from
   `window.bpCurrentUser`. Replace `getCurrentUser()` below with
   a call to the project's real auth/session service
   (e.g. authService.getCurrentUser() / a /me endpoint) once this
   is wired into the actual app. Do NOT hardcode the advisor's
   identity in production.
   ============================================================ */

const BP_NAV_ITEMS = [
  { key: "dashboard", label: "Dashboard", href: "../dashboard/dashboard.html", icon: "grid" },
  { key: "requests", label: "Requests", href: "../requests/requests.html", icon: "list" },
  { key: "hitl", label: "HITL", href: "../hitl/hitl.html", icon: "check" },
  { key: "agents", label: "AI Agents", href: "../agents/agents.html", icon: "cpu" },
];

const BP_ICONS = {
  grid: '<svg class="bp-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
  list: '<svg class="bp-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3.5" cy="6" r="1.2" fill="currentColor" stroke="none"/><circle cx="3.5" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="3.5" cy="18" r="1.2" fill="currentColor" stroke="none"/></svg>',
  check: '<svg class="bp-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="m8 12 3 3 5-6"/></svg>',
  cpu: '<svg class="bp-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3"/></svg>',
  settings: '<svg class="bp-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.14.36.22.75.22 1.15V10a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
  logout: '<svg class="bp-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg>',
};

/**
 * TODO (backend): replace with real auth/session lookup.
 * e.g. return authService.getCurrentUser()  /  fetch('/api/me')
 */
function bpGetCurrentUser() {
  return (
    window.bpCurrentUser || {
      name: "Advisor",
      role: "Academic Advisor",
      initials: "AD",
    }
  );
}

function bpInitials(name) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");
}

/**
 * Renders sidebar + topbar into the page.
 * @param {Object} opts
 * @param {string} opts.active - key of BP_NAV_ITEMS to highlight ('dashboard'|'requests'|'hitl'|'agents')
 * @param {string} [opts.searchPlaceholder]
 * @param {string} [opts.sidebarTarget] - selector for sidebar mount point
 * @param {string} [opts.topbarTarget] - selector for topbar mount point
 * @param {boolean} [opts.showSearch]
 * @param {string} [opts.backLink] - if set, shows a "Back to ..." link instead of search
 */
function bpRenderNav(opts) {
  const {
    active,
    searchPlaceholder = "Search students, requests, policies...",
    sidebarTarget = "#bp-sidebar",
    topbarTarget = "#bp-topbar",
    showSearch = true,
    backLink = null,
  } = opts;

  const user = bpGetCurrentUser();
  const initials = user.initials || bpInitials(user.name || "Advisor");

  const sidebarEl = document.querySelector(sidebarTarget);
  if (sidebarEl) {
    sidebarEl.innerHTML = `
      <div class="bp-brand">
        <div class="bp-brand-mark">B</div>
        <div class="bp-brand-text">
          <div class="name">Brightpeak Academy</div>
          <div class="sub">Advisor Portal</div>
        </div>
      </div>
      <nav class="bp-nav">
        ${BP_NAV_ITEMS.map(
          (item) => `
          <a class="bp-nav-item ${item.key === active ? "active" : ""}" href="${item.href}">
            ${BP_ICONS[item.icon]}
            <span>${item.label}</span>
          </a>`
        ).join("")}
      </nav>
      <div class="bp-nav-bottom">
        <a class="bp-nav-item" href="#">${BP_ICONS.settings}<span>Settings</span></a>
        <a class="bp-nav-item logout" href="#" id="bp-logout">${BP_ICONS.logout}<span>Logout</span></a>
      </div>
    `;

    document.getElementById("bp-logout")?.addEventListener("click", (e) => {
      e.preventDefault();
      // TODO (backend): call real logout / auth service, then redirect.
      console.log("Logout clicked — wire to real auth service.");
    });
  }

  const topbarEl = document.querySelector(topbarTarget);
  if (topbarEl) {
    topbarEl.innerHTML = `
      ${
        backLink
          ? `<a class="bp-topbar-back" href="${backLink.href}">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
              ${backLink.label}
            </a>`
          : showSearch
          ? `<div class="bp-search">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
              <span>${searchPlaceholder}</span>
            </div>`
          : `<div></div>`
      }
      <div class="bp-topbar-right">
        <div class="bp-bell">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>
        </div>
        <div class="bp-user">
          <div class="bp-avatar">${initials}</div>
          <div class="bp-user-meta">
            <div class="name">${user.name}</div>
            <div class="role">${user.role}</div>
          </div>
        </div>
      </div>
    `;
  }
}
