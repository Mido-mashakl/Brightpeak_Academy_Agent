// Dashboard page logic.
// BASE_URL: point this at your phase-4 backend origin once the routers are ready.
const BASE_URL = "http://localhost:3000";

const els = {
  name: document.getElementById("student-name"),
  firstName: document.getElementById("hero-first-name"),
  track: document.getElementById("student-track"),
  avatar: document.getElementById("student-avatar"),
  enrolled: document.getElementById("stat-enrolled"),
  completed: document.getElementById("stat-completed"),
  avg: document.getElementById("stat-avg"),
  hours: document.getElementById("stat-hours"),
  deadlines: document.getElementById("deadlines-list"),
};

// The auth-guard script (loaded before this file) already redirected
// anyone without a valid session and set window.currentUser. Use that
// as the source of truth for who's logged in — the static "Julian
// Vos" / "Alex" markup is only ever a placeholder until this runs.
function applyLoggedInUser() {
  const user = window.currentUser;
  if (!user) return;

  const name = user.name || user.email || "Student";
  els.name.textContent = name;
  els.firstName.textContent = name.split(" ")[0];
  if (user.track) els.track.textContent = user.track;
  if (user.avatarUrl) els.avatar.src = user.avatarUrl;
}
applyLoggedInUser();

async function loadDashboard() {
  const user = window.currentUser || window.BrightPeakAuth.getUser();
  if (!user) return;
  try {
    const res = await fetch(`${BASE_URL}/api/dashboard`, {
      headers: {
        "X-User-Id":   String(user.id),
        "X-User-Role": String(user.role || "student"),
      },
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.message || `dashboard request failed (${res.status})`);
    }
    const data = await res.json();

    // Dashboard stats/deadlines come from the backend; the name/track/
    // avatar above already came from the logged-in session, but let
    // the backend override them too if it returns richer profile data.
    if (data.student) {
      if (data.student.name) {
        els.name.textContent = data.student.name;
        els.firstName.textContent = data.student.name.split(" ")[0];
      }
      if (data.student.track) els.track.textContent = data.student.track;
      if (data.student.avatarUrl) els.avatar.src = data.student.avatarUrl;
    }

    if (data.stats) {
      els.enrolled.textContent = data.stats.enrolled ?? "—";
      els.completed.textContent = data.stats.completed ?? "—";
      els.avg.textContent = (data.stats.avgScore ?? "—") + "%";
      els.hours.textContent = data.stats.studyHours ?? "—";
    }

    if (Array.isArray(data.deadlines)) {
      renderDeadlines(data.deadlines);
    }
  } catch (err) {
    // Real backend error (e.g. not logged in, or DB unavailable) — show it,
    // never silently fall back to the placeholder markup as if it were data.
    console.error("Dashboard load failed:", err.message);
    els.enrolled.textContent = "—";
    els.completed.textContent = "—";
    els.avg.textContent = "—";
    els.hours.textContent = "—";
  }
}

function renderDeadlines(deadlines) {
  els.deadlines.innerHTML = deadlines
    .map(
      (d) => `
      <div class="flex items-center gap-3 bg-surface-container-high/60 rounded-lg p-3">
        <div class="w-9 h-9 rounded-lg bg-surface-container-highest flex items-center justify-center shrink-0 font-label-caps text-[13px] text-on-surface">${d.day}</div>
        <div class="min-w-0">
          <p class="text-body-sm text-on-surface truncate">${d.title}</p>
          <p class="text-[11px] text-on-surface-variant/60 flex items-center gap-1">
            <span class="material-symbols-outlined text-[12px]">schedule</span>${d.when}
          </p>
        </div>
      </div>`
    )
    .join("");
}

function goToNova(prompt) {
  const url = new URL("../ai-assistant/assistant.html", window.location.href);
  if (prompt) url.searchParams.set("prompt", prompt);
  window.location.href = url.toString();
}

document.getElementById("start-chat-btn").addEventListener("click", () => goToNova());

// Three of the five quick actions now have real standalone pages backed
// by the actual graphs (tracks_router.py, assessment_router.py,
// academic_integrity_router.py) — send those straight there instead of
// through Nova chat. "Ask about material" and "Certificate & Scholarship"
// have no dedicated graph/page of their own, so they still go to Nova.
const QUICK_ACTION_PAGES = {
  "recommend-track": "../tracks/tracks.html",
  "assessment": "../assessment/assessment.html",
  "appeals": "../integrity/integrity.html",
};
const QUICK_ACTION_PROMPTS = {
  "ask-material": "I have a question about a course material.",
  "certificate": "Tell me about certificates and scholarships.",
};

document.querySelectorAll(".quick-action").forEach((btn) => {
  btn.addEventListener("click", () => {
    const action = btn.dataset.quickAction;
    if (QUICK_ACTION_PAGES[action]) {
      window.location.href = QUICK_ACTION_PAGES[action];
      return;
    }
    goToNova(QUICK_ACTION_PROMPTS[action]);
  });
});

document.getElementById("logout-link").addEventListener("click", async (e) => {
  e.preventDefault();
  try {
    await fetch(`${BASE_URL}/api/auth/logout`, { method: "POST" });
  } catch (err) {
    console.info("Logout: backend not reachable —", err.message);
  } finally {
    // Clears localStorage("user") too and redirects to the real
    // login path (../login.html here was pointing at a non-existent file).
    window.BrightPeakAuth.logout();
  }
});

loadDashboard();