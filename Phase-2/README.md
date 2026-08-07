# Brightpeak Academic Management Assistant

An AI Assistant for Brightpeak Academy that helps students, instructors, and administrators access academic data securely and in an organized way, built using the Model Context Protocol (MCP).

---

## 🎯 Project Idea

The LLM (Gemini) does not connect to the database directly. Instead, every request flows through an MCP Server, which handles authorization, tool execution, resource access, and input validation.

```
User
  │
  ▼
Gemini (LLM)
  │
  ▼
MCP Server
  │
  ▼
Database
```

### MCP Server Responsibilities
- Access control / authorization
- Executing tools
- Reading resources
- Validating inputs
- Protecting the database

### Example Request Flow

A quick walkthrough of what happens when a user asks *"Show me student #1's profile"*:

```
User: "Show me student #1's profile"
        │
        ▼
Gemini Client
        │
        ▼
Gemini decides: "I need student data" → picks a tool
        │
        ▼
MCP Agent → call_tool("get_student_profile", {student_id: 1})
        │
        ▼
MCP Server → validates + authorizes the call
        │
        ▼
SQLite → returns the student's data
        │
        ▼
Gemini formats the final, natural-language answer
```

Gemini never queries SQLite directly — it only ever decides which tool to call; the MCP Server is the one actually touching the database.

---

## 3. Entity-Relationship Diagram
 
See [`db/ERD.png`](db/ERD.png). Summary:
 
```
Instructors (1) ──< (N) Courses (1) ──< (N) Assignments (1) ──< (N) Grades >── (N) Students
                          │                                                        │
                          └──< (N) Enrollments >────────────────────────────────────┘
                          └──< (N) Attendance  >────────────────────────────────────┘
 
Policies (standalone reference table — exposed as MCP Resources, not joined to anything)
```
 
- `Students` — id, name, email, level (Beginner/Intermediate/Advanced)
- `Instructors` — id, name, email
- `Courses` — id, title, category, duration, `instructor_id` (FK → Instructors)
- `Enrollments` — student ↔ course, `status` (active/completed/dropped), `progress`,
  `enrollment_date`
- `Assignments` — belongs to a course, `max_score`, `deadline`
- `Grades` — student × assignment, `score`, `graded_by` (FK → Instructors)
- `Attendance` — student × course, `percentage`
- `Policies` — standalone reference documents (attendance, scholarship, academic
  integrity, late submission, course withdrawal)
Engine: **SQLite** (`db/brightpeak.db`), built from `db/schema.sql` and seeded from
`db/seed.sql` automatically on first run (see `mcp_server/database.py`). Seed data
covers normal cases (active enrollments, graded assignments) and edge cases (a student
already `dropped`, attendance below the 75% floor, a student already above the 90%
scholarship threshold).

---

## 📂 Project Structure

```
Brightpeak_Academy_Agent/
│
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
│
├── db/
│   ├── schema.sql
│   ├── seed.sql
│   ├── brightpeak.db
│   └── ERD.png
│
├── documents/
│   ├── academic_rules.pdf
│   ├── attendance_policy.pdf
│   ├── scholarship_policy.pdf
│   ├── exam_policy.pdf
│   └── ...
│
├── mcp_server/
│   ├── server.py
│   ├── tools.py
│   ├── resources.py
│   ├── prompts.py
│   ├── notifications.py
│   ├── auth.py
│   ├── validation.py
│   └── schemas.py
│
├── agent/
│   ├── client.py
│   ├── agent.py
│   ├── memory_rag_agent.py
│   └── demo.py
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
│   ├── naive_rag.py
│   ├── hybrid_rag.py
│   ├── agentic_rag.py
│   ├── self_rag.py
|   ├── graph_rag.py
|   ├── rag_tool.py
│   └── ingestion.py
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
└── tests/
    ├── memory_tests.py
    ├── rag_tests.py
    └── integration_tests.py
```

---

## ✅ Required MCP Features

