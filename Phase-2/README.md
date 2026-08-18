# Brightpeak Academic Management Assistant

An AI assistant for Brightpeak Academy that helps students, instructors, and administrators access academic data securely and in an organized way using Gemini and the Model Context Protocol (MCP).

---

## 🎯 Project Idea

Gemini does not connect to the SQLite database directly. Requests go through the MCP server, which handles tool execution, authorization, validation, resources, prompts, notifications, elicitation, and sampling.

```text
User
  │
  ▼
Gemini / Agent
  │
  ▼
MCP Server
  │
  ▼
SQLite Database
```

For a request such as:

```text
"Show me student #1's profile"
```

the flow is:

```text
User
  ↓
Gemini Client
  ↓
Agent chooses get_student_profile
  ↓
MCP Server validates + authorizes
  ↓
SQLite returns the data
  ↓
Gemini formats the answer
```

Gemini never queries SQLite directly; the MCP server is the component that accesses the database.

---

## 🗄️ Database

The project uses **SQLite** with the database stored at `db/brightpeak.db`.

The database is defined by:

- `db/schema.sql` — table definitions and relationships.
- `db/seed.sql` — seed data and edge cases used by the project.
- `db/ERD.png` — entity-relationship diagram.

Main entities include `Students`, `Instructors`, `Courses`, `Enrollments`, `Assignments`, `Grades`, `Attendance`, and `Policies`.

```text
Instructors (1) ──< Courses (N)
                         │
                         ├──< Assignments ──< Grades >── Students
                         ├──< Enrollments >──────────── Students
                         └──< Attendance >───────────── Students

Policies are exposed as MCP Resources.
```

---

## 📂 Phase-2 Structure

```text
Phase-2/
│
├── README.md
├── requirements.txt
│
├── db/
│   ├── brightpeak.db
│   ├── schema.sql
│   ├── seed.sql
│   └── ERD.png
│
├── documents/
│   ├── academic_integrity.md
│   ├── attendance_policy.md
│   ├── course_withdrawal_policy.md
│   ├── exam_and_assessment_policy.md
│   ├── late_submission_policy.md
│   ├── scholarship_policy.md
│   └── student_handbook_excerpt.md
│
├── mcp_server/
│   ├── server.py
│   ├── database.py
│   ├── tools.py
│   ├── resources.py
│   ├── prompts.py
│   ├── notifications.py
│   ├── auth.py
│   ├── roles.py
│   ├── validation.py
│   └── schemas.py
│
├── agent/
│   ├── client.py
│   ├── agent_stage1.py
│   ├── agent_stage2.py
│   ├── agent_stage3.py
│   ├── agent_stage4.py
│   ├── agent_stage5.py
│   ├── agent_stage6.py
│   ├── demo.py
│   ├── demo_http.py
│   ├── demo_rag.py
│   ├── memory_integration.py
│   └── test_memory_integration.py
│
├── memory/
│   ├── short_term.py
│   ├── scratchpad.py
│   ├── router.py
│   ├── episodic.py
│   ├── semantic.py
│   ├── consolidation.py
│   ├── recall.py
│   └── verification.py
│
├── rag/
│   ├── chunker.py
│   ├── embedder.py
│   ├── vector_db.py
│   ├── ingestion.py
│   ├── naive_rag.py
│   ├── hybrid_rag.py
│   ├── agentic_rag.py
│   ├── graph_rag.py
│   ├── self_rag.py
│   ├── rag_tool.py
│   └── store/
│
├── context_eval/
│   ├── sliding_window.py
│   ├── observation_masking.py
│   ├── recursive_summary.py
│   ├── zone_pruning.py
│   ├── test_cases.json
│   └── evaluate.py
│
├── retrieval_eval/
│   ├── questions.json
│   ├── evaluate.py
│   ├── comparison_table.md
│   └── results.json
│
├── planning/
│   ├── algorithms/
│   │   ├── decomposition.py
│   │   ├── dynamic_decomposition.py
│   │   ├── environment.py
│   │   ├── reflexion.py
│   │   ├── self_refine.py
│   │   ├── plan_and_solve.py
│   │   ├── tree_of_thoughts.py
│   │   └── lats.py
│   ├── evidence/
│   ├── integration.py
│   ├── llm_provider.py
│   ├── models.py
│   ├── router.py
│   ├── demo_self_correction.py
│   ├── demo_grounding_comparison.py
│   └── tests/
│       ├── test_environment.py
│       ├── test_real_database.py
│       ├── test_reflexion.py
│       └── test_self_correction.py
│
├── planning_eval/
│   ├── cases/
│   │   ├── case_ps_001.json
│   │   ├── case_tot_001.json
│   │   └── case_lats_001.json
│   ├── artifacts/
│   │   ├── plan_and_solve/
│   │   ├── tree_of_thoughts/
│   │   ├── lats/
│   │   └── router/
│   ├── test_decomposition.py
│   ├── test_dynamic_decomposition.py
│   ├── test_plan_and_solve.py
│   ├── test_tree_of_thoughts.py
│   ├── test_lats.py
│   └── test_router.py
│
└── Tests/
    ├── integration_tests.py
    ├── sample_conversations.json
    ├── evidence/
    └── results/
```

