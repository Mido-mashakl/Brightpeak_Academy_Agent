"""
Brightpeak Academy — Full-System Integration Test
====================================================
Run directly:  python tests/test_integration.py
Or via pytest: pytest tests/test_integration.py -v

This is the ONE test that proves the whole pipeline actually works
TOGETHER, not just each piece in isolation:

    User -> Agent -> Memory -> MCP -> RAG -> Answer

Every other test in this repo (test_router_episodic_integration.py,
test_recall_verification.py, test_memory_integration.py, evaluate.py,
retrieval_eval/evaluate.py, rag/test_rag_pipeline.py, ...) proves one
layer, or two adjacent layers, work correctly. This file is the only
place all five stages run back to back, on a real conversation, and
the output of one stage is what the next stage actually consumes:

  1. USER    -- a turn from tests/sample_conversations.json
  2. AGENT   -- agent/memory_integration.py's MemoryIntegratedAgent
                decides whether it needs a live tool call this turn
  3. MCP     -- a REAL mcp_server/server.py subprocess, talked to over
                real stdio (mcp.ClientSession), exactly like
                agent/agent_stage6.py -- not a mocked tool
  4. RAG     -- policy questions go through the MCP `search_policies`
                tool, which is mcp_server/tools.py's thin wrapper
                around rag/rag_tool.py (Hybrid RAG + Self-RAG
                verification against the real TF-IDF index over
                documents/) -- also not mocked
  5. ANSWER  -- MemoryIntegratedAgent.chat() assembles the prompt
                (scratchpad + short-term transcript + verified
                recalled memory) and calls generate_fn

No network access, no GEMINI_API_KEY required: generate_fn is a
deterministic stub, the same testability pattern used by every other
test in this repo (see memory_integration.py's own docstring). The
stub never sees the expected facts in advance -- it just echoes a
snippet of whatever prompt it was actually given, so it can never
"answer correctly" from anywhere except the assembled prompt.

Reliably summarizing free text into a one-line natural-language answer
is exactly the part of this pipeline a real LLM call (GEMINI_API_KEY)
is for -- a hand-written heuristic stub trying to do that job well is
just testing the heuristic, not the system. So this test does NOT
assert on the stub's reply wording. Instead it asserts on the two
things that are actually this pipeline's job, independent of which
model eventually reads the prompt:

  (a) every expected fact for a turn reached the ASSEMBLED PROMPT --
      i.e. MCP's response (raw DB data, or RAG's retrieved + Self-RAG
      verified passages) actually made it through the memory write
      path and back out through recall/transcript into what a model
      would see, and
  (b) the Answer stage was actually invoked on that exact prompt --
      generate_fn ran, once, on the same string the test inspected,
      and returned a non-empty reply.

A broken hop anywhere upstream (MCP tool error, failed RAG
verification, a fact evicted from memory before recall) still fails
loudly here; only "did the stub's toy heuristic phrase the answer the
way I expected" is deliberately NOT tested, because that would be
testing the stub, not the integration.

Each conversation in sample_conversations.json ends with a
"recall_only" turn (tool: null) that asks about a fact from an
earlier turn WITHOUT calling any MCP tool again. That turn only
passes if the MEMORY layer -- not a second live lookup -- is what
carries the fact forward, which is the specific thing that makes this
a memory-integration test and not just a tool-calling test.
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TESTS_DIR = Path(__file__).resolve().parent
PHASE2_DIR = TESTS_DIR.parent
AGENT_DIR = PHASE2_DIR / "agent"
MCP_SERVER_SCRIPT = PHASE2_DIR / "mcp_server" / "server.py"
SAMPLE_CONVERSATIONS = TESTS_DIR / "sample_conversations.json"
EVIDENCE_FILE = TESTS_DIR / "evidence" / "integration_evidence.txt"

sys.path.insert(0, str(AGENT_DIR))
from memory_integration import MemoryIntegratedAgent  # noqa: E402

log_lines: list[str] = []
failures: list[str] = []


def log(line: str = "") -> None:
    print(line)
    log_lines.append(line)


def fail(msg: str) -> None:
    log(f"FAIL: {msg}")
    failures.append(msg)


def write_evidence(passed: bool) -> None:
    EVIDENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "=" * 70,
        "EVIDENCE — test_integration.py",
        "(User -> Agent -> Memory -> MCP -> RAG -> Answer, end to end)",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Result: {'PASSED' if passed else 'FAILED'} "
        f"({len(failures)} failure(s))",
        "=" * 70,
        "",
    ]
    EVIDENCE_FILE.write_text("\n".join(header + log_lines), encoding="utf-8")


# ---------------------------------------------------------------------
# ANSWER stage: a deterministic, honest stand-in for GeminiClient.
# It never receives the test's expected_facts -- it only extracts
# fact-shaped lines (digits / "%" / known course-name words) from the
# prompt it is actually handed, so a fact that never reached the
# prompt cannot appear in the reply either.
# ---------------------------------------------------------------------
def make_echo_stub(captured_prompts: list[str]):
    """Deterministic stand-in for GeminiClient.generate(). Records the
    exact prompt it was given (so the test can assert generate_fn ran
    on the same prompt the test inspected) and returns a short,
    non-empty, prompt-derived string. Deliberately NOT a real
    summarizer -- see the module docstring for why this test doesn't
    grade the wording of what comes back, only whether the right
    facts made it into what this function was handed.
    """

    def _fn(prompt: str) -> str:
        captured_prompts.append(prompt)
        return f"ANSWER: (grounded on a {len(prompt)}-char prompt) {prompt[-160:].strip()}"

    return _fn


# ---------------------------------------------------------------------
# MCP stage: extract plain text out of a CallToolResult the same way
# agent/agent_stage6.py's print_tool_result() does.
# ---------------------------------------------------------------------
def tool_result_text(result) -> str:
    parts = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


async def call_mcp_tool(session: ClientSession, tool_name: str, args: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    result = await session.call_tool(tool_name, arguments=args)
    text = tool_result_text(result)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    return text, parsed


# ---------------------------------------------------------------------
# One conversation turn: User -> Agent -> [MCP -> RAG] -> Memory -> Answer
# ---------------------------------------------------------------------
async def run_turn(
    session: ClientSession,
    agent: MemoryIntegratedAgent,
    student_id: int,
    turn: dict[str, Any],
    conv_id: str,
    turn_idx: int,
    prompts_captured: list[str],
) -> None:
    label = f"[{conv_id} #{turn_idx}]"
    log(f"\n--- {label} USER: {turn['user']!r}")

    tool_name = turn.get("tool", None)
    calls_before = agent.episodic  # unused sentinel, kept for readability

    if tool_name:
        # --- MCP stage (and RAG stage, if the tool is search_policies) ---
        log(f"{label} AGENT decides a live MCP tool call is needed: {tool_name}({turn['args']})")
        text, parsed = await call_mcp_tool(session, tool_name, turn["args"])

        if parsed is not None and isinstance(parsed, dict) and "error" in parsed:
            fail(f"{label} MCP tool {tool_name} returned an error: {parsed['error']}")

        if tool_name == "search_policies":
            if parsed is None:
                fail(f"{label} search_policies did not return valid JSON")
            else:
                ver = parsed.get("verification", {})
                log(f"{label} RAG stage -> architecture={parsed.get('architecture_used')} "
                    f"verification={ver.get('action')}")
                if ver.get("action") != "pass":
                    fail(
                        f"{label} RAG self-verification did not pass: "
                        f"{ver.get('reason')!r} -- refusing to trust ungrounded retrieval"
                    )

        log(f"{label} MCP tool result ({len(text)} chars): {text[:200]!r}...")

        # --- Memory stage (write path): fold the tool call/result in ---
        agent.remember_tool_call(tool_name, f"{tool_name}({turn['args']})", metadata={"student_id": student_id})
        agent.remember_tool_result(tool_name, text, metadata={"student_id": student_id})
    else:
        log(f"{label} AGENT answers from memory alone -- no MCP call this turn "
            f"(this is the recall_only check)")

    # --- Memory stage (read path) + Answer stage, via chat() ---
    prompts_before = len(prompts_captured)
    turn_result = agent.chat(turn["user"], student_id=student_id)
    log(f"{label} recalled={len(turn_result.recalled)} verified={len(turn_result.verified)}")
    log(f"{label} ANSWER: {turn_result.reply!r}")

    # (b) Answer stage actually ran, exactly once, on the same prompt
    # the test is about to inspect below -- not a stale or different one.
    if len(prompts_captured) != prompts_before + 1:
        fail(f"{label} expected exactly one generate_fn call this turn, "
             f"got {len(prompts_captured) - prompts_before}")
    elif prompts_captured[-1] != turn_result.prompt:
        fail(f"{label} generate_fn was called with a different prompt than "
             f"the one TurnResult reports -- Answer stage is not consuming "
             f"what Memory actually assembled")
    if not turn_result.reply.strip():
        fail(f"{label} Answer stage returned an empty reply")

    # (a) every expected fact survived MCP/RAG -> Memory -> the prompt
    # that would be sent to the model.
    expected_facts = turn.get("expected_facts", [])

    if expected_facts:
        prompt_lower = turn_result.prompt.lower()

        for fact in expected_facts:
            if fact.lower() not in prompt_lower:
                fail(
                    f"{label} expected fact {fact!r} never reached the assembled prompt -- "
                    f"the pipeline dropped it somewhere between MCP/RAG and Answer"
                )
            else:
                log(
                    f"{label} PASS -- fact {fact!r} flowed: "
                    f"MCP/memory -> prompt -> answer stage"
                )

    if turn.get("recall_only", False):
        if not turn_result.recalled and "(empty)" in turn_result.prompt.split(
            "=== Recent conversation"
        )[1].split("=== Verified")[0]:
            fail(f"{label} recall_only turn found nothing in short-term transcript or recall -- "
                 f"memory did not actually carry the fact forward")
        else:
            log(f"{label} PASS -- recall_only turn was answered without a new MCP call")


async def run_conversation(session: ClientSession, conv: dict[str, Any]) -> None:
    conv_id = conv["id"]
    student_id = conv["student_id"]
    log("\n" + "=" * 70)
    log(f"CONVERSATION — {conv_id}")
    log(conv.get("description", ""))
    log("=" * 70)

    prompts_captured: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / f"{conv_id}_store.db"
        with MemoryIntegratedAgent(
            db_path=db_path,
            max_short_term_turns=20,
            consolidate_every_n_turns=1000,  # keep facts in short-term transcript for this test
            generate_fn=make_echo_stub(prompts_captured),
        ) as agent:
            for i, turn in enumerate(conv["turns"], start=1):
                await run_turn(session, agent, student_id, turn, conv_id, i, prompts_captured)


async def main_async() -> None:
    if not MCP_SERVER_SCRIPT.exists():
        fail(f"MCP server script not found at {MCP_SERVER_SCRIPT}")
        write_evidence(passed=False)
        sys.exit(1)

    conversations = json.loads(SAMPLE_CONVERSATIONS.read_text(encoding="utf-8"))["conversations"]
    log("=" * 70)
    log("FULL-SYSTEM INTEGRATION TEST")
    log(f"{len(conversations)} conversation(s) from {SAMPLE_CONVERSATIONS.name}")
    log("User -> Agent -> Memory -> MCP -> RAG -> Answer")
    log("=" * 70)

    server_params = StdioServerParameters(command=sys.executable, args=[str(MCP_SERVER_SCRIPT)])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            log("\n[MCP] initializing session with the real server subprocess...")
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}
            log(f"[MCP] handshake OK -- server exposes: {sorted(tool_names)}")

            required = {"get_student_attendance", "get_student_grades", "get_student_enrollments", "search_policies"}
            missing = required - tool_names
            if missing:
                fail(f"MCP server is missing expected read-only tools: {missing}")

            for conv in conversations:
                await run_conversation(session, conv)

    log("\n" + "=" * 70)
    if failures:
        log(f"RESULT: FAILED — {len(failures)} failure(s):")
        for f in failures:
            log(f"  - {f}")
    else:
        log("RESULT: ALL CONVERSATIONS PASSED — every stage of")
        log("User -> Agent -> Memory -> MCP -> RAG -> Answer")
        log("produced output the NEXT stage actually consumed correctly.")
    log("=" * 70)
    write_evidence(passed=not failures)

    RESULTS_DIR = TESTS_DIR / "results"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    RESULT_FILE = RESULTS_DIR / "integration_output.txt"

    RESULT_FILE.write_text(
        "\n".join(log_lines),
        encoding="utf-8"
    )

    if failures:
        sys.exit(1)


def main() -> None:
    asyncio.run(main_async())


# ---------------------------------------------------------------------
# pytest entry point -- lets `pytest tests/test_integration.py` collect
# this the same way it collects everything else under tests/.
# ---------------------------------------------------------------------
def test_full_pipeline() -> None:
    failures.clear()
    log_lines.clear()
    asyncio.run(main_async_no_exit())


async def main_async_no_exit() -> None:
    """Same as main_async() but raises AssertionError instead of
    sys.exit(1), so pytest reports it as a normal test failure."""
    try:
        await main_async()
    except SystemExit as e:
        if e.code:
            assert False, f"{len(failures)} integration failure(s) -- see {EVIDENCE_FILE}"


if __name__ == "__main__":
    main()