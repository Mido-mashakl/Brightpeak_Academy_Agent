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
| Farida | Academic Integrity Investigation & Appeal (state graph candidate) | Teaching Flow — course-scoped RAG (not a state graph; correction/extension of the Memory & RAG Lab) |
| Fatma | _TBD_ | _TBD_ |
| Ahmed | _TBD_ | _TBD_ |

> Note: the Teaching Flow (course-material Q&A) is **not** a state-graph candidate — it's a
> single-pass RAG pipeline (question in, answer out). Per the assignment brief, an agent like this
> "neither holds state across days, waits on an outside reply, nor needs a human to sign off
> mid-run" so it can't be one of the three. It's kept in Phase-3 as a correction/extension of the
> Memory & RAG Lab instead.

## Candidate State Graph Problems (final 3 selected from these)

| # | Owner | Problem | Why it needs a state graph (not a linear script) | Two LLM-call additions |
|---|---|---|---|---|
| 1 | Farida | Academic Integrity Investigation & Appeal | Waits days for a student appeal; requires two separate human sign-offs (committee review + final decision); a single retry can't fix "no appeal ever arrives" | RAG (pull real academic-integrity policy to assess severity) + Tree of Thoughts (evaluate multiple interpretations of the student's appeal against the evidence) |
| 2 | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| 3 | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| 4 | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| 5 | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| 6 | _TBD_ | _TBD_ | _TBD_ | _TBD_ |

## Reusing Phase-2 From Phase-3 (local copies, not shared imports)

To avoid confusion across the team, needed Phase-2 assets are **copied** into `Phase-3/` directly
rather than imported at runtime. Copied once from `Phase-2/` on the `farida` branch:

- `db/` (`schema.sql`, `seed.sql`, `brightpeak.db`) — extended in Phase-3 with new tables
  (`IntegrityCases`, `IntegrityEvidence`, `IntegrityAppeals`, `IntegrityDecisions`); the
  LangGraph checkpointer also writes to this same `brightpeak.db`.
- `documents/academic_integrity.md` and `documents/course_materials/`
- `rag/` (chunker, ingestion, embedder, vector_db, rag_tool, and the prebuilt `store/`)
- `mcp_server/` (all tools, resources, schemas, auth, roles)
- `agent/teaching_agent.py` (only the current agent, not the historical `agent_stage*.py` files)

> Note: this is a point-in-time copy on the `farida` branch, not a live link. If `Phase-2/` changes
> later, these copies need to be manually re-synced.

## Corrections Carried Over From Prior Labs

| Lab | What was flagged | What was fixed | Owner |
|---|---|---|---|
| Memory & RAG Lab | _TBD_ | Chunker / ingestion / course-scoped filtering fixed in Phase 2, wired into Teaching Flow pipeline here | Farida |
| MCP Server Lab | _TBD_ | _TBD_ | _TBD_ |
| Decomposition & Planning Lab | _TBD_ | _TBD_ | _TBD_ |

## Repository Layout (this phase)

```
Phase-3/
  README.md                      <- this file
  state_graph/
    academic_integrity/          <- Farida's graph
      graph.py                   <- nodes, edges, cycles
      state.py                   <- typed state schema
      checkpointing.py           <- checkpointer wiring
      hitl.py                    <- HITL node(s)
      tickets.py                 <- failure/ticket path
    <problem_2>/
    <problem_3>/
  teaching_flow/
    pipeline.py                  <- Farida's RAG pipeline (question -> chunks -> answer + source)
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
