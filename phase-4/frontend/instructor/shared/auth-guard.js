// =========================================================
// Brightpeak Academy — Instructor Portal auth guard
// Thin wrapper: the real logic lives in frontend/shared/auth.js.
// Make sure that file is loaded on the page BEFORE this one.
// =========================================================
window.BrightPeakAuth.requireRole("instructor");
