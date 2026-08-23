/**
 * department-head-nav.js
 * ---------------------------------------------------------------
 * Renders the shared sidebar + top app bar for all Department Head
 * pages, and resolves the current authenticated user.
 *
 * INTEGRATION POINT (auth):
 *   Replace DHAuth.getCurrentUser() with a call into the existing
 *   app auth/session module (e.g. window.App.auth.getUser() or a
 *   /me endpoint). This file must NEVER hardcode "Ahmed" once real
 *   auth is wired in — it is used only as a design-preview fallback.
 *
 * Usage: each page needs
 *   <div id="dh-sidebar"></div> ... <div id="dh-topbar"></div>
 *   <script src="../shared/department-head-nav.js"></script>
 *   <script>DHNav.mount({ active: "dashboard" });</script>
 * ---------------------------------------------------------------
 */
const DHAuth = {
  ROLE_REQUIRED: "dept_head",

  /**
   * window.currentUser is set by frontend/shared/auth.js (BrightPeakAuth)
   * via this page's auth-guard.js, which runs before this file and
   * already validated the session against the logged-in email.
   */
  getCurrentUser() {
    if (window.currentUser) return window.currentUser;
    // Fallback so the design previews without a backend attached.
    return { id: "demo-dept-head", name: "Ahmed", role: "dept_head", avatarUrl: null };
  },

  /**
   * INTEGRATION POINT: replace with real RBAC check
   * (e.g. redirect to /login or /403 on failure).
   */
  requireDepartmentHead() {
    const user = this.getCurrentUser();
    if (user.role !== this.ROLE_REQUIRED) {
      console.error("[DHAuth] Access denied: department_head role required, got:", user.role);
      document.body.innerHTML =
        '<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0B0E14;color:#e1e2eb;font-family:Inter,sans-serif;">' +
        '<div style="text-align:center;"><h1 style="font-family:\'Hanken Grotesk\',sans-serif;font-size:24px;margin-bottom:8px;">Access restricted</h1>' +
        '<p style="color:#cbc3d7;">This section requires the Department Head role.</p></div></div>';
      throw new Error("Access denied: department_head role required");
    }
    return user;
  }
};

