// =========================================================
// Requests — list
//
// Rows only navigate to Request Details. No action here ever
// changes status directly — the flow is always
// Review -> Request Details -> decision (Approve/Reject).
// =========================================================

const BP_PAGE_SIZE = 10;

document.addEventListener("DOMContentLoaded", () => {
  BPLayout.mount({ active: "requests", userName: "Fatma", userRole: "Instructor" });

  document.getElementById("bp-search-icon").innerHTML = BPIcons.search;

  const container = document.getElementById("bp-requests-container");
  const paginationEl = document.getElementById("bp-pagination");
  const searchInput = document.getElementById("bp-search-input");
  const statusFilter = document.getElementById("bp-status-filter");

  let currentPage = 1;
  let debounceTimer = null;

  async function load() {
    container.innerHTML = BPState.loading("Loading requests...");
    paginationEl.innerHTML = "";
    try {
      const rows = await getRequests({
        search: searchInput.value,
        status: statusFilter.value,
      });
      renderTable(rows);
    } catch (err) {
      container.innerHTML = BPState.error("Unable to load requests. Please try again.");
    }
  }

  function renderTable(rows) {
    if (!rows || rows.length === 0) {
      container.innerHTML = BPState.empty("No requests found.");
      return;
    }

    const totalPages = Math.max(1, Math.ceil(rows.length / BP_PAGE_SIZE));
    currentPage = Math.min(currentPage, totalPages);
    const start = (currentPage - 1) * BP_PAGE_SIZE;
    const pageRows = rows.slice(start, start + BP_PAGE_SIZE);

    container.innerHTML = `
      <div class="bp-table-wrap">
        <table class="bp-table">
          <thead>
            <tr>
              <th>Request</th><th>Student</th><th>Course</th><th>Status</th><th>Submitted</th><th></th>
            </tr>
          </thead>
          <tbody>
            ${pageRows
              .map(
                (r) => `
              <tr class="bp-row" data-id="${r.id}">
                <td class="bp-cell-primary"><span class="bp-row-icon" style="background:rgba(96,165,250,0.14);color:#60a5fa">${BPIcons.requests}</span>${BPFormat.requestTypeLabel[r.type] || r.type}<br><span class="bp-cell-muted" style="font-weight:400">#${r.id}</span></td>
                <td>${r.student}</td>
                <td class="bp-cell-muted">${r.course}</td>
                <td>${BPFormat.statusBadge(r.status)}</td>
                <td class="bp-cell-muted">${r.submittedLabel}</td>
                <td class="bp-row-chevron">${BPIcons.chevronRight}</td>
              </tr>
            `
              )
              .join("")}
          </tbody>
        </table>
      </div>
    `;

    container.querySelectorAll(".bp-row").forEach((row) => {
      row.addEventListener("click", () => {
        window.location.href = `request-details.html?id=${row.dataset.id}`;
      });
    });

    renderPagination(totalPages, () => renderTable(rows));
  }

  function renderPagination(totalPages, rerender) {
    if (totalPages <= 1) {
      paginationEl.innerHTML = "";
      return;
    }
    let html = `<button data-dir="-1" ${currentPage === 1 ? "disabled" : ""}>${BPIcons.chevronLeft}</button>`;
    for (let i = 1; i <= totalPages; i++) {
      html += `<button data-page="${i}" class="${i === currentPage ? "active" : ""}">${i}</button>`;
    }
    html += `<button data-dir="1" ${currentPage === totalPages ? "disabled" : ""}>${BPIcons.chevronRight}</button>`;
    paginationEl.innerHTML = html;

    paginationEl.querySelectorAll("button[data-page]").forEach((btn) => {
      btn.addEventListener("click", () => {
        currentPage = parseInt(btn.dataset.page, 10);
        rerender();
      });
    });
    paginationEl.querySelectorAll("button[data-dir]").forEach((btn) => {
      btn.addEventListener("click", () => {
        currentPage += parseInt(btn.dataset.dir, 10);
        rerender();
      });
    });
  }

  searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      currentPage = 1;
      load();
    }, 250);
  });
  statusFilter.addEventListener("change", () => {
    currentPage = 1;
    load();
  });

  load();
});
