// =========================================================
// Brightpeak Academy — MCP Tools module (privileged, shared)
// Lives under shared/ because it is a capability, not a role
// page — Instructor, Advisor, or Department Head may all reach
// it if shared/permissions.js grants them "tools".
//   GET    /api/tools
//   GET    /api/tools/{agent_id}
//   POST   /api/tools/{agent_id}
//   DELETE /api/tools/{agent_id}/{tool_id}
// =========================================================

window.BrightPeakToolsService = (function () {
  function listTools() {
    return window.BrightPeakAPI.get("/api/tools");
  }

  function listToolsForAgent(agentId) {
    return window.BrightPeakAPI.get(`/api/tools/${agentId}`);
  }

  function attachTool(agentId, toolConfig) {
    return window.BrightPeakAPI.post(`/api/tools/${agentId}`, toolConfig);
  }

  // DELETE isn't wrapped by shared/api.js yet — add it there if this
  // module moves past the placeholder stage.

  return { listTools, listToolsForAgent, attachTool };
})();

document.addEventListener("DOMContentLoaded", () => {
  const user = window.BrightPeakAuth.getUser();
  if (!user || !window.BrightPeakPermissions.can(user.role, "tools")) {
    window.location.href = window.BrightPeakAuth.LOGIN_URL;
  }
});
