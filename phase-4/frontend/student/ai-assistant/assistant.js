// AI Assistant (Nova) page logic.
// BASE_URL: FastAPI (port 8000); dashboard/logout stay on Express (port 3000).
const BASE_URL      = "http://localhost:8000";
const EXPRESS_URL   = "http://localhost:3000";

// Tracks the active course_id when the student is in the material flow.
// Set by materialCourse() — cleared on new flow start.
let _activeCourseId = null;

// Explicit flow state ("track" | "material" | "assessment" | "certificate"
// | "cases" | null). More robust than inferring routing purely from
// whether _activeCourseId happens to be truthy — every flow starter sets
// this so sendMessage() always knows the real active context.
let _currentFlow = null;

// Extracts a readable string from a FastAPI error body's `detail` field,
// which can be a plain string, an array of Pydantic validation error
// objects, or something else entirely. Passing an array/object straight
// into `new Error(...)` stringifies it as "[object Object]", so every
// catch block in this file should route `detail` through this first.
function _readableDetail(detail) {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((e) => (e && typeof e === "object" ? (e.msg || JSON.stringify(e)) : String(e))).join("; ");
  }
  if (typeof detail === "object") return JSON.stringify(detail);
  return String(detail);
}

const thread = document.getElementById("chat-thread");
const typingIndicator = document.getElementById("typing-indicator");
const input = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const NOVA_AVATAR = "../../assets/images/student/nova-mascot.png";