| # | Feature | Description |
|---|---|---|
| 1 | **Capability Negotiation** | On connection, the server announces its capabilities and the client verifies them. Tools that need elicitation or sampling check the client's declared capabilities at call-time and degrade gracefully if unsupported. |
| 2 | **Notifications** | When a user authenticates (`authenticate_staff`), the server calls `tools/list_changed` so the client discovers new write tools immediately without reconnecting or polling. |
| 3 | **Elicitation** | Sensitive write operations pause mid-call and require explicit human confirmation before executing (see Tool Reference below). |
| 4 | **Resources** | Static policy documents (Attendance Policy, Scholarship Policy, Academic Integrity, Late Submission, Course Withdrawal) are exposed as `policy://` Resources — not Tools — so the model reads them once and reasons over them. |
| 5 | **Prompts** | Ready-made, parameterised templates: `draft_attendance_warning` and `explain_scholarship_eligibility`, available via `prompts/get`. |
| 6 | **Progress Tracking** | `generate_course_report` walks every enrolled student and emits real intermediate progress notifications (e.g. `50% - Processing Ahmed Mostafa`) so the client is never blocked. |
| 7 | **Defensive Tool Design** | Every tool has a JSON Schema derived from Python type hints. The server re-validates all inputs against the database independently of whatever the client sent, and re-derives authorization from the DB rather than trusting caller claims. |
| 8 | **Sampling** | `generate_academic_advisory` asks the connected client's own model (Gemini) to write a personalized narrative from raw student data via `sampling/createMessage`. The server never hard-codes a template; if the client doesn't declare sampling support the tool degrades to returning the raw structured facts instead of failing. |
| 9 | **Transport** | `stdio` for local development; `Streamable HTTP` for multi-session production (see Transport section below). |

---

## 🔧 Tool Reference

### Read-Only Tools
Available to every session, including unauthenticated front-desk connections. No write access, no role check required.

| Tool | What it does |
|---|---|
| `get_student_profile` | Look up a student's name, email, and level |
| `get_student_enrollments` | List a student's course enrollments and progress |
| `get_student_attendance` | Get a student's attendance percentage per course |
| `get_student_grades` | Get a student's grades and overall average |
| `generate_academic_advisory` | Generate a personalised advisory note via sampling |
| `generate_course_report` | Full progress report for every student in a course (with progress tracking) |

### Write Tools
**Not registered at startup.** Only available after a successful `authenticate_staff` call, which fires `tools/list_changed` to notify the client.

| Tool | Role required | Elicitation triggered when… |
|---|---|---|
| `record_grade` | instructor (own course) or registrar | Change crosses the 90% scholarship threshold **or** overwrites an existing grade by more than 15 points |
| `update_attendance` | instructor (own course) or registrar | Never — straightforward write |
| `change_enrollment_status` | instructor (own course) or registrar | Status is `dropped` and the student enrolled more than 14 days ago (Course Withdrawal Policy) |

### What happens when a required capability is missing?

| Situation | Server behaviour |
|---|---|
| `record_grade` needs elicitation but client didn't declare it | Returns an error message asking the operator to use a client that supports elicitation — **no change is made** |
| `change_enrollment_status` needs elicitation but client didn't declare it | Same — returns an error, no change made |
| `generate_academic_advisory` needs sampling but client didn't declare it | Degrades gracefully — returns the raw structured facts (grades, attendance, enrollments) instead of a generated narrative |

The server **never assumes** every client supports every capability. Both guards are checked at call-time via `ctx.session.client_params.capabilities`.

---

## 🚀 Transport

### What was built

The server supports two transports, selectable at startup:

```bash
# Local development (default — stdio)
python server.py

# Production / multi-campus (Streamable HTTP)
python server.py --http
```

### stdio — local development

**When to use:** A single staff member running the agent on their own machine.

**Why it fits here:** stdio launches the server as a subprocess of the client — no network, no open port, no auth layer needed at the transport level. The MCP session is 1-to-1 by design, which matches a local development or grading environment perfectly. This is what `demo.py` uses.

```
Client process
    └── spawns → server.py (subprocess)
                  stdin / stdout pipe
```

### Streamable HTTP — production

**When to use:** Multiple campuses or multiple staff sessions hitting the same server simultaneously.

