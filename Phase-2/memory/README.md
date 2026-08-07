# Memory System Extension — `memory/`

**Owner:** Fatma Saber
**Scope:** Short-Term Memory, Scratchpad, Promote-or-Drop Router, Episodic Memory, Semantic Memory, Consolidation Layer, Memory Recall + Verification (memory-side), Memory Integration with the Agent (`agent/memory_integration.py`)

## The problem this extends on top of the existing MCP server

Brightpeak advisors (instructors and the registrar) currently lose all context the moment a session ends. An instructor who tells the assistant "Ahmed is now ineligible for the merit scholarship" today has to re-establish that fact from scratch tomorrow — the MCP server and database already hold the *raw* records (grades, attendance), but nothing persists the *advisory reasoning* built on top of them across sessions. This extension adds a real long-term memory system behind the existing agent so that reasoning survives.

## Architecture, module by module

| Module | Responsibility |
|---|---|
| `short_term.py` | Rolling message buffer (`max_turns`). Evicts the oldest message when full and hands it to the router — never silently drops it. |
| `scratchpad.py` | The agent's current plan / sub-goal / working state. Structurally separate from the transcript buffer — short-term eviction can **never** touch it (see `test_short_term.py`, which asserts scratchpad fields are byte-identical before/after 20 evictions). |
| `router.py` | Fires exactly once per evicted message. Decides `forget` or `episodic` **only** — `semantic` is not a reachable value, enforced both by the `Destination` type and a runtime guard in `route()`. Every decision carries a mandatory `reasoning` string. |
| `episodic.py` | Timestamped event store (SQLite). Sealed, append-only. |
| `semantic.py` | Versioned fact store. Never overwrites — a changed fact gets a new row with `superseded_by` set on the old one, so `get_history()` shows the full timeline. Facts also support `expires_at` so a stale fact stops being returned by `get_current()` even with no explicit update. |
| `consolidation.py` | The **only** writer to `semantic.py`. Runs as a separate, periodic pass over new episodes (`run()`), never at write time. Resolves in-batch conflicts (see below) and is idempotent — a second `run()` over the same episodes reports `unchanged` and creates zero new fact versions. |
| `recall.py` / `verification.py` | Memory-side Self-RAG-style check: `recall()` searches both stores, `supported_only()` drops anything stale/expired/off-topic before it reaches a prompt. This is the memory half of the Self-RAG-style verification concern (the RAG-corpus half is owned separately). |
| `agent/memory_integration.py` | `MemoryIntegratedAgent` — composes all of the above into one object with a real write path and read path (see below). Contains no new memory *logic*; it only calls each module's already-tested public API in the right order. |

## Write path (every turn)

```
message -> ShortTermMemory.add()
         -> [on overflow] PromoteOrDropRouter.process_overflow()
         -> [if "episodic"] EpisodicStore.insert()
         -> [every N turns] ConsolidationLayer.run() -> SemanticStore.upsert()
```

## Read path (before every reply)

```
query -> MemoryRecall.recall()  (searches episodic + semantic)
       -> MemoryVerifier.supported_only()  (drops stale/expired/off-topic)
       -> only verified memory reaches the prompt
```

## A real conflict the consolidation layer resolves

Two episodes for the same student implied contradictory track preferences within one consolidation batch:

```
episode 1 (earlier): "Ahmed asked about the Flutter track"
episode 2 (later):   "Ahmed confirmed the AI track"
```

`consolidation.py` does not silently pick one. It logs both decisions:

```
episode=1 -> conflict_resolved  fact_key=preferred_track:student_14
    reasoning: Episode 1 also implied preferred_track:student_14='Flutter', but
    episode 2 is more recent and supersedes it within this batch. Only the more
    recent episode's value is written to semantic memory.
episode=2 -> created            fact_key=preferred_track:student_14
    reasoning: Episode 2 states a track preference (Ai) -- generalizable beyond
    this single conversation.

semantic.get_current('preferred_track:student_14') -> 'Ai'
Full fact history: [(1, 'Ai')]
```

The losing episode is never lost from the record — it's logged with the reasoning for why it lost, and the semantic store's history stays inspectable.

## Cross-session persistence — proven with two genuinely separate processes

Because the MCP-style stores are SQLite-backed (not a Python variable), memory survives a real process restart, not just multiple calls within one script. `test_persistence_session_1.py` writes facts and closes its connections explicitly; `test_persistence_session_2.py` is run **afterward, as its own separate `python` invocation**, and recovers the full fact history from disk with no in-memory link to session 1.

## Running the tests

Each module has a standalone, runnable proof (no pytest required, though pytest also works):

```bash
cd memory
python test_short_term.py
python test_router.py
python test_episodic.py
python test_semantic.py
python test_consolidation.py
python test_router_episodic_integration.py
python test_recall_verification.py

# Cross-session persistence — run as two SEPARATE commands, in order:
python test_persistence_session_1.py
python test_persistence_session_2.py
```

Full integration through the agent-facing class:
```bash
cd ../agent
python test_memory_integration.py
```

Evidence from each run is written to `memory/evidence/` and `agent/evidence/`.

## Rubric mapping

| Rubric item | Where it's demonstrated |
|---|---|
| Short-term memory and scratchpad (5) | `short_term.py`, `scratchpad.py`, `test_short_term.py` |
| Promote-or-drop routing (6) | `router.py` — structural guard against writing `semantic`, reasoning logged per decision |
| Semantic memory consolidation layer (10) | `consolidation.py` — versioning, expiration, real conflict resolved above, idempotent `run()` |
| Self-RAG-style verification, memory half (part of 8) | `recall.py`, `verification.py`, `test_recall_verification.py` |
| Agent and system integration (part of 10) | `agent/memory_integration.py`, `test_memory_integration.py` |

## Known scope boundary

This folder does not implement context-window management strategies (`context_eval/`) or the RAG/vector-store pipeline (`rag/`, `retrieval_eval/`) — those are owned separately by other team members per the team table in the top-level README.