function scrollToBottom() {
  thread.parentElement.scrollTop = thread.parentElement.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

let rowId = 0;
function nextId(prefix) {
  rowId += 1;
  return `${prefix}-${rowId}`;
}

/* ---------------------------------------------------------------------
   Generic chat-thread rendering helpers
   All guided-flow states are built out of these three primitives so the
   visual language (avatar, bubble, spacing, animation) stays consistent
   with the rest of Nova, per DESIGN.md.
--------------------------------------------------------------------- */

// A short chat-style reply bubble representing the student's choice
// (mirrors a real user message, right-aligned).
function appendUserReply(text) {
  const row = document.createElement("div");
  row.className = "flex gap-4 items-end justify-end slide-up";
  const avatarSrc = document.getElementById("student-avatar")?.src || "";
  row.innerHTML = `
    <div class="bg-gradient-to-br from-primary-container to-secondary-container rounded-2xl rounded-br-sm px-5 py-4 max-w-[85%] shadow-[0_8px_24px_rgba(128,131,255,0.2)] text-body-md text-on-primary-container leading-relaxed">
      ${escapeHtml(text)}
    </div>
    <img alt="Profile" class="w-8 h-8 rounded-full border border-primary/30 object-cover shrink-0 shadow-[0_4px_12px_rgba(0,0,0,0.2)]" src="${avatarSrc}"/>
  `;
  thread.insertBefore(row, typingIndicator);
  scrollToBottom();
  return row;
}

// A simple Nova text bubble.
function appendBotMessage(text) {
  const row = document.createElement("div");
  row.className = "flex gap-4 items-end slide-up";
  row.innerHTML = `
    <img src="${NOVA_AVATAR}" alt="Nova" class="w-8 h-8 rounded-full bg-surface-container-high object-cover shrink-0 border border-white/10 shadow-[0_4px_12px_rgba(0,0,0,0.2)]"/>
    <div class="bg-surface-container-high/80 backdrop-blur-md rounded-2xl rounded-bl-sm px-5 py-4 max-w-[85%] border border-white/10 shadow-lg text-body-md text-on-surface leading-relaxed">
      ${escapeHtml(text)}
    </div>
  `;
  thread.insertBefore(row, typingIndicator);
  scrollToBottom();
  return row;
}

// A richer Nova "card" block — used for cards with their own buttons,
// checklists, progress bars, forms, etc. `innerHtml` supplies the card
// body; this wrapper only adds the avatar + consistent card chrome.
function appendBotCard(innerHtml, { id } = {}) {
  const row = document.createElement("div");
  row.className = "flex gap-4 items-end slide-up";
  if (id) row.id = id;
  row.innerHTML = `
    <img src="${NOVA_AVATAR}" alt="Nova" class="w-8 h-8 rounded-full bg-surface-container-high object-cover shrink-0 border border-white/10 shadow-[0_4px_12px_rgba(0,0,0,0.2)]"/>
    <div class="bg-surface-container/60 backdrop-blur-lg rounded-xl p-5 border border-white/10 shadow-[0_12px_32px_rgba(0,0,0,0.25)] max-w-[85%] w-full">
      ${innerHtml}
    </div>
  `;
  thread.insertBefore(row, typingIndicator);
  scrollToBottom();
  return row;
}

// A lightweight "Nova is working on it" bubble that can be swapped out
// once the (simulated) processing finishes.
function appendProcessing(text) {
  const id = nextId("processing");
  const row = document.createElement("div");
  row.className = "flex gap-4 items-end slide-up";
  row.id = id;
  row.innerHTML = `
    <img src="${NOVA_AVATAR}" alt="Nova" class="w-8 h-8 rounded-full bg-surface-container-high object-cover shrink-0 border border-white/10 shadow-[0_4px_12px_rgba(0,0,0,0.2)]"/>
    <div class="bg-surface-container-high/60 backdrop-blur-md rounded-2xl rounded-bl-sm px-5 py-4 border border-white/10 shadow-lg text-body-md text-on-surface-variant leading-relaxed flex items-center gap-2">
      <span>${escapeHtml(text)}</span>
      <span class="inline-flex gap-1">
        <span class="w-1 h-1 bg-primary/70 rounded-full animate-bounce"></span>
        <span class="w-1 h-1 bg-primary/70 rounded-full animate-bounce" style="animation-delay:.15s;"></span>
        <span class="w-1 h-1 bg-primary/70 rounded-full animate-bounce" style="animation-delay:.3s;"></span>
      </span>
    </div>
  `;
  thread.insertBefore(row, typingIndicator);
  scrollToBottom();
  return id;
}

function removeNode(id) {
  document.getElementById(id)?.remove();
}

// Disables the control that triggered a step so it can't be re-fired,
// while leaving it visible in the conversation history.
function lockControl(el) {
  if (!el) return;
  el.disabled = true;
  el.classList.add("opacity-50", "pointer-events-none");
}

// After a flow reaches a resting point, gently re-offer the main menu
// so the student always has an obvious next step (DESIGN.md §17).
function appendMoreHelpPrompt() {
  appendBotCard(`
    <p class="text-body-sm text-on-surface-variant mb-3">Need help with something else?</p>
    <div class="flex flex-wrap gap-2">
      <button data-flow="track" class="quick-action px-3 py-2 rounded-full bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface-variant hover:text-on-surface">🎯 Recommend my Track</button>
      <button data-flow="material" class="quick-action px-3 py-2 rounded-full bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface-variant hover:text-on-surface">📖 Ask about course material</button>
      <button data-flow="assessment" class="quick-action px-3 py-2 rounded-full bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface-variant hover:text-on-surface">🧠 Start an Assessment</button>
      <button data-flow="certificate" class="quick-action px-3 py-2 rounded-full bg-surface-container-low/80 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface-variant hover:text-on-surface">🎓 Certificate &amp; Scholarship</button>
      <button data-flow="cases" class="quick-action px-3 py-2 rounded-full bg-surface-container-low/80 border border-white/10 hover:border-error/40 hover:bg-error-container/10 transition-all text-body-sm font-medium text-on-surface-variant hover:text-error">⚠️ My Cases &amp; Appeals</button>
    </div>
  `);
}

/* ---------------------------------------------------------------------
   FLOW: Track Recommendation (DESIGN.md §8)
--------------------------------------------------------------------- */
function startTrackFlow(triggerEl) {
  lockControl(triggerEl);
  _activeCourseId = null; // leaving material flow context — don't route free text there
  _currentFlow = "track";
  appendUserReply("🎯 Recommend my Track");
  appendBotCard(`
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-2">🎯 Let's find the right track for you!</h4>
    <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">I'll look at your academic progress and help you identify the track that best matches your strengths.</p>
    <button data-action="track-start" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">Start Recommendation</button>
  `);
}

async function trackStart(el) {
  lockControl(el);
  const pid = appendProcessing("Analyzing your academic profile... ✨");
  try {
    const _user = window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
    const res = await fetch(`${BASE_URL}/tracks/recommend`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id":   String(_user.id   || ""),
        "X-User-Role": String(_user.role || "student"),
      },
    });
    removeNode(pid);
    if (!res.ok) throw new Error(`status ${res.status}`);
    const data = await res.json();
    // The real track/confidence fields live inside data.result, named
    // final_track / final_confidence (state.py). final_confidence is
    // already a 0-100 number — don't multiply by 100 again.
    const result = data.result || {};
    const track      = result.final_track;
    const confidence = result.final_confidence;

    if (!track) {
      // Graph hasn't reached final_track yet — e.g. still mid-flow /
      // awaiting a diagnostic (result._interrupt set). Show an
      // in-progress state instead of a blank "—" card.
      const interrupted = !!result._interrupt;
      appendBotCard(`
        <div class="flex items-center gap-2 mb-2">
          <span class="text-lg">🕐</span>
          <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface">${interrupted ? "We need a bit more information first" : "Still working on your recommendation"}</h4>
        </div>
        <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">${interrupted
          ? "Some of your prerequisite data is missing, so a diagnostic step or advisor review is needed before I can give you a final recommendation."
          : "I wasn't able to finalize a recommendation just yet. Please try again in a moment."}</p>
      `);
      appendMoreHelpPrompt();
      return;
    }

    const confidencePct  = confidence != null ? Math.round(confidence) : null;
    const confidenceText = confidencePct != null ? `${confidencePct}% AI Match` : "";
    appendBotCard(`
      <div class="flex items-center justify-between mb-4">
        <h4 class="font-headline-md text-[18px] leading-[24px] font-semibold text-on-surface flex items-center gap-2">🎯 Your Recommended Track</h4>
      </div>
      <p class="text-headline-md text-[20px] font-semibold text-primary mb-1">${escapeHtml(String(track))}</p>
      ${confidenceText ? `<div class="flex items-center gap-2 mb-3"><span class="text-secondary font-semibold text-body-sm">${escapeHtml(confidenceText)}</span></div>` : ""}
      <div class="h-2 w-full bg-surface-container-highest rounded-full overflow-hidden mb-4">
        <div class="h-full bg-gradient-to-r from-primary to-secondary rounded-full shadow-[0_0_12px_rgba(192,193,255,0.6)]" style="width:${confidencePct != null ? confidencePct : 80}%;"></div>
      </div>
      <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">Based on your academic performance and skills profile.</p>
      <button data-action="track-view-details" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">View Details</button>
    `);
  } catch (err) {
    removeNode(pid);
    appendBotMessage(`Sorry, I couldn't reach the track recommendation service right now. (${err.message})`);
    appendMoreHelpPrompt();
  }
}

function trackViewDetails(el) {
  lockControl(el);
  appendBotCard(`
    <div class="flex items-center gap-2 mb-2">
      <span class="text-lg">🕐</span>
      <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface">Your recommendation is being reviewed</h4>
    </div>
    <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">Your academic advisor will review the recommendation before it is finalized.</p>
    <span class="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-400/10 border border-amber-400/30 text-amber-300 text-body-sm font-medium">
      <span class="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse"></span> Waiting for Review
    </span>
  `);
  appendMoreHelpPrompt();
}

/* ---------------------------------------------------------------------
   FLOW: Start an Assessment (real backend — assessment_router.py)
   POST /assessments/start  → session_id + first question in _interrupt
   POST /assessments/{id}/answer → next question or final result
--------------------------------------------------------------------- */

// Active session state (reset on each new flow start)
let _assessmentSessionId  = null;
let _assessmentQuestionNo = 0;
let _assessmentTotal      = 8;   // max_questions sent on start; actual may differ

