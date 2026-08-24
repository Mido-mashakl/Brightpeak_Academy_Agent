// =========================================================
// My Courses — student page logic.
// Lists the student's real enrolled courses via GET /teaching/courses
// (the same endpoint the AI Assistant's material flow already uses).
// =========================================================

const root = document.getElementById("courses-root");

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

function applyUser() {
  const user = window.currentUser;
  if (!user) return;
  const nameEl = document.getElementById("student-name");
  const avatarEl = document.getElementById("student-avatar");
  if (nameEl) nameEl.textContent = user.name || user.email || "Student";
  if (avatarEl && user.avatarUrl) avatarEl.src = user.avatarUrl;
}
applyUser();

document.getElementById("logout-link")?.addEventListener("click", (e) => {
  e.preventDefault();
  window.BrightPeakAuth.logout();
});

const COURSE_COLORS = [
  "from-primary to-secondary",
  "from-secondary to-primary-container",
  "from-emerald-400 to-primary",
  "from-amber-400 to-secondary",
];

function renderCourses(courses) {
  if (!courses.length) {
    root.innerHTML = `
      <div class="bg-surface-container/60 backdrop-blur-xl border border-white/10 rounded-xl p-8 col-span-2 text-center">
        <p class="text-body-sm text-on-surface-variant">You're not enrolled in any courses yet.</p>
      </div>
    `;
    return;
  }
  root.innerHTML = courses.map((c, i) => `
    <div class="bg-surface-container/60 backdrop-blur-xl border border-white/10 rounded-xl p-6 flex flex-col gap-4">
      <div class="h-10 w-10 rounded-xl bg-gradient-to-br ${COURSE_COLORS[i % COURSE_COLORS.length]} flex items-center justify-center shadow-[0_0_16px_rgba(128,131,255,0.25)]">
        <span class="material-symbols-outlined text-on-primary text-[20px]">school</span>
      </div>
      <div>
        <h3 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface">${escapeHtml(c.title)}</h3>
        <p class="text-body-sm text-on-surface-variant mt-1">Course ID #${escapeHtml(c.course_id)}</p>
      </div>
      <a href="../ai-assistant/assistant.html?prompt=I%20have%20a%20question%20about%20a%20course%20material."
         class="mt-auto inline-flex items-center gap-1.5 text-body-sm font-medium text-primary hover:text-secondary transition-colors">
        Ask Nova about this course
        <span class="material-symbols-outlined text-[16px]">arrow_forward</span>
      </a>
    </div>
  `).join("");
}

function renderError(message) {
  root.innerHTML = `
    <div class="bg-surface-container/60 backdrop-blur-xl border border-white/10 rounded-xl p-8 col-span-2">
      <div class="flex items-center gap-3 text-error">
        <span class="material-symbols-outlined">error</span>
        <p class="text-body-sm">Couldn't load your courses. (${escapeHtml(message)})</p>
      </div>
      <button id="courses-retry-btn" class="mt-4 px-5 py-2.5 rounded-xl bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface">Try again</button>
    </div>
  `;
  document.getElementById("courses-retry-btn")?.addEventListener("click", loadCourses);
}

async function loadCourses() {
  root.innerHTML = `
    <div class="bg-surface-container/60 backdrop-blur-xl border border-white/10 rounded-xl p-6 col-span-2">
      <div class="flex items-center gap-3 text-on-surface-variant">
        <span class="material-symbols-outlined animate-spin">progress_activity</span>Loading your courses…
      </div>
    </div>
  `;
  try {
    const courses = await SPApi.getMyCourses();
    renderCourses(courses || []);
  } catch (err) {
    renderError(err.message);
  }
}

loadCourses();