**Why it fits here:** HTTP lets the server run as a standalone process that any number of clients can reach over the network. Each session gets its own session ID (confirmed in the demo output: `a2e0d24984bb4f20981cb5863f7c89b6`), so role escalation and write-tool unlocking are scoped correctly per connection — an instructor authenticating on Campus A does not unlock write tools for a front-desk session on Campus B.

```
Campus A client ──┐
Campus B client ──┼──► http://server:8000/mcp
Campus C client ──┘
         each with its own session ID and role state
```

**Why not WebSocket?** Streamable HTTP covers the same real-time use case (server-to-client notifications, progress streaming) without requiring a persistent connection, making it simpler to deploy behind a standard reverse proxy.

---

## 👥 Team Split

| Member     | Responsibilities                                                                                                                                                                                                                                                                         |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Ahmed**  |   **Memory & Retrieval Evaluation** — Context Window Management (Sliding Window, Observation Masking, Recursive Summarization, Zone-Based Pruning) + Database — ERD design, schema.sql, seed.sql, SQLite setup, test data                                                                                                    |
| **Omar**   | **MCP Server** — MCP Server, Tools, Notifications, Resources, Prompts, Authorization, Validation, Progress Tracking, Sampling                                                                                                                                                  |
| **Farida** | **Agent** — Gemini Client, Handshake, Tool Discovery, Tool Calls, Demo, README  + Responsible for designing and implementing Retrieval-Augmented Generation (RAG) pipeline-->  Document Collection & Preparation, Chunking, Embedding ,Vector Database, Naive RAG, Hybrid Search, Agentic RAG, Self-RAG Verification                                                                                                                                                                                            |
| **Fatma**  | **Memory System Extension** — Short-Term Memory, Scratchpad, Promote-or-Drop Router, Episodic Memory, Semantic Memory, Consolidation Layer, Memory Integration with the Agent   |


---

## 📝 Suggested GitHub Issues

- [ ] Design Database
- [ ] Create ERD
- [ ] Build MCP Server
- [ ] Implement Notifications
- [ ] Implement Resources
- [ ] Implement Sampling
- [ ] Build Agent
- [ ] Demo
- [ ] README
---------------------------------
**Phase 2**
 Implement Short-Term Memory
 Implement Scratchpad
 Implement Promote-or-Drop Router
 Build Episodic Memory
 Build Semantic Memory
 Implement Consolidation Layer
 Implement Sliding Window
 Implement Observation Masking
 Implement Recursive Summarization
 Implement Zone-Based Pruning
 Build Vector Database
 Implement Chunking Pipeline
 Generate Embeddings
 Implement Naive RAG
 Implement Hybrid Search
 Implement Agentic RAG
 Implement Self-RAG Verification
 Retrieval Evaluation
 Context Evaluation
 Integrate Memory & RAG with MCP Agent
 Update README
 Final Demo

---

## 🎥 Demo Requirements

The demo (`agent/demo.py`) covers all 8 protocol concerns in order:

| Step | Concern | Verified in demo output |
|---|---|---|
| 1 | Handshake | `Server: brightpeak-academy (protocol 2025-11-25)` |
| 2 | Tool Call | `get_student_profile` → Ahmed Mostafa returned |
| 3 | Notification | `notifications/tools/list_changed RECEIVED` |
| 4 | Resource | `policy://all` → policy text returned |
| 5 | Prompt | `draft_attendance_warning` template returned |
| 6 | Elicitation | Human confirmed drop → `"status": "dropped"` |
| 7 | Progress Tracking | `50% → 100%` printed during course report |
| 8 | Sampling (Final Result) | Gemini generated narrative for Mariam Nabil |

---

## 🧭 Project Summary

We are building an AI assistant for Brightpeak Academy powered by Gemini. Instead of accessing the database directly, it goes through an MCP Server that provides secure, organized data access, supporting all required MCP features: Notifications, Resources, Elicitation, Progress Tracking, Sampling, and Authorization.

---

## 🧠 Memory & RAG Extension (Phase 2)

### The real problem we found

