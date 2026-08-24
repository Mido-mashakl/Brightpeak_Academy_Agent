// =========================================================
// Track Recommendation — student page logic.
//
// thread_id is the only resume key (TrackRecommendations has no
// thread_id column — see tracks_router.py's module docstring), so we
// keep it in localStorage per-student and also accept it back via
// ?threadId=... when assessment.js redirects here after a diagnostic /
// targeted assessment completes.
//
// State is always re-derived from GET /tracks/thread/{thread_id}
// (snapshot.values + snapshot.next), not from whatever a POST call
// happened to return — that way a page reload shows the same thing as
// right after the action, and we don't need to special-case each
// entry point. `next` tells us exactly which await_*/hitl node the
// graph is paused on:
//   ("await_diagnostic_response",)          -> missing-prereq diagnostic
//   ("await_ticket_resolution",)            -> broken track document, admin fixing
//   ("hitl_node",)                          -> advisor is deciding
//   ("await_targeted_assessment_response",) -> advisor asked for more evidence
//   ()  (empty) + values.final_track set    -> done
// =========================================================

const CONFIDENCE_GAP_THRESHOLD = 5.0; // mirrors state.py — display only

const qThreadId = new URLSearchParams(window.location.search).get("threadId");
const root = document.getElementById("tracks-root");
const historySection = document.getElementById("history-section");
const historyList = document.getElementById("history-list");

function storageKey() {
  const user = window.currentUser;
  return `bp_track_thread_${user ? user.id : "anon"}`;
}
function saveThreadId(id) {
  if (id) localStorage.setItem(storageKey(), id);
}
function clearThreadId() {
  localStorage.removeItem(storageKey());
}
function getStoredThreadId() {
  return localStorage.getItem(storageKey());
}

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

function renderLoadingBlock(text) {
  return `<div class="flex items-center gap-3 text-on-surface-variant"><span class="material-symbols-outlined animate-spin">progress_activity</span>${escapeHtml(text)}</div>`;
}
function renderErrorBlock(text) {
  return `<div class="flex items-center gap-3 text-error"><span class="material-symbols-outlined">error</span>${escapeHtml(text)}</div>`;
}

/* ---------------------------------------------------------------------
   Start screen (no active thread)
--------------------------------------------------------------------- */
function renderStart() {
  root.innerHTML = `
    <h2 class="font-headline-md text-[18px] text-on-surface mb-2">Let's find the right track for you</h2>
    <p class="text-body-sm text-on-surface-variant mb-6 leading-relaxed">
      Nova will review your grades, attendance, and any missing prerequisite data, then match you against the tracks that fit best.
    </p>
    <button id="start-btn" class="px-6 py-3 rounded-xl bg-gradient-to-br from-primary to-secondary text-on-primary text-body-sm font-semibold shadow-[0_8px_24px_rgba(128,131,255,0.35)] hover:shadow-[0_0_28px_rgba(255,176,205,0.45)] transition-all">
      Get My Track Recommendation
    </button>
    <p id="start-error" class="mt-3 text-body-sm text-error hidden"></p>
  `;
  document.getElementById("start-btn").addEventListener("click", startRecommendation);
  loadHistory();
}

