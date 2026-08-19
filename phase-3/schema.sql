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
-- ------------------------------------------------------------
-- Academic Integrity Investigation & Appeal (Phase-3 state graph)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS IntegrityCases (
    case_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      INTEGER NOT NULL REFERENCES Students(student_id),
    course_id       INTEGER NOT NULL REFERENCES Courses(course_id),
    assignment_id   INTEGER REFERENCES Assignments(assignment_id),
    reported_by     INTEGER NOT NULL REFERENCES Instructors(instructor_id),
    description     TEXT NOT NULL,
    similarity_score REAL,
    severity        TEXT CHECK (severity IN ('minor','major','severe')),
    status          TEXT NOT NULL DEFAULT 'reported'
                        CHECK (status IN ('reported','under_review','awaiting_appeal',
                                           'appeal_under_review','closed')),
    created_at      TEXT NOT NULL DEFAULT (DATETIME('now')),
    updated_at      TEXT NOT NULL DEFAULT (DATETIME('now'))
);

CREATE TABLE IF NOT EXISTS IntegrityEvidence (
    evidence_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id         INTEGER NOT NULL REFERENCES IntegrityCases(case_id),
    evidence_type   TEXT NOT NULL,
    content         TEXT NOT NULL,
    collected_at    TEXT NOT NULL DEFAULT (DATETIME('now'))
);

CREATE TABLE IF NOT EXISTS IntegrityAppeals (
    appeal_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id         INTEGER NOT NULL REFERENCES IntegrityCases(case_id),
    student_argument TEXT NOT NULL,
    submitted_at    TEXT NOT NULL DEFAULT (DATETIME('now')),
    evaluation      TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','evaluated'))
);

CREATE TABLE IF NOT EXISTS IntegrityDecisions (
    decision_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id         INTEGER NOT NULL REFERENCES IntegrityCases(case_id),
    decision_stage  TEXT NOT NULL CHECK (decision_stage IN ('committee_review','final_decision')),
    decided_by      TEXT NOT NULL,
    decision        TEXT NOT NULL,
    notes           TEXT,
    decided_at      TEXT NOT NULL DEFAULT (DATETIME('now'))
);

-- ------------------------------------------------------------
-- Adaptive Assessment & Mastery Evaluation (Phase-3 state graph)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS AssessmentSessions (
    session_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      INTEGER NOT NULL REFERENCES Students(student_id),
    course_id       INTEGER NOT NULL REFERENCES Courses(course_id),
    topic           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'in_progress'
                        CHECK (status IN ('in_progress','flagged_for_review','completed')),
    mastery_level   TEXT,
    final_score     REAL,
    started_at      TEXT NOT NULL DEFAULT (DATETIME('now')),
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS AssessmentAnswers (
    answer_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES AssessmentSessions(session_id),
    question_text   TEXT NOT NULL,
    difficulty      TEXT NOT NULL,
    student_answer  TEXT NOT NULL,
    is_correct      INTEGER,
    score_awarded   REAL,
    answered_at     TEXT NOT NULL DEFAULT (DATETIME('now'))
);

-- ------------------------------------------------------------
-- Tickets (shared failure/recovery path — both Phase-3 graphs)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Tickets (
    ticket_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    source_graph    TEXT NOT NULL,     -- 'academic_integrity' | 'adaptive_assessment'
    source_id       INTEGER NOT NULL,  -- case_id or session_id
    thread_id       TEXT NOT NULL,     -- LangGraph thread_id, to resume from checkpoint
    failure_type    TEXT NOT NULL,     -- e.g. 'tool_error', 'schema_validation_failed'
    status          TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','investigating','resolved')),
    details         TEXT,
    created_at      TEXT NOT NULL DEFAULT (DATETIME('now')),
    resolved_at     TEXT
);

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
CREATE INDEX IF NOT EXISTS idx_integrity_cases_student     ON IntegrityCases(student_id);
CREATE INDEX IF NOT EXISTS idx_integrity_cases_course      ON IntegrityCases(course_id);
CREATE INDEX IF NOT EXISTS idx_integrity_evidence_case     ON IntegrityEvidence(case_id);
CREATE INDEX IF NOT EXISTS idx_integrity_appeals_case      ON IntegrityAppeals(case_id);
CREATE INDEX IF NOT EXISTS idx_integrity_decisions_case    ON IntegrityDecisions(case_id);
CREATE INDEX IF NOT EXISTS idx_assessment_sessions_student ON AssessmentSessions(student_id);
CREATE INDEX IF NOT EXISTS idx_assessment_answers_session  ON AssessmentAnswers(session_id);
CREATE INDEX IF NOT EXISTS idx_tickets_thread              ON Tickets(thread_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status               ON Tickets(status);