async function startAssessmentFlow(triggerEl) {
  lockControl(triggerEl);
  _activeCourseId = null; // leaving material flow context — don't route free text there
  _currentFlow = "assessment";
  appendUserReply("🧠 Start an Assessment");
  const pid = appendProcessing("Loading your enrolled courses...");
  try {
    const _user = window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
    const res = await fetch(`${BASE_URL}/teaching/courses`, {
      headers: {
        "Content-Type": "application/json",
        "X-User-Id":   String(_user.id   || ""),
        "X-User-Role": String(_user.role || "student"),
      },
    });
    removeNode(pid);
    const courses = res.ok ? await res.json() : [];
    if (!courses.length) {
      appendBotCard(`
        <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-2">Ready for an adaptive assessment?</h4>
        <p class="text-body-sm text-on-surface-variant leading-relaxed">You're not enrolled in any courses yet, so there's nothing for me to generate questions from. Once you're enrolled in a course, come back and I'll build an assessment for it.</p>
      `);
      appendMoreHelpPrompt();
      return;
    }
    const courseButtons = courses.map((c) =>
      `<button data-action="assessment-pick-topic" data-course-id="${c.course_id}" data-topic="${escapeHtml(c.title)}"
        class="px-4 py-2 rounded-xl bg-surface-container-low/60 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface">${escapeHtml(c.title)}</button>`
    ).join("");
    appendBotCard(`
      <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-2">Ready for an adaptive assessment?</h4>
      <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">I'll generate questions tailored to your enrolled courses and adapt based on your answers.</p>
      <p class="text-body-sm text-on-surface-variant mb-4">Which course would you like to be assessed on?</p>
      <div class="flex flex-wrap gap-2">${courseButtons}</div>
    `);
  } catch (err) {
    removeNode(pid);
    appendBotMessage(`Sorry, I couldn't load your courses right now. (${err.message})`);
    appendMoreHelpPrompt();
  }
}

async function assessmentPickTopic(el) {
  lockControl(el);
  const topic    = el.dataset.topic || "General";
  const courseId = el.dataset.courseId ? parseInt(el.dataset.courseId, 10) : null;
  appendUserReply(`📖 ${topic}`);
  _assessmentSessionId  = null;
  _assessmentQuestionNo = 0;

  if (!courseId) {
    appendBotMessage("Sorry, I couldn't tell which course this was for — please start the assessment again.");
    appendMoreHelpPrompt();
    return;
  }

  const pid = appendProcessing("Starting your assessment...");
  try {
    const _user = window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
    // Real course_id (not hardcoded) + topic derived from the course's own
    // title, so decompose_and_pick_question has real material to work from.
    const res = await fetch(`${BASE_URL}/assessments/start`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id":   String(_user.id   || ""),
        "X-User-Role": String(_user.role || "student"),
      },
      body: JSON.stringify({ course_id: courseId, topic, max_questions: 5, mastery_threshold: 0.75 }),
    });
    removeNode(pid);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(_readableDetail(err.detail) || `status ${res.status}`);
    }
    const data = await res.json();
    _assessmentSessionId = data.session_id;
    _renderAssessmentQuestion(data.result);
  } catch (err) {
    removeNode(pid);
    appendBotMessage(`Sorry, couldn't start the assessment. (${err.message})`);
    appendMoreHelpPrompt();
  }
}

function _renderAssessmentQuestion(result) {
  // The graph pauses at await_answer and surfaces the question via _interrupt
  const interrupt = result?._interrupt;
  const pending   = interrupt?.[0]?.pending_question ?? interrupt?.[0];

  if (!pending || !pending.question_text) {
    if (_assessmentQuestionNo === 0) {
      // The graph never asked a single question — this is a genuine
      // "no questions available" failure, not a completed assessment.
      // Rendering these identically would make a silent backend failure
      // look like the student aced it.
      appendBotCard(`
        <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-2">No questions available</h4>
        <p class="text-body-sm text-on-surface-variant leading-relaxed">I wasn't able to generate any questions for this course yet. This usually means there isn't enough material indexed for it — please try a different course, or check back later.</p>
      `);
      appendMoreHelpPrompt();
      return;
    }
    // At least one question was asked — graph completed normally
    // (mastery reached or max questions).
    _renderAssessmentComplete(result);
    return;
  }

  _assessmentQuestionNo += 1;
  const cardId     = nextId("assess-q");
  const q          = pending.question_text;
  const opts       = Array.isArray(pending.options) ? pending.options : [];
  const progressPct = Math.min(100, Math.round((_assessmentQuestionNo / _assessmentTotal) * 100));

  const optionsHtml = opts.map((opt, i) => `
    <label class="block cursor-pointer group">
      <input class="peer sr-only" type="radio" name="${cardId}-opt" value="${escapeHtml(opt)}"/>
      <div class="w-full p-4 rounded-xl border border-white/10 bg-surface-container-low/50 group-hover:bg-white/5 group-hover:border-white/20 peer-checked:bg-primary/10 peer-checked:border-primary/50 transition-all duration-200 flex gap-3 items-start">
        <div class="w-5 h-5 rounded-full border-2 border-on-surface-variant/40 flex-shrink-0 mt-0.5 flex items-center justify-center">
          <div class="w-2 h-2 rounded-full bg-primary opacity-0 peer-checked:opacity-100 transition-opacity"></div>
        </div>
        <div class="text-body-sm text-on-surface-variant group-hover:text-on-surface peer-checked:text-on-surface transition-colors">${escapeHtml(opt)}</div>
      </div>
    </label>`).join("");

  appendBotCard(`
    <div class="h-1 w-full bg-surface-container-highest rounded-full overflow-hidden mb-4">
      <div class="h-full bg-gradient-to-r from-primary to-secondary rounded-full" style="width:${progressPct}%;"></div>
    </div>
    <span class="inline-block mb-3 px-3 py-1 rounded-md bg-primary/10 border border-primary/20 text-primary text-[11px] font-label-caps tracking-wide">🧠 Question ${_assessmentQuestionNo}</span>
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-4">${escapeHtml(q)}</h4>
    <div class="space-y-3 mb-5">${optionsHtml}</div>
    <button data-action="assessment-submit-answer" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">Submit Answer</button>
  `, { id: cardId });
}

