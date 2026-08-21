# Phase 3 — Persistent State, HITL, and the Product Surface

Extending the Brightpeak Academy Agent system (same MCP server, same `db/`, same agents from
Phase 1 and Phase 2) with:
1. Three genuinely stateful problems, modeled as LangGraph state graphs with checkpointing.
2. Corrections/extensions to the three prior labs (MCP Server, Memory & RAG, Decomposition & Planning).
3. A platform (admin + user surface) that actually talks to the live MCP server and database.

## Team & Ownership

The instructor requires **3** final state-graph problems. As a team we're drafting **6** candidate
problems (2 per person) so we have a strong backup if any single problem doesn't hold up to
scrutiny — the strongest 3 get selected for final submission.

| Owner | Candidate Problem 1 | Candidate Problem 2 |
|---|---|---|
| Farida | Academic Integrity Investigation & Appeal (state graph candidate) | Adaptive Assessment & Mastery Evaluation (state graph candidate) |
| Fatma Saber | Faculty Hiring — CV Intake, Scoring & Shortlisting (state graph candidate) | _TBD_ |
| Ahmed | Student Advisor — Certificate & Scholarship Eligibility | Teaching feature: RAG-based Q&A over course material |

> Note: an earlier draft used "Teaching Flow" (plain course-scoped RAG, question in/answer out) as
> Farida's second candidate. Dropped — per the assignment brief, a single-pass RAG pipeline
> "neither holds state across days, waits on an outside reply, nor needs a human to sign off
> mid-run" so it can't be a state graph. Replaced with Adaptive Assessment & Mastery Evaluation,
> which genuinely cycles, pauses, and needs human review. The course-scoped RAG fix itself is kept
> as part of the Memory & RAG Lab correction, not a state graph candidate.

## Candidate State Graph Problems

