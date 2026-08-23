// =========================================================
// Adaptive Assessment — student page logic.
//
// Two ways to land here:
//   1) Standalone: no query params -> pick a course + topic ->
//      POST /assessments/start.
//   2) Handed off by tracks.js: ?sessionId=...&returnTo=tracks&
//      threadId=...&resumeKind=diagnostic|targeted. The session row
//      already exists (track_recommendation's assessment_bridge
//      created it directly against the graph), so we never call
//      /start for it -- only GET /assessments/{id}/state, exactly
//      like assessment_router.py's own docstring says to.
//
// Every render pass is driven off the real AdaptiveAssessmentState
// fields (state_graph/adaptive_assessment/state.py): status,
// pending_question, answers, running_score, final_score,
// mastery_level, flagged, flag_reason -- not the placeholder
// mastery_score/mastery_achieved names the in-chat flow guesses at.
// =========================================================

const qs = new URLSearchParams(window.location.search);
const qSessionId  = qs.get("sessionId");
const qReturnTo   = qs.get("returnTo");   // "tracks" | null
const qThreadId   = qs.get("threadId");   // track_recommendation thread, if returnTo=tracks
const qResumeKind = qs.get("resumeKind"); // "diagnostic" | "targeted"

const MAX_QUESTIONS = 8;
const MASTERY_THRESHOLD = 0.75;

const root = document.getElementById("assessment-root");
const historySection = document.getElementById("history-section");
const historyList = document.getElementById("history-list");

let _sessionId = qSessionId ? Number(qSessionId) : null;

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
   Start screen (no active session) — pick a real enrolled course + topic
--------------------------------------------------------------------- */
async function renderStart() {
  root.innerHTML = renderLoadingBlock("Loading your courses…");
  let courses = [];
  try {
    courses = await SPApi.getMyCourses();
  } catch (err) {
    // Non-fatal — the form still works if the student types a course_id
    // manually is not an option, so just show the error and stop here.
    root.innerHTML = renderErrorBlock(`Couldn't load your courses. (${err.message})`);
    return;
  }

  if (!Array.isArray(courses) || !courses.length) {
    root.innerHTML = `
      <h2 class="font-headline-md text-[18px] text-on-surface mb-2">No courses yet</h2>
      <p class="text-body-sm text-on-surface-variant">You need to be enrolled in a course before starting an assessment.</p>
    `;
    loadHistory();
    return;
  }

  const courseOptions = courses
    .map((c) => `<option value="${c.course_id}">${escapeHtml(c.title)}</option>`)
    .join("");

  root.innerHTML = `
    <h2 class="font-headline-md text-[18px] text-on-surface mb-2">Ready for an adaptive assessment?</h2>
    <p class="text-body-sm text-on-surface-variant mb-6 leading-relaxed">
      Nova will ask up to ${MAX_QUESTIONS} questions, adapting the difficulty to how you're doing, until it's confident about your mastery level.
    </p>

    <label class="block text-[11px] font-label-caps text-on-surface-variant/70 mb-2">Course</label>
    <select id="assess-course" class="w-full mb-5 px-4 py-3 rounded-xl bg-surface-container-low/70 border border-white/10 text-body-sm text-on-surface outline-none focus:border-primary/50">
      ${courseOptions}
    </select>

    <label class="block text-[11px] font-label-caps text-on-surface-variant/70 mb-2">Topic</label>
    <input id="assess-topic" type="text" placeholder="e.g. Machine Learning, Data Structures…"
      class="w-full mb-3 px-4 py-3 rounded-xl bg-surface-container-low/70 border border-white/10 text-body-sm text-on-surface placeholder:text-on-surface-variant/40 outline-none focus:border-primary/50"/>
    <div class="flex flex-wrap gap-2 mb-6">
      ${["Data Science", "Machine Learning", "Programming", "General"]
        .map(
          (t) =>
            `<button type="button" data-topic-chip="${escapeHtml(t)}" class="px-3 py-1.5 rounded-full bg-surface-container-low/60 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-[12px] font-medium text-on-surface-variant hover:text-on-surface">${escapeHtml(t)}</button>`
        )
        .join("")}
    </div>

    <button id="start-btn" class="px-6 py-3 rounded-xl bg-gradient-to-br from-primary to-secondary text-on-primary text-body-sm font-semibold shadow-[0_8px_24px_rgba(128,131,255,0.35)] hover:shadow-[0_0_28px_rgba(255,176,205,0.45)] transition-all">
      Start Assessment
    </button>
    <p id="start-error" class="mt-3 text-body-sm text-error hidden"></p>
  `;

  document.querySelectorAll("[data-topic-chip]").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.getElementById("assess-topic").value = chip.dataset.topicChip;
    });
  });
  document.getElementById("start-btn").addEventListener("click", startAssessment);

  loadHistory();
}