const DHNav = (function () {
  const NAV_ITEMS = [
    { key: "dashboard", label: "Dashboard", icon: "dashboard", href: "../dashboard/dashboard.html" },
    { key: "hiring", label: "Faculty Hiring", icon: "person_add", href: "../hiring/jobs.html" },
    { key: "hitl", label: "Committee Review", icon: "groups", href: "../hitl/hitl.html" },
    { key: "tickets", label: "Tickets", icon: "confirmation_number", href: "../tickets/tickets.html" },
    { key: "agents", label: "AI Agents", icon: "hub", href: "../agents/agents.html" }
  ];

  function linkClasses(isActive) {
    return isActive
      ? "flex items-center gap-md px-md py-sm rounded-lg text-primary font-bold border-r-2 border-primary bg-primary/5 hover:bg-primary/10 transition-all active:scale-[0.98] duration-200"
      : "flex items-center gap-md px-md py-sm rounded-lg text-on-surface-variant/60 font-medium hover:bg-primary/10 hover:text-primary transition-all active:scale-[0.98] duration-200";
  }

  function renderSidebar(active) {
    const items = NAV_ITEMS.map(
      (item) =>
        `<a class="${linkClasses(item.key === active)}" href="${item.href}" data-nav-key="${item.key}">
           <span class="material-symbols-outlined"${item.key === active ? ' style="font-variation-settings: \'FILL\' 1;"' : ""}>${item.icon}</span>
           ${item.label}
         </a>`
    ).join("");

    return `
      <nav class="h-screen w-72 fixed left-0 top-0 bg-surface-container/40 backdrop-blur-xl border-r border-outline-variant/10 shadow-2xl flex flex-col py-md px-sm z-50">
        <div class="mb-xl px-sm">
          <a href="../dashboard/dashboard.html" class="flex items-center gap-sm mb-xs no-underline">
            <span class="material-symbols-outlined text-primary text-3xl">school</span>
            <span class="font-display-lg font-bold text-primary" style="font-size:24px;line-height:32px;">Brightpeak</span>
          </a>
          <div class="font-label-caps text-label-caps text-on-surface-variant">Academy Intelligence</div>
        </div>
        <div class="flex-1 flex flex-col gap-sm">${items}</div>
        <div class="mt-auto border-t border-outline-variant/10 pt-md flex flex-col gap-xs">
          <a class="flex items-center gap-md px-md py-sm rounded-lg text-on-surface-variant/60 font-medium hover:bg-primary/10 hover:text-primary transition-all" href="#" data-action="profile">
            <span class="material-symbols-outlined">account_circle</span> Profile
          </a>
          <a class="flex items-center gap-md px-md py-sm rounded-lg text-on-surface-variant/60 font-medium hover:bg-primary/10 hover:text-primary transition-all" href="#" data-action="settings">
            <span class="material-symbols-outlined">settings</span> Settings
          </a>
          <a class="flex items-center gap-md px-md py-sm rounded-lg text-on-error/80 font-medium hover:bg-error-container/20 hover:text-error transition-all" href="#" data-action="logout">
            <span class="material-symbols-outlined">logout</span> Logout
          </a>
        </div>
      </nav>`;
  }

  function renderTopbar(user, searchPlaceholder) {
    const initials = (user.name || "?").trim().charAt(0).toUpperCase();
    const avatar = user.avatarUrl
      ? `<img alt="${user.name}" class="w-8 h-8 rounded-full border border-outline-variant/50 group-hover:border-primary transition-colors object-cover" src="${user.avatarUrl}"/>`
      : `<div class="w-8 h-8 rounded-full border border-outline-variant/50 group-hover:border-primary transition-colors bg-primary-container/40 flex items-center justify-center text-on-surface text-sm font-semibold">${initials}</div>`;

    return `
      <header class="sticky top-0 z-40 border-b border-outline-variant/10 bg-surface/80 backdrop-blur-md flex justify-between items-center w-full px-lg py-sm ml-72" style="max-width:calc(100% - 18rem);">
        <div class="flex-1 flex items-center gap-md">
          <div class="relative w-64">
            <span class="material-symbols-outlined absolute left-sm top-1/2 -translate-y-1/2 text-on-surface-variant" style="left:12px;">search</span>
            <input class="w-full bg-surface-container-highest/50 border border-outline-variant/30 rounded-full py-xs pl-xl pr-sm text-body-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-tertiary-container focus:border-transparent transition-all" style="padding-left:36px;" placeholder="${searchPlaceholder || "Search..."}" type="text"/>
          </div>
        </div>
        <div class="flex items-center gap-md">
          <button class="p-xs text-on-surface-variant hover:text-primary transition-colors relative" data-action="notifications">
            <span class="material-symbols-outlined">notifications</span>
            <span class="absolute top-1 right-1 w-2 h-2 rounded-full bg-error ai-glow"></span>
          </button>
          <button class="p-xs text-on-surface-variant hover:text-primary transition-colors" data-action="apps">
            <span class="material-symbols-outlined">apps</span>
          </button>
          <div class="h-6 w-px bg-outline-variant/30 mx-xs"></div>
          <div class="flex items-center gap-sm cursor-pointer group" data-action="profile">
            ${avatar}
            <span class="font-body-sm text-body-sm text-on-surface-variant group-hover:text-primary transition-colors">${user.name}</span>
            <span class="material-symbols-outlined text-on-surface-variant group-hover:text-primary transition-colors text-sm">expand_more</span>
          </div>
        </div>
      </header>`;
  }

  function mount(opts) {
    const options = opts || {};
    const user = DHAuth.requireDepartmentHead();

    const sidebarMount = document.getElementById("dh-sidebar");
    const topbarMount = document.getElementById("dh-topbar");
    if (sidebarMount) sidebarMount.outerHTML = renderSidebar(options.active);
    if (topbarMount) topbarMount.outerHTML = renderTopbar(user, options.searchPlaceholder);

    document.querySelectorAll('[data-action="logout"]').forEach((el) =>
      el.addEventListener("click", (e) => {
        e.preventDefault();
        // INTEGRATION POINT: call real logout endpoint / clear session
        localStorage.removeItem("bp_current_user");
        alert("Logout is wired to the shared auth module in production. (design preview)");
      })
    );

    return user;
  }

  return { mount, NAV_ITEMS };
})();