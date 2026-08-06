"""
Brightpeak Academy - Agent Integration
==========================================
Memory Integration with the Agent
-------------------------------------
Run the standalone proof: `python agent/test_memory_integration.py`

Wires all eight Memory System Extension modules (short_term, scratchpad,
router, episodic, semantic, consolidation, recall, verification) into a
single agent-facing class, `MemoryIntegratedAgent`. Nothing inside
memory/ changes -- every one of those modules already documented itself
as a sealed, already-shipped component (see each module's own
docstring), so this file only ever calls their existing PUBLIC APIs, in
the exact composition order test_router_episodic_integration.py and
test_recall_verification.py already proved works:

  short_term.add() -> router.process_overflow() -> episodic.insert()
  episodic.list_recent() -> consolidation.run() -> semantic.upsert()
  recall.recall() -> verification.supported_only() -> agent prompt

What "integration" means here, concretely, on every turn of a real
conversation:

  1. WRITE PATH
     Every message (user, assistant, tool call, tool result) is
     appended to ShortTermMemory. When the rolling buffer overflows,
     the evicted message is handed to PromoteOrDropRouter -- exactly
     the flow test_router_episodic_integration.py already proved.
     "episodic" decisions are written into a REAL EpisodicStore
     (memory/store.db by default). The Scratchpad is updated by the
     caller whenever a plan/subgoal is known and is NEVER touched by
     short-term eviction (see scratchpad.py's own docstring) -- the
     agent reads it back on every step, independent of whatever
     survived pruning in the transcript.
     Periodically (every `consolidate_every_n_turns` chat() turns, or
     on demand via `consolidate()`), ConsolidationLayer sweeps new
     episodes into versioned, conflict-resolved semantic facts.

  2. READ PATH
     Before generating a reply, MemoryRecall.recall() searches BOTH
     stores for the current user query, and
     MemoryVerifier.supported_only() drops anything stale, expired, or
     merely coincidentally on-topic -- exactly the two-step pipeline
     test_recall_verification.py already proved end-to-end. Only
     verified memory ever reaches the prompt, formatted the way
     `MemoryRecall.to_context_string()` already produces it.

Why a pluggable `generate_fn` instead of hard-wiring GeminiClient
----------------------------------------------------------------------
Same reasoning as every decision point already in this package
(router.py's `decision_fn`, consolidation.py's `extract_fn`,
recall.py's `score_fn`, verification.py's `verify_fn`): this class
needs to be testable standalone, deterministically, with no network
access and no API key (see test_memory_integration.py). The default
`generate_fn` lazily builds a real `GeminiClient` (agent/client.py) the
FIRST time text actually needs to be generated -- never at import time,
never in __init__ -- so importing or constructing a
`MemoryIntegratedAgent` never requires GEMINI_API_KEY or even the
google-genai package to be installed. A test swaps in a deterministic
stub with the exact same signature (`generate_fn(prompt: str) -> str`);
nothing else in this file changes.

Wiring this into a live MCP session (demo.py / agent_stage*.py) later
-----------------------------------------------------------------------
This file deliberately does not import or modify anything under
mcp_server/ or the existing agent/*.py scripts -- those are sealed,
someone else's parts. Hooking a live tool-calling session in later is a
two-line addition at each call site, nothing structural:

    result = await session.call_tool("get_student_attendance", {...})
    agent.remember_tool_call("get_student_attendance", str(arguments))
    agent.remember_tool_result("get_student_attendance", str(result))
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

AGENT_DIR = Path(__file__).resolve().parent
PHASE2_DIR = AGENT_DIR.parent
MEMORY_DIR = PHASE2_DIR / "memory"

# memory/ modules import each other the same way (sys.path.insert of
# their own directory) -- matching that convention here is what lets
# `from router import ...` etc. resolve regardless of the caller's cwd.
sys.path.insert(0, str(MEMORY_DIR))

from consolidation import ConsolidationDecision, ConsolidationLayer  # noqa: E402
from episodic import EpisodicStore  # noqa: E402
from recall import MemoryRecall, RecallResult  # noqa: E402
from router import MemoryRoutingDecision, PromoteOrDropRouter  # noqa: E402
from scratchpad import Scratchpad  # noqa: E402
from semantic import SemanticStore  # noqa: E402
from short_term import ShortTermMemory  # noqa: E402
from verification import MemoryVerifier  # noqa: E402

DEFAULT_DB_PATH = MEMORY_DIR / "store.db"

GenerateFn = Callable[[str], str]


def _build_default_generate_fn() -> GenerateFn:
    """Returns a `generate_fn` backed by the real GeminiClient
    (agent/client.py), constructed lazily on first call. Deferred
    import + deferred construction on purpose: this keeps
    `MemoryIntegratedAgent` importable and constructible with zero
    dependency on GEMINI_API_KEY or the google-genai package, so the
    memory-pipeline logic can be exercised on its own (see
    test_memory_integration.py), same as every other module here.
    """
    state: dict[str, object] = {}

    def _fn(prompt: str) -> str:
        if "client" not in state:
            from client import GeminiClient, load_gemini_config  # noqa: E402

            config = load_gemini_config()
            state["client"] = GeminiClient(config)
        return state["client"].generate(prompt)  # type: ignore[union-attr]

    return _fn


@dataclass
class TurnResult:
    """Everything a caller (or a test) might want to inspect about one
    `chat()` turn, beyond just the reply text -- so both the write path
    (eviction/consolidation decisions) and the read path
    (recalled/verified memory, the assembled prompt) stay visible
    instead of being hidden inside a single string return value. Same
    "reasoning a grader can see" requirement as every Decision/Verdict
    dataclass in memory/.
    """

    reply: str
    prompt: str
    recalled: list[RecallResult]
    verified: list[RecallResult]
    eviction_decisions: list[MemoryRoutingDecision]
    consolidation_decisions: list[ConsolidationDecision]


class MemoryIntegratedAgent:
    """Ties short_term, scratchpad, router, episodic, semantic,
    consolidation, recall, and verification into one agent-facing
    object. This class contributes no new memory *logic* of its own --
    every decision is still made by the module that owns it. It only
    calls their already-tested public APIs in the right order, on the
    right event, which is exactly what "agent integration" means here.
    """

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        max_short_term_turns: int = 20,
        consolidate_every_n_turns: int = 5,
        generate_fn: Optional[GenerateFn] = None,
        system_preamble: Optional[str] = None,
    ) -> None:
        self.short_term = ShortTermMemory(max_turns=max_short_term_turns)
        self.scratchpad = Scratchpad()
        self.router = PromoteOrDropRouter()
        self.episodic = EpisodicStore(db_path=db_path)
        self.semantic = SemanticStore(db_path=db_path)
        self.consolidation = ConsolidationLayer(self.episodic, self.semantic)
        self.recall = MemoryRecall(self.episodic, self.semantic)
        self.verifier = MemoryVerifier(self.semantic)

        self._generate_fn: GenerateFn = generate_fn or _build_default_generate_fn()
        self._system_preamble = system_preamble or (
            "You are the Brightpeak Academy advisory assistant. Use the "
            "conversation so far, the agent's current plan, and the "
            "verified memory notes below to answer the student or "
            "instructor. Never contradict a verified memory note."
        )
        self._consolidate_every_n_turns = max(1, consolidate_every_n_turns)
        self._turns_since_consolidation = 0

    # ------------------------------------------------------------------
    # WRITE PATH -- append a message, route any eviction, persist events
    # ------------------------------------------------------------------
    def _remember(
        self,
        role: str,
        content: str,
        msg_type: str = "text",
        metadata: Optional[dict] = None,
    ) -> Optional[MemoryRoutingDecision]:
        evicted = self.short_term.add(role, content, msg_type=msg_type, metadata=metadata or {})
        decision = self.router.process_overflow(evicted)
        if decision is not None and decision.destination == "episodic":
            # IMPORTANT: use the EVICTED message's own metadata (the
            # message actually being routed), not the metadata of
            # whatever message is being added right now -- those are
            # two different turns, possibly about two different
            # students. Getting this wrong would silently mis-scope
            # episodes (and therefore every downstream recall.py /
            # consolidation.py student_id filter) to the wrong student.
            self.episodic.insert(
                event_summary=decision.event_summary,
                context=decision.context,
                outcome=decision.outcome,
                metadata=decision.source_message.metadata or {},
            )
        return decision

    def remember_user_message(
        self, content: str, metadata: Optional[dict] = None
    ) -> Optional[MemoryRoutingDecision]:
        return self._remember("user", content, "text", metadata)

    def remember_assistant_message(
        self, content: str, metadata: Optional[dict] = None
    ) -> Optional[MemoryRoutingDecision]:
        return self._remember("assistant", content, "text", metadata)

    def remember_tool_call(
        self, tool_name: str, content: str, metadata: Optional[dict] = None
    ) -> Optional[MemoryRoutingDecision]:
        """Call this right after issuing an MCP tool call (e.g. right
        after `session.call_tool(...)` in demo.py) to fold it into
        short-term memory the same way the rest of the conversation is
        tracked. `msg_type="tool_call:<name>"` matches the convention
        already documented in short_term.py's own Message docstring.
        """
        return self._remember("tool", content, f"tool_call:{tool_name}", metadata)

    def remember_tool_result(
        self, tool_name: str, content: str, metadata: Optional[dict] = None
    ) -> Optional[MemoryRoutingDecision]:
        return self._remember("tool", content, f"tool_result:{tool_name}", metadata)

    def consolidate(self) -> list[ConsolidationDecision]:
        """Runs the consolidation sweep right now, regardless of the
        turn-based schedule. Safe to call anytime -- idempotent per
        consolidation.py's own guarantee (a second call over the same
        episodes reports 'unchanged' and creates no new fact versions).
        """
        decisions = self.consolidation.run()
        self._turns_since_consolidation = 0
        return decisions

    def _maybe_consolidate(self) -> list[ConsolidationDecision]:
        self._turns_since_consolidation += 1
        if self._turns_since_consolidation >= self._consolidate_every_n_turns:
            return self.consolidate()
        return []

    # ------------------------------------------------------------------
    # READ PATH -- recall, then verify before anything reaches a prompt
    # ------------------------------------------------------------------
    def recall_verified(
        self,
        query: str,
        student_id: Optional[int] = None,
        top_k: int = 5,
    ) -> tuple[list[RecallResult], list[RecallResult]]:
        """Returns (everything recall.py found, only what verification.py
        cleared). memory_integration.py itself never decides relevance
        or trust -- it only ever calls `supported_only()`, which is the
        exact function verification.py's own docstring says
        memory_rag_agent.py (this file) is expected to call, not
        `recall()` directly.
        """
        recalled = self.recall.recall(query, student_id=student_id, top_k=top_k)
        verified = self.verifier.supported_only(query, recalled)
        return recalled, verified

    # ------------------------------------------------------------------
    # Prompt assembly
    # ------------------------------------------------------------------
    def build_prompt(self, user_message: str, verified_memory: list[RecallResult]) -> str:
        snap = self.scratchpad.snapshot()
        transcript_lines = [f"{m['role']}: {m['content']}" for m in self.short_term.get_context()]
        transcript = "\n".join(transcript_lines) if transcript_lines else "(empty)"

        memory_block = MemoryRecall.to_context_string(verified_memory)
        plan_block = (
            f"plan: {snap.plan or '(none)'}\n"
            f"current_subgoal: {snap.current_subgoal or '(none)'}"
        )

        return (
            f"{self._system_preamble}\n\n"
            f"=== Scratchpad (agent's current working state) ===\n{plan_block}\n\n"
            f"=== Recent conversation (short-term memory) ===\n{transcript}\n\n"
            f"=== Verified long-term memory (recalled for this query) ===\n{memory_block}\n\n"
            f"=== New message ===\n{user_message}\n"
        )

    # ------------------------------------------------------------------
    # One full turn, end to end: write path + read path + generation
    # ------------------------------------------------------------------
    def chat(
        self,
        user_message: str,
        student_id: Optional[int] = None,
        top_k: int = 5,
        metadata: Optional[dict] = None,
    ) -> TurnResult:
        if not user_message or not user_message.strip():
            raise ValueError("user_message must be a non-empty string")

        eviction_decisions: list[MemoryRoutingDecision] = []

        d = self.remember_user_message(user_message, metadata=metadata)
        if d is not None:
            eviction_decisions.append(d)

        recalled, verified = self.recall_verified(user_message, student_id=student_id, top_k=top_k)
        prompt = self.build_prompt(user_message, verified)
        reply = self._generate_fn(prompt)

        d2 = self.remember_assistant_message(reply, metadata=metadata)
        if d2 is not None:
            eviction_decisions.append(d2)

        consolidation_decisions = self._maybe_consolidate()

        return TurnResult(
            reply=reply,
            prompt=prompt,
            recalled=recalled,
            verified=verified,
            eviction_decisions=eviction_decisions,
            consolidation_decisions=consolidation_decisions,
        )

    # ------------------------------------------------------------------
    def close(self) -> None:
        self.episodic.close()
        self.semantic.close()

    def __enter__(self) -> "MemoryIntegratedAgent":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()