async function assessmentSubmitAnswer(el) {
  const card    = el.closest(".flex.gap-4.items-end");
  const checked = card?.querySelector("input[type=radio]:checked");
  if (!checked) {
    el.classList.add("animate-pulse");
    setTimeout(() => el.classList.remove("animate-pulse"), 400);
    return;
  }
  lockControl(el);
  card.querySelectorAll("input[type=radio]").forEach((r) => (r.disabled = true));

  if (!_assessmentSessionId) {
    appendBotMessage("Session lost — please start a new assessment.");
    appendMoreHelpPrompt();
    return;
  }

  const pid = appendProcessing("Evaluating your answer...");
  try {
    const _user = window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
    const res = await fetch(`${BASE_URL}/assessments/${_assessmentSessionId}/answer`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id":   String(_user.id   || ""),
        "X-User-Role": String(_user.role || "student"),
      },
      body: JSON.stringify({ student_answer: checked.value }),
    });
    removeNode(pid);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(_readableDetail(err.detail) || `status ${res.status}`);
    }
    const data = await res.json();
    _renderAssessmentQuestion(data.result);
  } catch (err) {
    removeNode(pid);
    appendBotMessage(`Sorry, couldn't submit your answer. (${err.message})`);
    appendMoreHelpPrompt();
  }
}

function _renderAssessmentComplete(result) {
  // Graph finished — show whatever mastery info the state contains
  const state    = result?.values ?? result ?? {};
  const mastery  = state.mastery_score  != null ? Math.round(state.mastery_score  * 100) : null;
  const achieved = state.mastery_achieved ?? (mastery != null && mastery >= 75);
  const scoreHtml = mastery != null
    ? `<p class="text-headline-md text-[20px] font-semibold ${achieved ? "text-primary" : "text-error"} mb-4">Score: ${mastery}%</p>`
    : "";

  appendBotCard(`
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-2">✨ Assessment Complete</h4>
    <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">You've finished the adaptive assessment.</p>
    ${scoreHtml}
    <span class="inline-flex items-center gap-2 px-4 py-2 rounded-xl ${achieved ? "bg-emerald-400/10 border-emerald-400/30 text-emerald-300" : "bg-amber-400/10 border-amber-400/30 text-amber-300"} border text-body-sm font-medium">
      <span class="w-1.5 h-1.5 ${achieved ? "bg-emerald-400" : "bg-amber-400"} rounded-full"></span>
      ${achieved ? "Mastery Achieved 🎉" : "Under Advisor Review"}
    </span>
  `);
  appendMoreHelpPrompt();
}

/* ---------------------------------------------------------------------
   FLOW: Ask about course material (DESIGN.md §10)
--------------------------------------------------------------------- */
async function startMaterialFlow(triggerEl) {
  lockControl(triggerEl);
  _activeCourseId = null;  // clear any previous course context
  _currentFlow = "material";
  appendUserReply("📖 Ask about course material");
  const pid = appendProcessing("Loading your enrolled courses...");
  try {
    const _user = window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
    const res = await fetch(`${BASE_URL}/teaching/courses`, {
      headers: {
        "Content-Type": "application/json",
        "X-User-Id":   String(_user.id   || ""),
        "X-User-Role": String(_user.role || "student"),
      },
    });
    removeNode(pid);
    const courses = res.ok ? await res.json() : [];
    const courseButtons = courses.length
      ? courses.map((c) =>
          `<button data-action="material-course" data-course-id="${c.course_id}" data-course="${escapeHtml(c.title)}"
            class="px-4 py-3 rounded-xl bg-surface-container-low/60 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface text-left">${escapeHtml(c.title)}</button>`
        ).join("")
      : `<p class="text-body-sm text-on-surface-variant">You're not enrolled in any courses yet.</p>`;
    appendBotCard(`
      <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-4">📖 What course would you like help with?</h4>
      <div class="grid grid-cols-2 gap-3">
        ${courseButtons}
        <button data-action="material-other" class="px-4 py-3 rounded-xl bg-surface-container-low/60 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface text-left">Other...</button>
      </div>
    `);
  } catch (err) {
    removeNode(pid);
    appendBotMessage("Sorry, I couldn't load your courses right now. Type your question below and I'll help anyway.");
  }
}

function materialCourse(el) {
  lockControl(el);
  const course = el.dataset.course;
  // Store numeric course_id so sendMessage() routes to /teaching/chat
  _activeCourseId = el.dataset.courseId ? parseInt(el.dataset.courseId, 10) : null;
  appendUserReply(course);
  appendBotCard(`
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-4">What would you like to explore?</h4>
    <div class="flex flex-wrap gap-3">
      <button data-action="material-topic" data-course="${escapeHtml(course)}" data-kind="Explain a topic" class="px-4 py-2.5 rounded-xl bg-surface-container-low/60 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface">Explain a topic</button>
      <button data-action="material-topic" data-course="${escapeHtml(course)}" data-kind="Find a specific concept" class="px-4 py-2.5 rounded-xl bg-surface-container-low/60 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface">Find a specific concept</button>
      <button data-action="material-topic" data-course="${escapeHtml(course)}" data-kind="Summarize material" class="px-4 py-2.5 rounded-xl bg-surface-container-low/60 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface">Summarize material</button>
    </div>
    <p class="text-[11px] text-on-surface-variant/50 mt-4">Or just type a specific question in the box below.</p>
  `);
}

function materialTopic(el) {
  lockControl(el);
  const course = el.dataset.course;
  const kind = el.dataset.kind;
  appendUserReply(kind);
  const cardId = nextId("material-form");
  appendBotCard(
    `
    <p class="text-body-sm text-on-surface mb-4 leading-relaxed">Great choice! 💡 What topic would you like to understand better in <span class="font-semibold text-primary">${escapeHtml(course)}</span>?</p>
    <div class="flex items-center gap-2">
      <input type="text" data-role="material-topic-input" placeholder="Enter a topic..." class="flex-1 bg-surface-container-low/60 border border-white/10 focus:border-primary/50 outline-none rounded-xl px-4 py-2.5 text-body-sm text-on-surface placeholder:text-on-surface-variant/40"/>
      <button data-action="material-ask" data-course="${escapeHtml(course)}" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shrink-0 shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">Ask Nova</button>
    </div>
  `,
    { id: cardId }
  );
}

