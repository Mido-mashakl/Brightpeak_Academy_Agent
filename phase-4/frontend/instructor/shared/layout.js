// =========================================================
// Brightpeak Academy — Instructor Portal
// Shared app shell (sidebar + topbar) and small UI helpers.
//
// Usage: each page includes a <div id="bp-shell"> wrapping its
// <main class="bp-content">...</main>, then calls:
//   BPLayout.mount({ active: "integrity", userName: window.currentUser.name });
// =========================================================

const BPLayout = (() => {
  const NAV = [
    { key: "dashboard", label: "Dashboard", href: "../dashboard/dashboard.html", icon: "dashboard" },
    { key: "courses", label: "My Courses", href: "../courses/courses.html", icon: "courses" },
    { key: "students", label: "Students", href: "../students/students.html", icon: "students" },
    {
      key: "integrity",
      label: "Academic Integrity",
      href: "../integrity/integrity.html",
      icon: "shield",
      children: [
        { key: "integrity-all", label: "All Cases", href: "../integrity/integrity.html" },
        { key: "integrity-report", label: "Report New Case", href: "../integrity/report-case.html" },
      ],
    },
    { key: "requests", label: "Requests", href: "../requests/requests.html", icon: "requests" },
    { key: "hitl", label: "HITL", href: "../hitl/hitl.html", icon: "hitl" },
    { key: "agents", label: "AI Agents", href: "../agents/agents.html", icon: "agents" },
  ];

  function navItemHtml(item, active) {
    const isActive = item.key === active;
    return `
      <a class="bp-nav-item ${isActive ? "active" : ""}" href="${item.href}">
        ${BPIcons[item.icon] || ""}<span>${item.label}</span>
      </a>
      ${
        item.children
          ? `<div class="bp-nav-sub">${item.children
              .map(
                (c) =>
                  `<a class="bp-nav-item ${c.key === active ? "active" : ""}" href="${c.href}"><span>${c.label}</span></a>`
              )
              .join("")}</div>`
          : ""
      }
    `;
  }

  function initials(name) {
    return name
      .split(" ")
      .map((p) => p[0])
      .slice(0, 2)
      .join("")
      .toUpperCase();
  }

  function mount({ active, userName = "Instructor", userRole = "Instructor" } = {}) {
    const shell = document.getElementById("bp-shell");
    if (!shell) return;

    const content = shell.innerHTML; // page content authored inside #bp-shell

    shell.innerHTML = `
      <div class="bp-sidebar-backdrop" id="bp-sidebar-backdrop"></div>
      <aside class="bp-sidebar" id="bp-sidebar">
        <div class="bp-logo">
          <div class="bp-logo-mark">⚡</div>
          <div class="bp-logo-text">Brightpeak</div>
        </div>
        <nav class="bp-nav">
          ${NAV.map((item) => navItemHtml(item, active)).join("")}
        </nav>
        <div class="bp-sidebar-footer">
          <div class="bp-account">
            <div class="bp-avatar">${initials(userName)}</div>
            <div>
              <div class="bp-account-name">${userName}</div>
              <div class="bp-account-role">${userRole}</div>
            </div>
          </div>
          <button class="bp-logout" id="bp-logout-btn">${BPIcons.logout}<span>Log out</span></button>
        </div>
      </aside>

      <div class="bp-main">
        <header class="bp-topbar">
          <button class="bp-menu-toggle" id="bp-menu-toggle">${BPIcons.menu}</button>
          <button class="bp-icon-btn" title="Notifications">${BPIcons.bell}<span class="dot"></span></button>
          <div class="bp-topbar-user">
            <div class="bp-avatar">${initials(userName)}</div>
            <span>${userName}</span>
          </div>
        </header>
        ${content}
      </div>
    `;

    const sidebar = document.getElementById("bp-sidebar");
    const backdrop = document.getElementById("bp-sidebar-backdrop");
    document.getElementById("bp-menu-toggle").addEventListener("click", () => {
      sidebar.classList.toggle("open");
      backdrop.classList.toggle("open");
    });
    backdrop.addEventListener("click", () => {
      sidebar.classList.remove("open");
      backdrop.classList.remove("open");
    });
    document.getElementById("bp-logout-btn").addEventListener("click", () => {
      if (window.BrightPeakAuth && window.BrightPeakAuth.logout) {
        window.BrightPeakAuth.logout();
      } else {
        window.location.href = "../../login/login.html";
      }
    });
  }

  return { mount };
})();

