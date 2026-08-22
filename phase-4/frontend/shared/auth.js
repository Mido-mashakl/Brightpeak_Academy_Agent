// =========================================================
// Brightpeak Academy — shared auth core
// The ONE place that knows how the logged-in user is stored
// and how to redirect back to login. Each role's
// <role>/shared/auth-guard.js is a 2-line wrapper that calls
// BrightPeakAuth.requireRole("<role>") — load this file first.
// =========================================================

window.BrightPeakAuth = (function () {
  const LOGIN_URL = "http://localhost:3000/frontend/login/login.html";

  function getUser() {
    try {
      const raw = localStorage.getItem("user");
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  }

  // Redirects to login if there's no user or the role doesn't match.
  // On success, stashes the user on window.currentUser and returns it.
  function requireRole(expectedRole) {
    const user = getUser();

    if (!user || user.role !== expectedRole) {
      window.location.href = LOGIN_URL;
      return null;
    }

    window.currentUser = user;
    return user;
  }

  function logout() {
    localStorage.removeItem("user");
    window.location.href = LOGIN_URL;
  }

  return { getUser, requireRole, logout, LOGIN_URL };
})();