async function materialAsk(el) {
  const card = el.closest(".flex.gap-4.items-end");
  const topicInput = card?.querySelector('[data-role="material-topic-input"]');
  const topic = topicInput?.value.trim();
  if (!topic) { topicInput?.focus(); return; }
  lockControl(el);
  if (topicInput) topicInput.disabled = true;
  appendUserReply(topic);
  const pid = appendProcessing("Looking through your course material... ✨");
  try {
    const _user   = window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
    const courseId = _activeCourseId;
    if (!courseId) throw new Error("No course selected");
    const res = await fetch(`${BASE_URL}/teaching/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id":   String(_user.id   || ""),
        "X-User-Role": String(_user.role || "student"),
      },
      body: JSON.stringify({ course_id: courseId, question: topic }),
    });
    removeNode(pid);
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(_readableDetail(errBody.detail) || `status ${res.status}`);
    }
    const data = await res.json();
    appendBotMessage(data.answer ?? "I couldn't find enough information in this course's material to answer that.");
    if (data.sources && data.sources.length) {
      appendBotMessage(`📚 Sources: ${data.sources.join(", ")}`);
    }
    appendMoreHelpPrompt();
  } catch (err) {
    removeNode(pid);
    appendBotMessage(`Sorry, I couldn't reach the course material service. (${err.message})`);
    appendMoreHelpPrompt();
  }
}

function materialOther(el) {
  lockControl(el);
  appendUserReply("Other...");
  appendBotMessage("No problem — type the course name in the box below and I'll help you from there.");
  input.placeholder = "Type a course name...";
  input.focus();
}

/* ---------------------------------------------------------------------
   FLOW: Certificate & Scholarship (DESIGN.md §11)
--------------------------------------------------------------------- */
function startCertificateFlow(triggerEl) {
  lockControl(triggerEl);
  _activeCourseId = null; // leaving material flow context — don't route free text there
  _currentFlow = "certificate";
  appendUserReply("🎓 Certificate & Scholarship");
  appendBotCard(`
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-2">Let's check your eligibility.</h4>
    <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">I'll review your academic information and the current requirements.</p>
    <button data-action="certificate-start" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">Check My Eligibility</button>
  `);
}

async function certificateStart(el) {
  lockControl(el);
  const pid = appendProcessing("Checking your eligibility...");
  try {
    const _user = window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
    const res = await fetch(`${BASE_URL}/advisor/certificate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id":   String(_user.id   || ""),
        "X-User-Role": String(_user.role || "student"),
      },
      // StartRequestBody requires request_type (no default); "notes" isn't
      // even a field on that model, so it was silently dropped and the
      // request always failed 422 with a missing request_type.
      body: JSON.stringify({ request_type: "certificate" }),
    });
    removeNode(pid);
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(_readableDetail(errBody.detail) || `status ${res.status}`);
    }
    const data = await res.json();
    // advisor_router returns the graph state — eligible flag or status from state
    const eligible = data.eligible ?? data.status === "approved" ?? true;
    const check = `<span class="material-symbols-outlined text-[18px] text-emerald-400">check_circle</span>`;
    const pend  = `<span class="material-symbols-outlined text-[18px] text-amber-400">radio_button_unchecked</span>`;
    if (eligible) {
      appendBotCard(`
        <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-3">✨ Request Submitted!</h4>
        <p class="text-body-sm text-on-surface-variant mb-3">Your certificate request is now under advisor review.</p>
        <ul class="space-y-2 mb-4">
          <li class="flex items-center gap-2 text-body-sm text-on-surface-variant">${check} Academic standing verified</li>
          <li class="flex items-center gap-2 text-body-sm text-on-surface-variant">${check} Request recorded</li>
        </ul>
        <button data-action="certificate-view-details" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">View Details</button>
      `);
    } else {
      appendBotCard(`
        <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-3">Request under review</h4>
        <ul class="space-y-2 mb-4">
          <li class="flex items-center gap-2 text-body-sm text-on-surface-variant">${pend} Advisor review pending</li>
        </ul>
        <button data-action="certificate-view-details" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">View Status</button>
      `);
    }
  } catch (err) {
    removeNode(pid);
    appendBotMessage(`Sorry, couldn't submit your certificate request. (${err.message})`);
    appendMoreHelpPrompt();
  }
}

// ---- Certificate/Scholarship status card & student-reply flow ----

// request_id of the most-recently-viewed cert/scholarship request —
// used by the student-reply submit handler.
let _certRequestId = null;

// Wire SNBus handler (student-notifications.js fires this on both
// page-load poll AND real-time SSE — one handler covers both paths).
document.addEventListener("DOMContentLoaded", () => {
  if (window.SNBus) {
    SNBus.on("more_info_requested", (data) => {
      // Show the card if it's for the request we're tracking,
      // or always if we haven't seen any request yet.
      if (!_certRequestId || data.request_id === _certRequestId) {
        _certRequestId = data.request_id;
        _showCertInfoRequestCard(data.request_id, data.missing_info, data._notificationId);
      }
    });
  }
});

/**
 * Renders a card telling the student the advisor needs more information,
 * with the missing_info list and a text-area to reply.
 * notificationId — DB id to mark as read once shown (optional).
 */
function _showCertInfoRequestCard(requestId, missingInfo, notificationId) {
  _certRequestId = requestId;
  // Mark durable notification as read — student has now seen the card.
  if (notificationId && window.SNMarkRead) SNMarkRead(notificationId);
  const infoList = (missingInfo || [])
    .map((m) => `<li class="flex items-start gap-2 text-body-sm text-on-surface-variant"><span class="material-symbols-outlined text-amber-400 text-[16px] mt-0.5">info</span>${escapeHtml(m)}</li>`)
    .join("") || `<li class="text-body-sm text-on-surface-variant">Please provide additional information.</li>`;

  const cardId = nextId("cert-info-request");
  appendBotCard(`
    <div class="flex items-center gap-2 mb-3">
      <span class="material-symbols-outlined text-amber-400">pending_actions</span>
      <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface">Advisor needs more information</h4>
    </div>
    <p class="text-body-sm text-on-surface-variant mb-3">Your advisor reviewed your request and needs the following before they can proceed:</p>
    <ul class="space-y-2 mb-4">${infoList}</ul>
    <textarea
      id="cert-reply-text-${cardId}"
      placeholder="Type your reply here…"
      rows="3"
      class="w-full bg-surface-container-high/60 border border-white/10 rounded-xl px-4 py-3 text-body-sm text-on-surface placeholder:text-on-surface-variant/50 resize-none focus:outline-none focus:border-primary/50 mb-3"
    ></textarea>
    <button
      data-action="certificate-send-reply"
      data-card-id="${cardId}"
      class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all"
    >Send Reply</button>
  `, { id: cardId });
}

/**
 * Fetches the student's latest certificate/scholarship request and shows a
 * status card.  Replaces the old stub that just printed a "coming soon" message.
 */
async function certificateViewDetails(el) {
  lockControl(el);
  const pid = appendProcessing("Fetching your request status…");
  try {
    const user = window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
    const headers = {
      "Content-Type": "application/json",
      "X-User-Id":   String(user.id   || ""),
      "X-User-Role": String(user.role || "student"),
    };
    // GET /advisor/requests returns the student's own history when called as
    // a student (advisor_router filters by student_id automatically).
    const requests = await fetch(`${BASE_URL}/advisor/requests`, { headers }).then(async (r) => {
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `status ${r.status}`);
      return r.json();
    });

    removeNode(pid);

    if (!requests || requests.length === 0) {
      appendBotMessage("I couldn't find any certificate or scholarship request on your account. Please try submitting a new one.");
      appendMoreHelpPrompt();
      return;
    }

    // Most recent request first (router already sorts DESC).
    const req = requests[0];
    _certRequestId = req.request_id;

    // Fetch the graph state to check for a live wait_for_student interrupt.
    let graphState = null;
    try {
      const detail = await fetch(`${BASE_URL}/advisor/requests/${req.request_type}/${req.request_id}`, { headers })
        .then(async (r) => {
          if (!r.ok) return null;
          return r.json();
        });
      graphState = detail?.graph_state || null;
    } catch (_) { /* non-critical */ }

    // Check for live wait_for_student interrupt in graph state.
    const interrupts = graphState?.interrupts || [];
    const studentInterrupt = interrupts.find((iv) => iv?.type === "student_info_request");

    const STATUS_LABELS = {
      pending:      { icon: "radio_button_unchecked", color: "text-amber-400",  label: "Pending" },
      needs_review: { icon: "pending_actions",         color: "text-blue-400",   label: "Under Advisor Review" },
      in_progress:  { icon: "autorenew",               color: "text-primary",    label: "In Progress" },
      eligible:     { icon: "check_circle",             color: "text-emerald-400", label: "Approved — Eligible" },
      ineligible:   { icon: "cancel",                   color: "text-error",       label: "Not Eligible" },
      approved:     { icon: "check_circle",             color: "text-emerald-400", label: "Approved" },
      rejected:     { icon: "cancel",                   color: "text-error",       label: "Rejected" },
    };
    const meta = STATUS_LABELS[req.status] || { icon: "help", color: "text-on-surface-variant", label: req.status };

    const typeLabel = req.request_type === "certificate" ? "Certificate" : "Scholarship";
    const notes = req.recommendation
      ? `<p class="text-body-sm text-on-surface-variant mt-3 p-3 bg-surface-container-high/50 rounded-xl border border-white/10">${escapeHtml(req.recommendation)}</p>`
      : "";

    // If a wait_for_student interrupt is live, show the reply form inline.
    if (studentInterrupt) {
      const missingInfo = studentInterrupt.missing_info || [];
      removeNode(pid); // already removed above but guard anyway
      _showCertInfoRequestCard(req.request_id, missingInfo);
      return;
    }

    const decidedBy = req.decided_by ? `<p class="text-body-sm text-on-surface-variant/70 mt-2">Reviewed by: ${escapeHtml(req.decided_by)}</p>` : "";
    const decidedAt = req.decided_at ? `<p class="text-body-sm text-on-surface-variant/70">On: ${new Date(req.decided_at).toLocaleDateString()}</p>` : "";

    appendBotCard(`
      <div class="flex items-center gap-2 mb-3">
        <span class="material-symbols-outlined ${meta.color}">${meta.icon}</span>
        <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface">${typeLabel} Request — ${meta.label}</h4>
      </div>
      <div class="space-y-1 mb-2">
        <p class="text-body-sm text-on-surface-variant">Request #${req.request_id}</p>
        ${decidedBy}
        ${decidedAt}
      </div>
      ${notes}
      <p class="text-body-sm text-on-surface-variant/60 mt-3 text-[11px]">
        You'll be notified here if your advisor needs additional information.
      </p>
    `);
    appendMoreHelpPrompt();
  } catch (err) {
    removeNode(pid);
    appendBotMessage(`Sorry, couldn't load your request status. (${err.message})`);
    appendMoreHelpPrompt();
  }
}

/**
 * Submits the student's free-text reply to the advisor's "more info" request
 * via POST /advisor/requests/{id}/student-response.
 */
async function certificateSendReply(el) {
  lockControl(el);
  const cardId = el.dataset.cardId;
  const textarea = document.getElementById(`cert-reply-text-${cardId}`);
  const reply = textarea?.value?.trim();
  if (!reply) {
    textarea?.focus();
    el.disabled = false;
    el.classList.remove("opacity-50", "pointer-events-none");
    return;
  }
  if (!_certRequestId) {
    appendBotMessage("I lost track of which request to reply to — please refresh and try again.");
    return;
  }

  appendUserReply(reply);
  const pid = appendProcessing("Sending your reply to the advisor…");
  try {
    const user = window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
    const res = await fetch(`${BASE_URL}/advisor/requests/${_certRequestId}/student-response`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id":   String(user.id   || ""),
        "X-User-Role": String(user.role || "student"),
      },
      body: JSON.stringify({ response: reply }),
    });
    removeNode(pid);
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(_readableDetail(errBody.detail) || `status ${res.status}`);
    }
    appendBotCard(`
      <div class="flex items-center gap-2 mb-2">
        <span class="material-symbols-outlined text-emerald-400">check_circle</span>
        <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface">Reply sent!</h4>
      </div>
      <p class="text-body-sm text-on-surface-variant">Your response has been forwarded to the advisor. They'll review it and you'll be notified here if anything else is needed.</p>
    `);
    appendMoreHelpPrompt();
  } catch (err) {
    removeNode(pid);
    appendBotMessage(`Sorry, couldn't send your reply. (${err.message})`);
    appendMoreHelpPrompt();
  }
}