// ---------------------------------------------------------
// Formatting helpers shared across pages
// ---------------------------------------------------------
const BPFormat = {
  severityLabel: { minor: "Minor", major: "Major", severe: "Severe" },
  severityClass: { minor: "bp-badge-minor", major: "bp-badge-major", severe: "bp-badge-severe" },

  statusLabel: {
    reported: "Reported",
    under_review: "Under Review",
    awaiting_appeal: "Awaiting Appeal",
    closed: "Closed",
    committee_review: "Committee Review",
    // Request statuses (Grade Update / Attendance / Enrollment write-ops)
    pending: "Pending",
    approved: "Approved",
    rejected: "Rejected",
    info_requested: "Info Requested",
    // Roster / course standing (My Courses, Students)
    good_standing: "Good Standing",
    at_risk: "At Risk",
    active: "Active",
  },
  statusClass: {
    reported: "bp-badge-reported",
    under_review: "bp-badge-underreview",
    awaiting_appeal: "bp-badge-awaitingappeal",
    closed: "bp-badge-closed",
    committee_review: "bp-badge-committeereview",
    pending: "bp-badge-pending",
    approved: "bp-badge-approved",
    rejected: "bp-badge-rejected",
    info_requested: "bp-badge-reported",
    good_standing: "bp-badge-approved",
    at_risk: "bp-badge-major",
    active: "bp-badge-approved",
  },

  requestTypeLabel: {
    grade_update: "Grade Update",
    attendance_update: "Attendance Update",
    enrollment_change: "Enrollment Change",
  },

  severityBadge(sev) {
    if (!sev) return `<span class="bp-badge bp-badge-neutral"><span class="bp-badge-dot"></span>—</span>`;
    const cls = this.severityClass[sev] || "bp-badge-neutral";
    const label = this.severityLabel[sev] || sev;
    return `<span class="bp-badge ${cls}"><span class="bp-badge-dot"></span>${label}</span>`;
  },
  statusBadge(status) {
    const cls = this.statusClass[status] || "bp-badge-neutral";
    const label = this.statusLabel[status] || status;
    return `<span class="bp-badge ${cls}"><span class="bp-badge-dot"></span>${label}</span>`;
  },
};

// ---------------------------------------------------------
// Toasts
// ---------------------------------------------------------
const BPToast = (() => {
  function ensureWrap() {
    let wrap = document.querySelector(".bp-toast-wrap");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.className = "bp-toast-wrap";
      document.body.appendChild(wrap);
    }
    return wrap;
  }
  function show(message, type = "success", ms = 3500) {
    const wrap = ensureWrap();
    const el = document.createElement("div");
    el.className = `bp-toast ${type}`;
    const icon = type === "success" ? BPIcons.checkCircle : type === "error" ? BPIcons.alert : BPIcons.bell;
    el.innerHTML = `${icon}<span>${message}</span>`;
    wrap.appendChild(el);
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transition = "opacity 0.2s ease";
      setTimeout(() => el.remove(), 200);
    }, ms);
  }
  return {
    success: (msg) => show(msg, "success"),
    error: (msg) => show(msg, "error"),
    info: (msg) => show(msg, "info"),
  };
})();

// ---------------------------------------------------------
// Small state renderers (loading / empty / error) reused by pages
// ---------------------------------------------------------
const BPState = {
  loading(message) {
    return `<div class="bp-state"><div class="bp-spinner"></div><span>${message}</span></div>`;
  },
  empty(message) {
    return `<div class="bp-state">${BPIcons.inbox}<span>${message}</span></div>`;
  },
  error(message) {
    return `<div class="bp-state error">${BPIcons.alert}<span>${message}</span></div>`;
  },
};