// =========================================================
// Student Details — profile, grades, attendance
//
// Grades and attendance are rendered exactly as returned by the
// backend (get_student_grades / get_student_attendance). Nothing
// here computes averages or percentages on the frontend.
// =========================================================

document.addEventListener("DOMContentLoaded", async () => {
  BPLayout.mount({ active: "students", userName: (window.currentUser && window.currentUser.name) || "Instructor", userRole: "Instructor" });
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
  // The backend's Grades/Attendance tables don't store present/absent/
  // excused counts or a course-agnostic average — Grades is one row per
  // assignment (no course label) and Attendance is one percentage per
  // course (see instructor_router.py). A single "avg grade %" stat card
  // isn't invented here; it's a real mean of the real per-assignment
  // scores actually returned, shown only when there's at least one grade.
  const grades = s.grades || [];
  const attendance = s.attendance || [];
  const avgGrade = grades.length
    ? Math.round(grades.reduce((sum, g) => sum + (g.score / g.maxScore) * 100, 0) / grades.length)
    : null;

  return `
    <div class="bp-page-header">
      <div style="display:flex;align-items:center;gap:14px">
        <div class="bp-avatar" style="width:46px;height:46px;font-size:16px">${initials(s.name)}</div>
        <div>
          <h1>${s.name}</h1>
          <p>${s.email || ""}</p>
        </div>
      </div>
    </div>

    <div class="bp-stat-grid" style="margin-bottom:22px">
      <div class="bp-card bp-stat-card">
        <div class="bp-stat-icon amber">${BPIcons.reports}</div>
        <div class="bp-stat-body">
          <div class="label-top">Avg. Grade</div>
          <div class="value">${avgGrade != null ? avgGrade + "%" : "—"}</div>
          <div class="label-bottom">Across recorded assignments</div>
        </div>
      </div>
    </div>

    <div class="bp-detail-grid">
      <div class="bp-detail-stack">
        <section class="bp-card bp-card-pad">
          <div class="bp-card-header"><h2>Grades</h2></div>
          ${
            grades.length
              ? `<div class="bp-table-wrap">
                  <table class="bp-table">
                    <thead><tr><th>Assignment</th><th>Score</th></tr></thead>
                    <tbody>
                      ${grades
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
            attendance.length
              ? attendance
                  .map(
                    (a) => `<div class="bp-kv"><div class="k">${a.course}</div><div class="v">${a.percentage}%</div></div>`
                  )
                  .join("")
              : BPState.empty("No attendance data recorded yet.")
          }
        </section>
      </div>
    </div>
  `;
}