/* ---------------------------------------------------------------------
   FLOW: My Cases & Appeals (DESIGN.md §12)
--------------------------------------------------------------------- */
function startCasesFlow(triggerEl) {
  lockControl(triggerEl);
  _activeCourseId = null; // leaving material flow context — don't route free text there
  _currentFlow = "cases";
  appendUserReply("⚠️ My Cases & Appeals");
  appendBotCard(`
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-2">Let's check your cases &amp; appeals.</h4>
    <button data-action="cases-view" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">View My Cases</button>
  `);
}

async function casesView(el) {
  lockControl(el);
  const pid = appendProcessing("Loading your cases...");
  try {
    const _user = window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
    const res = await fetch(`${BASE_URL}/academic-integrity/cases`, {
      headers: {
        "Content-Type": "application/json",
        "X-User-Id":   String(_user.id   || ""),
        "X-User-Role": String(_user.role || "student"),
      },
    });
    removeNode(pid);
    const cases = res.ok ? await res.json() : [];
    if (!cases || cases.length === 0) {
      appendBotCard(`
        <div class="flex items-center gap-2">
          <span class="material-symbols-outlined text-emerald-400">check_circle</span>
          <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface">You're all clear!</h4>
        </div>
        <p class="text-body-sm text-on-surface-variant mt-2">You don't have any active cases or appeals.</p>
      `);
      appendMoreHelpPrompt();
      return;
    }
    // Render each case as a card; student can submit appeal if awaiting_appeal
    cases.forEach((c) => {
      const statusLabel = c.status === "awaiting_appeal" ? "🟡 Awaiting Your Appeal"
                        : c.status === "closed"          ? "✅ Closed"
                        : c.status === "under_review"    ? "🔵 Under Review"
                        : c.status;
      const bgClass = c.status === "awaiting_appeal" ? "bg-amber-400/10 border-amber-400/30 text-amber-300"
                    : c.status === "closed"           ? "bg-emerald-400/10 border-emerald-400/30 text-emerald-300"
                    : "bg-primary/10 border-primary/30 text-primary";
      appendBotCard(`
        <div class="flex items-center justify-between mb-2">
          <span class="text-[11px] font-label-caps text-on-surface-variant/70 uppercase tracking-wide flex items-center gap-1.5">
            <span class="material-symbols-outlined text-[16px] text-amber-400">warning</span> Case #${c.case_id}
          </span>
          <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full ${bgClass} border text-[11px] font-medium">${statusLabel}</span>
        </div>
        <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-1">Academic Integrity Review</h4>
        <p class="text-body-sm text-on-surface-variant mb-4">${escapeHtml(c.description || "")}</p>
        ${c.status === "awaiting_appeal"
          ? `<button data-action="cases-view-case" data-case-id="${c.case_id}" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">Submit Appeal</button>`
          : ""}
      `);
    });
    appendMoreHelpPrompt();
  } catch (err) {
    removeNode(pid);
    appendBotMessage(`Sorry, I couldn't load your cases right now. (${err.message})`);
    appendMoreHelpPrompt();
  }
}

function casesViewCase(el) {
  lockControl(el);
  const caseId = el.dataset.caseId || "";
  const cardId = nextId("appeal-form");
  appendBotCard(
    `
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-1">Submit Appeal</h4>
    <p class="text-body-sm text-on-surface-variant mb-3">Tell us why you'd like to appeal this case.</p>
    <textarea data-role="appeal-text" rows="4" placeholder="Draft your appeal here..." class="w-full bg-surface-container-low/60 border border-white/10 focus:border-primary/50 outline-none rounded-xl px-4 py-3 text-body-sm text-on-surface placeholder:text-on-surface-variant/40 resize-none mb-4"></textarea>
    <button data-action="cases-submit-appeal" data-case-id="${escapeHtml(caseId)}" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">Submit Appeal</button>
  `,
    { id: cardId }
  );
}

async function casesSubmitAppeal(el) {
  const card = el.closest(".flex.gap-4.items-end");
  const textarea = card?.querySelector('[data-role="appeal-text"]');
  const text    = textarea?.value.trim();
  const caseId  = el.dataset.caseId;
  if (!text) { textarea?.focus(); return; }
  if (!caseId) { appendBotMessage("Unable to identify case — please reload and try again."); return; }
  lockControl(el);
  if (textarea) textarea.disabled = true;
  const pid = appendProcessing("Submitting your appeal...");
  try {
    const _user = window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
    const res = await fetch(`${BASE_URL}/academic-integrity/cases/${caseId}/appeal`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id":   String(_user.id   || ""),
        "X-User-Role": String(_user.role || "student"),
      },
      body: JSON.stringify({ appeal_argument: text }),
    });
    removeNode(pid);
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(_readableDetail(errBody.detail) || `status ${res.status}`);
    }
    appendBotCard(`
      <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-2">Your appeal has been submitted.</h4>
      <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">We'll review it and let you know when a decision is available.</p>
      <span class="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-400/10 border border-amber-400/30 text-amber-300 text-body-sm font-medium">
        <span class="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse"></span> Under Review
      </span>
    `);
    appendMoreHelpPrompt();
  } catch (err) {
    removeNode(pid);
    appendBotMessage(`Sorry, couldn't submit your appeal. (${err.message})`);
    appendMoreHelpPrompt();
  }
}