Brightpeak staff already use the MCP tools to look up students, grades, and attendance. Two recurring failures appeared once real usage started:

1. **Memory gap** — Advisors re-explain the same student’s scholarship risk, attendance warnings, and preferred track every new session because the agent forgets everything when the process ends.
2. **Knowledge gap** — Questions about the full policy manuals (attendance thresholds, Protocol 4.2b special arrangements, late-submission ladders, integrity sanctions and their effect on scholarships) live in multi-page documents that nobody wants to turn into dozens of extra MCP tools. The short `policy://` resources help, but they are not searchable at the passage level and cannot support multi-hop reasoning.

### What Farida built (RAG pipeline)

| Component | Location | What it does |
|-----------|----------|--------------|
| Document corpus | `documents/` | 7 detailed policy / handbook documents (Attendance, Scholarship, Academic Integrity, Late Submission, Course Withdrawal, Exam & Assessment, Student Handbook excerpt) |
| Chunker | `rag/chunker.py` | Heading-aware + paragraph chunking with overlap; every chunk carries `document_id`, `section`, `category`, `last_reviewed` |
| Vector store | `rag/vector_db.py` | Real HNSW ANN index (hnswlib) + metadata payload store + metadata filter applied **before** similarity search |
| Ingestion | `rag/ingestion.py` | One-command re-index of the whole corpus |
| Naive RAG | `rag/naive_rag.py` | Baseline retrieve-then-generate |
| Hybrid Search | `rag/hybrid_rag.py` | Vector similarity + BM25 fused scores |
| Agentic RAG | `rag/agentic_rag.py` | Multi-hop retrieve → grade → rewrite → retrieve loop |
| Graph RAG (bonus) | `rag/graph_rag.py` | Policy entity graph (thresholds, sanctions, processes, roles, tracks) with 1-hop expansion |
| Self-RAG verification | `rag/self_rag.py` | Relevance + support check before any answer reaches the user; applied to both RAG and memory recall |
| MCP-facing helper | `rag/rag_tool.py` | `search_policies()` used by the agent; auto-routes multi-part queries to Agentic RAG |
| Retrieval eval | `retrieval_eval/` | 12 domain questions, comparison table, results.json |

### Retrieval comparison table (real numbers)

| Architecture | Accuracy (12 questions) | Avg tokens/query | Avg latency/query |
|---|---|---|---|
| Naive RAG | 86% | 469 | 0.001s |
| Hybrid Search | 89% | 492 | 0.001s |
| Agentic RAG | 89% | 404 | 0.001s |
| Graph RAG (bonus) | 38%* | 538 | 0.024s |

\*Graph RAG currently wins on relationship-heavy questions (q11) but needs tighter entity linking for citation queries; retained as an optional path.

**Shipping decision (driven by the table, not intuition):**  
Default = **Hybrid Search**. Multi-part / decomposition questions are routed to **Agentic RAG**. Graph RAG is available for relationship queries. This matches Brightpeak’s live-call pattern: mostly quick citation and general policy lookups while a staff member is waiting, with occasional multi-condition eligibility questions.

### How to re-run the evaluation

```bash
cd Phase-2
python -m retrieval_eval.evaluate
```

### Memory system (Fatma) — already present

- `memory/short_term.py` — rolling buffer, returns evicted items
- `memory/scratchpad.py` — plan / sub-goal / working state (never pruned by transcript eviction)
- `memory/router.py` — promote-or-drop (forget | episodic only), reasoning logged
- `memory/episodic.py` — persistent SQLite episodes
- `memory/semantic.py` — versioned facts with expiration and supersession

### Suggested GitHub Issues for Phase 2 (Farida’s ownership)

- [ ] Build Vector Database (HNSW + metadata filter)
- [ ] Implement Chunking Pipeline
- [ ] Implement Naive RAG
- [ ] Implement Hybrid Search
- [ ] Implement Agentic RAG
- [ ] Implement Self-RAG Verification
- [ ] Graph RAG (bonus)
- [ ] Retrieval Evaluation + comparison table
- [ ] Integrate RAG with Agent (`rag/rag_tool.py`)
- [ ] Update README with RAG section and numbers

