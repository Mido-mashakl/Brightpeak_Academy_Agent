// =========================================================
// Course Details — course info + roster
//
// Roster rows link to Student Details. Nothing here computes
// averages or attendance on the frontend; the backend returns
// them per student.
// =========================================================

document.addEventListener("DOMContentLoaded", async () => {
  BPLayout.mount({ active: "courses", userName: (window.currentUser && window.currentUser.name) || "Instructor", userRole: "Instructor" });
  document.getElementById("bp-back-icon").innerHTML = BPIcons.arrowLeft;

  const root = document.getElementById("bp-course-root");
  const id = new URLSearchParams(window.location.search).get("id");

  if (!id) {
    root.innerHTML = BPState.error("No course selected.");
    return;
  }

  root.innerHTML = BPState.loading("Loading course...");

  try {
    const c = await getCourse(id);
    root.innerHTML = renderCourse(c);
    // The course roster join (Enrollments+Students) has no attendance/grade
    // columns of its own — those are computed per-student by
    // GET /instructor/students, the same endpoint the Students page uses.
    // Reuse it here (filtered to this course) instead of inventing values.
    const students = await getStudents({ course: id });
    wireRoster(students);
  } catch (err) {
    root.innerHTML = BPState.error("Unable to load this course. Please try again.");
  }
});

function renderCourse(c) {
  return `
    <div class="bp-page-header">
      <div>
        <h1>${c.name}</h1>
        <p>${c.category} · ${c.duration}h</p>
      </div>
    </div>

    <div class="bp-stat-grid" style="margin-bottom:22px">
      <div class="bp-card bp-stat-card">
        <div class="bp-stat-icon pink">${BPIcons.students}</div>
        <div class="bp-stat-body">
          <div class="label-top">Students</div>
          <div class="value">${c.studentsCount}</div>
          <div class="label-bottom">Enrolled</div>
        </div>
      </div>
      <div class="bp-card bp-stat-card">
        <div class="bp-stat-icon amber">${BPIcons.reports}</div>
        <div class="bp-stat-body">
          <div class="label-top">Avg. Grade</div>
          <div class="value">${c.avgGrade != null ? c.avgGrade + "%" : "—"}</div>
          <div class="label-bottom">Across all students</div>
        </div>
      </div>
    </div>

    <section class="bp-card bp-card-pad">
      <div class="bp-card-header"><h2>Roster</h2></div>
      <div id="bp-roster-container"></div>
    </section>
  `;
}

function wireRoster(roster) {
  const container = document.getElementById("bp-roster-container");

  if (!roster || roster.length === 0) {
    container.innerHTML = BPState.empty("No students enrolled in this course yet.");
    return;
  }

  container.innerHTML = `
    <div class="bp-table-wrap">
      <table class="bp-table">
        <thead>
          <tr>
            <th>Student</th><th>Attendance</th><th>Avg. Grade</th><th></th>
          </tr>
        </thead>
        <tbody>
          ${roster
            .map(
              (s) => `
            <tr class="bp-row" data-id="${s.id}">
              <td class="bp-cell-primary"><span class="bp-row-icon" style="background:rgba(236,72,153,0.14);color:#ec4899">${BPIcons.students}</span>${s.name}</td>
              <td class="bp-cell-muted">${s.attendancePct != null ? s.attendancePct + "%" : "—"}</td>
              <td class="bp-cell-muted">${s.avgGrade != null ? s.avgGrade + "%" : "—"}</td>
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
      window.location.href = `../students/student-details.html?id=${row.dataset.id}`;
    });
  });
}