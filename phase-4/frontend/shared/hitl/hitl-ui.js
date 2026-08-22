// =========================================================
// Brightpeak Academy — shared HITL UI helpers
// Small render helpers built on top of hitl-service.js so every
// role's HITL queue page shares one card layout and one toast
// on resolve, instead of three copy-pasted implementations.
// Requires: shared/hitl/hitl-service.js, shared/components/components.js
// =========================================================

window.BrightPeakHitlUI = (function () {
  function renderTaskCard(task) {
    const el = document.createElement("div");
    el.className = "hitl-card";
    el.dataset.taskId = task.id;
    el.innerHTML = `
      <div class="hitl-card-header">
        <span class="hitl-card-title">${task.title || "Untitled task"}</span>
        <span class="hitl-card-status hitl-card-status--${task.status || "pending"}">${task.status || "pending"}</span>
      </div>
      <p class="hitl-card-summary">${task.summary || ""}</p>
      <div class="hitl-card-actions">
        <button class="btn btn-primary btn-sm" data-action="approve">Approve</button>
        <button class="btn btn-ghost btn-sm" data-action="reject">Reject</button>
      </div>
    `;

    el.querySelectorAll("[data-action]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await window.BrightPeakHitl.resolveTask(task.id, { action: btn.dataset.action });
          window.BrightPeakComponents.showToast(`Task ${btn.dataset.action}d`);
          el.remove();
        } catch (err) {
          window.BrightPeakComponents.showToast(err.message || "Failed to resolve task", "error");
        }
      });
    });

    return el;
  }

  async function renderQueueInto(container, query = {}) {
    container.innerHTML = "";
    const tasks = await window.BrightPeakHitl.listTasks(query);
    (tasks || []).forEach((task) => container.appendChild(renderTaskCard(task)));
  }

  return { renderTaskCard, renderQueueInto };
})();
