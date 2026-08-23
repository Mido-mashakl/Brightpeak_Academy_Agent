// =========================================================
// Instructor Dashboard
// =========================================================

// auth-guard.js (loaded before this file) already validated the session
// and set window.currentUser from the logged-in user's data.
const BP_CURRENT_USER = window.currentUser || { name: "Instructor", role: "Instructor" };

document.addEventListener("DOMContentLoaded", async () => {
  BPLayout.mount({ active: "dashboard", userName: BP_CURRENT_USER.name, userRole: BP_CURRENT_USER.role });
  document.getElementById("bp-greeting").textContent = `Good morning, ${BP_CURRENT_USER.name} 👋`;

  const statGrid = document.getElementById("bp-stat-grid");
  const statusSummary = document.getElementById("bp-status-summary");
  const recentCasesEl = document.getElementById("bp-recent-cases");
  const recentRequestsEl = document.getElementById("bp-recent-requests");

  statGrid.innerHTML = BPState.loading("Loading overview...");
  recentCasesEl.innerHTML = "";
  recentRequestsEl.innerHTML = "";

  try {
    const data = await getInstructorDashboard();
    renderStats(data.stats);
    renderStatusSummary(data.statusCounts);
    renderRecentCases(data.recentCases);
    renderRecentRequests(data.recentRequests);
  } catch (err) {
    statGrid.innerHTML = BPState.error("Unable to load dashboard. Please try again.");
    statusSummary.innerHTML = "";
    recentRequestsEl.innerHTML = "";
  }

  function renderStats(stats) {
    statGrid.innerHTML = `
      <div class="bp-card bp-stat-card" id="bp-stat-courses" style="cursor:pointer">
        <div class="bp-stat-icon purple">${BPIcons.courses}</div>
        <div class="bp-stat-body">
          <div class="label-top">Courses</div>
          <div class="value">${stats.courses}</div>
          <div class="label-bottom">Active courses</div>
        </div>
      </div>
      <div class="bp-card bp-stat-card" id="bp-stat-students" style="cursor:pointer">
        <div class="bp-stat-icon pink">${BPIcons.students}</div>
        <div class="bp-stat-body">
          <div class="label-top">Students</div>
          <div class="value">${stats.students}</div>
          <div class="label-bottom">Total students</div>
        </div>
      </div>
      <div class="bp-card bp-stat-card">
        <div class="bp-stat-icon amber">${BPIcons.reports}</div>
        <div class="bp-stat-body">
          <div class="label-top">Reports</div>
          <div class="value">${stats.reports}</div>
          <div class="label-bottom">Integrity cases</div>
        </div>
      </div>
      <div class="bp-card bp-stat-card">
        <div class="bp-stat-icon blue">${BPIcons.requests}</div>
        <div class="bp-stat-body">
          <div class="label-top">Pending Requests</div>
          <div class="value">${stats.pendingRequests}</div>
          <div class="label-bottom">Awaiting your decision</div>
        </div>
      </div>
    `;
    document.getElementById("bp-stat-courses").addEventListener("click", () => (window.location.href = "../courses/courses.html"));
    document.getElementById("bp-stat-students").addEventListener("click", () => (window.location.href = "../students/students.html"));
  }

  function renderStatusSummary(counts) {
    const rows = [
      ["Reported", counts.reported],
      ["Under Review", counts.underReview],
      ["Awaiting Appeal", counts.awaitingAppeal],
      ["Closed", counts.closed],
    ];
    statusSummary.innerHTML = rows
      .map(([name, count]) => `
        <div class="bp-status-pill">
          <span class="name">${name}</span>
          <span class="count">${count}</span>
        </div>
      `)
      .join("");
  }

  function renderRecentCases(cases) {
    if (!cases || cases.length === 0) {
      recentCasesEl.innerHTML = BPState.empty("No academic integrity cases found.");
      return;
    }
    recentCasesEl.innerHTML = cases
      .map(
        (c) => `
        <div class="bp-list-row" data-id="${c.id}">
          <span class="bp-row-icon" style="background:rgba(139,92,246,0.14);color:#a78bfa">${BPIcons.shield}</span>
          <span class="bp-cell-primary">Case #${c.id}<br><span class="bp-cell-muted" style="font-weight:400">${c.student}</span></span>
          <span class="bp-cell-muted">${c.course}</span>
          <span>${BPFormat.severityBadge(c.severity)}</span>
          <span>${BPFormat.statusBadge(c.status)}</span>
          <span class="bp-row-chevron">${BPIcons.chevronRight}</span>
        </div>
      `
      )
      .join("");

    recentCasesEl.querySelectorAll(".bp-list-row").forEach((row) => {
      row.addEventListener("click", () => {
        window.location.href = `../integrity/case-details.html?id=${row.dataset.id}`;
      });
    });
  }

  function renderRecentRequests(requests) {
    if (!requests || requests.length === 0) {
      recentRequestsEl.innerHTML = BPState.empty("No requests found.");
      return;
    }
    recentRequestsEl.innerHTML = requests
      .map(
        (r) => `
        <div class="bp-list-row" data-id="${r.id}">
          <span class="bp-row-icon" style="background:rgba(96,165,250,0.14);color:#60a5fa">${BPIcons.requests}</span>
          <span class="bp-cell-primary">${BPFormat.requestTypeLabel[r.type] || r.type}<br><span class="bp-cell-muted" style="font-weight:400">${r.student}</span></span>
          <span class="bp-cell-muted">${r.course}</span>
          <span class="bp-cell-muted">${r.submittedLabel}</span>
          <span>${BPFormat.statusBadge(r.status)}</span>
          <span class="bp-row-chevron">${BPIcons.chevronRight}</span>
        </div>
      `
      )
      .join("");

    recentRequestsEl.querySelectorAll(".bp-list-row").forEach((row) => {
      row.addEventListener("click", () => {
        window.location.href = `../requests/request-details.html?id=${row.dataset.id}`;
      });
    });
  }
});