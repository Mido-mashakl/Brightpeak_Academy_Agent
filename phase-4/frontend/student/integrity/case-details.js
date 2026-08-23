// =========================================================
// Case Details — student page logic.
// GET /academic-integrity/cases/{id} already 403s if the case isn't
// this student's own (academic_integrity_router.get_case), so no
// extra client-side check is needed here.
//
// The endpoint returns a superset shape shared with the instructor's
// hitl-review.js (see the router's own docstring) — this page only
// reads the case-details.js field names: id, student, course,
// reportedBy, reportedOnLabel, status, incidentType, description,
// evidence[], aiAssessment{severity, policyMatchPct, reasoning},
// workflow{steps, currentStep}.
// =========================================================

const caseId = new URLSearchParams(window.location.search).get("id");
const root = document.getElementById("case-root");

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

function renderTimeline(workflow) {
  const steps = workflow?.steps || [];
  const currentIdx = steps.findIndex((s) => s.key === workflow?.currentStep);
  return `
    <div class="flex items-center gap-1 overflow-x-auto no-scrollbar py-1">
      ${steps
        .map((s, i) => {
          const done = currentIdx >= 0 && i < currentIdx;
          const active = i === currentIdx;
          const dotCls = active
            ? "bg-primary border-primary shadow-[0_0_10px_rgba(128,131,255,0.6)]"
            : done
            ? "bg-emerald-400 border-emerald-400"
            : "bg-transparent border-white/20";
          const textCls = active ? "text-on-surface font-medium" : done ? "text-on-surface-variant" : "text-on-surface-variant/50";
          return `
          <div class="flex items-center gap-1 shrink-0">
            <div class="flex flex-col items-center gap-1.5">
              <span class="w-3 h-3 rounded-full border-2 ${dotCls}"></span>
              <span class="text-[10px] font-label-caps whitespace-nowrap ${textCls}">${escapeHtml(s.label)}</span>
            </div>
            ${i < steps.length - 1 ? `<span class="w-8 h-[2px] ${done ? "bg-emerald-400" : "bg-white/10"} -mt-4"></span>` : ""}
          </div>`;
        })
        .join("")}
    </div>`;
}

function renderEvidence(evidence) {
  if (!evidence || !evidence.length) {
    return `<p class="text-body-sm text-on-surface-variant/60">No evidence recorded.</p>`;
  }
  return `
    <div class="grid sm:grid-cols-2 gap-3">
      ${evidence
        .map(
          (e) => `
        <div class="flex items-center gap-3 bg-surface-container-high/50 border border-white/10 rounded-xl p-4">
          <span class="material-symbols-outlined text-[20px] text-on-surface-variant shrink-0">description</span>
          <div class="min-w-0">
            <p class="text-body-sm text-on-surface truncate">${escapeHtml(e.name)}</p>
            <p class="text-[11px] text-on-surface-variant/60 truncate">${escapeHtml(e.size)}</p>
          </div>
        </div>`
        )
        .join("")}
    </div>`;
}

function renderAppealForm() {
  return `
    <div class="bg-amber-400/5 border border-amber-400/20 rounded-xl p-6">
      <h3 class="font-headline-md text-[16px] text-on-surface mb-2 flex items-center gap-2">
        <span class="material-symbols-outlined text-[18px] text-amber-300">edit_note</span>Submit Your Appeal
      </h3>
      <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">
        Explain why you believe this case should be reconsidered. Be specific — your argument goes straight to the review committee.
      </p>
      <textarea id="appeal-text" rows="5" placeholder="Type your appeal here…"
        class="w-full px-4 py-3 rounded-xl bg-surface-container-low/70 border border-white/10 text-body-sm text-on-surface placeholder:text-on-surface-variant/40 outline-none focus:border-primary/50 resize-none"></textarea>
      <div class="flex items-center gap-3 mt-4">
        <button id="submit-appeal-btn" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-secondary text-on-primary text-body-sm font-semibold shadow-[0_8px_24px_rgba(128,131,255,0.35)] hover:shadow-[0_0_28px_rgba(255,176,205,0.45)] transition-all">
          Submit Appeal
        </button>
        <p id="appeal-error" class="text-body-sm text-error hidden"></p>
      </div>
    </div>`;
}

