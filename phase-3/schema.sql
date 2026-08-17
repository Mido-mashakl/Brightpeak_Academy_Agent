-- ============================================================
-- Brightpeak Academy — Database Schema (SQLite)
-- Matches ERD.png
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- Students
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Students (
    student_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    level           TEXT NOT NULL CHECK (level IN ('Beginner', 'Intermediate', 'Advanced'))
);

-- ------------------------------------------------------------
-- Instructors
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Instructors (
    instructor_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE
);

-- ------------------------------------------------------------
-- Courses
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Courses (
    course_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    category        TEXT NOT NULL,
    duration        INTEGER NOT NULL,                      -- duration in hours
    instructor_id   INTEGER,
    FOREIGN KEY (instructor_id) REFERENCES Instructors(instructor_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

-- ------------------------------------------------------------
-- Enrollments
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Enrollments (
    enrollment_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       INTEGER NOT NULL,
    course_id        INTEGER NOT NULL,
    status           TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'completed', 'dropped')),
    progress         INTEGER NOT NULL DEFAULT 0
                        CHECK (progress BETWEEN 0 AND 100),
    enrollment_date  TEXT NOT NULL DEFAULT (DATE('now')),
    FOREIGN KEY (student_id) REFERENCES Students(student_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    FOREIGN KEY (course_id) REFERENCES Courses(course_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    UNIQUE (student_id, course_id)
);

-- ------------------------------------------------------------
-- Assignments
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Assignments (
    assignment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id       INTEGER NOT NULL,
    title           TEXT NOT NULL,
    deadline        TEXT NOT NULL,                          -- ISO date/datetime
    max_score       INTEGER NOT NULL DEFAULT 100,
    FOREIGN KEY (course_id) REFERENCES Courses(course_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- ------------------------------------------------------------
-- Grades
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Grades (
    grade_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      INTEGER NOT NULL,
    assignment_id   INTEGER NOT NULL,
    score           REAL NOT NULL CHECK (score >= 0),
    graded_by       INTEGER,
    FOREIGN KEY (student_id) REFERENCES Students(student_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    FOREIGN KEY (assignment_id) REFERENCES Assignments(assignment_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    FOREIGN KEY (graded_by) REFERENCES Instructors(instructor_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    UNIQUE (student_id, assignment_id)
);

-- ------------------------------------------------------------
-- Attendance
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Attendance (
    attendance_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      INTEGER NOT NULL,
    course_id       INTEGER NOT NULL,
    percentage      REAL NOT NULL CHECK (percentage BETWEEN 0 AND 100),
    FOREIGN KEY (student_id) REFERENCES Students(student_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    FOREIGN KEY (course_id) REFERENCES Courses(course_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    UNIQUE (student_id, course_id)
);

-- ------------------------------------------------------------
-- Policies (standalone reference data — exposed as MCP Resources)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Policies (
    policy_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    category        TEXT NOT NULL,
    content         TEXT NOT NULL
);

-- ------------------------------------------------------------
-- CourseMaterials 
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS CourseMaterials (
    material_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id       INTEGER NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT,
    material_type   TEXT NOT NULL
                        CHECK (material_type IN ('lecture', 'chapter', 'reading', 'exercise')),
    source_file     TEXT NOT NULL,                         
    created_at      TEXT NOT NULL DEFAULT (DATETIME('now')),
    updated_at      TEXT NOT NULL DEFAULT (DATETIME('now')),
    FOREIGN KEY (course_id) REFERENCES Courses(course_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    UNIQUE (course_id, source_file)
);


CREATE TRIGGER IF NOT EXISTS trg_course_materials_updated_at
AFTER UPDATE ON CourseMaterials
FOR EACH ROW
BEGIN
    UPDATE CourseMaterials
    SET updated_at = DATETIME('now')
    WHERE material_id = NEW.material_id;
END;
-- ============================================================
-- Indexes for common lookups
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_courses_instructor       ON Courses(instructor_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_student       ON Enrollments(student_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_course        ON Enrollments(course_id);
CREATE INDEX IF NOT EXISTS idx_assignments_course        ON Assignments(course_id);
CREATE INDEX IF NOT EXISTS idx_grades_student             ON Grades(student_id);
CREATE INDEX IF NOT EXISTS idx_grades_assignment          ON Grades(assignment_id);
CREATE INDEX IF NOT EXISTS idx_grades_graded_by           ON Grades(graded_by);
CREATE INDEX IF NOT EXISTS idx_attendance_student         ON Attendance(student_id);
CREATE INDEX IF NOT EXISTS idx_attendance_course          ON Attendance(course_id);
CREATE INDEX IF NOT EXISTS idx_course_materials_course    ON CourseMaterials(course_id);
