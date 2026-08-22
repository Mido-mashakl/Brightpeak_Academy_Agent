// =========================================================
// Brightpeak Academy — shared role permissions
// Single source of truth for "which nav items / features can
// this role see". Screens use BrightPeakPermissions.can(...)
// instead of hardcoding role checks in every page.
//
// IMPORTANT: this is a UX convenience only. The real gate is
// always the backend — every /api/tools and /api/rag call must
// re-check the caller's permission server-side, even if a page
// somehow gets opened directly.
// =========================================================

window.BrightPeakPermissions = (function () {
  // Ordinary, per-role screens.
  const PERMISSIONS = {
    student: ["dashboard", "ai-assistant", "agents"],
    instructor: ["dashboard", "agents", "requests", "hitl"],
    advisor: ["dashboard", "agents", "requests", "hitl"],
    dept_head: ["dashboard", "hiring", "agents", "hitl", "tickets"],
  };

  // Privileged capabilities. These are NOT screens under a role
  // folder — they live under shared/tools and shared/rag and are
  // opt-in per role. Nothing is granted here by default; wire a
  // role in once the rubric/backend confirms who should get it.
  const PRIVILEGED = {
    student: [],
    instructor: [],
    advisor: [],
    dept_head: [],
  };

  function can(role, feature) {
    return Boolean(
      (PERMISSIONS[role] && PERMISSIONS[role].includes(feature)) ||
      (PRIVILEGED[role] && PRIVILEGED[role].includes(feature))
    );
  }

  function featuresFor(role) {
    return PERMISSIONS[role] || [];
  }

  function privilegedFeaturesFor(role) {
    return PRIVILEGED[role] || [];
  }

  return { can, featuresFor, privilegedFeaturesFor, PERMISSIONS, PRIVILEGED };
})();
