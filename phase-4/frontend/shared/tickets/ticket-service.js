// =========================================================
// Brightpeak Academy — shared tickets service
// Thin wrapper around the Phase-4 ticket endpoints. Only
// Department Head currently exposes a Tickets screen, but the
// service lives here (not under department-head/) so any role
// later granted the permission can reuse it.
// Requires shared/api.js (BrightPeakAPI) to be loaded first.
//   GET  /api/tickets
//   GET  /api/tickets/{ticket_id}
//   POST /api/tickets/{ticket_id}/investigate
//   POST /api/tickets/{ticket_id}/resolve
// =========================================================

window.BrightPeakTickets = (function () {
  function listTickets(query = {}) {
    const qs = new URLSearchParams(query).toString();
    return window.BrightPeakAPI.get(qs ? `/api/tickets?${qs}` : "/api/tickets");
  }

  function getTicket(ticketId) {
    return window.BrightPeakAPI.get(`/api/tickets/${ticketId}`);
  }

  function investigateTicket(ticketId) {
    return window.BrightPeakAPI.post(`/api/tickets/${ticketId}/investigate`, {});
  }

  function resolveTicket(ticketId, resolution) {
    return window.BrightPeakAPI.post(`/api/tickets/${ticketId}/resolve`, resolution);
  }

  return { listTickets, getTicket, investigateTicket, resolveTicket };
})();
