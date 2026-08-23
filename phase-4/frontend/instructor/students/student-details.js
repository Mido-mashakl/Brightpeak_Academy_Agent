// =========================================================
// Student Details — profile, grades, attendance
//
// Grades and attendance are rendered exactly as returned by the
// backend (get_student_grades / get_student_attendance). Nothing
// here computes averages or percentages on the frontend.
// =========================================================

document.addEventListener("DOMContentLoaded", async () => {
  BPLayout.mount({ active: "students", userName: "Fatma", userRole: "Instructor" });
  document.getElementById("bp-back-icon").innerHTML = BPIcons.arrowLeft;

  const root = document.getElementById("bp-student-root");
  const id = new URLSearchParams(window.location.search).get("id");

  if (!id) {
    root.innerHTML = BPState.error("No student selected.");
    return;
  }

  root.innerHTML = BPState.loading("Loading student...");

  try {
    const s = await getStudent(id);
    root.innerHTML = renderStudent(s);
  } catch (err) {
    root.innerHTML = BPState.error("Unable to load this student. Please try again.");
  }
});

function initials(name) {
  return name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
}

function renderStudent(s) {
  return `
    <div class="bp-page-header">
      <div style="display:flex;align-items:center;gap:14px">
        <div class="bp-avatar" style="width:46px;height:46px;font-size:16px">${initials(s.name)}</div>
        <div>
          <h1>${s.name}</h1>
          <p>${s.course}${s.email ? ` · ${s.email}` : ""}</p>
        </div>
      </div>
      <span>${BPFormat.statusBadge(s.status)}</span>
    </div>

    <div class="bp-stat-grid" style="margin-bottom:22px">
      <div class="bp-card bp-stat-card">
        <div class="bp-stat-icon amber">${BPIcons.reports}</div>
        <div class="bp-stat-body">
          <div class="label-top">Avg. Grade</div>
          <div class="value">${s.avgGrade}%</div>
          <div class="label-bottom">Across graded work</div>
        </div>
      </div>
      <div class="bp-card bp-stat-card">
        <div class="bp-stat-icon blue">${BPIcons.checkCircle}</div>
        <div class="bp-stat-body">
          <div class="label-top">Attendance</div>
          <div class="value">${s.attendancePct}%</div>
          <div class="label-bottom">${s.attendance ? `${s.attendance.present}/${s.attendance.totalSessions} sessions` : "This term"}</div>
        </div>
      </div>
    </div>

    <div class="bp-detail-grid">
      <div class="bp-detail-stack">
        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Grades</h2></div>
          ${
            s.grades && s.grades.length
              ? `<div class="bp-table-wrap">
                  <table class="bp-table">
                    <thead><tr><th>Assignment</th><th>Score</th></tr></thead>
                    <tbody>
                      ${s.grades
                        .map(
                          (g) => `
                        <tr>
                          <td class="bp-cell-primary">${g.assignment}</td>
                          <td>${g.score}/${g.maxScore}</td>
                        </tr>
                      `
                        )
                        .join("")}
                    </tbody>
                  </table>
                </div>`
              : BPState.empty("No grades recorded yet.")
          }
        </section>
      </div>

      <div class="bp-detail-stack">
        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Attendance</h2></div>
          ${
            s.attendance
              ? `
            <div class="bp-kv"><div class="k">Present</div><div class="v">${s.attendance.present}</div></div>
            <div class="bp-kv"><div class="k">Absent</div><div class="v">${s.attendance.absent}</div></div>
            <div class="bp-kv"><div class="k">Excused</div><div class="v">${s.attendance.excused}</div></div>
            <div class="bp-kv"><div class="k">Total Sessions</div><div class="v">${s.attendance.totalSessions}</div></div>
          `
              : BPState.empty("No attendance data recorded yet.")
          }
        </section>
      </div>
    </div>
  `;
}
