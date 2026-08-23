document.addEventListener("DOMContentLoaded", async () => {
  bpRenderNav({ active: "requests", backLink: { href: "requests.html", label: "Back to Requests" } });

  const params = new URLSearchParams(window.location.search);
  const id = params.get("id") || "REQ-1032";
  document.getElementById("bp-req-id").textContent = id;

  const req = await bpFetchRequestById(id);
  if (!req) {
    document.querySelector(".bp-content").innerHTML = `<p class="bp-muted">Request ${id} not found.</p>`;
    return;
  }

  document.getElementById("bp-hitl-link").href = `../hitl/hitl.html?id=${req.id}`;

  const meta = BP_STATUS_META[req.status];
  const initials = req.student.split(" ").map((p) => p[0]).slice(0, 2).join("");

  document.getElementById("bp-summary").innerHTML = `
    <div class="bp-student-block">
      <div class="bp-student-avatar">${initials}</div>
      <div>
        <div class="bp-student-name">${req.student}</div>
        <div class="bp-student-meta">ID: ${req.studentId}</div>
        <div class="bp-student-meta">${req.program || ""} ${req.level ? "· " + req.level : ""}</div>
      </div>
    </div>
    <div>
      <div class="bp-summary-field"><div class="k">Request Type</div><div class="v">${req.type}</div></div>
      <div class="bp-summary-field"><div class="k">Submitted</div><div class="v">${req.submitted || "—"}</div></div>
    </div>
    <div class="bp-summary-right">
      <div>
        <div class="bp-summary-field"><div class="k">Status</div><div class="v"><span class="bp-badge ${meta.badgeClass}">${meta.label}</span></div></div>
      </div>
      <img class="bp-type-icon" src="../assets/graduation-certificate.png" alt="${req.type} request icon" onerror="this.style.display='none'" />
    </div>
  `;

  const timeline = req.timeline || [
    { label: "Request Submitted", date: req.submitted || "—", state: "done" },
    { label: "Data & Eligibility Check", date: "—", state: "pending" },
    { label: "AI Analysis", date: "—", state: "pending" },
    { label: "Advisor Review", date: "—", state: "pending" },
    { label: "Final Decision", date: "—", state: "pending" },
  ];
  document.getElementById("bp-timeline").innerHTML = timeline
    .map((t) => `
      <div class="bp-tl-step ${t.state}">
        <div class="bp-tl-dot"></div>
        <div class="bp-tl-label">${t.label}</div>
        <div class="bp-tl-date">${t.date}</div>
      </div>`)
    .join("");

  // Tab panels
  const panels = {
    info: `
      <div class="bp-panel-grid">
        <div class="bp-card">
          <h3>Request Information</h3>
          <div class="field"><div class="k">Student Message</div><div class="v">${req.message || "—"}</div></div>
          <div class="field"><div class="k">Additional Notes</div><div class="v">${req.notes || "—"}</div></div>
          <div class="field"><div class="k">Attachments</div><div class="v">
            ${(req.attachments || []).map((a) => `<span class="bp-attachment">📄 ${a}</span>`).join(" ") || "—"}
          </div></div>
        </div>
        <div class="bp-card">
          <h3>Program Information</h3>
          <div class="field"><div class="k">Certificate</div><div class="v">${req.programInfo?.certificate || "—"}</div></div>
          <div class="field"><div class="k">Academic Plan</div><div class="v">${req.programInfo?.plan || "—"}</div></div>
          <div class="field"><div class="k">Advisor</div><div class="v">${req.programInfo?.advisor || "—"}</div></div>
        </div>
      </div>`,
    requirements: `
      <div class="bp-card">
        <h3 style="margin:0 0 12px;">Requirements Check</h3>
        <div class="bp-req-list">
          ${(req.requirements || []).map((r) => `
            <div class="bp-req-row">
              <span>${r.label}</span>
              <span class="ok">${r.value}</span>
            </div>`).join("") || `<p class="bp-muted">No requirements data available.</p>`}
        </div>
      </div>`,
    academic: `<div class="bp-card"><p class="bp-muted">Academic data will appear here once the transcript/records service is connected.</p></div>`,
    policy: `<div class="bp-card"><p class="bp-muted">Related policy documents will appear here once the Policy Search Agent results are connected.</p></div>`,
    ai: `
      <div class="bp-card bp-ai-card">
        <span class="bp-ai-tag">AI Recommendation (not final)</span>
        <h3 style="margin:0 0 6px;">${req.aiRecommendation?.verdict || "Pending analysis"}</h3>
        <p class="bp-muted" style="font-size:12px;">Confidence: ${req.aiRecommendation?.confidence ?? "—"}%</p>
        <p style="font-size:13px; line-height:1.6;">${req.aiRecommendation?.reasoning || "No AI analysis available yet."}</p>
      </div>`,
  };

  document.getElementById("bp-tab-panels").innerHTML = Object.entries(panels)
    .map(([key, html], i) => `<div class="bp-panel ${i === 0 ? "active" : ""}" data-panel="${key}">${html}</div>`)
    .join("");

  document.querySelectorAll("#bp-detail-tabs .bp-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#bp-detail-tabs .bp-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      document.querySelectorAll(".bp-panel").forEach((p) => p.classList.toggle("active", p.dataset.panel === tab.dataset.tab));
    });
  });
});