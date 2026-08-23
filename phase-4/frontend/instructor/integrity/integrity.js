// =========================================================
// Academic Integrity — All Cases
// =========================================================

const BP_PAGE_SIZE = 10;

document.addEventListener("DOMContentLoaded", () => {
  BPLayout.mount({ active: "integrity-all", userName: "Fatma", userRole: "Instructor" });

  document.getElementById("bp-plus-icon").innerHTML = BPIcons.plus;
  document.getElementById("bp-search-icon").innerHTML = BPIcons.search;

  const container = document.getElementById("bp-cases-container");
  const paginationEl = document.getElementById("bp-pagination");
  const searchInput = document.getElementById("bp-search-input");
  const statusFilter = document.getElementById("bp-status-filter");
  const reportBtn = document.getElementById("bp-report-btn");

  reportBtn.addEventListener("click", () => {
    window.location.href = "report-case.html";
  });

  let currentPage = 1;
  let debounceTimer = null;

  async function load() {
    container.innerHTML = BPState.loading("Loading integrity cases...");
    paginationEl.innerHTML = "";
    try {
      const rows = await getIntegrityCases({
        search: searchInput.value,
        status: statusFilter.value,
      });
      renderTable(rows);
    } catch (err) {
      container.innerHTML = BPState.error("Unable to load integrity cases. Please try again.");
    }
  }

  function renderTable(rows) {
    if (!rows || rows.length === 0) {
      container.innerHTML = BPState.empty("No academic integrity cases found.");
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
              <th>Case</th><th>Student</th><th>Course</th><th>Severity</th><th>Status</th><th>Reported</th><th></th>
            </tr>
          </thead>
          <tbody>
            ${pageRows
              .map(
                (c) => `
              <tr class="bp-row" data-id="${c.id}">
                <td class="bp-cell-primary"><span class="bp-row-icon" style="background:rgba(139,92,246,0.14);color:#a78bfa">${BPIcons.shield}</span>Case #${c.id}</td>
                <td>${c.student}</td>
                <td class="bp-cell-muted">${c.course}</td>
                <td>${BPFormat.severityBadge(c.severity)}</td>
                <td>${BPFormat.statusBadge(c.status)}</td>
                <td class="bp-cell-muted">${c.reportedLabel}</td>
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
        window.location.href = `case-details.html?id=${row.dataset.id}`;
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