async function startAssessment() {
  const courseId = Number(document.getElementById("assess-course").value);
  const topic = document.getElementById("assess-topic").value.trim();
  if (!topic) {
    const errEl = document.getElementById("start-error");
    errEl.textContent = "Please enter a topic to be assessed on.";
    errEl.classList.remove("hidden");
    return;
  }

  root.innerHTML = renderLoadingBlock("Starting your assessment…");
  try {
    const data = await SPApi.startAssessment({
      course_id: courseId,
      topic,
      max_questions: MAX_QUESTIONS,
      mastery_threshold: MASTERY_THRESHOLD,
    });
    _sessionId = data.session_id;
    render(data.result || {});
  } catch (err) {
    root.innerHTML = `
      ${renderErrorBlock(`Couldn't start the assessment. (${err.message})`)}
      <button id="start-retry-btn" class="mt-4 px-5 py-2.5 rounded-xl bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface">Try again</button>
    `;
    document.getElementById("start-retry-btn").addEventListener("click", renderStart);
  }
}

/* ---------------------------------------------------------------------
   Resume an existing session (handed off from tracks.js, or picked from
   history) — GET /assessments/{id}/state, never /start a second time.
--------------------------------------------------------------------- */
async function loadSessionState() {
  root.innerHTML = renderLoadingBlock("Loading your assessment…");
  try {
    const state = await SPApi.getAssessmentState(_sessionId);
    render(state.result || {});
  } catch (err) {
    root.innerHTML = `
      ${renderErrorBlock(`Couldn't load this assessment. (${err.message})`)}
      <button id="load-back-btn" class="mt-4 px-5 py-2.5 rounded-xl bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface">Start a new one</button>
    `;
    document.getElementById("load-back-btn").addEventListener("click", () => {
      _sessionId = null;
      history.replaceState(null, "", "assessment.html");
      renderStart();
    });
  }
}

/* ---------------------------------------------------------------------
   Route the current state to the right renderer.
   pending_question is a real top-level AdaptiveAssessmentState field,
   so we read it directly first -- falling back to the __interrupt__
   payload only if a given result shape doesn't carry it flat.
--------------------------------------------------------------------- */
function extractPendingQuestion(result) {
  if (result?.pending_question?.question_text) return result.pending_question;
  const interrupt = result?._interrupt;
  const fromInterrupt = interrupt?.[0]?.pending_question ?? interrupt?.[0];
  if (fromInterrupt?.question_text) return fromInterrupt;
  return null;
}

function render(result) {
  const pending = extractPendingQuestion(result);
  if (pending) {
    renderQuestion(result, pending);
    return;
  }
  if (result.status === "flagged_for_review" || result.flagged) {
    renderFlagged(result);
    return;
  }
  if (result.status === "completed") {
    renderComplete(result);
    return;
  }
  root.innerHTML = `
    ${renderErrorBlock("This assessment isn't in a state we recognize yet.")}
    <button id="refresh-btn" class="mt-4 px-5 py-2.5 rounded-xl bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface">Refresh</button>
  `;
  document.getElementById("refresh-btn").addEventListener("click", loadSessionState);
}

/* ---- pending question ---- */
function renderQuestion(result, pending) {
  const answered = Array.isArray(result.answers) ? result.answers.length : 0;
  const questionNo = answered + 1;
  const progressPct = Math.min(100, Math.round((questionNo / MAX_QUESTIONS) * 100));
  const opts = Array.isArray(pending.options) ? pending.options : [];
  const letters = ["A", "B", "C", "D"];

  const difficultyCls =
    { easy: "text-emerald-300", medium: "text-amber-300", hard: "text-error" }[pending.difficulty] ||
    "text-on-surface-variant";

  root.innerHTML = `
    <div class="h-1 w-full bg-surface-container-highest rounded-full overflow-hidden mb-5">
      <div class="h-full bg-gradient-to-r from-primary to-secondary rounded-full transition-all" style="width:${progressPct}%;"></div>
    </div>
    <div class="flex items-center gap-3 mb-4">
      <span class="px-3 py-1 rounded-md bg-primary/10 border border-primary/20 text-primary text-[11px] font-label-caps tracking-wide">Question ${questionNo}</span>
      <span class="text-[11px] font-label-caps ${difficultyCls} capitalize">${escapeHtml(pending.difficulty || "")}</span>
    </div>
    <h2 class="font-headline-md text-[18px] leading-[26px] font-semibold text-on-surface mb-6">${escapeHtml(pending.question_text)}</h2>
    <div id="option-list" class="space-y-3 mb-6">
      ${opts
        .map(
          (opt, i) => `
        <label class="block cursor-pointer group">
          <input class="peer sr-only" type="radio" name="opt" value="${escapeHtml(opt)}"/>
          <div class="w-full p-4 rounded-xl border border-white/10 bg-surface-container-low/50 group-hover:bg-white/5 group-hover:border-white/20 peer-checked:bg-primary/10 peer-checked:border-primary/50 transition-all flex gap-3 items-start">
            <span class="w-6 h-6 shrink-0 rounded-full border border-white/15 flex items-center justify-center text-[11px] font-label-caps text-on-surface-variant peer-checked:text-primary">${letters[i] || i + 1}</span>
            <span class="text-body-sm text-on-surface-variant group-hover:text-on-surface peer-checked:text-on-surface transition-colors">${escapeHtml(opt)}</span>
          </div>
        </label>`
        )
        .join("")}
    </div>
    <button id="submit-answer-btn" class="px-6 py-3 rounded-xl bg-gradient-to-br from-primary to-secondary text-on-primary text-body-sm font-semibold shadow-[0_8px_24px_rgba(128,131,255,0.35)] hover:shadow-[0_0_28px_rgba(255,176,205,0.45)] transition-all">
      Submit Answer
    </button>
    <p id="answer-error" class="mt-3 text-body-sm text-error hidden"></p>
  `;

  document.getElementById("submit-answer-btn").addEventListener("click", submitAnswer);
}

async function submitAnswer() {
  const checked = document.querySelector('#option-list input[type=radio]:checked');
  if (!checked) {
    const errEl = document.getElementById("answer-error");
    errEl.textContent = "Pick an answer first.";
    errEl.classList.remove("hidden");
    return;
  }
  document.querySelectorAll('#option-list input[type=radio]').forEach((r) => (r.disabled = true));
  document.getElementById("submit-answer-btn").disabled = true;

  const pid = document.createElement("div");
  pid.className = "mt-4";
  pid.innerHTML = renderLoadingBlock("Evaluating your answer…");
  root.appendChild(pid);

  try {
    const data = await SPApi.answerAssessment(_sessionId, checked.value);
    render(data.result || {});
  } catch (err) {
    pid.innerHTML = renderErrorBlock(`Couldn't submit your answer. (${err.message})`);
    document.getElementById("submit-answer-btn").disabled = false;
    document.querySelectorAll('#option-list input[type=radio]').forEach((r) => (r.disabled = false));
  }
}

