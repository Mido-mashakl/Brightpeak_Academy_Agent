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
-- DeptHeads — Faculty Hiring HITL reviewers (real identity, not just a role)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS DeptHeads (
    dept_head_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    department      TEXT
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
-- Student Advisor: Certificate & Scholarship Eligibility
-- (state_graph/advisory/ — written by data.py's create_request_row() /
-- finalize_request_row(); request_id/application_id doubles as the
-- LangGraph thread_id source, see advisory/checkpointing.py)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS CertificateRequests (
    request_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      INTEGER NOT NULL REFERENCES Students(student_id),
    course_id       INTEGER REFERENCES Courses(course_id),
    purpose         TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','eligible','ineligible',
                                           'needs_review')),
    recommendation  TEXT,
    decided_by      TEXT,
    created_at      TEXT NOT NULL DEFAULT (DATETIME('now')),
    decided_at      TEXT
);

CREATE TABLE IF NOT EXISTS ScholarshipApplications (
    application_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      INTEGER NOT NULL REFERENCES Students(student_id),
    course_id       INTEGER REFERENCES Courses(course_id),
    purpose         TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','eligible','ineligible',
                                           'needs_review')),
    recommendation  TEXT,
    decided_by      TEXT,
    created_at      TEXT NOT NULL DEFAULT (DATETIME('now')),
    decided_at      TEXT
);

-- ------------------------------------------------------------
-- Faculty Hiring — Certificate & Scholarship Eligibility sibling graph
-- (Farida/graph-team: Faculty Hiring State Graph)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS JobPostings (
    job_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    qualifications  TEXT NOT NULL,      -- JSON list of qualification strings
    application_deadline TEXT,          -- display/validation only; MVP uses admin "close" button, no scheduler
    status          TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','closed','hitl_review','completed')),
    created_at      TEXT NOT NULL DEFAULT (DATETIME('now')),
    updated_at      TEXT NOT NULL DEFAULT (DATETIME('now'))
);

CREATE TABLE IF NOT EXISTS Candidates (
    candidate_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES JobPostings(job_id),
    name            TEXT NOT NULL,
    raw_cv_text     TEXT NOT NULL,
    parsed_profile  TEXT,               -- JSON column (flexible CV structure — see design decisions)
    parse_status    TEXT NOT NULL DEFAULT 'pending'
                        CHECK (parse_status IN ('pending','parsed','failed','missing_fields')),
    submitted_at    TEXT NOT NULL DEFAULT (DATETIME('now'))
);

CREATE TABLE IF NOT EXISTS CandidateScores (
    score_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER NOT NULL REFERENCES Candidates(candidate_id),
    score           REAL NOT NULL,
    breakdown       TEXT,               -- JSON: per-qualification PASS/FAIL/MISSING + evidence
    trigger         TEXT NOT NULL DEFAULT 'initial'
                        CHECK (trigger IN ('initial','rescore')),
    scored_at       TEXT NOT NULL DEFAULT (DATETIME('now'))
);

CREATE TABLE IF NOT EXISTS Shortlists (
    shortlist_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES JobPostings(job_id),
    generated_at    TEXT NOT NULL DEFAULT (DATETIME('now'))
);

