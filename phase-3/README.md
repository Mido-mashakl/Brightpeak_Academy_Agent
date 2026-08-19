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
| Fatma | _TBD_ | _TBD_ |
| Ahmed | _TBD_ | _TBD_ |

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
| 3 | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| 4 | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
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
| MCP Server Lab | _TBD_ | _TBD_ | _TBD_ |
| Decomposition & Planning Lab | _TBD_ | _TBD_ | _TBD_ |

## Repository Layout (this phase)

```
Phase-3/
  README.md                      <- this file
  state_graph/
    academic_integrity/          <- Farida's graph 1
      graph.py                   <- nodes, edges, cycles
      state.py                   <- typed state schema
      checkpointing.py           <- checkpointer wiring
      hitl.py                    <- HITL node(s)
      tickets.py                 <- failure/ticket path
    adaptive_assessment/         <- Farida's graph 2
      graph.py
      state.py
      checkpointing.py
      hitl.py
      tickets.py
    <fatma's problems>/
    <ahmed's problems>/
  teaching_flow/
    pipeline.py                  <- course-scoped RAG fix (question -> chunks -> answer + source; NOT a state graph)
  platform/
    admin/                       <- tool add/remove, RAG doc add/remove, HITL + ticket resolution
    user/                        <- agent switcher + chat
  evidence/                      <- demo recordings/transcripts (HITL pause+resume, ticket resolve+resume, crash+resume)
```

## Locatable Concerns (per grading rubric)

For every graph under `state_graph/<problem>/`, a grader must be able to find without reading the
whole file:
- the graph + cycle definitions → `graph.py`
- the checkpointing calls → `checkpointing.py`
- the HITL node → `hitl.py`
- the ticket/failure-recovery path → `tickets.py`

## Setup

_TBD — fill in once the environment/dependencies for Phase 3 are finalized (same `db/brightpeak.db`,
same `mcp_server/`, plus `langgraph` and platform dependencies)._

## Demo Evidence

- [ ] HITL pause on a genuine condition, resolved by an admin through the platform
- [ ] A run failing mid-node → ticket created → resolved → resumed from checkpoint
- [ ] Process killed mid-run → restarted → resumes without re-execution