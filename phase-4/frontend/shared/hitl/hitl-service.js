// =========================================================
// Brightpeak Academy — shared HITL service
// Thin wrapper around the Phase-4 HITL endpoints so Instructor,
// Advisor, and Department Head screens don't each reimplement it.
// Requires shared/api.js (BrightPeakAPI) to be loaded first.
//   GET  /api/hitl
//   GET  /api/hitl/{task_id}
//   POST /api/hitl/{task_id}/resolve
// =========================================================

window.BrightPeakHitl = (function () {
  function listTasks(query = {}) {
    const qs = new URLSearchParams(query).toString();
    return window.BrightPeakAPI.get(qs ? `/api/hitl?${qs}` : "/api/hitl");
  }

  function getTask(taskId) {
    return window.BrightPeakAPI.get(`/api/hitl/${taskId}`);
  }

  // decision: { action: "approve" | "reject" | "edit", payload?: any, notes?: string }
  function resolveTask(taskId, decision) {
    return window.BrightPeakAPI.post(`/api/hitl/${taskId}/resolve`, decision);
  }

  return { listTasks, getTask, resolveTask };
})();
