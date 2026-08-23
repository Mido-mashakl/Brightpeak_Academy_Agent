// AI Assistant (Nova) page logic.
// BASE_URL: point this at your phase-4 backend origin once the chat/RAG router is ready.
// Nova chat goes to FastAPI (port 8000); dashboard/logout stay on Express (port 3000).
const BASE_URL      = "http://localhost:8000";
const EXPRESS_URL   = "http://localhost:3000";

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
  appendUserReply("🎯 Recommend my Track");
  appendBotCard(`
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-2">🎯 Let's find the right track for you!</h4>
    <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">I'll look at your academic progress and help you identify the track that best matches your strengths.</p>
    <button data-action="track-start" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">Start Recommendation</button>
  `);
}

function trackStart(el) {
  lockControl(el);
  const pid = appendProcessing("Analyzing your academic profile... ✨");
  setTimeout(() => {
    removeNode(pid);
    appendBotCard(`
      <div class="flex items-center justify-between mb-4">
        <h4 class="font-headline-md text-[18px] leading-[24px] font-semibold text-on-surface flex items-center gap-2">🎯 Your Recommended Track</h4>
      </div>
      <p class="text-headline-md text-[20px] font-semibold text-primary mb-1">Data Science</p>
      <div class="flex items-center gap-2 mb-3">
        <span class="text-secondary font-semibold text-body-sm">94% AI Match</span>
      </div>
      <div class="h-2 w-full bg-surface-container-highest rounded-full overflow-hidden mb-4">
        <div class="h-full bg-gradient-to-r from-primary to-secondary rounded-full shadow-[0_0_12px_rgba(192,193,255,0.6)]" style="width:94%;"></div>
      </div>
      <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">Your academic performance and quantitative skills make this a strong match for you.</p>
      <button data-action="track-view-details" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">View Details</button>
    `);
  }, 1400);
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
   FLOW: Start an Assessment (DESIGN.md §9)
--------------------------------------------------------------------- */
const ASSESSMENT_QUESTIONS = [
  { q: "Which of the following best describes the core principle of Neural Network backpropagation?", options: ["Forward passing inputs directly to outputs without intermediate calculations.", "Calculating the gradient of the loss function with respect to each weight by the chain rule.", "Randomly dropping nodes during training to prevent overfitting.", "Updating weights entirely randomly until the error rate decreases."] },
  { q: "What is the primary purpose of a control group in an experiment?", options: ["To make the experiment take longer", "To provide a baseline for comparison", "To increase the sample size", "To reduce the cost of the study"] },
  { q: "In data science, what does 'overfitting' typically indicate?", options: ["The model performs well on new, unseen data", "The model is too simple to capture patterns", "The model fits the training data too closely and generalizes poorly", "The dataset is too small to train on"] },
  { q: "Which structure is most associated with sequential data processing?", options: ["Convolutional Neural Network", "Recurrent Neural Network", "Decision Tree", "K-Means Clustering"] },
  { q: "What does 'normalization' typically achieve when preparing a dataset?", options: ["It removes all outliers automatically", "It rescales features to a comparable range", "It guarantees a higher model accuracy", "It converts categorical data into images"] },
  { q: "Which metric is most appropriate for an imbalanced classification problem?", options: ["Raw accuracy", "F1 score", "Mean squared error", "R-squared"] },
  { q: "What is the main advantage of using version control in a group project?", options: ["It automatically writes documentation", "It tracks changes and enables collaboration without overwriting work", "It compiles the code faster", "It removes the need for testing"] },
  { q: "Why is peer review valuable in an academic or research setting?", options: ["It guarantees the work is free of all errors", "It helps catch gaps and improve quality through outside perspective", "It is only required for published papers", "It replaces the need for citations"] },
];

let assessmentIndex = 0;
let assessmentScore = 0;

function startAssessmentFlow(triggerEl) {
  lockControl(triggerEl);
  appendUserReply("🧠 Start an Assessment");
  appendBotCard(`
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-2">Ready for a quick assessment?</h4>
    <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">I'll ask you a few questions and adapt them based on your answers.</p>
    <button data-action="assessment-start" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">Start Assessment</button>
  `);
}

function assessmentStart(el) {
  lockControl(el);
  assessmentIndex = 0;
  assessmentScore = 0;
  renderAssessmentQuestion();
}

function renderAssessmentQuestion() {
  const total = ASSESSMENT_QUESTIONS.length;
  const current = ASSESSMENT_QUESTIONS[assessmentIndex];
  const progressPct = Math.round(((assessmentIndex + 1) / total) * 100);
  const cardId = nextId("assessment-card");
  const optionsHtml = current.options
    .map(
      (opt, i) => `
      <label class="block cursor-pointer group">
        <input class="peer sr-only" type="radio" name="${cardId}-opt" value="${i}"/>
        <div class="w-full p-4 rounded-xl border border-white/10 bg-surface-container-low/50 group-hover:bg-white/5 group-hover:border-white/20 peer-checked:bg-primary/10 peer-checked:border-primary/50 transition-all duration-200 flex gap-3 items-start">
          <div class="w-5 h-5 rounded-full border-2 border-on-surface-variant/40 peer-checked:border-primary flex-shrink-0 mt-0.5 relative flex items-center justify-center">
            <div class="w-2 h-2 rounded-full bg-primary opacity-0 peer-checked:opacity-100 transition-opacity"></div>
          </div>
          <div class="text-body-sm text-on-surface-variant group-hover:text-on-surface peer-checked:text-on-surface transition-colors">${escapeHtml(opt)}</div>
        </div>
      </label>`
    )
    .join("");

  appendBotCard(
    `
    <div class="h-1 w-full bg-surface-container-highest rounded-full overflow-hidden mb-4">
      <div class="h-full bg-gradient-to-r from-primary to-secondary rounded-full" style="width:${progressPct}%;"></div>
    </div>
    <span class="inline-block mb-3 px-3 py-1 rounded-md bg-primary/10 border border-primary/20 text-primary text-[11px] font-label-caps tracking-wide">🧠 Question ${assessmentIndex + 1} of ${total}</span>
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-4">${escapeHtml(current.q)}</h4>
    <div class="space-y-3 mb-5">${optionsHtml}</div>
    <button data-action="assessment-submit" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">Submit Answer</button>
  `,
    { id: cardId }
  );
}

function assessmentSubmit(el) {
  const card = el.closest(".flex.gap-4.items-end");
  const checked = card?.querySelector("input[type=radio]:checked");
  if (!checked) {
    el.classList.add("animate-pulse");
    setTimeout(() => el.classList.remove("animate-pulse"), 400);
    return;
  }
  lockControl(el);
  card.querySelectorAll("input[type=radio]").forEach((r) => (r.disabled = true));
  // Demo scoring: option index 1 counted as "correct" for variety.
  if (checked.value === "1") assessmentScore += 1;

  assessmentIndex += 1;
  if (assessmentIndex < ASSESSMENT_QUESTIONS.length) {
    renderAssessmentQuestion();
    return;
  }

  // Demo scoring only — the real assessment engine will return the
  // actual score once that flow is wired to the backend.
  const pct = Math.round((assessmentScore / ASSESSMENT_QUESTIONS.length) * 100);
  appendBotCard(`
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-2">✨ Assessment Complete</h4>
    <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">You've completed the assessment.</p>
    <p class="text-headline-md text-[20px] font-semibold text-primary mb-4">Score: ${pct}%</p>
    <button data-action="assessment-view-results" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">View Results</button>
  `);
}

function assessmentViewResults(el) {
  lockControl(el);
  appendBotCard(`
    <div class="flex items-center gap-2 mb-2">
      <span class="text-lg">🕐</span>
      <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface">Your assessment is under review</h4>
    </div>
    <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">We'll let you know when the final result is available.</p>
    <span class="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-400/10 border border-amber-400/30 text-amber-300 text-body-sm font-medium">
      <span class="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse"></span> Under Review
    </span>
  `);
  appendMoreHelpPrompt();
}

/* ---------------------------------------------------------------------
   FLOW: Ask about course material (DESIGN.md §10)
--------------------------------------------------------------------- */
function startMaterialFlow(triggerEl) {
  lockControl(triggerEl);
  appendUserReply("📖 Ask about course material");
  appendBotCard(`
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-4">📖 What course would you like help with?</h4>
    <div class="grid grid-cols-2 gap-3">
      <button data-action="material-course" data-course="Advanced Bio-Eng" class="px-4 py-3 rounded-xl bg-surface-container-low/60 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface text-left">Advanced Bio-Eng</button>
      <button data-action="material-course" data-course="Neural Networks" class="px-4 py-3 rounded-xl bg-surface-container-low/60 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface text-left">Neural Networks</button>
      <button data-action="material-course" data-course="Data Science" class="px-4 py-3 rounded-xl bg-surface-container-low/60 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface text-left">Data Science</button>
      <button data-action="material-other" class="px-4 py-3 rounded-xl bg-surface-container-low/60 border border-white/10 hover:border-primary/40 hover:bg-surface-container-high transition-all text-body-sm font-medium text-on-surface text-left">Other...</button>
    </div>
  `);
}

function materialCourse(el) {
  lockControl(el);
  const course = el.dataset.course;
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

function materialAsk(el) {
  const card = el.closest(".flex.gap-4.items-end");
  const topicInput = card?.querySelector('[data-role="material-topic-input"]');
  const topic = topicInput?.value.trim();
  if (!topic) {
    topicInput?.focus();
    return;
  }
  lockControl(el);
  if (topicInput) topicInput.disabled = true;
  appendUserReply(topic);
  const pid = appendProcessing("Looking through your course material... ✨");
  setTimeout(() => {
    removeNode(pid);
    appendBotMessage(
      `Here's a quick overview of "${topic}" in ${el.dataset.course} — once the course-material RAG endpoint is connected, I'll pull this directly from your syllabus and readings instead of this demo answer.`
    );
    appendMoreHelpPrompt();
  }, 1200);
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
  appendUserReply("🎓 Certificate & Scholarship");
  appendBotCard(`
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-2">Let's check your eligibility.</h4>
    <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">I'll review your academic information and the current requirements.</p>
    <button data-action="certificate-start" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">Check My Eligibility</button>
  `);
}

function certificateStart(el) {
  lockControl(el);
  const pid = appendProcessing("Checking your eligibility...");
  setTimeout(() => {
    removeNode(pid);
    // Demo payload — swap for the real eligibility response once the
    // certificate/scholarship advisory flow is wired to the backend.
    const eligible = true;
    if (eligible) {
      appendBotCard(`
        <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-3">✨ You're Eligible!</h4>
        <ul class="space-y-2 mb-4">
          <li class="flex items-center gap-2 text-body-sm text-on-surface-variant"><span class="material-symbols-outlined text-[18px] text-emerald-400">check_circle</span> Academic standing</li>
          <li class="flex items-center gap-2 text-body-sm text-on-surface-variant"><span class="material-symbols-outlined text-[18px] text-emerald-400">check_circle</span> Required credits</li>
          <li class="flex items-center gap-2 text-body-sm text-on-surface-variant"><span class="material-symbols-outlined text-[18px] text-emerald-400">check_circle</span> Attendance requirements</li>
        </ul>
        <button data-action="certificate-view-details" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">View Details</button>
      `);
    } else {
      appendBotCard(`
        <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-3">You're not eligible yet</h4>
        <ul class="space-y-2 mb-4">
          <li class="flex items-center gap-2 text-body-sm text-on-surface-variant"><span class="material-symbols-outlined text-[18px] text-amber-400">radio_button_unchecked</span> Required credits</li>
          <li class="flex items-center gap-2 text-body-sm text-on-surface-variant"><span class="material-symbols-outlined text-[18px] text-amber-400">radio_button_unchecked</span> Attendance requirement</li>
        </ul>
        <button data-action="certificate-view-details" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">View Requirements</button>
      `);
    }
  }, 1200);
}

function certificateViewDetails(el) {
  lockControl(el);
  appendBotMessage("Opening the full certificate & scholarship details will be available once that module is connected — for now this confirms your current status. 🎓");
  appendMoreHelpPrompt();
}

/* ---------------------------------------------------------------------
   FLOW: My Cases & Appeals (DESIGN.md §12)
--------------------------------------------------------------------- */
function startCasesFlow(triggerEl) {
  lockControl(triggerEl);
  appendUserReply("⚠️ My Cases & Appeals");
  appendBotCard(`
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-2">Let's check your cases &amp; appeals.</h4>
    <button data-action="cases-view" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">View My Cases</button>
  `);
}

function casesView(el) {
  lockControl(el);
  // Demo payload — swap for the real cases/appeals response once the
  // academic-integrity / appeals flow is wired to the backend.
  const hasCase = true;
  if (!hasCase) {
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
  appendBotCard(`
    <div class="flex items-center justify-between mb-2">
      <span class="text-[11px] font-label-caps text-on-surface-variant/70 uppercase tracking-wide flex items-center gap-1.5"><span class="material-symbols-outlined text-[16px] text-amber-400">warning</span> Case #204</span>
      <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-400/10 border border-amber-400/30 text-amber-300 text-[11px] font-medium">🟡 Awaiting Your Appeal</span>
    </div>
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-4">Academic Integrity Review</h4>
    <button data-action="cases-view-case" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">View Case</button>
  `);
}

function casesViewCase(el) {
  lockControl(el);
  const cardId = nextId("appeal-form");
  appendBotCard(
    `
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-1">Submit Appeal</h4>
    <p class="text-body-sm text-on-surface-variant mb-3">Tell us why you'd like to appeal.</p>
    <textarea data-role="appeal-text" rows="4" placeholder="Draft your appeal here..." class="w-full bg-surface-container-low/60 border border-white/10 focus:border-primary/50 outline-none rounded-xl px-4 py-3 text-body-sm text-on-surface placeholder:text-on-surface-variant/40 resize-none mb-4"></textarea>
    <button data-action="cases-submit-appeal" class="px-5 py-2.5 rounded-xl bg-gradient-to-br from-primary to-inverse-primary text-on-primary text-body-sm font-semibold shadow-[0_0_16px_rgba(192,193,255,0.25)] hover:shadow-[0_0_24px_rgba(192,193,255,0.4)] transition-all">Submit Appeal</button>
  `,
    { id: cardId }
  );
}

function casesSubmitAppeal(el) {
  const card = el.closest(".flex.gap-4.items-end");
  const textarea = card?.querySelector('[data-role="appeal-text"]');
  const text = textarea?.value.trim();
  if (!text) {
    textarea?.focus();
    return;
  }
  lockControl(el);
  if (textarea) textarea.disabled = true;
  appendBotCard(`
    <h4 class="font-headline-md text-[16px] leading-[22px] font-semibold text-on-surface mb-2">Your appeal has been submitted.</h4>
    <p class="text-body-sm text-on-surface-variant mb-4 leading-relaxed">We'll review it and let you know when a decision is available.</p>
    <span class="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-400/10 border border-amber-400/30 text-amber-300 text-body-sm font-medium">
      <span class="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse"></span> Under Review
    </span>
  `);
  appendMoreHelpPrompt();
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
  "assessment-start": assessmentStart,
  "assessment-submit": assessmentSubmit,
  "assessment-view-results": assessmentViewResults,
  "material-course": materialCourse,
  "material-topic": materialTopic,
  "material-ask": materialAsk,
  "material-other": materialOther,
  "certificate-start": certificateStart,
  "certificate-view-details": certificateViewDetails,
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
    const res = await fetch(`${BASE_URL}/ai/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id":   String(_user.id   || ""),
        "X-User-Role": String(_user.role || "student"),
      },
      body: JSON.stringify({ message: text }),
    });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.detail || `chat request failed (${res.status})`);
    }
    const data = await res.json();
    typingIndicator.classList.add("hidden");
    typingIndicator.classList.remove("flex");
    // Backend returns { answer, sources } per ai_assistant_router.py
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
    const res = await fetch(`${EXPRESS_URL}/api/dashboard`, { credentials: "include" });
    if (!res.ok) throw new Error("no session yet");
    const data = await res.json();
    if (data.student?.name) {
      document.getElementById("student-name").textContent = data.student.name;
      const greeting = document.getElementById("nova-greeting-name");
      if (greeting) greeting.textContent = `Hi ${data.student.name.split(" ")[0]}! 👋`;
    }
    if (data.student?.track) document.getElementById("student-track").textContent = data.student.track;
    if (data.student?.avatarUrl) document.getElementById("student-avatar").src = data.student.avatarUrl;
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
