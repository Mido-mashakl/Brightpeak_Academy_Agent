// AI Assistant (Nova) page logic.
// BASE_URL: point this at your phase-4 backend origin once the chat/RAG router is ready.
const BASE_URL = "http://localhost:3000";

const thread = document.getElementById("chat-thread");
const typingIndicator = document.getElementById("typing-indicator");
const input = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const NOVA_AVATAR = "../../assets/images/student/nova-mascot.png";

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

function appendBotMessage(text) {
  const row = document.createElement("div");
  row.className = "flex gap-4 items-end slide-up";
  row.innerHTML = `
    <img src="${NOVA_AVATAR}" alt="Nova" class="w-8 h-8 rounded-full bg-surface-container-high object-cover shrink-0 border border-white/10 shadow-[0_4px_12px_rgba(0,0,0,0.2)]"/>
    <div class="bg-surface-container-high/80 backdrop-blur-md rounded-2xl rounded-bl-sm px-5 py-4 max-w-[85%] border border-white/10 shadow-lg text-body-md text-on-surface leading-relaxed">
      ${escapeHtml(text)}
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

  try {
    const res = await fetch(`${BASE_URL}/api/nova/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ message: text }),
    });
    if (!res.ok) throw new Error(`chat request failed (${res.status})`);
    const data = await res.json();
    typingIndicator.classList.add("hidden");
    appendBotMessage(data.reply ?? "…");
  } catch (err) {
    console.info("Nova chat: backend not reachable, showing demo reply —", err.message);
    setTimeout(() => {
      typingIndicator.classList.add("hidden");
      appendBotMessage("I'm running on demo data right now — once the chat endpoint is live I'll answer this for real.");
    }, 900);
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

// The auth-guard script (loaded before this file) already redirected
// anyone without a valid session and set window.currentUser. Use that
// first — it's the real logged-in user, not a demo placeholder.
function applyLoggedInUser() {
  const user = window.currentUser;
  if (!user) return;
  document.getElementById("student-name").textContent = user.name || user.email || "Student";
  if (user.track) document.getElementById("student-track").textContent = user.track;
  if (user.avatarUrl) document.getElementById("student-avatar").src = user.avatarUrl;
}
applyLoggedInUser();

// Header profile info (best-effort; the backend can override with
// richer profile data once /api/dashboard is wired up).
async function loadProfile() {
  try {
    const res = await fetch(`${BASE_URL}/api/dashboard`, { credentials: "include" });
    if (!res.ok) throw new Error("no session yet");
    const data = await res.json();
    if (data.student?.name) document.getElementById("student-name").textContent = data.student.name;
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
    await fetch(`${BASE_URL}/api/auth/logout`, { method: "POST", credentials: "include" });
  } catch (err) {
    console.info("Logout: backend not reachable —", err.message);
  } finally {
    // Clears localStorage("user") too and redirects to the real
    // login path (../login.html here was pointing at a non-existent file).
    window.BrightPeakAuth.logout();
  }
});
