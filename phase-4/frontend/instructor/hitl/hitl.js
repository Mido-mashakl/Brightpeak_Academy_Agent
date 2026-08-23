// =========================================================
// Human-in-the-Loop — list
//
// Categories are rendered only when the backend actually returns
// cases for them. Nothing here invents a HITL state or action.
// =========================================================

const BP_HITL_CATEGORIES = [
  { key: "needsAttention", label: "Needs Your Attention" },
  { key: "awaitingAppeal", label: "Awaiting Appeal" },
  { key: "committeeDecisions", label: "Committee Decisions" },
];

document.addEventListener("DOMContentLoaded", async () => {
  BPLayout.mount({ active: "hitl", userName: "Fatma", userRole: "Instructor" });

  const root = document.getElementById("bp-hitl-root");
  root.innerHTML = BPState.loading("Loading HITL cases...");

  try {
    const data = await getHITLCases();
    render(data);
  } catch (err) {
    root.innerHTML = BPState.error("Unable to load HITL cases. Please try again.");
  }

  function render(data) {
    const active = BP_HITL_CATEGORIES.filter((c) => (data[c.key] || []).length > 0);

    if (active.length === 0) {
      root.innerHTML = `<div class="bp-card bp-card-pad">${BPState.empty("No HITL cases require your attention right now.")}</div>`;
      return;
    }

    let currentTab = active[0].key;

    function paint() {
      root.innerHTML = `
        <section class="bp-card bp-card-pad">
          <div class="bp-hitl-tabs">
            ${active
              .map(
                (c) => `
              <div class="bp-hitl-tab ${c.key === currentTab ? "active" : ""}" data-key="${c.key}">
                ${c.label}<span class="count">${data[c.key].length}</span>
              </div>
            `
              )
              .join("")}
          </div>
          <div id="bp-hitl-list"></div>
        </section>
      `;

      root.querySelectorAll(".bp-hitl-tab").forEach((tab) => {
        tab.addEventListener("click", () => {
          currentTab = tab.dataset.key;
          paint();
        });
      });

      renderList(data[currentTab]);
    }

    function renderList(items) {
      const listEl = document.getElementById("bp-hitl-list");
      if (!items || items.length === 0) {
        listEl.innerHTML = BPState.empty("No cases in this category.");
        return;
      }
      listEl.innerHTML = items
        .map(
          (c) => `
        <div class="bp-card bp-hitl-card" style="border-color:var(--bp-border)">
          <div class="bp-hitl-card-icon">${BPIcons.shield}</div>
          <div class="bp-hitl-card-main">
            <div class="bp-hitl-card-title">Academic Integrity Case #${c.id}</div>
            <div class="bp-hitl-card-meta">
              <div class="item"><div class="k">Student</div><div class="v">${c.student}</div></div>
              <div class="item"><div class="k">Course</div><div class="v">${c.course}</div></div>
              <div class="item"><div class="k">Severity</div><div class="v">${BPFormat.severityBadge(c.severity)}</div></div>
              <div class="item"><div class="k">Workflow Step</div><div class="v">${c.workflowStep}</div></div>
              <div class="item"><div class="k">Evidence</div><div class="v">${c.evidenceCount} items</div></div>
              <div class="item"><div class="k">Policy Match</div><div class="v">${c.policyMatchPct}%</div></div>
              ${
                c.pendingWith
                  ? `<div class="item"><div class="k">Pending With</div><div class="v">${c.pendingWith}</div></div>`
                  : ""
              }
            </div>
          </div>
          <button class="bp-btn bp-btn-primary" data-id="${c.id}">Review Case</button>
        </div>
      `
        )
        .join("");

      listEl.querySelectorAll("button[data-id]").forEach((btn) => {
        btn.addEventListener("click", () => {
          window.location.href = `hitl-review.html?id=${btn.dataset.id}`;
        });
      });
    }

    paint();
  }
});
