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
   SERVER
========================= */

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
});