// =========================================================
// Brightpeak Academy — shared UI components
// Small reusable DOM helpers so every role doesn't reinvent
// its own toast / user-chip filling logic.
// =========================================================

window.BrightPeakComponents = (function () {
  function showToast(message, iconName = "check_circle") {
    let toast = document.querySelector(".toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.className = "toast";
      document.body.appendChild(toast);
    }
    toast.innerHTML = `<span class="material-symbols-outlined">${iconName}</span><span>${message}</span>`;
    toast.classList.add("show");
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove("show"), 2600);
  }

  // Fills any ".user-chip span" / ".greeting .name" elements on the page
  // with the logged-in user's name — used right after BrightPeakAuth.requireRole().
  function fillUserChip(user) {
    if (!user) return;
    document.querySelectorAll(".user-chip span").forEach((el) => {
      el.textContent = user.name || user.email || "User";
    });
    document.querySelectorAll(".greeting .name").forEach((el) => {
      el.textContent = (user.name || "User").split(" ")[0];
    });
    if (user.avatarUrl) {
      document.querySelectorAll(".user-chip .avatar img").forEach((img) => {
        img.src = user.avatarUrl;
      });
    }
  }

  return { showToast, fillUserChip };
})();