CREATE TABLE IF NOT EXISTS ShortlistEntries (
    entry_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    shortlist_id    INTEGER NOT NULL REFERENCES Shortlists(shortlist_id),
    candidate_id    INTEGER NOT NULL REFERENCES Candidates(candidate_id),
    score           REAL NOT NULL,
    rank            INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS Interviews (
    interview_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES JobPostings(job_id),
    candidate_id    INTEGER NOT NULL REFERENCES Candidates(candidate_id),
    status          TEXT NOT NULL DEFAULT 'scheduled'
                        CHECK (status IN ('scheduled','completed','cancelled')),
    scheduled_at    TEXT,
    result          TEXT CHECK (result IN ('pass','fail','pending') OR result IS NULL),
    score           REAL,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (DATETIME('now')),
    updated_at      TEXT NOT NULL DEFAULT (DATETIME('now'))
);

CREATE TABLE IF NOT EXISTS HiringDecisions (
    decision_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES JobPostings(job_id),
    candidate_id    INTEGER NOT NULL,   -- 0 = "multiple/see notes" (used by rescore decisions)
    dept_head_id    INTEGER REFERENCES DeptHeads(dept_head_id),  -- real identity of the reviewer
    decided_by      TEXT NOT NULL,      -- display label, e.g. "Laila Hassan (id=1)" — derived from dept_head_id, not caller-supplied
    decision        TEXT NOT NULL
                        CHECK (decision IN ('hire','reject','interview','rescore')),
    notes           TEXT,
    decided_at      TEXT NOT NULL DEFAULT (DATETIME('now'))
);

CREATE TRIGGER IF NOT EXISTS trg_job_postings_updated_at
AFTER UPDATE ON JobPostings
FOR EACH ROW
BEGIN
    UPDATE JobPostings SET updated_at = DATETIME('now') WHERE job_id = NEW.job_id;
END;

-- ------------------------------------------------------------
-- Track Recommendation (Phase-3 state graph)
-- Tracks table — available tracks + requirements, sourced by RAG
-- from documents/track_requirements.md (kept in sync manually).
-- prerequisites_json / core_courses_json reference real Courses.title
-- values only (see seed.sql Courses) — no invented subjects.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Tracks (
    track_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL UNIQUE,   -- 'Data Science', 'AI Engineering', etc.
    description         TEXT,
    prerequisites_json  TEXT NOT NULL,          -- JSON list: [{"course": "...", "min_score": N}, ...]
    core_courses_json   TEXT NOT NULL           -- JSON list of course titles
);

-- TrackRecommendations table — one row per recommendation run for a student.
CREATE TABLE IF NOT EXISTS TrackRecommendations (
    recommendation_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         INTEGER NOT NULL REFERENCES Students(student_id),
    recommended_track  TEXT,
    runner_up_track    TEXT,
    confidence         REAL,
    advisor_decision   TEXT CHECK (advisor_decision IN ('approve','choose_other','request_assessment')
                                    OR advisor_decision IS NULL),
    decided_by         TEXT,
    status             TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','awaiting_diagnostic','awaiting_advisor',
                                         'awaiting_assessment','completed','failed')),
    created_at         TEXT NOT NULL DEFAULT (DATETIME('now')),
    decided_at         TEXT
);

-- DiagnosticAssessments table — diagnostic/targeted exams tied to a
-- recommendation run. `subject` is always a real Courses.title (never an
-- invented subject like "Linear Algebra"), so a result can be matched
-- back to a Track's prerequisites/core_courses directly.
-- `trigger` distinguishes the missing-data diagnostic (session #1) from
-- an advisor-requested targeted assessment (session #2+) on the same
-- course, so a prior result is reused as evidence instead of re-asked.
CREATE TABLE IF NOT EXISTS DiagnosticAssessments (
    assessment_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id  INTEGER NOT NULL REFERENCES TrackRecommendations(recommendation_id),
    student_id         INTEGER NOT NULL REFERENCES Students(student_id),
    subject             TEXT NOT NULL,     -- Courses.title, e.g. 'Introduction to Python'
    trigger             TEXT NOT NULL CHECK (trigger IN ('missing_data', 'advisor_request')),
    score                REAL,              -- NULL until completed
    status               TEXT NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending','completed')),
    created_at           TEXT NOT NULL DEFAULT (DATETIME('now')),
    completed_at         TEXT
);

-- ------------------------------------------------------------
-- Tickets (shared failure/recovery path — Phase-3 graphs)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Tickets (
    ticket_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    source_graph    TEXT NOT NULL,     -- 'academic_integrity' | 'adaptive_assessment' | 'track_recommendation'
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
CREATE INDEX IF NOT EXISTS idx_cert_requests_student        ON CertificateRequests(student_id);
CREATE INDEX IF NOT EXISTS idx_scholarship_apps_student     ON ScholarshipApplications(student_id);
CREATE INDEX IF NOT EXISTS idx_candidates_job               ON Candidates(job_id);
CREATE INDEX IF NOT EXISTS idx_candidate_scores_candidate    ON CandidateScores(candidate_id);
CREATE INDEX IF NOT EXISTS idx_shortlists_job                ON Shortlists(job_id);
CREATE INDEX IF NOT EXISTS idx_shortlist_entries_shortlist    ON ShortlistEntries(shortlist_id);
CREATE INDEX IF NOT EXISTS idx_shortlist_entries_candidate    ON ShortlistEntries(candidate_id);
CREATE INDEX IF NOT EXISTS idx_interviews_job                 ON Interviews(job_id);
CREATE INDEX IF NOT EXISTS idx_interviews_candidate            ON Interviews(candidate_id);
CREATE INDEX IF NOT EXISTS idx_hiring_decisions_job            ON HiringDecisions(job_id);
CREATE INDEX IF NOT EXISTS idx_track_recs_student               ON TrackRecommendations(student_id);
CREATE INDEX IF NOT EXISTS idx_diagnostic_assess_rec             ON DiagnosticAssessments(recommendation_id);
CREATE INDEX IF NOT EXISTS idx_diagnostic_assess_student         ON DiagnosticAssessments(student_id);