---

## ✅ MCP Features

| Feature | What the project demonstrates |
|---|---|
| Capability negotiation | Client/server capabilities are checked during the MCP session. |
| Notifications | Authentication can trigger `tools/list_changed`. |
| Elicitation | Sensitive writes can require explicit human confirmation. |
| Resources | Academic policies are exposed through `policy://` resources. |
| Prompts | Reusable prompt templates are exposed through MCP prompts. |
| Progress tracking | Long-running reporting tools emit progress updates. |
| Defensive tool design | Inputs and authorization are validated against the server/database. |
| Sampling | The connected client model can generate an academic advisory narrative. |
| Transport | `stdio` and Streamable HTTP are supported. |

---

## 🔧 MCP Tool Model

### Read-only tools

Examples include:

- `get_student_profile`
- `get_student_enrollments`
- `get_student_attendance`
- `get_student_grades`
- `generate_academic_advisory`
- `generate_course_report`

### Write tools

Write access is unlocked after successful staff authentication and is protected by role checks and validation:

- `record_grade`
- `update_attendance`
- `change_enrollment_status`

Sensitive operations can pause for human confirmation through MCP elicitation.

---

## 🚀 Transport

### stdio

Used for local development and the normal demo flow.

```bash
python server.py
```

### Streamable HTTP

Used when the server runs as a standalone service and supports multiple sessions.

```bash
python server.py --http
```

---

# Phase 2 — Memory & RAG Extension

## 🧠 Memory Problem

The MCP tools expose current structured data, but the agent also needs to remember useful information from earlier sessions.

The memory system addresses this with:

```text
Conversation
   ↓
Short-Term Memory
   ↓
Promote / Drop Router
   ↓
Episodic Memory
   ↓
Consolidation
   ↓
Semantic Memory
```

Relevant memories are recalled and verified before being included in the agent context.

Main memory components:

- `memory/short_term.py` — rolling recent-message buffer.
- `memory/scratchpad.py` — current plan, sub-goal, and working state.
- `memory/router.py` — decides whether evicted information is forgotten or promoted to episodic memory.
- `memory/episodic.py` — persistent event memory.
- `memory/semantic.py` — versioned facts with supersession/expiration.
- `memory/consolidation.py` — converts useful episodes into stable semantic facts.
- `memory/recall.py` — retrieves relevant memories.
- `memory/verification.py` — filters unsupported or stale memories.

---

## 📚 RAG Problem

Company policies are stored as documents rather than being converted into one MCP tool per paragraph. RAG gives the agent passage-level retrieval over that knowledge.

```text
Documents
   ↓
Chunking
   ↓
Embeddings / Vector Index
   ↓
Retrieval
   ↓
Verification
   ↓
Grounded Answer
```

The current RAG pipeline contains:

- Heading-aware document chunking.
- Vector storage using an HNSW index and metadata.
- Naive RAG baseline.
- Hybrid retrieval using vector similarity + BM25.
- Agentic multi-step retrieval.
- Graph RAG as an optional path.
- Self-RAG verification before an answer is returned.
- Retrieval evaluation under `retrieval_eval/`.

### Retrieval results

The current repository reports the following comparison over 12 questions:

| Architecture | Accuracy | Avg tokens/query | Avg latency/query |
|---|---:|---:|---:|
| Naive RAG | 86% | 469 | 0.001s |
| Hybrid Search | 89% | 492 | 0.001s |
| Agentic RAG | 89% | 404 | 0.001s |
| Graph RAG | 38% | 538 | 0.024s |

Shipping choice:

- **Hybrid Search** is the default retrieval path.
- **Agentic RAG** is used for multi-part / decomposition-style retrieval questions.
- **Graph RAG** remains available for relationship-heavy queries.