| # | Owner | Problem | Why it needs a state graph (not a linear script) | Two LLM-call additions |
|---|---|---|---|---|
| 1 | Farida | **Academic Integrity Investigation & Appeal** | Waits days for a student appeal; requires two separate human sign-offs (committee review + final decision); a single retry can't fix "no appeal ever arrives". | **RAG** (pull real academic-integrity policy to assess severity) + **Tree of Thoughts** (evaluate multiple interpretations of the student's appeal against the evidence) |
| 2 | Farida | **Adaptive Assessment & Mastery Evaluation** | Genuinely cycles (select question → evaluate answer until mastery or question-cap is reached, not a single pass); a student can close the browser mid-assessment and resume later from checkpoint; a suspicious answer pattern must pause official grading for a human instructor review, not auto-record. | **Task Decomposition** (build the next-question sequence based on performance so far) + **Constrained ReAct** (grade answers, including free-text, against a fixed rubric/partial-credit tool set, not free LLM judgment) |
| 3 | Ahmed | **Student Advisor — Certificate & Scholarship Eligibility** | The advisor workflow may wait for missing student information or human review, can return to eligibility evaluation after new evidence arrives, and must preserve the collected profile and analysis across interruptions. | **RAG** + **Task Decomposition** |
| 4 | Fatma Saber | **Faculty Hiring — CV Intake, Scoring & Shortlisting** | Waits indefinitely at `awaiting_more_applications` for new CVs or the deadline event (not a linear script); new CVs arrive as external events on the same thread without reprocessing existing candidates; the shortlist pauses at `hitl_dept_head_review` for a real human sign-off (hire / interview / rescore), and the rescore → shortlist → HITL path is a genuine cycle; a parse/score failure opens a ticket and resumes from checkpoint instead of restarting. | **RAG** (`parse_and_validate` grounds parsing rules in `documents/hiring/hiring_policies.md`, especially "never invent missing fields") + **Constrained ReAct** (`score_cv_against_qualifications` force-calls a single `score_candidate` tool so scores/breakdowns can't be free-form prose or hallucinated) |
| 5 | fatma | **Track Recommendation & Prerequisite Assessment** | Genuinely cycles through missing prerequisite courses, pausing for the student to complete a real Adaptive Assessment for each missing course; resumes Track Recommendation only when all gaps are filled; requires Human-in-the-Loop (Advisor) review for unclear confidence gaps; supports RAG failure recovery via ticketing. | **RAG** (validate track requirements against `documents/track_requirements.md`) + **Tree of Thoughts** (rank candidate tracks using multiple strategies) |


**Teaching is not one of the five state-graph problems**. It
doesn't hold state across days, wait on an outside reply, or need a
human to sign off mid-run — so it stays a plain, single-pass RAG
chatbot: student asks a question, we answer from *their course's*
material only.

## Reusing Phase-2 From Phase-3 (local copies, not shared imports)

To avoid confusion across the team, needed Phase-2 assets are **copied** into `Phase-3/` directly
rather than imported at runtime. Copied once from `Phase-2/` on the `farida` branch:

- `db/` (`schema.sql`, `seed.sql`, `brightpeak.db`) — extended in Phase-3 with new tables:
  `IntegrityCases`, `IntegrityEvidence`, `IntegrityAppeals`, `IntegrityDecisions` (Academic
  Integrity graph), `AssessmentSessions`, `AssessmentAnswers` (Adaptive Assessment graph), and a
  shared `Tickets` table used by both graphs' failure-recovery path. The LangGraph checkpointer
  also writes to this same `brightpeak.db`.
- `documents/academic_integrity.md` and `documents/course_materials/`
- `rag/` (chunker, ingestion, embedder, vector_db, rag_tool, and the prebuilt `store/`)
- `mcp_server/` (all tools, resources, schemas, auth, roles)
- `agent/teaching_agent.py` (kept as the course-scoped RAG fix — see "Corrections" below; only the
  current agent copied, not the historical `agent_stage*.py` files)

> Note: this is a point-in-time copy on the `farida` branch, not a live link. If `Phase-2/` changes
> later, these copies need to be manually re-synced.

## New DB Tables (additive — nothing existing is modified)

```sql
-- Academic Integrity Investigation & Appeal
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

-- Adaptive Assessment & Mastery Evaluation
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

-- Shared failure/ticket path used by both graphs
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
```

## Corrections Carried Over From Prior Labs

| Lab | What was flagged | What was fixed | Owner |
|---|---|---|---|
| Memory & RAG Lab | Retrieval could leak chunks across courses (missing strict `course_id` filtering) | Chunker / ingestion / course-scoped filtering fixed in Phase 2; reused as-is by both new Phase-3 graphs (RAG node in Academic Integrity's `analyze_severity`, and course-material lookups) | Farida |
| Faculty Hiring (`state_graph/faculty_hiring/graph.py`) | Every `score_cv_against_qualifications` / `parse_and_validate` call returned `score=0`, empty `breakdown`, placeholder `reasoning` | Root cause: `.env` was overriding `GEMINI_MODEL` with a value that resolved to a weak/flaky model (`gemini-flash-lite-latest` → `gemini-3.5-flash-lite`), which under forced function-calling wrote stub args instead of real ones; the default in code was also briefly set to a nonexistent `gemini-2.5-flash` id for this account. Fixed by pinning `GEMINI_MODEL=gemini-3.6-flash` (confirmed available via `check_gemini_models.py`) in both the code default and `.env`. Also added retry-with-backoff on `429`/`503` HTTP errors in `_call_claude_constrained` and `_parse_cv_with_policy`, honoring the API's `retryDelay` when present. | Fatma Saber |
| Faculty Hiring (`mcp_server/database.py`) | `DeptHeads` table stayed empty even though `seed.sql` seeds it, so HITL sign-off (`submit_hire_decision`, etc.) failed with "No dept head with id 1" | `_init_db()` only checks whether `Students` is empty to decide whether to run `seed.sql`; if `brightpeak.db` already had rows in `Students` from an earlier run, `seed.sql` was skipped entirely and `DeptHeads` (created by `schema.sql` but never populated) stayed empty. Worked around by deleting the stale `brightpeak.db` and letting it rebuild from `schema.sql` + `seed.sql`; a proper fix would check each seeded table independently rather than gating the whole script on `Students` alone. | Fatma Saber |
| MCP Server Lab | *TBD* | *TBD* | *TBD* |
| Decomposition & Planning Lab | *TBD* | *TBD* | *TBD* |
| Track Recommendation (`state_graph/track_recommendation/`) | Demo scenarios crashed. Happy Path used an incomplete student (Ahmed). Missing Data scenario didn't loop through 3 interrupt/resume cycles for the 3 missing courses. `schema.sql` was missing the `decided_by` column, and student grades in `seed.sql` caused unclear confidence gaps. | Fixed Happy Path to use Student 3 (Mariam) with complete seed data. Added a while loop in the Missing Data scenario to handle all interrupts. Updated `schema.sql` to include `decided_by`. Adjusted `seed.sql` enrollments and grades to ensure clear auto-finalization for the Happy Path. | fatma saber |

## Repository Layout (this phase)

```
phase-3/
│
├── README.md
│
├── state_graph/
│   │
│   ├── academic_integrity/        # built
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── checkpointing.py
│   │   ├── hitl.py
│   │   └── tickets.py
│   │
│   ├── adaptive_assessment/       # built
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── checkpointing.py
│   │   ├── hitl.py
│   │   └── tickets.py
│   │
│   ├── advisory/                  # built (Student Advisor — Ahmed's problem)
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── data.py
│   │   ├── checkpointing.py
│   │   ├── hitl.py
│   │   └── tickets.py
│   │
│   └── faculty_hiring/            # built (Fatma Saber's problem)
│       ├── graph.py
│       ├── state.py
│       ├── checkpointing.py
│       ├── hitl.py
│       ├── tickets.py
│       ├── cv_text_extraction.py
│       ├── demo_faculty_hiring.py
│       ├── seed_demo.py
│       └── data/                  # demo_job.json, demo_candidates.json
│
├── test_academic_integrity_graph.py
├── test_adaptive_assessment_graph.py
├── crash_test_start.py
├── crash_test_resume.py
│
├── agent/
├── db/
├── documents/
├── mcp_server/
├── rag/
│
├── platform/                      # not yet built — see "Setup"
│   ├── admin/
│   └── user/
│
└── evidence/
```

> Faculty Hiring (`state_graph/faculty_hiring/`) uses Google Gemini (not Anthropic's Messages API)
> for its two LLM-call additions — see the `NOTE ON LLM PROVIDER` docstring at the top of
> `faculty_hiring/graph.py`. Requires `GEMINI_API_KEY` (and optionally `GEMINI_MODEL`, default
> `gemini-3.6-flash`) in `phase-3/.env`. The free tier is rate- and quota-limited (per-minute and
> per-day caps that vary by account); `_call_claude_constrained` and `_parse_cv_with_policy` retry
> automatically on `429`/`503` and back off using the API's own `retryDelay` when present, but a
> daily-quota `429` won't clear until the quota resets — swap in a different API key/account or a
> lighter model if you hit that mid-demo.
``` 
## Track Recommendation Scenarios (`seed_demo.py`)

The **`seed_demo.py`** script provides executable scenarios that drive the Track Recommendation graph and the REAL Adaptive Assessment graph across genuine **`interrupt()`** pauses using LangGraph's **`Command(resume=...)`**.

1. **Happy Path (`happy`)**: Uses Student 3 (Mariam), who has complete grades for all prerequisites. The graph collects data, runs RAG, calculates Tree of Thoughts (ToT) ranking, and auto-finalizes a track without hitting any interrupts.

2. **Missing Data (`missing_data`)**: Uses Student 1 (Ahmed), who is missing 3 prerequisite courses. The graph prepares 3 Diagnostic Assessments and interrupts once per missing course. The script loops through each interrupt, drives the REAL Adaptive Assessment to completion using **`aa_graph.resume_session(...)`**, and resumes the Track Recommendation graph until finalized.

3. **RAG Failure (`rag_failure`)**: Simulates a broken document in the RAG vector store. The graph opens a support Ticket, pauses for an admin to "fix" it, and resumes from the checkpoint (without restarting data collection) once the admin resumes with **`Command(resume={"fixed": True})`**.

4. **HITL Approve (`hitl_approve`)**: The graph calculates a close confidence gap between the top tracks, triggering an Advisor Review interrupt. The advisor approves the top recommendation, and the graph finalizes it.

5. **HITL Choose Other (`hitl_choose_other`)**: Similar to the above, but the advisor overrides the AI and selects the alternative track. The graph finalizes the advisor's choice.

6. **Targeted Assessment (`targeted_assessment`)**: The advisor requests more evidence on a specific subject. The graph starts a targeted Adaptive Assessment, interrupts for the student to complete it, re-evaluates the confidence scores with the new evidence, and routes back to the Advisor for a final decision.

7. **Checkpoint Restart (`checkpoint_restart`)**: Proves SQLite checkpoint persistence. The script drops the graph object entirely and rebuilds it from scratch (simulating a server restart) between interrupt/resume cycles for missing data, targeted assessments, and final HITL approval.