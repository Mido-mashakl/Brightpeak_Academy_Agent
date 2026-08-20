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
| Ahmed | Student Advisor — Certificate & Scholarship Eligibility | _TBD_ |

> Note: an earlier draft used "Teaching Flow" (plain course-scoped RAG, question in/answer out) as
> Farida's second candidate. Dropped — per the assignment brief, a single-pass RAG pipeline
> "neither holds state across days, waits on an outside reply, nor needs a human to sign off
> mid-run" so it can't be a state graph. Replaced with Adaptive Assessment & Mastery Evaluation,
> which genuinely cycles, pauses, and needs human review. The course-scoped RAG fix itself is kept
> as part of the Memory & RAG Lab correction, not a state graph candidate.

## Candidate State Graph Problems (final 3 selected from these)

| # | Owner | Problem | Why it needs a state graph (not a linear script) | Two LLM-call additions |
|---|---|---|---|---|
| 1 | Farida | Academic Integrity Investigation & Appeal | Waits days for a student appeal; requires two separate human sign-offs (committee review + final decision); a single retry can't fix "no appeal ever arrives" | RAG (pull real academic-integrity policy to assess severity) + Tree of Thoughts (evaluate multiple interpretations of the student's appeal against the evidence) |
| 2 | Farida | Adaptive Assessment & Mastery Evaluation | Genuinely cycles (select question ↔ evaluate answer until mastery or question-cap is reached, not a single pass); a student can close the browser mid-assessment and resume later from checkpoint; a suspicious answer pattern must pause official grading for a human instructor review, not auto-record | Task decomposition (build the next-question sequence based on performance so far) + Constrained ReAct (grade answers, including free-text, against a fixed rubric/partial-credit tool set, not free LLM judgment) |
| 3 | Ahmed | Student Advisor — Certificate & Scholarship Eligibility | The advisor workflow may wait for missing student information or human review, can return to eligibility evaluation after new evidence arrives, and must preserve the collected profile and analysis across interruptions. | RAG + Task Decomposition |
| 4 | Fatma Saber | Faculty Hiring — CV Intake, Scoring & Shortlisting | Waits indefinitely at `awaiting_more_applications` for new CVs or the deadline event (not a linear script); new CVs arrive as external events on the same thread without reprocessing existing candidates; the shortlist pauses at `hitl_dept_head_review` for a real human sign-off (hire / interview / rescore), and the rescore → shortlist → HITL path is a genuine cycle; a parse/score failure opens a ticket and resumes from checkpoint instead of restarting | RAG (`parse_and_validate` grounds parsing rules in `documents/hiring/hiring_policies.md`, esp. "never invent missing fields") + Constrained ReAct (`score_cv_against_qualifications` force-calls a single `score_candidate` tool so scores/breakdowns can't be free-form prose or hallucinated) |
| 5 | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| 6 | _TBD_ | _TBD_ | _TBD_ | _TBD_ |

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
| Faculty Hiring (`state_graph/faculty_hiring/graph.py`) | Every `score_cv_against_qualifications` / `parse_and_validate` call returned `score=0`, empty `breakdown`, placeholder `reasoning` | Root cause: `.env` was overriding `GEMINI_MODEL` with a value that resolved to a weak/flaky model (`gemini-flash-lite-latest` → `gemini-3.5-flash-lite`), which under forced function-calling wrote stub args instead of real ones; the default in code was also briefly set to a nonexistent `gemini-2.5-flash` id for this account. Fixed by pinning `GEMINI_MODEL=gemini-3.6-flash` (confirmed available via `check_gemini_models.py`) in both the code default and `.env`. Also added retry-with-backoff on `429`/`503` HTTP errors in `_call_claude_constrained` and `_parse_cv_with_policy`, honoring the API's `retryDelay` when present | Fatma Saber |
| Faculty Hiring (`mcp_server/database.py`) | `DeptHeads` table stayed empty even though `seed.sql` seeds it, so HITL sign-off (`submit_hire_decision`, etc.) failed with "No dept head with id 1" | `_init_db()` only checks whether `Students` is empty to decide whether to run `seed.sql`; if `brightpeak.db` already had rows in `Students` from an earlier run, `seed.sql` was skipped entirely and `DeptHeads` (created by `schema.sql` but never populated) stayed empty. Worked around by deleting the stale `brightpeak.db` and letting it rebuild from `schema.sql` + `seed.sql`; a proper fix would check each seeded table independently rather than gating the whole script on `Students` alone | Fatma Saber |
| MCP Server Lab | _TBD_ | _TBD_ | _TBD_ |
| Decomposition & Planning Lab | _TBD_ | _TBD_ | _TBD_ |

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
│   ├── advisory/                  # built (Student Advisor — Ahmed's problem)
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── data.py
│   │   ├── checkpointing.py
│   │   ├── hitl.py
│   │   └── tickets.py
│   │
│   ├── faculty_hiring/            # built (Fatma Saber's problem)
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── checkpointing.py
│   │   ├── hitl.py
│   │   ├── tickets.py
│   │   ├── cv_text_extraction.py
│   │   ├── demo_faculty_hiring.py
│   │   ├── seed_demo.py
│   │   └── data/                  # demo_job.json, demo_candidates.json
│   │
│   └── adaptive_assessment/       # planned, not yet built
│       └── ...
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