function attachAppealHandler(c) {
  const btn = document.getElementById("submit-appeal-btn");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    const text = document.getElementById("appeal-text").value.trim();
    const errEl = document.getElementById("appeal-error");
    if (!text) {
      errEl.textContent = "Please write your appeal before submitting.";
      errEl.classList.remove("hidden");
      return;
    }
    btn.disabled = true;
    btn.textContent = "Submitting…";
    errEl.classList.add("hidden");
    try {
      await SPApi.submitAppeal(c.id, text);
      await loadCase(); // re-render with the updated status
    } catch (err) {
      btn.disabled = false;
      btn.textContent = "Submit Appeal";
      errEl.textContent = `Couldn't submit your appeal. (${err.message})`;
      errEl.classList.remove("hidden");
    }
  });
}

function render(c) {
  const status = STATUS_STYLE[c.status] || { label: c.status, cls: "bg-surface-container-high border-white/10 text-on-surface-variant" };
  const ai = c.aiAssessment;
  const severityCls = ai ? SEVERITY_STYLE[ai.severity] || "text-on-surface-variant" : "";

  root.innerHTML = `
    <div>
      <div class="flex items-start justify-between gap-4 mb-1">
        <h1 class="font-headline-md text-[26px] leading-[34px] font-semibold text-on-surface">Case #${c.id} · ${escapeHtml(c.course)}</h1>
        <span class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full ${status.cls} border text-[11px] font-medium whitespace-nowrap shrink-0">${status.label}</span>
      </div>
      <p class="text-body-sm text-on-surface-variant">Reported by ${escapeHtml(c.reportedBy)} · ${escapeHtml(c.reportedOnLabel)}</p>
    </div>

    <div class="bg-surface-container/60 backdrop-blur-xl border border-white/10 rounded-xl p-6">
      ${renderTimeline(c.workflow)}
    </div>

    <div class="bg-surface-container/60 backdrop-blur-xl border border-white/10 rounded-xl p-6">
      <h3 class="font-headline-md text-[16px] text-on-surface mb-3">What was reported</h3>
      ${c.incidentType && c.incidentType !== "—" ? `<p class="text-[11px] font-label-caps text-on-surface-variant/60 mb-2">${escapeHtml(c.incidentType)}</p>` : ""}
      <p class="text-body-sm text-on-surface-variant leading-relaxed">${escapeHtml(c.description)}</p>
    </div>

    ${
      ai
        ? `<div class="bg-surface-container/60 backdrop-blur-xl border border-white/10 rounded-xl p-6">
             <h3 class="font-headline-md text-[16px] text-on-surface mb-3 flex items-center gap-2">
               <span class="material-symbols-outlined text-[18px] text-secondary">smart_toy</span>Nova's Assessment
             </h3>
             <div class="flex items-center gap-6 mb-3">
               <div>
                 <p class="text-[11px] font-label-caps text-on-surface-variant/60 mb-1">Severity</p>
                 <p class="text-body-md font-semibold capitalize ${severityCls}">${escapeHtml(ai.severity)}</p>
               </div>
               <div>
                 <p class="text-[11px] font-label-caps text-on-surface-variant/60 mb-1">Policy Match</p>
                 <p class="text-body-md font-semibold text-on-surface">${ai.policyMatchPct}%</p>
               </div>
             </div>
             <p class="text-body-sm text-on-surface-variant leading-relaxed">${escapeHtml(ai.reasoning)}</p>
           </div>`
        : ""
    }

    <div class="bg-surface-container/60 backdrop-blur-xl border border-white/10 rounded-xl p-6">
      <h3 class="font-headline-md text-[16px] text-on-surface mb-4">Evidence</h3>
      ${renderEvidence(c.evidence)}
    </div>

    ${c.status === "awaiting_appeal" ? renderAppealForm() : ""}

    ${
      c.pendingWith
        ? `<p class="text-body-sm text-on-surface-variant/60 text-center">Currently pending with: ${escapeHtml(c.pendingWith)}</p>`
        : ""
    }
  `;

  attachAppealHandler(c);
}

async function loadCase() {
  try {
    const c = await SPApi.getCase(caseId);
    render(c);
  } catch (err) {
    root.innerHTML = `<div class="flex items-center gap-3 text-error"><span class="material-symbols-outlined">error</span>Couldn't load this case. (${escapeHtml(err.message)})</div>`;
  }
}

applyUser();
if (!caseId) {
  root.innerHTML = `<div class="flex items-center gap-3 text-error"><span class="material-symbols-outlined">error</span>No case selected.</div>`;
} else {
  loadCase();
}
