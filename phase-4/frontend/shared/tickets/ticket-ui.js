// =========================================================
// Brightpeak Academy — shared ticket UI helpers
// Mirrors shared/hitl/hitl-ui.js so Tickets gets the same card
// layout / toast pattern without a second implementation.
// Requires: shared/tickets/ticket-service.js, shared/components/components.js
// =========================================================

window.BrightPeakTicketUI = (function () {
  function renderTicketCard(ticket) {
    const el = document.createElement("div");
    el.className = "ticket-card";
    el.dataset.ticketId = ticket.id;
    el.innerHTML = `
      <div class="ticket-card-header">
        <span class="ticket-card-title">${ticket.title || "Untitled ticket"}</span>
        <span class="ticket-card-status ticket-card-status--${ticket.status || "open"}">${ticket.status || "open"}</span>
      </div>
      <p class="ticket-card-summary">${ticket.summary || ""}</p>
      <div class="ticket-card-actions">
        <button class="btn btn-ghost btn-sm" data-action="investigate">Investigate</button>
        <button class="btn btn-primary btn-sm" data-action="resolve">Resolve</button>
      </div>
    `;

    el.querySelector('[data-action="investigate"]').addEventListener("click", async () => {
      try {
        await window.BrightPeakTickets.investigateTicket(ticket.id);
        window.BrightPeakComponents.showToast("Investigation started");
      } catch (err) {
        window.BrightPeakComponents.showToast(err.message || "Failed to start investigation", "error");
      }
    });

    el.querySelector('[data-action="resolve"]').addEventListener("click", async () => {
      try {
        await window.BrightPeakTickets.resolveTicket(ticket.id, {});
        window.BrightPeakComponents.showToast("Ticket resolved");
        el.remove();
      } catch (err) {
        window.BrightPeakComponents.showToast(err.message || "Failed to resolve ticket", "error");
      }
    });

    return el;
  }

  async function renderListInto(container, query = {}) {
    container.innerHTML = "";
    const tickets = await window.BrightPeakTickets.listTickets(query);
    (tickets || []).forEach((ticket) => container.appendChild(renderTicketCard(ticket)));
  }

  return { renderTicketCard, renderListInto };
})();
