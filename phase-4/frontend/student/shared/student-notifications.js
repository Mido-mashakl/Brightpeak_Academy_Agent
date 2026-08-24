// =========================================================
// student-notifications.js
// Shared notification layer for all student pages.
//
// TWO delivery paths for the same events:
//   1) SSE (real-time) — open if the page is already loaded
//      when the advisor acts. Uses the existing
//      GET /advisor/notifications/student-stream endpoint.
//   2) DB poll (durable) — called on every page load via
//      GET /notifications so events missed while offline
//      surface automatically.
//
// Both paths call the same handler registered via
//   window.SNBus.on("more_info_requested", fn)
//   window.SNBus.on("assessment_requested", fn)
// so each page only needs one handler per event type,
// regardless of which path delivered it.
//
// Load this AFTER shared/auth.js + student/shared/auth-guard.js
// but BEFORE the page's own script.
// =========================================================

(function () {
  const BASE_URL = "http://localhost:8000";

  // ---- Tiny event bus ----
  const _handlers = {};
  const SNBus = {
    on(event, fn) {
      (_handlers[event] = _handlers[event] || []).push(fn);
    },
    emit(event, data) {
      (_handlers[event] || []).forEach((fn) => {
        try { fn(data); } catch (e) { console.error("[SNBus] handler error:", e); }
      });
    },
  };
  window.SNBus = SNBus;

  // ---- Auth headers ----
  function _authHeaders() {
    const user = window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
    return {
      "Content-Type": "application/json",
      "X-User-Id":   String(user.id   || ""),
      "X-User-Role": String(user.role || "student"),
    };
  }
  function _user() {
    return window.currentUser || JSON.parse(localStorage.getItem("user") || "{}");
  }

  // ---- Mark a notification as read ----
  // Called by each page after it has shown / acted on the card.
  window.SNMarkRead = async function (notificationId) {
    try {
      await fetch(`${BASE_URL}/notifications/${notificationId}/read`, {
        method: "POST",
        headers: _authHeaders(),
      });
    } catch (_) { /* fire-and-forget — unread stays, no harm */ }
  };

  // ---- 1) Page-load poll (durable) ----
  // Fetches every unread notification and emits it through SNBus.
  // Each item has: { id, type, payload, created_at }
  async function _pollUnread() {
    const user = _user();
    if (!user.id || user.role !== "student") return;
    try {
      const res = await fetch(`${BASE_URL}/notifications`, {
        headers: _authHeaders(),
      });
      if (!res.ok) return;
      const items = await res.json();
      items.forEach((item) => {
        SNBus.emit(item.type, { ...item.payload, _notificationId: item.id });
      });
    } catch (_) { /* non-critical — page still works without it */ }
  }

  // ---- 2) SSE (real-time) ----
  // Opens once per page, reconnects automatically on drop.
  // We guard with a flag so navigating between tabs doesn't open
  // multiple connections on the same page.
  let _sse = null;
  function _subscribeSSE() {
    if (_sse) return;
    const user = _user();
    if (!user.id || user.role !== "student") return;
    const url =
      `${BASE_URL}/advisor/notifications/student-stream` +
      `?user_id=${encodeURIComponent(user.id)}&role=student`;
    const es = new EventSource(url);

    ["more_info_requested", "assessment_requested"].forEach((evt) => {
      es.addEventListener(evt, (e) => {
        try {
          const data = JSON.parse(e.data);
          // Backend includes the DB row id as _notification_id so a
          // notification seen live can still be marked read (same key
          // shape as the poll path's _notificationId below) — otherwise
          // it would stay "unread" in the DB and reappear on next load.
          if (data._notification_id != null) {
            data._notificationId = data._notification_id;
          }
          SNBus.emit(evt, data);
        } catch (err) {
          console.error(`[SNBus] bad ${evt} payload:`, err);
        }
      });
    });

    es.onerror = () => {}; // EventSource retries automatically
    _sse = es;
  }

  // ---- Boot ----
  // Wait for auth-guard to finish (currentUser may not be set yet at
  // script-parse time — auth-guard sets it synchronously before
  // DOMContentLoaded, so listening for that is safe).
  document.addEventListener("DOMContentLoaded", () => {
    const user = _user();
    if (!user.id || user.role !== "student") return;
    _subscribeSSE();
    _pollUnread();   // catches anything missed while the student was offline
  });
})();