async function startRecommendation() {
  root.innerHTML = renderLoadingBlock("Analyzing your academic profile…");
  try {
    const data = await SPApi.recommendTrack();
    const threadId = data.thread_id;
    saveThreadId(threadId);
    await loadThread(threadId);
  } catch (err) {
    root.innerHTML = `
      ${renderErrorBlock(`Couldn't start the recommendation. (${err.message})`)}
      <button id="start-retry-btn" class="mt-4 px-5 py-2.5 rounded-xl bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface">Try again</button>
    `;
    document.getElementById("start-retry-btn").addEventListener("click", renderStart);
  }
}

/* ---------------------------------------------------------------------
   Load + classify the current thread state
--------------------------------------------------------------------- */
async function loadThread(threadId) {
  root.innerHTML = renderLoadingBlock("Checking your recommendation status…");
  try {
    const state = await SPApi.getTrackThreadState(threadId);
    render(threadId, state.values || {}, state.next || []);
  } catch (err) {
    root.innerHTML = `
      ${renderErrorBlock(`Couldn't load this recommendation. (${err.message})`)}
      <button id="load-reset-btn" class="mt-4 px-5 py-2.5 rounded-xl bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface">Start a new one</button>
    `;
    document.getElementById("load-reset-btn").addEventListener("click", () => {
      clearThreadId();
      renderStart();
    });
  }
}

function render(threadId, values, next) {
  const nextNode = next && next.length ? next[0] : null;

  if (!nextNode && values.final_track) {
    renderFinal(threadId, values);
    return;
  }
  if (nextNode === "await_diagnostic_response") {
    renderDiagnostic(threadId, values);
    return;
  }
  if (nextNode === "await_ticket_resolution") {
    renderTicket(threadId, values);
    return;
  }
  if (nextNode === "hitl_node") {
    renderAdvisorReview(threadId, values);
    return;
  }
  if (nextNode === "await_targeted_assessment_response") {
    renderTargetedAssessment(threadId, values);
    return;
  }
  // Nothing recognizable paused, and no final_track yet — likely still
  // mid-run (shouldn't normally be observable, invoke() runs straight
  // through non-pause nodes) or a run that failed before finishing.
  root.innerHTML = `
    ${renderErrorBlock("This recommendation isn't in a state we recognize yet.")}
    <button id="refresh-btn" class="mt-4 px-5 py-2.5 rounded-xl bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface">Refresh</button>
  `;
  document.getElementById("refresh-btn").addEventListener("click", () => loadThread(threadId));
}

/* ---- await_diagnostic_response: missing prerequisite data ---- */
function renderDiagnostic(threadId, values) {
  const missing = values.missing_courses || [];
  const grades = values.grades || {};
  const course = missing.find((c) => !(c in grades)) || missing[0];
  const assessmentId = (values.pending_diagnostic_ids || {})[course];

  root.innerHTML = `
    <div class="flex items-center gap-2 mb-3">
      <span class="material-symbols-outlined text-[22px] text-primary">quiz</span>
      <h2 class="font-headline-md text-[18px] text-on-surface">One quick prerequisite check</h2>
    </div>
    <p class="text-body-sm text-on-surface-variant mb-6 leading-relaxed">
      We don't have a grade on file for <span class="text-on-surface font-medium">${escapeHtml(course || "a prerequisite course")}</span>,
      so Nova needs a short adaptive assessment on it before it can finish matching your track.
    </p>
    ${
      assessmentId
        ? `<button id="diag-start-btn" class="px-6 py-3 rounded-xl bg-gradient-to-br from-primary to-secondary text-on-primary text-body-sm font-semibold shadow-[0_8px_24px_rgba(128,131,255,0.35)] hover:shadow-[0_0_28px_rgba(255,176,205,0.45)] transition-all">
             Start the Assessment
           </button>`
        : renderErrorBlock("Couldn't determine which assessment to start — try refreshing.")
    }
  `;
  document.getElementById("diag-start-btn")?.addEventListener("click", () => {
    window.location.href =
      `../assessment/assessment.html?sessionId=${assessmentId}&returnTo=tracks&threadId=${encodeURIComponent(threadId)}&resumeKind=diagnostic`;
  });
}

/* ---- await_targeted_assessment_response: advisor asked for more evidence ---- */
function renderTargetedAssessment(threadId, values) {
  const subject = (values.advisor_decision || {}).subject || "a specific subject";
  const assessmentId = values.pending_assessment_id;

  root.innerHTML = `
    <div class="flex items-center gap-2 mb-3">
      <span class="material-symbols-outlined text-[22px] text-primary">quiz</span>
      <h2 class="font-headline-md text-[18px] text-on-surface">Your advisor requested more evidence</h2>
    </div>
    <p class="text-body-sm text-on-surface-variant mb-6 leading-relaxed">
      To make a confident call, your advisor asked for a targeted assessment on
      <span class="text-on-surface font-medium">${escapeHtml(subject)}</span>.
    </p>
    ${
      assessmentId
        ? `<button id="targeted-start-btn" class="px-6 py-3 rounded-xl bg-gradient-to-br from-primary to-secondary text-on-primary text-body-sm font-semibold shadow-[0_8px_24px_rgba(128,131,255,0.35)] hover:shadow-[0_0_28px_rgba(255,176,205,0.45)] transition-all">
             Start the Assessment
           </button>`
        : renderErrorBlock("Couldn't determine which assessment to start — try refreshing.")
    }
  `;
  document.getElementById("targeted-start-btn")?.addEventListener("click", () => {
    window.location.href =
      `../assessment/assessment.html?sessionId=${assessmentId}&returnTo=tracks&threadId=${encodeURIComponent(threadId)}&resumeKind=targeted`;
  });
}

/* ---- await_ticket_resolution: broken track document, admin fixing ---- */
function renderTicket(threadId, values) {
  root.innerHTML = `
    <div class="flex items-center gap-2 mb-3">
      <span class="material-symbols-outlined text-[22px] text-amber-400">build</span>
      <h2 class="font-headline-md text-[18px] text-on-surface">Hang tight — a document needs fixing</h2>
    </div>
    <p class="text-body-sm text-on-surface-variant mb-6 leading-relaxed">
      The requirements document for <span class="text-on-surface font-medium">${escapeHtml(values.rag_failed_track || "one of your candidate tracks")}</span>
      failed validation, so an admin has been notified (ticket #${escapeHtml(values.open_ticket_id ?? "—")}). There's nothing you need to do — check back later.
    </p>
    <button id="ticket-refresh-btn" class="px-5 py-2.5 rounded-xl bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface">Check status</button>
  `;
  document.getElementById("ticket-refresh-btn").addEventListener("click", () => loadThread(threadId));
}

/* ---- hitl_node: advisor reviewing ---- */
function renderAdvisorReview(threadId, values) {
  const ranked = values.ranked || [];
  const [topTrack, topScore] = ranked[0] || [null, null];
  const [altTrack, altScore] = ranked[1] || [null, null];
  const gap = values.confidence_gap;

  const concerns = [];
  if (values.policy_ok === false) concerns.push(`'${topTrack}' prerequisite minimum not fully satisfied.`);
  if (typeof gap === "number" && gap < CONFIDENCE_GAP_THRESHOLD) concerns.push(`Top two tracks are close (${gap} pt gap).`);

  root.innerHTML = `
    <div class="flex items-center gap-2 mb-3">
      <span class="material-symbols-outlined text-[22px] text-amber-400">hourglass_top</span>
      <h2 class="font-headline-md text-[18px] text-on-surface">Your advisor is reviewing this</h2>
    </div>
    <p class="text-body-sm text-on-surface-variant mb-5 leading-relaxed">
      Nova's leading match needs a human sign-off before it's final.
    </p>
    <div class="grid sm:grid-cols-2 gap-4 mb-5">
      <div class="bg-surface-container-high/50 border border-white/10 rounded-xl p-4">
        <p class="text-[11px] font-label-caps text-on-surface-variant/70 mb-1">Leading Match</p>
        <p class="text-body-md font-semibold text-primary">${escapeHtml(topTrack || "—")}</p>
        ${topScore != null ? `<p class="text-[11px] text-on-surface-variant/60 mt-1">${topScore}% match</p>` : ""}
      </div>
      ${
        altTrack
          ? `<div class="bg-surface-container-high/50 border border-white/10 rounded-xl p-4">
               <p class="text-[11px] font-label-caps text-on-surface-variant/70 mb-1">Alternative</p>
               <p class="text-body-md font-semibold text-on-surface">${escapeHtml(altTrack)}</p>
               ${altScore != null ? `<p class="text-[11px] text-on-surface-variant/60 mt-1">${altScore}% match</p>` : ""}
             </div>`
          : ""
      }
    </div>
    ${
      concerns.length
        ? `<div class="mb-5 bg-amber-400/10 border border-amber-400/30 rounded-xl p-4">
             <p class="text-[11px] font-label-caps text-amber-300 mb-2">Why an advisor is looking at this</p>
             <ul class="space-y-1">${concerns.map((c) => `<li class="text-body-sm text-on-surface-variant">• ${escapeHtml(c)}</li>`).join("")}</ul>
           </div>`
        : ""
    }
    <button id="advisor-refresh-btn" class="px-5 py-2.5 rounded-xl bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface">Check status</button>
  `;
  document.getElementById("advisor-refresh-btn").addEventListener("click", () => loadThread(threadId));
}

/* ---- done ---- */
function renderFinal(threadId, values) {
  root.innerHTML = `
    <div class="flex items-center gap-2 mb-4">
      <span class="material-symbols-outlined text-[22px] text-emerald-400">check_circle</span>
      <h2 class="font-headline-md text-[18px] text-on-surface">Your Recommended Track</h2>
    </div>
    <p class="font-headline-md text-[28px] font-semibold text-primary mb-2">${escapeHtml(values.final_track)}</p>
    ${values.final_confidence != null ? `<p class="text-body-sm text-on-surface-variant mb-6">${values.final_confidence}% match confidence</p>` : ""}
    <div class="flex gap-3">
      <button id="final-new-btn" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-secondary text-on-primary text-body-sm font-semibold shadow-[0_8px_24px_rgba(128,131,255,0.35)]">Get a New Recommendation</button>
      <a href="../dashboard/dashboard.html" class="px-5 py-2.5 rounded-xl bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface">Back to Dashboard</a>
    </div>
  `;
  document.getElementById("final-new-btn").addEventListener("click", () => {
    clearThreadId();
    renderStart();
  });
  loadHistory();
}

/* ---------------------------------------------------------------------
   History (read-only — TrackRecommendations rows have no thread_id)
--------------------------------------------------------------------- */
async function loadHistory() {
  try {
    const recs = await SPApi.listTrackRecommendations();
    if (!Array.isArray(recs) || !recs.length) return;
    historySection.classList.remove("hidden");
    historyList.innerHTML = recs
      .slice(0, 8)
      .map((r) => {
        const statusLabel =
          r.status === "completed"
            ? `<span class="text-emerald-300">Completed</span>`
            : r.status === "failed"
            ? `<span class="text-error">Failed</span>`
            : `<span class="text-amber-300">${escapeHtml(r.status.replace(/_/g, " "))}</span>`;
        return `
          <div class="flex items-center justify-between bg-surface-container/60 border border-white/10 rounded-xl px-5 py-4">
            <div>
              <p class="text-body-sm text-on-surface font-medium">${escapeHtml(r.recommended_track || "—")}</p>
              <p class="text-[11px] text-on-surface-variant/60 mt-0.5">${statusLabel}</p>
            </div>
            <p class="font-headline-md text-[16px] text-on-surface">${r.confidence != null ? `${r.confidence}%` : "—"}</p>
          </div>`;
      })
      .join("");
  } catch (err) {
    // History is a nice-to-have; fail silently.
  }
}

/* ---------------------------------------------------------------------
   Boot
--------------------------------------------------------------------- */
applyUser();
if (qThreadId) saveThreadId(qThreadId);
const activeThreadId = qThreadId || getStoredThreadId();
if (activeThreadId) {
  loadThread(activeThreadId);
} else {
  renderStart();
}

// Real-time + durable notifications for track assessment requests.
// student-notifications.js (loaded before this script) handles both
// the page-load DB poll and the SSE stream — we just listen on the bus.
document.addEventListener("DOMContentLoaded", () => {
  if (!window.SNBus) return;

  SNBus.on("assessment_requested", (data) => {
    // Mark durable notification as read — student has seen the card.
    if (data._notificationId && window.SNMarkRead) SNMarkRead(data._notificationId);

    const threadId = data.thread_id || getStoredThreadId();
    if (!threadId) return;

    // Save thread_id so the page can resume correctly.
    saveThreadId(threadId);

    // If we already have a thread loaded, refresh it to show the new state.
    // If not, load it now.
    loadThread(threadId);
  });
});