/* ---------------------------------------------------------------------
   Dispatchers
--------------------------------------------------------------------- */
const FLOW_STARTERS = {
  track: startTrackFlow,
  material: startMaterialFlow,
  assessment: startAssessmentFlow,
  certificate: startCertificateFlow,
  cases: startCasesFlow,
};

const ACTION_HANDLERS = {
  "track-start": trackStart,
  "track-view-details": trackViewDetails,
  "assessment-pick-topic": assessmentPickTopic,
  "assessment-submit-answer": assessmentSubmitAnswer,
  "material-course": materialCourse,
  "material-topic": materialTopic,
  "material-ask": materialAsk,
  "material-other": materialOther,
  "certificate-start": certificateStart,
  "certificate-view-details": certificateViewDetails,
  "certificate-send-reply": certificateSendReply,
  "cases-view": casesView,
  "cases-view-case": casesViewCase,
  "cases-submit-appeal": casesSubmitAppeal,
};

// A single delegated listener handles every control ever injected into
// the thread — including rows added later by appendMoreHelpPrompt().
thread.addEventListener("click", (e) => {
  const flowBtn = e.target.closest("[data-flow]");
  if (flowBtn && !flowBtn.disabled) {
    const starter = FLOW_STARTERS[flowBtn.dataset.flow];
    if (starter) starter(flowBtn);
    return;
  }
  const actionBtn = e.target.closest("[data-action]");
  if (actionBtn && !actionBtn.disabled) {
    const handler = ACTION_HANDLERS[actionBtn.dataset.action];
    if (handler) handler(actionBtn);
  }
});

