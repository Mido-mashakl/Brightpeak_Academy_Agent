document.addEventListener("DOMContentLoaded", async () => {
  bpRenderNav({ active: "dashboard" });

  const user = bpGetCurrentUser();
  document.getElementById("bp-greeting").innerHTML =
    `Good morning, <span class="accent">${user.name.split(" ")[0]}</span> 👋`;

  // Real counts straight from GET /dashboard/advisor — no client-side
  // computation, no fabricated week-over-week deltas (no history table
  // exists to diff against, so that UI element is dropped rather than faked).
  const stats = await bpFetchDashboardStats();

  document.getElementById("bp-stats").innerHTML = `
    <div class="bp-stat total">
      <div class="label">Total Requests</div>
      <div class="value">${stats.total}</div>
    </div>
    <div class="bp-stat progress">
      <div class="label">In Progress</div>
      <div class="value">${stats.inProgress}</div>
    </div>
    <div class="bp-stat review">
      <div class="label">Pending Review</div>
      <div class="value">${stats.pendingReview}</div>
    </div>
    <div class="bp-stat completed">
      <div class="label">Completed</div>
      <div class="value">${stats.completed}</div>
    </div>
  `;

  document.getElementById("bp-attention-list").innerHTML = stats.needingAttention
    .map((r) => {
      const meta = BP_STATUS_META[r.status];
      const initials = r.student.split(" ").map((p) => p[0]).slice(0, 2).join("");
      return `
        <div class="bp-attention-row">
          <div class="bp-attention-avatar">${initials}</div>
          <div class="bp-attention-info">
            <div class="name">${r.student}</div>
            <div class="type">${r.type}</div>
          </div>
          <div class="bp-attention-right">
            <span class="bp-badge ${meta.badgeClass}">${meta.label}</span>
            <a href="../requests/request-detail.html?id=${r.id}">View Request →</a>
          </div>
        </div>`;
    })
    .join("");

  // No "avg. eligibility accuracy" or "recommendations generated" column
  // exists anywhere in the schema — the AI-insights ring that used to
  // show those was fabricated demo data and is removed rather than
  // faked with a null/zero value. The insights panel is hidden until
  // there's a real metric behind it.
  const insightsPanel = document.getElementById("bp-insights");
  if (insightsPanel) {
    insightsPanel.innerHTML = `<p class="bp-muted">AI insights are not yet available from the backend.</p>`;
  }
});