/* ---- flagged_for_review: borderline score, waiting on an instructor ---- */
function renderFlagged(result) {
  root.innerHTML = `
    <div class="flex items-center gap-2 mb-3">
      <span class="material-symbols-outlined text-[22px] text-amber-400">hourglass_top</span>
      <h2 class="font-headline-md text-[18px] text-on-surface">Your result needs a quick human check</h2>
    </div>
    <p class="text-body-sm text-on-surface-variant mb-5 leading-relaxed">
      Your score came out close to the mastery threshold, so an instructor is reviewing it before it's finalized.
      ${result.flag_reason ? `<span class="block mt-2 text-[12px] text-on-surface-variant/60">${escapeHtml(result.flag_reason)}</span>` : ""}
    </p>
    <button id="flagged-refresh-btn" class="px-5 py-2.5 rounded-xl bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface">Check status</button>
  `;
  document.getElementById("flagged-refresh-btn").addEventListener("click", loadSessionState);
}

/* ---- completed ---- */
const MASTERY_STYLE = {
  mastered: { label: "Mastered", cls: "bg-emerald-400/10 border-emerald-400/30 text-emerald-300" },
  proficient: { label: "Proficient", cls: "bg-primary/10 border-primary/30 text-primary" },
  developing: { label: "Developing", cls: "bg-amber-400/10 border-amber-400/30 text-amber-300" },
  novice: { label: "Novice", cls: "bg-error-container/40 border-error/30 text-error" },
};