Run the retrieval evaluation from `Phase-2` with:

```bash
python -m retrieval_eval.evaluate
```

---

## 🧾 Context Management Evaluation

The project compares four strategies for reducing the active context:

| Strategy | Accuracy | Passed | Avg Token Reduction | Avg Tokens After | Avg Latency (ms) |
|---|---:|---:|---:|---:|---:|
| Sliding Window | 66.7% | 4/6 | 22.9% | 116.0 | 0.0062 |
| Observation Masking | 66.7% | 4/6 | -4.6% | 166.3 | 0.0143 |
| Recursive Summary | 66.7% | 4/6 | -3.1% | 164.0 | 0.0195 |
| Zone Pruning | 83.3% | 5/6 | 11.2% | 133.0 | 0.0853 |

---

# Phase 2 — Planning Agent

## 🎯 Why a separate planning agent?

The planning lab adds a **new agent** for requests that cannot be safely handled by a single tool call or single LLM turn. The planning agent reuses the existing `mcp_server/` and `db/` instead of duplicating them.

```text
User Request
    ↓
Planning Agent
    ↓
DAG Decomposition
    ↓
Planning Algorithm (via Router)
    ↓
Execution / Verification
    ↓
Self-Correction
    ↓
Final Output
```

The repository contains both decomposition algorithms and the planning algorithms required by the lab. The final README deliberately does not invent planning benchmark numbers that are not present in the final repository.

---

## 🧩 Planning Components

### Decomposition

- `planning/algorithms/decomposition.py` — decomposition-first planning.
- `planning/algorithms/dynamic_decomposition.py` — interleaved plan → act → observe → replan behavior.

### Planning algorithms

- `planning/algorithms/plan_and_solve.py` — single structured plan followed by execution. The model is instructed to explicitly separate a **PLAN** phase from a **SOLUTION** phase in one pass (temperature `0.2`, favoring deterministic output). This is the cheapest of the three methods and the router's default.
- `planning/algorithms/tree_of_thoughts.py` — beam-search style planning. At each depth, every node in the frontier generates up to 2 candidate continuations (`ThoughtCandidates`, structured output), each candidate is scored independently by a second, judge-style structured call (`ThoughtEvaluation`, score in `[0, 1]` + rationale), and only the top `beam_width` scoring thoughts survive to the next depth. Generation uses a higher temperature (`0.5`) for diverse candidates, while judging uses a low temperature (`0.1`) to keep scoring consistent.
- `planning/algorithms/lats.py` — Monte Carlo Tree Search (MCTS) over candidate solutions, grounded by real environment feedback. Each iteration: selects a leaf via **UCT** (`_uct`, exploration constant `√2`), expands it with `n_actions` distinct candidate solutions, evaluates every candidate against the real `Environment` (`environment.evaluate(state)` → `EnvironmentFeedback`), combines that grounded score with a model self-estimate (`0.75 × environment_score + 0.25 × model_score`) as the backpropagated value, and — for any branch that fails — asks the model to write a short reflection that later expansions can read (capped to the last 4 reflections along the trajectory). The search stops early on the first environment-verified success, or after `iterations` rounds, returning the best-scoring node found. `flatten_lats_tree` serializes the full search tree (visits, mean value, environment/model scores, feedback, reflections) for evidence/inspection.
- `planning/router.py` — routes each instruction to one of the three algorithms above and dispatches to it through a single uniform interface (`route_and_solve`). See **🔀 Planning Router** below.
- `planning/llm_provider.py` — shared LLM client (`get_planning_llm`) used by the planning algorithms, the router, and the evaluation scripts, so every algorithm talks to the model through one configured provider instead of instantiating its own client.

### Supporting integration

- `planning/models.py` — planning data structures (`Thought`, `EnvironmentFeedback`, etc.) shared across algorithms.
- `planning/integration.py` — planning integration layer.

---

## 🔀 Planning Router

`planning/router.py` decides which planning algorithm handles a given instruction. The decision is a **pure function** (`classify_task`) over the instruction text — no LLM call is made to route — so the rationale stays inspectable and testable in isolation.

Routing checks LATS signals first, then Tree-of-Thoughts signals, and anything left over falls through to Plan-and-Solve. The intent is to route on **the real cost of being wrong**, not on how "hard" the task sounds:

| Signal in instruction | Routed to | Why |
|---|---|---|
| `recommend`, `recommendation`, `advisory`, `advise`, `final decision`, `should the advisor`, `intervention plan`, `propose` | **LATS** | This is the sub-task whose output actually ships to a student/advisor. A wrong answer here has a real cost, so it's worth paying for grounded, environment-verified search instead of trusting the model's opinion of itself. |
| `rank`, `prioriti(ze/se)`, `compare`, `which option`, `best order`, `risk factors` | **Tree of Thoughts** | Several plausible orderings/framings exist and are worth comparing before committing, but a wrong pick is cheap to redo — self-evaluated lookahead is enough without paying for a grounded environment call. |
| *(no signal matched)* | **Plan-and-Solve** | No branching or high-stakes recommendation is involved — treated as a single deterministic reasoning chain, the cheapest method that fits. |

### Dispatch: `route_and_solve`

```python
route_and_solve(
    instruction: str,
    llm: Any,
    *,
    environment: Any = None,
    tot_depth: int = 2,
    tot_beam_width: int = 2,
    lats_iterations: int = 2,
    lats_n_actions: int = 2,
) -> dict[str, Any]
```

`route_and_solve` calls `classify_task`, then dispatches to the matching algorithm and returns a **uniform result envelope**:

- always: `method`, `reason`, `result`
- Tree of Thoughts adds: `candidates` (all surviving thoughts, not just the best)
- LATS adds: `success`, `best_score`, `iterations`

This uniform shape is what lets `planning_eval` compare all three methods on the same basis.

**Safety guard:** if `classify_task` routes to LATS but no grounded `environment` is passed in, `route_and_solve` raises a `ValueError` instead of silently falling back to an ungrounded evaluator — LATS's whole value comes from grounded feedback, so it must never run without it.

### Example

```python
from planning.llm_provider import get_planning_llm
from planning.router import route_and_solve

llm = get_planning_llm()
result = route_and_solve(
    "Recommend whether this student should get the scholarship",
    llm,
    environment=environment,
)
print(result["method"])   # "lats"
print(result["reason"])   # why it was routed there
```

### Running the router test

```bash
cd Phase-2
python -m planning_eval.test_router
```

This verifies `classify_task` against three fixed cases (`case_ps_001`, `case_tot_001`, `case_lats_001`), performs one real dispatch through `route_and_solve` for Plan-and-Solve, confirms LATS refuses to run without an explicit environment, and saves evidence to `planning_eval/artifacts/router/case_router_001_result_live.json`.

---

# Self-Correction & Grounding

This is the Self-Correction and Grounding implementation owned by **Farida**.

## 🌱 Grounded Environment

`planning/algorithms/environment.py` replaces the toolkit's generic/random evaluator with a Brightpeak-specific check backed by the real database.

The scholarship example uses:

```text
Student data + Grades
        ↓
Brightpeak DB
        ↓
Average calculation
        ↓
Scholarship threshold check
        ↓
PASS / FAIL feedback
```

The real database used by the integration tests is:

```text
db/brightpeak.db
```

This makes the feedback external to the model instead of relying on the model to judge its own answer. It is the same `Environment.evaluate(state) -> EnvironmentFeedback` interface that `planning/algorithms/lats.py` calls during its grounded MCTS search.

## ✏️ Self-Refine

`planning/algorithms/self_refine.py` implements the single-draft correction scope:

```text
Draft
  ↓
Grounded critique
  ↓
Revision
  ↓
Verification
```

The project includes `planning/tests/test_self_correction.py` and `planning/demo_self_correction.py` as evidence.

## 🔄 Reflexion

`planning/algorithms/reflexion.py` implements the multi-trial correction scope:

```text
Trial 1
  ↓
External evaluation
  ↓
Reflection
  ↓
Capped memory
  ↓
Trial 2
```

The reflection from a failed trial is visible to the next trial, and `planning/tests/test_reflexion.py` verifies that transfer.

*(LATS uses the same idea internally, at the search-node level: every failed branch gets a short reflection, and expansions along that branch see the last 4 reflections in the trajectory.)*

## ⚖️ Grounded vs. Ungrounded Evidence

`planning/demo_grounding_comparison.py` demonstrates the same incorrect scholarship decision under two evaluators:

```text
Ungrounded critique
→ accepts the draft because it looks clear and consistent

Grounded environment
→ checks Brightpeak data
→ detects that the student's average is 85% while the threshold is above 90%
→ rejects the decision
```

This provides an explicit example where external verification catches a failure that an ungrounded self-critique misses.

---

## 🧪 Self-Correction Tests

The planning self-correction suite includes:

- `planning/tests/test_environment.py`
- `planning/tests/test_self_correction.py`
- `planning/tests/test_reflexion.py`
- `planning/tests/test_real_database.py`

During development, these tests were run together and produced:

```text
11 passed
```

The real-database integration tests use `Phase-2/db/brightpeak.db`.

Example command:

```bash
cd Phase-2
python -m pytest planning/tests/test_environment.py planning/tests/test_self_correction.py planning/tests/test_reflexion.py planning/tests/test_real_database.py -q
```

### Self-correction demos

Run the Self-Refine + Reflexion demo from `Phase-2` with:

```bash
python -m planning.demo_self_correction
```

Run the grounded-vs-ungrounded comparison with:

```bash
python -m planning.demo_grounding_comparison
```

---

## 👥 Team Responsibilities

| Member | Responsibility |
|---|---|
| **Ahmed** | Task decomposition, including decomposition-first, dynamic decomposition, DAG construction, and related integration work. |
| **Fatma** | Planning algorithms (`planning/algorithms/plan_and_solve.py`, `tree_of_thoughts.py`, `lats.py`), the algorithm router (`planning/router.py`), and the shared LLM provider layer (`planning/llm_provider.py`). |
| **Farida** | Self-Correction & Grounding: `self_refine.py`, `reflexion.py`, real `EnvironmentFeedback`, grounded-vs-ungrounded evidence, related tests/demos, and README maintenance. |
| **Omar** | MCP server, tools, notifications, resources, prompts, authorization, validation, progress tracking, and sampling. |

Memory and RAG components are shared Phase-2 work owned by the corresponding team members described in the project history.

---

## 📝 Planning Evaluation Status

The repository contains planning evaluation scaffolding under `planning_eval/`, including:

- decomposition and dynamic-decomposition tests (`test_decomposition.py`, `test_dynamic_decomposition.py`),
- routing + dispatch tests (`test_router.py`) with fixed cases `case_ps_001`, `case_tot_001`, `case_lats_001`, and saved evidence under `planning_eval/artifacts/router/`,
- per-algorithm evaluation tests (`test_plan_and_solve.py`, `test_tree_of_thoughts.py`, `test_lats.py`), with evidence saved under `planning_eval/artifacts/plan_and_solve/`, `tree_of_thoughts/`, and `lats/`.

The final README does **not** claim a completed PS vs. ToT vs. LATS benchmark comparison (accuracy/success rate, LLM calls, tokens, latency across all three) because that aggregate comparison is not yet present as complete evidence in the final repository snapshot.

When the team finishes the remaining planning evaluation, this section should be extended with the required fixed-request comparison of:

- decomposition-first vs. dynamic decomposition,
- Plan-and-Solve vs. Tree of Thoughts vs. LATS,
- Self-Refine vs. Reflexion,
- accuracy/task success,
- LLM calls,
- tokens,
- latency,
- and grounded vs. ungrounded evidence.

---

## 🎥 Demos and Evidence

The repository contains evidence and demos across the system:

- `agent/` — MCP protocol demos and memory/RAG integration.
- `Tests/` — broader integration evidence and outputs.
- `memory/evidence/` — memory-system evidence.
- `context_eval/evidence/` — context strategy comparison evidence.
- `rag/evidence/` — retrieval verification evidence.
- `planning/` — self-correction demos and tests.
- `planning/evidence/` — routing decisions and dispatch evidence saved by the router evaluation.
- `planning_eval/artifacts/` — planning evaluation traces currently present in the repository, including per-algorithm runs (`plan_and_solve/`, `tree_of_thoughts/`, `lats/`) and router dispatch runs (`router/case_router_001_result_live.json`).

---

## 🧭 Final Architecture

```text
                         ┌──────────────────┐
                         │      User        │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  Agent / Gemini  │
                         └───────┬──────────┘
                                 │
                ┌────────────────┼─────────────────┐
                │                │                 │
                ▼                ▼                 ▼
           Memory/RAG       Planning Agent     MCP Tools
                │                │                 │
                │        ┌───────┴────────┐        ▼
                │        │                │     MCP Server
                │        ▼                │        │
                │   Router (PS/ToT/LATS)  │        ▼
                │        │                │     SQLite DB
                │        ▼                │
                │   DAG + verification ───┘
                ▼                
        Relevant memories         
        + document evidence       
```

The architecture keeps the existing MCP server and database shared across the agents while separating the Memory & RAG path from the new Planning Agent.