/* ---------------------------------------------------------------------
   Free-text fallback (secondary interaction — DESIGN.md §6)
--------------------------------------------------------------------- */
async function sendMessage(text) {
  if (!text || !text.trim()) return;
  appendUserReply(text);
  input.value = "";
  typingIndicator.classList.remove("hidden");
  typingIndicator.classList.add("flex");
  thread.appendChild(typingIndicator);
  scrollToBottom();

  try {
    const _user = window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
    const authHeaders = {
      "Content-Type": "application/json",
      "X-User-Id":   String(_user.id   || ""),
      "X-User-Role": String(_user.role || "student"),
    };

    // Only route to /teaching/chat when we're actually still in the
    // material flow AND have a course selected — otherwise use /ai/chat
    // for the general assistant. Checking _currentFlow (not just
    // _activeCourseId) means a stale course id from an earlier material
    // session can never leak into another flow's free text.
    let endpoint, body;
    if (_currentFlow === "material" && _activeCourseId) {
      endpoint = `${BASE_URL}/teaching/chat`;
      body     = JSON.stringify({ course_id: _activeCourseId, question: text });
    } else {
      endpoint = `${BASE_URL}/ai/chat`;
      body     = JSON.stringify({ message: text });
    }

    const res = await fetch(endpoint, { method: "POST", headers: authHeaders, body });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(_readableDetail(errBody.detail) || `chat request failed (${res.status})`);
    }
    const data = await res.json();
    typingIndicator.classList.add("hidden");
    typingIndicator.classList.remove("flex");
    // Both /teaching/chat and /ai/chat return { answer, sources }
    appendBotMessage(data.answer ?? data.reply ?? "…");
  } catch (err) {
    console.error("Nova chat error:", err.message);
    typingIndicator.classList.add("hidden");
    typingIndicator.classList.remove("flex");
    appendBotMessage(`Sorry, I couldn't reach the server right now. Please try again. (${err.message})`);
  }
}

sendBtn.addEventListener("click", () => sendMessage(input.value));
input.addEventListener("keypress", (e) => {
  if (e.key === "Enter") sendMessage(input.value);
});

// If the dashboard linked here with ?prompt=..., either jump straight
// into the matching guided flow, or fall back to a free-text send.
const PROMPT_TO_FLOW = {
  "Can you recommend a track for me?": "track",
  "I have a question about a course material.": "material",
  "I'd like to start an assessment.": "assessment",
  "Tell me about certificates and scholarships.": "certificate",
  "I need to open a case or appeal.": "cases",
};

const params = new URLSearchParams(window.location.search);
const prefill = params.get("prompt");
if (prefill) {
  const flowKey = PROMPT_TO_FLOW[prefill];
  if (flowKey) {
    const starterBtn = document.querySelector(`#quick-actions-start [data-flow="${flowKey}"]`);
    FLOW_STARTERS[flowKey](starterBtn);
  } else {
    sendMessage(prefill);
  }
}

// The auth-guard script (loaded before this file) already redirected
// anyone without a valid session and set window.currentUser. Use that
// first — it's the real logged-in user, not a demo placeholder.
function applyLoggedInUser() {
  const user = window.currentUser;
  if (!user) return;
  const fullName = user.name || user.email || "Student";
  const firstName = fullName.split(" ")[0];
  document.getElementById("student-name").textContent = fullName;
  if (user.track) document.getElementById("student-track").textContent = user.track;
  if (user.avatarUrl) document.getElementById("student-avatar").src = user.avatarUrl;
  const greeting = document.getElementById("nova-greeting-name");
  if (greeting) greeting.textContent = `Hi ${firstName}! 👋`;
}
applyLoggedInUser();

// Header profile info (best-effort; the backend can override with
// richer profile data once /api/dashboard is wired up).
async function loadProfile() {
  try {
    const _user = window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
    const res = await fetch(`${EXPRESS_URL}/api/dashboard`, {
      credentials: "include",
      headers: {
        "X-User-Id":   String(_user.id   || ""),
        "X-User-Role": String(_user.role || "student"),
      },
    });
    if (!res.ok) throw new Error("no session yet");
    const data = await res.json();
    if (data.student?.name) {
      document.getElementById("student-name").textContent = data.student.name;
      const greeting = document.getElementById("nova-greeting-name");
      if (greeting) greeting.textContent = `Hi ${data.student.name.split(" ")[0]}! 👋`;
    }
    if (data.student?.track)      document.getElementById("student-track").textContent  = data.student.track;
    if (data.student?.avatarUrl)  document.getElementById("student-avatar").src         = data.student.avatarUrl;
  } catch (err) {
    console.info("Profile header: using session data only —", err.message);
  }
}
loadProfile();

document.getElementById("logout-link").addEventListener("click", async (e) => {
  e.preventDefault();
  try {
    await fetch(`${EXPRESS_URL}/api/auth/logout`, { method: "POST", credentials: "include" });
  } catch (err) {
    console.info("Logout: backend not reachable —", err.message);
  } finally {
    // Clears localStorage("user") too and redirects to the real
    // login path (../login.html here was pointing at a non-existent file).
    window.BrightPeakAuth.logout();
  }
});