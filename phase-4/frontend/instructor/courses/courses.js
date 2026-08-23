// =========================================================
// My Courses — list
//
// Cards only navigate to Course Details. Grade/roster figures
// are rendered exactly as returned by the backend.
// =========================================================

document.addEventListener("DOMContentLoaded", async () => {
  BPLayout.mount({ active: "courses", userName: (window.currentUser && window.currentUser.name) || "Instructor", userRole: "Instructor" });

  const root = document.getElementById("bp-courses-root");
  root.innerHTML = BPState.loading("Loading your courses...");

  try {
    const courses = await getCourses();
    render(courses);
  } catch (err) {
    root.innerHTML = BPState.error("Unable to load your courses. Please try again.");
  }

  function render(courses) {
    if (!courses || courses.length === 0) {
      root.innerHTML = BPState.empty("You aren't assigned to any courses yet.");
      return;
    }

    root.innerHTML = `
      <div class="bp-course-grid">
        ${courses
          .map(
            (c) => `
          <div class="bp-card bp-course-card" data-id="${c.id}">
            <div class="bp-course-top">
              <div class="bp-course-icon">${BPIcons.courses}</div>
            </div>
            <div>
              <div class="bp-course-name">${c.name}</div>
              <div class="bp-course-meta">${c.category} · ${c.duration}h</div>
            </div>
            <div class="bp-course-stats">
              <div class="item"><div class="k">Students</div><div class="v">${c.studentsCount}</div></div>
              <div class="item"><div class="k">Avg. Grade</div><div class="v">${c.avgGrade != null ? c.avgGrade + "%" : "—"}</div></div>
            </div>
          </div>
        `
          )
          .join("")}
      </div>
    `;

    root.querySelectorAll(".bp-course-card").forEach((card) => {
      card.addEventListener("click", () => {
        window.location.href = `course-details.html?id=${card.dataset.id}`;
      });
    });
  }
});