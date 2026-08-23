// =========================================================
// Students — list
//
// Rows only navigate to Student Details. Search + course filter
// are sent to the backend via getStudents(); nothing is filtered
// against a frontend copy of the full roster.
// =========================================================

const BP_PAGE_SIZE = 10;

document.addEventListener("DOMContentLoaded", async () => {
  BPLayout.mount({ active: "students", userName: "Fatma", userRole: "Instructor" });

  document.getElementById("bp-search-icon").innerHTML = BPIcons.search;

  const container = document.getElementById("bp-students-container");
  const paginationEl = document.getElementById("bp-pagination");
  const searchInput = document.getElementById("bp-search-input");
  const courseFilter = document.getElementById("bp-course-filter");

  let currentPage = 1;
  let debounceTimer = null;

  try {
    const courses = await getCourses();
    courseFilter.innerHTML =
      `<option value="all">All Courses</option>` +
      courses.map((c) => `<option value="${c.id}">${c.name}</option>`).join("");
  } catch (err) {
    // Filter still works with "All Courses" if the course list fails to load.
  }

  async function load() {
    container.innerHTML = BPState.loading("Loading students...");
    paginationEl.innerHTML = "";
    try {
      const rows = await getStudents({
        search: searchInput.value,
        course: courseFilter.value,
      });
      renderTable(rows);
    } catch (err) {
      container.innerHTML = BPState.error("Unable to load students. Please try again.");
    }
  }

  function renderTable(rows) {
    if (!rows || rows.length === 0) {
      container.innerHTML = BPState.empty("No students found.");
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
              <th>Student</th><th>Course</th><th>Attendance</th><th>Avg. Grade</th><th>Standing</th><th></th>
            </tr>
          </thead>
          <tbody>
            ${pageRows
              .map(
                (s) => `
              <tr class="bp-row" data-id="${s.id}">
                <td class="bp-cell-primary"><span class="bp-row-icon" style="background:rgba(236,72,153,0.14);color:#ec4899">${BPIcons.students}</span>${s.name}</td>
                <td class="bp-cell-muted">${s.course}</td>
                <td class="bp-cell-muted">${s.attendancePct}%</td>
                <td class="bp-cell-muted">${s.avgGrade}%</td>
                <td>${BPFormat.statusBadge(s.status)}</td>
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
        window.location.href = `student-details.html?id=${row.dataset.id}`;
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
  courseFilter.addEventListener("change", () => {
    currentPage = 1;
    load();
  });

  load();
});
