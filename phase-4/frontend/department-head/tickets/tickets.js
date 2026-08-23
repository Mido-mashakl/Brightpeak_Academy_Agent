(function () {
  DHNav.mount({ active: "tickets", searchPlaceholder: "Search tickets..." });

  let activeFilter = "all";
  let allTickets = [];

  init();

  async function init() {
    allTickets = await DHApi.listTickets();
    renderTable();
    bindFilters();
    document.getElementById("drawer-close").addEventListener("click", closeDrawer);
    document.getElementById("ticket-drawer-backdrop").addEventListener("click", (e) => {
      if (e.target.id === "ticket-drawer-backdrop") closeDrawer();
    });
  }

  function bindFilters() {
    document.querySelectorAll(".filter-pill").forEach((pill) =>
      pill.addEventListener("click", () => {
        activeFilter = pill.dataset.filter;
        document.querySelectorAll(".filter-pill").forEach((p) => p.classList.toggle("active", p === pill));
        renderTable();
      })
    );
  }

  function renderTable() {
    const tbody = document.getElementById("ticket-rows");
    const rows = activeFilter === "all" ? allTickets : allTickets.filter((t) => t.status === activeFilter);
    tbody.innerHTML = rows.length
      ? rows
          .map(
            (t) => `
      <tr data-id="${t.id}">
        <td class="ticket-id">${t.id}</td>
        <td>${escapeHtml(t.sourceGraph)}</td>
        <td class="text-on-surface-variant">${escapeHtml(t.sourceId)}</td>
        <td class="text-on-surface-variant">${escapeHtml(t.threadId)}</td>
        <td>${escapeHtml(t.failureType)}</td>
        <td><span class="status-chip ${t.status}"><span class="material-symbols-outlined text-sm">${statusIcon(t.status)}</span>${t.status}</span></td>
        <td><span class="priority-chip">${t.priority ? escapeHtml(t.priority) : "—"}</span></td>
        <td><span class="material-symbols-outlined text-on-surface-variant">chevron_right</span></td>
      </tr>`
          )
          .join("")
      : `<tr><td colspan="8" class="text-center text-on-surface-variant p-lg">No tickets match this filter.</td></tr>`;

    tbody.querySelectorAll("tr[data-id]").forEach((row) =>
      row.addEventListener("click", () => openDrawer(allTickets.find((t) => t.id === row.dataset.id)))
    );
  }

  function statusIcon(status) {
    return { Open: "radio_button_unchecked", Investigating: "search", Resolved: "check_circle" }[status] || "circle";
  }

  let currentTicket = null;
  function openDrawer(ticket) {
    currentTicket = ticket;
    document.getElementById("drawer-ticket-id").textContent = `Ticket ${ticket.id}`;
    document.getElementById("drawer-workflow").textContent = ticket.workflow || "—";
    document.getElementById("drawer-source-graph").textContent = ticket.sourceGraph;
    document.getElementById("drawer-source-id").textContent = ticket.sourceId;
    document.getElementById("drawer-thread-id").textContent = ticket.threadId;
    document.getElementById("drawer-failure-type").textContent = ticket.failureType;
    document.getElementById("drawer-related").textContent = ticket.relatedWorkflow || "—";
    document.getElementById("drawer-details").textContent = ticket.details;
    renderStatusActions(ticket);
    document.getElementById("ticket-drawer-backdrop").classList.remove("hidden");
  }
  function closeDrawer() {
    document.getElementById("ticket-drawer-backdrop").classList.add("hidden");
  }

  function renderStatusActions(ticket) {
    // tickets_router.py only supports forward transitions (open ->
    // investigating -> resolved, see POST /investigate, /resolve) — there's
    // no "reopen" endpoint, so "Open" is shown as a read-only past state,
    // never a clickable target once a ticket has moved past it.
    const statuses = ["Open", "Investigating", "Resolved"];
    const el = document.getElementById("drawer-status-actions");
    el.innerHTML = statuses
      .map((s) => {
        const isCurrent = s === ticket.status;
        const disabled = isCurrent || s === "Open";
        return `<button class="drawer-status-btn ${isCurrent ? "active" : ""}" data-status="${s}" ${disabled ? "disabled" : ""}>${s}</button>`;
      })
      .join("");
    el.querySelectorAll("[data-status]:not([disabled])").forEach((btn) =>
      btn.addEventListener("click", async () => {
        try {
          await DHApi.updateTicketStatus(ticket.id, btn.dataset.status);
          allTickets = await DHApi.listTickets();
          renderTable();
          openDrawer(allTickets.find((t) => t.id === ticket.id));
        } catch (err) {
          console.error(err);
          alert("Could not update ticket status.");
        }
      })
    );
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
})();