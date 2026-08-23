// AI Assistant (Nova) page logic.
//
// BASE_URL points at the FastAPI backend (port 8000), same as
// department-head-api.js and teaching_router.py — this platform's RAG
// and State-Graph endpoints all live there, not on the Express server
// (port 3000, which only handles login + static file serving). See
// phase-4/backend/main.py and routers/ai_assistant_router.py.
const BASE_URL = "http://localhost:8000";

const thread = document.getElementById("chat-thread");
const typingIndicator = document.getElementById("typing-indicator");
const input = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const NOVA_AVATAR = "../assets/nova-mascot.png";

// The logged-in student — required to call /ai/chat (course-scoped RAG
// needs to know whose enrollments to search). No session/demo fallback:
// if there's no real logged-in student, the page can't chat for real.
const currentUser = (window.BrightPeakAuth && window.BrightPeakAuth.getUser()) || null;

function scrollToBottom() {
  thread.parentElement.scrollTop = thread.parentElement.scrollHeight;
}

function appendUserMessage(text) {
  const row = document.createElement("div");
  row.className = "flex gap-4 items-end justify-end slide-up";
  row.innerHTML = `
    <div class="bg-gradient-to-br from-primary-container to-secondary-container rounded-2xl rounded-br-sm px-5 py-4 max-w-[85%] shadow-[0_8px_24px_rgba(128,131,255,0.2)] text-body-md text-on-primary-container leading-relaxed">
      ${escapeHtml(text)}
    </div>
    <img alt="Profile" class="w-8 h-8 rounded-full border border-primary/30 object-cover shrink-0 shadow-[0_4px_12px_rgba(0,0,0,0.2)]" id="user-avatar-msg" src="${document.getElementById("student-avatar").src}"/>
  `;
  thread.appendChild(row);
  scrollToBottom();
}

function appendBotMessage(text, { sources = [], isError = false } = {}) {
  const row = document.createElement("div");
  row.className = "flex gap-4 items-end slide-up";
  const sourcesHtml = sources.length
    ? `<div class="mt-2 text-body-sm text-on-surface-variant">Sources: ${sources.map(escapeHtml).join(", ")}</div>`
    : "";
  row.innerHTML = `
    <img src="${NOVA_AVATAR}" alt="Nova" class="w-8 h-8 rounded-full bg-surface-container-high object-cover shrink-0 border border-white/10 shadow-[0_4px_12px_rgba(0,0,0,0.2)]"/>
    <div class="${isError ? "bg-error-container/80 border-error/30" : "bg-surface-container-high/80 border-white/10"} backdrop-blur-md rounded-2xl rounded-bl-sm px-5 py-4 max-w-[85%] border shadow-lg text-body-md ${isError ? "text-on-error-container" : "text-on-surface"} leading-relaxed">
      ${escapeHtml(text)}
      ${sourcesHtml}
    </div>
  `;
  thread.appendChild(row);
  scrollToBottom();
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function sendMessage(text) {
  if (!text || !text.trim()) return;
  appendUserMessage(text);
  input.value = "";
  typingIndicator.classList.remove("hidden");
  scrollToBottom();

  if (!currentUser || currentUser.role !== "student") {
    typingIndicator.classList.add("hidden");
    appendBotMessage("You need to be logged in as a student to use the AI Assistant.", { isError: true });
    return;
  }

  try {
    const res = await fetch(`${BASE_URL}/ai/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-User-Id": String(currentUser.id),
        "X-User-Role": "student",
      },
      body: JSON.stringify({ message: text }),
    });
    typingIndicator.classList.add("hidden");

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Request failed (${res.status})`);
    }
    const data = await res.json();
    appendBotMessage(data.answer, { sources: data.sources || [] });
  } catch (err) {
    // Real error state — NEVER a fake/demo answer. If the backend is
    // unreachable, down, or misconfigured (e.g. missing GEMINI_API_KEY),
    // the student sees that honestly instead of a canned reply.
    console.error("AI Assistant chat failed:", err);
    typingIndicator.classList.add("hidden");
    appendBotMessage("AI Assistant is currently unavailable. Please try again.", { isError: true });
  }
}

sendBtn.addEventListener("click", () => sendMessage(input.value));
input.addEventListener("keypress", (e) => {
  if (e.key === "Enter") sendMessage(input.value);
});

document.querySelectorAll(".quick-action").forEach((btn) => {
  btn.addEventListener("click", () => sendMessage(btn.dataset.prompt));
});

// If the dashboard linked here with ?prompt=..., send it automatically.
const params = new URLSearchParams(window.location.search);
const prefill = params.get("prompt");
if (prefill) {
  sendMessage(prefill);
}

// Header profile info — from the real logged-in session (see
// frontend/shared/auth.js), not a demo/static fallback.
function applyLoggedInUser() {
  if (!currentUser) return;
  document.getElementById("student-name").textContent = currentUser.name || currentUser.email || "Student";
  if (currentUser.track) document.getElementById("student-track").textContent = currentUser.track;
  if (currentUser.avatarUrl) document.getElementById("student-avatar").src = currentUser.avatarUrl;
}
applyLoggedInUser();

document.getElementById("logout-link").addEventListener("click", (e) => {
  e.preventDefault();
  window.BrightPeakAuth.logout();
});