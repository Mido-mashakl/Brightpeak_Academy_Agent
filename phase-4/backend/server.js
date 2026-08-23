const express = require("express");
const cors = require("cors");
const path = require("path");
const db = require("./db");

const app = express();

app.use(cors());
app.use(express.json());

// Serves everything under phase-4 (backend + frontend + images) from one origin,
// so login.html, the dashboard, and the images folder all resolve correctly
// regardless of which folder the browser opened first.
app.use(express.static(path.join(__dirname, "..")));

/* =========================
   LOGIN
   Looks the email up across every role table (Instructors,
   DeptHeads, Advisors, Students) and returns which role it
   belongs to, so the frontend can route to the right dashboard.
========================= */

app.post("/api/login", (req, res) => {
    try {
        const email = req.body.email?.trim().toLowerCase();

        if (!email) {
            return res.status(400).json({
                message: "Email is required."
            });
        }

        /* 1. INSTRUCTORS */
        const instructor = db
            .prepare(
                `SELECT instructor_id, name, email
                 FROM Instructors
                 WHERE LOWER(email) = ?`
            )
            .get(email);

        if (instructor) {
            return res.json({
                success: true,
                user: {
                    id: instructor.instructor_id,
                    name: instructor.name,
                    email: instructor.email,
                    role: "instructor"
                }
            });
        }

        /* 2. DEPT HEADS */
        const deptHead = db
            .prepare(
                `SELECT dept_head_id, name, email, department
                 FROM DeptHeads
                 WHERE LOWER(email) = ?`
            )
            .get(email);

        if (deptHead) {
            return res.json({
                success: true,
                user: {
                    id: deptHead.dept_head_id,
                    name: deptHead.name,
                    email: deptHead.email,
                    department: deptHead.department,
                    role: "dept_head"
                }
            });
        }

        /* 3. ADVISORS */
        const advisor = db
            .prepare(
                `SELECT advisor_id, name, email
                 FROM Advisors
                 WHERE LOWER(email) = ?`
            )
            .get(email);

        if (advisor) {
            return res.json({
                success: true,
                user: {
                    id: advisor.advisor_id,
                    name: advisor.name,
                    email: advisor.email,
                    role: "advisor"
                }
            });
        }

        /* 4. STUDENTS */
        const student = db
            .prepare(
                `SELECT student_id, name, email, level
                 FROM Students
                 WHERE LOWER(email) = ?`
            )
            .get(email);

        if (student) {
            return res.json({
                success: true,
                user: {
                    id: student.student_id,
                    name: student.name,
                    email: student.email,
                    level: student.level,
                    role: "student"
                }
            });
        }

        /* EMAIL NOT FOUND */
        return res.status(404).json({
            message: "This email is not registered in BrightPeak Academy."
        });
    } catch (error) {
        console.error(error);
        return res.status(500).json({
            message: "Internal server error."
        });
    }
});

/* =========================
   STUDENT DASHBOARD
   Real query against Students / Enrollments / Courses / Grades /
   Assignments — no session cookie exists anywhere in this stack yet
   (see core/auth.py's docstring on the FastAPI side for the same
   gap), so like every FastAPI graph route, this identifies the
   caller via an explicit header set by the frontend from the
   already-logged-in user (shared/auth.js's stored "user" object).
========================= */

app.get("/api/dashboard", (req, res) => {
    try {
        const studentId = Number(req.header("X-User-Id"));
        if (!studentId) {
            return res.status(401).json({ message: "Missing X-User-Id header. Log in first." });
        }

        const student = db
            .prepare(`SELECT student_id, name, email, level FROM Students WHERE student_id = ?`)
            .get(studentId);
        if (!student) {
            return res.status(401).json({ message: "No student with that id. Log in again." });
        }

        const enrolled = db
            .prepare(`SELECT COUNT(*) AS n FROM Enrollments WHERE student_id = ? AND status = 'active'`)
            .get(studentId).n;

        const completed = db
            .prepare(`SELECT COUNT(*) AS n FROM Enrollments WHERE student_id = ? AND status = 'completed'`)
            .get(studentId).n;

        const avgRow = db
            .prepare(
                `SELECT AVG(g.score) AS avg
                 FROM Grades g
                 WHERE g.student_id = ?`
            )
            .get(studentId);
        const avgScore = avgRow.avg != null ? Math.round(avgRow.avg) : null;

        // No time-tracking table exists anywhere in the schema — there is
        // no real "hours studied" to report. Rather than invent a number,
        // this is total course duration across active enrollments, which
        // IS real data (Courses.duration), just labeled honestly for what
        // it is: enrolled course hours, not hours actually spent studying.
        const hoursRow = db
            .prepare(
                `SELECT COALESCE(SUM(c.duration), 0) AS hours
                 FROM Enrollments e
                 JOIN Courses c ON c.course_id = e.course_id
                 WHERE e.student_id = ? AND e.status = 'active'`
            )
            .get(studentId);

        const deadlineRows = db
            .prepare(
                `SELECT a.title, a.deadline
                 FROM Assignments a
                 JOIN Enrollments e ON e.course_id = a.course_id
                 WHERE e.student_id = ? AND e.status = 'active' AND a.deadline >= DATE('now')
                 ORDER BY a.deadline ASC
                 LIMIT 5`
            )
            .all(studentId);

        const deadlines = deadlineRows.map((d) => {
            const date = new Date(d.deadline);
            return {
                day: isNaN(date) ? "--" : String(date.getDate()).padStart(2, "0"),
                title: d.title,
                when: d.deadline,
            };
        });

        return res.json({
            student: { name: student.name, track: student.level },
            stats: {
                enrolled,
                completed,
                avgScore,
                studyHours: hoursRow.hours,
            },
            deadlines,
        });
    } catch (error) {
        console.error(error);
        return res.status(500).json({ message: "Unable to load dashboard data." });
    }
});

app.post("/api/auth/logout", (req, res) => {
    // Stateless (no server-side session to invalidate — see the
    // /api/dashboard comment above for why). This exists so the
    // frontend has a real endpoint to call instead of failing
    // silently; the actual sign-out is clearing localStorage("user")
    // client-side (shared/auth.js's BrightPeakAuth.logout()).
    return res.json({ status: "ok" });
});

/* =========================
   SERVER
========================= */

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
});