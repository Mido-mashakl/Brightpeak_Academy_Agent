document.addEventListener("DOMContentLoaded", async () => {
  bpRenderNav({ active: "dashboard" });

  const user = bpGetCurrentUser();
  document.getElementById("bp-greeting").innerHTML =
    `Good morning, <span class="accent">${user.name.split(" ")[0]}</span> 👋`;

  // NOTE: dashboard statistics are mock/demo data — see brief section 4 & 10.
  const stats = await bpFetchDashboardStats();

  document.getElementById("bp-stats").innerHTML = `
    <div class="bp-stat total">
      <div class="label">Total Requests</div>
      <div class="value">${stats.total}</div>
      <div class="delta">↑ ${stats.deltas.total}</div>
    </div>
    <div class="bp-stat progress">
      <div class="label">In Progress</div>
      <div class="value">${stats.inProgress}</div>
      <div class="delta">↑ ${stats.deltas.inProgress}</div>
    </div>
    <div class="bp-stat review">
      <div class="label">Pending Review</div>
      <div class="value">${stats.pendingReview}</div>
      <div class="delta">↑ ${stats.deltas.pendingReview}</div>
    </div>
    <div class="bp-stat completed">
      <div class="label">Completed</div>
      <div class="value">${stats.completed}</div>
      <div class="delta">↑ ${stats.deltas.completed}</div>
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

  const ai = stats.aiInsights;
  const circumference = 2 * Math.PI * 46;
  const offset = circumference * (1 - ai.avgEligibilityAccuracy / 100);

  document.getElementById("bp-insights").innerHTML = `
    <div class="bp-ring-wrap">
      <svg width="120" height="120" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="46" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="10" />
        <circle cx="60" cy="60" r="46" fill="none" stroke="url(#bpRingGrad)" stroke-width="10"
          stroke-linecap="round" stroke-dasharray="${circumference}" stroke-dashoffset="${offset}"
          transform="rotate(-90 60 60)" />
        <defs>
          <linearGradient id="bpRingGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="#8b5cf6" />
            <stop offset="100%" stop-color="#ec4899" />
          </linearGradient>
        </defs>
        <text x="60" y="56" text-anchor="middle" fill="#f4f2fb" font-size="22" font-weight="700">${ai.avgEligibilityAccuracy}%</text>
        <text x="60" y="74" text-anchor="middle" fill="#a6a0c3" font-size="9">Avg. Eligibility</text>
        <text x="60" y="85" text-anchor="middle" fill="#a6a0c3" font-size="9">Accuracy</text>
      </svg>
    </div>
    <div class="bp-insight-metrics">
      <div><div class="num">${ai.requestsAnalyzed}</div><div class="lbl">Requests<br/>Analyzed</div></div>
      <div><div class="num">${ai.recommendationsGenerated}</div><div class="lbl">Recommendations<br/>Generated</div></div>
    </div>
  `;
});
