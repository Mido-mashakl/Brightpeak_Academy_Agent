// =========================================================
// Brightpeak Academy — Advisor Portal
// Shared interactions
// =========================================================

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

document.addEventListener("DOMContentLoaded", () => {
  /* ---------------- Fill in the logged-in advisor's name/avatar ---------------- */
  const user = window.currentUser;
  if (user) {
    document.querySelectorAll(".user-chip span").forEach((el) => {
      el.textContent = user.name || user.email || "Advisor";
    });
    document.querySelectorAll(".greeting .name").forEach((el) => {
      el.textContent = (user.name || "Advisor").split(" ")[0];
    });
    if (user.avatarUrl) {
      document.querySelectorAll(".user-chip .avatar img").forEach((img) => {
        img.src = user.avatarUrl;
      });
    }
  }

  /* ---------------- Logout ---------------- */
  document.querySelectorAll(".logout").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      localStorage.removeItem("user");
      window.location.href = "/login.html"; // غيّر المسار لو صفحة اللوجين في مكان مختلف
    });
  });

  /* ---------------- Fallback placeholders until real robot images are added ---------------- */
  const placeholderSvg = (emoji, bg) =>
    "data:image/svg+xml;utf8," +
    encodeURIComponent(
      `<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'>
        <rect width='100%' height='100%' rx='24' fill='${bg}'/>
        <text x='50%' y='56%' font-size='96' text-anchor='middle' dominant-baseline='middle'>${emoji}</text>
      </svg>`
    );

  document.querySelectorAll("img[src*='assets/']").forEach((img) => {
    img.addEventListener(
      "error",
      () => {
        if (img.dataset.fallbackApplied) return;
        img.dataset.fallbackApplied = "true";
        if (img.src.includes("avatar-sarah")) {
          img.src = placeholderSvg("🙂", "#2a2245");
        } else {
          img.src = placeholderSvg("🤖", "#1b1533");
        }
      },
      { once: true }
    );
  });

  /* ---------------- Requests page: search + filter ---------------- */
  const searchInput = document.getElementById("searchInput");
  const filterPills = document.querySelectorAll(".filter-pill");
  const requestRows = document.querySelectorAll("[data-type]");
  const emptyState = document.getElementById("emptyState");

  function applyFilters() {
    if (!requestRows.length) return;
    const activePill = document.querySelector(".filter-pill.active");
    const activeType = activePill ? activePill.dataset.filter : "all";
    const query = (searchInput?.value || "").trim().toLowerCase();
    let visibleCount = 0;

    requestRows.forEach((row) => {
      const matchesType = activeType === "all" || row.dataset.type === activeType;
      const matchesQuery = row.dataset.name.toLowerCase().includes(query);
      const visible = matchesType && matchesQuery;
      row.style.display = visible ? "" : "none";
      if (visible) visibleCount++;
    });

    if (emptyState) emptyState.classList.toggle("show", visibleCount === 0);
  }

  filterPills.forEach((pill) => {
    pill.addEventListener("click", () => {
      filterPills.forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      applyFilters();
    });
  });

  if (searchInput) searchInput.addEventListener("input", applyFilters);
  applyFilters();

  /* ---------------- Request detail page: decision actions ---------------- */
  const approveBtn = document.getElementById("approveBtn");
  const rejectBtn = document.getElementById("rejectBtn");
  const infoBtn = document.getElementById("infoBtn");
  const submitBtn = document.getElementById("submitDecisionBtn");
  const statusVal = document.getElementById("statusVal");

  let selectedDecision = null;

  function selectDecision(btn, decision, label, color) {
    [approveBtn, rejectBtn, infoBtn].forEach((b) => b && b.classList.remove("btn-selected"));
    if (btn) btn.classList.add("btn-selected");
    selectedDecision = decision;
    if (statusVal) {
      statusVal.textContent = label;
      statusVal.style.color = color;
    }
  }

  if (approveBtn) {
    approveBtn.addEventListener("click", () =>
      selectDecision(approveBtn, "approved", "Approved", "var(--success)")
    );
  }
  if (rejectBtn) {
    rejectBtn.addEventListener("click", () =>
      selectDecision(rejectBtn, "rejected", "Rejected", "var(--danger)")
    );
  }
  if (infoBtn) {
    infoBtn.addEventListener("click", () =>
      selectDecision(infoBtn, "more_info", "Awaiting Info", "var(--warning)")
    );
  }

  if (submitBtn) {
    submitBtn.addEventListener("click", () => {
      if (!selectedDecision) {
        showToast("Please choose Approve, Reject, or Request More Info first.", "priority_high");
        return;
      }
      showToast("Decision submitted successfully.", "check_circle");
    });
  }
});