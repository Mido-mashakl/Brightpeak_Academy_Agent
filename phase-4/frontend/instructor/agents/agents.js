// =========================================================
// AI Agents
// =========================================================

document.addEventListener("DOMContentLoaded", async () => {
  BPLayout.mount({ active: "agents", userName: "Fatma", userRole: "Instructor" });

  const root = document.getElementById("bp-agents-root");
  root.innerHTML = BPState.loading("Loading agents...");

  try {
    const agents = await getAgents();
    render(agents);
  } catch (err) {
    root.innerHTML = BPState.error("Unable to load agents. Please try again.");
  }

  function render(agents) {
    if (!agents || agents.length === 0) {
      root.innerHTML = BPState.empty("No agents are available right now.");
      return;
    }
    root.innerHTML = `
      <div class="bp-agent-grid">
        ${agents
          .map(
            (a) => `
          <div class="bp-card bp-agent-card">
            <div class="bp-agent-top">
              <div class="bp-agent-icon">${BPIcons.agents}</div>
              <div>
                <div class="bp-agent-name">${a.name}</div>
                <div class="bp-agent-status ${a.status !== "available" ? "offline" : ""}">
                  <span class="dot"></span>${a.status === "available" ? "Available" : "Unavailable"}
                </div>
              </div>
            </div>
            <div class="bp-agent-desc">${a.description}</div>
            <button class="bp-btn bp-btn-secondary bp-btn-full" data-id="${a.id}" ${a.status !== "available" ? "disabled" : ""}>Open Agent</button>
          </div>
        `
          )
          .join("")}
      </div>
    `;

    root.querySelectorAll("button[data-id]").forEach((btn) => {
      btn.addEventListener("click", () => {
        BPToast.info("Agent workspace will open here once connected.");
      });
    });
  }
});
