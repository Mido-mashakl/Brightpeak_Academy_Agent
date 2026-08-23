// =========================================================
// My Cases & Appeals — list page.
// GET /academic-integrity/cases already scopes to the logged-in
// student server-side (academic_integrity_router.list_cases: "a student
// can only ever see their own cases") — no client-side filtering needed.
// =========================================================

const root = document.getElementById("cases-root");

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

document.getElementById("logout-link")?.addEventListener("click", (e) => {
  e.preventDefault();
  window.BrightPeakAuth.logout();
});

const STATUS_STYLE = {
  reported: { label: "Reported", cls: "bg-primary/10 border-primary/30 text-primary" },
  under_review: { label: "Under Review", cls: "bg-primary/10 border-primary/30 text-primary" },
  awaiting_appeal: { label: "Awaiting Your Appeal", cls: "bg-amber-400/10 border-amber-400/30 text-amber-300" },
  appeal_under_review: { label: "Appeal Under Review", cls: "bg-primary/10 border-primary/30 text-primary" },
  closed: { label: "Closed", cls: "bg-emerald-400/10 border-emerald-400/30 text-emerald-300" },
};

const SEVERITY_STYLE = {
  minor: "text-emerald-300",
  major: "text-amber-300",
  severe: "text-error",
  pending: "text-on-surface-variant",
};

function renderCases(cases) {
  if (!cases.length) {
    root.innerHTML = `
      <div class="bg-surface-container/60 backdrop-blur-xl border border-white/10 rounded-xl p-10 text-center">
        <span class="material-symbols-outlined text-[36px] text-emerald-400 mb-3">check_circle</span>
        <h2 class="font-headline-md text-[18px] text-on-surface mb-1">You're all clear</h2>
        <p class="text-body-sm text-on-surface-variant">You don't have any academic integrity cases on record.</p>
      </div>`;
    return;
  }

  root.innerHTML = cases
    .map((c) => {
      const status = STATUS_STYLE[c.status] || { label: c.status, cls: "bg-surface-container-high border-white/10 text-on-surface-variant" };
      const severityCls = SEVERITY_STYLE[c.severity] || "text-on-surface-variant";
      return `
        <a href="case-details.html?id=${c.id}" class="block bg-surface-container/60 backdrop-blur-xl border border-white/10 hover:border-primary/40 rounded-xl p-6 transition-all">
          <div class="flex items-start justify-between gap-4">
            <div>
              <p class="text-[11px] font-label-caps text-on-surface-variant/60 mb-1">Case #${c.id} · ${escapeHtml(c.course)}</p>
              <h3 class="text-body-md font-semibold text-on-surface">${escapeHtml(c.student)}</h3>
              <p class="text-[11px] text-on-surface-variant/60 mt-1">Reported ${escapeHtml(c.reportedLabel)} · Severity: <span class="${severityCls} capitalize">${escapeHtml(c.severity)}</span></p>
            </div>
            <span class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full ${status.cls} border text-[11px] font-medium whitespace-nowrap">${status.label}</span>
          </div>
        </a>`;
    })
    .join("");
}

async function init() {
  applyUser();
  try {
    const cases = await SPApi.listMyCases();
    renderCases(Array.isArray(cases) ? cases : []);
  } catch (err) {
    root.innerHTML = `<div class="flex items-center gap-3 text-error"><span class="material-symbols-outlined">error</span>Couldn't load your cases. (${escapeHtml(err.message)})</div>`;
  }
}

init();