function renderComplete(result) {
  const pct = result.final_score != null ? Math.round(result.final_score * 100) : null;
  const level = MASTERY_STYLE[result.mastery_level] || { label: result.mastery_level || "—", cls: "bg-surface-container-high border-white/10 text-on-surface-variant" };

  root.innerHTML = `
    <div class="flex items-center gap-2 mb-4">
      <span class="material-symbols-outlined text-[22px] text-emerald-400">check_circle</span>
      <h2 class="font-headline-md text-[18px] text-on-surface">Assessment Complete</h2>
    </div>
    ${pct != null ? `<p class="font-headline-md text-[36px] font-semibold text-on-surface mb-2">${pct}%</p>` : ""}
    <span class="inline-flex items-center gap-2 px-4 py-2 rounded-xl ${level.cls} border text-body-sm font-medium mb-6">
      <span class="w-1.5 h-1.5 rounded-full bg-current"></span>${escapeHtml(level.label)}
    </span>
    <div id="complete-actions" class="flex flex-wrap gap-3"></div>
  `;

  const actions = document.getElementById("complete-actions");

  if (qReturnTo === "tracks" && qThreadId) {
    const btn = document.createElement("button");
    btn.id = "continue-track-btn";
    btn.className =
      "px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-secondary text-on-primary text-body-sm font-semibold shadow-[0_8px_24px_rgba(128,131,255,0.35)] hover:shadow-[0_0_28px_rgba(255,176,205,0.45)] transition-all";
    btn.textContent = "Continue Track Recommendation";
    btn.addEventListener("click", () => continueTrackFlow(btn));
    actions.appendChild(btn);
  } else {
    const newBtn = document.createElement("button");
    newBtn.className =
      "px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-secondary text-on-primary text-body-sm font-semibold shadow-[0_8px_24px_rgba(128,131,255,0.35)]";
    newBtn.textContent = "Take Another Assessment";
    newBtn.addEventListener("click", () => {
      _sessionId = null;
      history.replaceState(null, "", "assessment.html");
      renderStart();
    });
    actions.appendChild(newBtn);
  }

  const backLink = document.createElement("a");
  backLink.href = "../dashboard/dashboard.html";
  backLink.className =
    "px-5 py-2.5 rounded-xl bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface";
  backLink.textContent = "Back to Dashboard";
  actions.appendChild(backLink);

  loadHistory();
}

async function continueTrackFlow(btn) {
  btn.disabled = true;
  btn.textContent = "Resuming…";
  try {
    if (qResumeKind === "targeted") {
      await SPApi.targetedAssessmentComplete(qThreadId);
    } else {
      await SPApi.diagnosticComplete(qThreadId);
    }
    window.location.href = `../tracks/tracks.html?threadId=${encodeURIComponent(qThreadId)}`;
  } catch (err) {
    btn.disabled = false;
    btn.textContent = "Continue Track Recommendation";
    const p = document.createElement("p");
    p.className = "mt-3 text-body-sm text-error w-full";
    p.textContent = `Couldn't resume the track recommendation. (${err.message})`;
    document.getElementById("complete-actions").appendChild(p);
  }
}

/* ---------------------------------------------------------------------
   History
--------------------------------------------------------------------- */
async function loadHistory() {
  try {
    const sessions = await SPApi.listAssessmentSessions();
    if (!Array.isArray(sessions) || !sessions.length) return;
    historySection.classList.remove("hidden");
    historyList.innerHTML = sessions
      .slice(0, 8)
      .map((s) => {
        const isResumable = s.status === "in_progress" || s.status === "flagged_for_review";
        const statusLabel =
          s.status === "completed"
            ? `<span class="text-emerald-300">Completed</span>`
            : s.status === "flagged_for_review"
            ? `<span class="text-amber-300">Pending review</span>`
            : `<span class="text-primary">In progress</span>`;
        const scoreLabel = s.final_score != null ? `${Math.round(s.final_score * 100)}%` : "—";
        const inner = `
          <div>
            <p class="text-body-sm text-on-surface font-medium">${escapeHtml(s.topic || "—")}</p>
            <p class="text-[11px] text-on-surface-variant/60 mt-0.5">${statusLabel}${s.mastery_level ? ` · ${escapeHtml(s.mastery_level)}` : ""}</p>
          </div>
          <p class="font-headline-md text-[16px] text-on-surface">${scoreLabel}</p>`;
        return isResumable
          ? `<a href="assessment.html?sessionId=${s.session_id}" class="flex items-center justify-between bg-surface-container/60 hover:border-primary/40 border border-white/10 rounded-xl px-5 py-4 transition-all">${inner}</a>`
          : `<div class="flex items-center justify-between bg-surface-container/60 border border-white/10 rounded-xl px-5 py-4">${inner}</div>`;
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
if (_sessionId) {
  loadSessionState();
} else {
  renderStart();
}
