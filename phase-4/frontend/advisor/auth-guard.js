// =========================================================
// Brightpeak Academy — Advisor Portal
// Auth guard: runs before the page renders its content.
// Make sure this script is loaded BEFORE script.js in every HTML file.
// =========================================================

(function () {
  const raw = localStorage.getItem("user");
  let user = null;

  try {
    user = raw ? JSON.parse(raw) : null;
  } catch (e) {
    user = null;
  }

  // No logged-in user, or wrong role -> back to login
  if (!user || user.role !== "advisor") {
    window.location.href =
    "http://localhost:3000/frontend/login/login.html"; // غيّر المسار ده لو صفحة اللوجين عندك في مكان مختلف
    return;
  }

  // Make the user available to script.js and to the page itself
  window.currentUser = user;
})();