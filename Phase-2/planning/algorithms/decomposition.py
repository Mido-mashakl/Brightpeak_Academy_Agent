"""
Brightpeak Academy - Decomposition-First DAG

Adapted from:
Mido-mashakl/task_decomposition_and_planning

Purpose:
    Decompose a real Brightpeak Academy request into a validated DAG,
    then execute the DAG against the existing MCP server.

This module intentionally reuses the toolkit's Plan model and its
NetworkX-based DAG validation instead of rebuilding graph logic.

Brightpeak planning problem:
    Build a safe academic intervention plan for a student.

Typical request:
    "Review student 2's academic situation and recommend what the
     advisor should do next."

The plan can require:
    - student profile
    - enrollments
    - attendance
    - grades
    - relevant policies
    - synthesis / recommendation

The actual student facts come from the existing MCP server.
This module does NOT access SQLite directly.
"""


from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from pydantic import BaseModel, ConfigDict

from ..models import Plan


PLANNER_SYSTEM ="""
You are the Brightpeak Academy academic planning agent.

Your job is to turn a complex academic-support request into a SMALL
executable DAG.

The plan must:

1. contain 3-6 concrete tasks;
2. use short unique ids such as t1, t2, t3;
3. use dependencies only when one task genuinely needs another task;
4. keep independent data collection tasks independent so they can run
   in parallel;
5. end with exactly ONE synthesis task;
6. make every task contribute directly to the final goal;
7. NEVER create a cycle;
8. prefer existing Brightpeak MCP tools for factual data.

Available MCP tools include:

- get_student_profile
- get_student_enrollments
- get_student_attendance
- get_student_grades
- search_policies
- generate_academic_advisory
- generate_course_report

Do not invent database facts.
Do not access SQLite directly.
"""

# ---------------------------------------------------------------------------
# Structured planner output
# ---------------------------------------------------------------------------
class PlannedTask(BaseModel):
    """Wire schema; richer semantic constraints are applied by the Task domain model."""

    model_config = ConfigDict(extra="forbid")

    id: str
    instruction: str
    depends_on: list[str]


class GeneratedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str
    tasks: list[PlannedTask]

# ---------------------------------------------------------------------------
# MCP execution adapter
# ---------------------------------------------------------------------------
@dataclass
class MCPToolExecutor:
    """
    Small adapter around the existing MCP ClientSession.

    The decomposition algorithm doesn't know how the MCP session works.
    It only asks this adapter to execute a Brightpeak MCP tool.

    Example:

        executor = MCPToolExecutor(session)
        result = await executor.call(
            "get_student_grades",
            {"student_id": 2},
        )
    """

    session: Any

    async def call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        result = await self.session.call_tool(
            tool_name,
            arguments=arguments,
        )

        return _parse_mcp_result(result)
def _parse_mcp_result(result: Any) -> dict[str, Any]:
    """
    Normalize MCP tool results into a Python dictionary.

    Handles:
    - dict results
    - MCP CallToolResult objects
    - content[].text
    - structuredContent / structured_content
    - plain text
    """

    # =========================================================
    # 1. Result is already a dictionary
    # =========================================================
    if isinstance(result, dict):
        # Already normalized.
        if "error" not in result or len(result) > 1:
            return result

        # If it is an error dict, preserve it.
        return result

    # =========================================================
    # 2. structuredContent
    # =========================================================
    structured = getattr(result, "structuredContent", None)

    if structured is None:
        structured = getattr(result, "structured_content", None)

    if structured is not None:
        if isinstance(structured, dict):
            return structured

        if isinstance(structured, str):
            try:
                parsed = json.loads(structured)

                if isinstance(parsed, dict):
                    return parsed

                return {"data": parsed}

            except json.JSONDecodeError:
                return {"text": structured}

    # =========================================================
    # 3. Standard MCP content blocks
    # =========================================================
    content = getattr(result, "content", None)

    if content:
        texts: list[str] = []

        for block in content:

            # MCP TextContent object
            text = getattr(block, "text", None)

            if text:
                texts.append(str(text))
                continue

            # Dictionary-style content block
            if isinstance(block, dict):
                text = block.get("text")

                if text:
                    texts.append(str(text))

        if texts:
            combined = "\n".join(texts).strip()

            try:
                parsed = json.loads(combined)

                if isinstance(parsed, dict):
                    return parsed

                return {"data": parsed}

            except json.JSONDecodeError:
                return {"text": combined}

    # =========================================================
    # 4. Other common result attributes
    # =========================================================
    for attribute in ("data", "result", "output"):

        value = getattr(result, attribute, None)

        if value is None:
            continue

        if isinstance(value, dict):
            return value

        if isinstance(value, str):
            try:
                parsed = json.loads(value)

                if isinstance(parsed, dict):
                    return parsed

                return {"data": parsed}

            except json.JSONDecodeError:
                return {"text": value}

    # =========================================================
    # 5. Nothing readable
    # =========================================================
    return {
        "error": "MCP tool returned no readable content.",
        "raw_type": type(result).__name__,
        "raw": repr(result),
    }


# ---------------------------------------------------------------------------
# Brightpeak task -> MCP tool routing
# ---------------------------------------------------------------------------
def _select_mcp_tool(
    instruction: str,
) -> tuple[str, dict[str, Any]] | None:
    """
    Convert a decomposed Brightpeak task into an actual MCP call.

    This is deliberately narrow.

    The LLM creates the task.
    This router decides which real MCP tool is allowed to satisfy it.

    The router does NOT allow arbitrary tool names generated by the model.
    """

    text = instruction.lower()

    # Student profile
    if "profile" in text:
        student_id = _extract_student_id(instruction)

        if student_id is not None:
            return (
                "get_student_profile",
                {"student_id": student_id},
            )

    # Enrollments
    if (
        "enrollment" in text
        or "enrolled courses" in text
        or "courses" in text
    ):
        student_id = _extract_student_id(instruction)

        if student_id is not None:
            return (
                "get_student_enrollments",
                {"student_id": student_id},
            )

    # Attendance
    if "attendance" in text:
        student_id = _extract_student_id(instruction)

        if student_id is not None:
            return (
                "get_student_attendance",
                {"student_id": student_id},
            )
    # Grades
    if (
        "grade" in text
        or "grades" in text
        or "academic performance" in text
    ):
        student_id = _extract_student_id(instruction)

        if student_id is not None:
            return (
                "get_student_grades",
                {"student_id": student_id},
            )

    # Policy retrieval
    if (
        "policy" in text
        or "attendance rule" in text
        or "scholarship rule" in text
        or "withdrawal rule" in text
        or "late submission" in text
    ):
        query = instruction.strip()

        return (
            "search_policies",
            {"query": query},
        )

    return None
def _extract_student_id(instruction: str) -> int | None:
    """
    Extract a student id from the task text.

    Expected examples:
        student 2
        student #2
        student_id=2
    """

    import re

    patterns = [
        r"student[_\s]*id\s*[=:]\s*(\d+)",
        r"student\s*#?\s*(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, instruction.lower())

        if match:
            return int(match.group(1))

    return None


# ---------------------------------------------------------------------------
# DAG decomposition
# ---------------------------------------------------------------------------
def decompose_goal(
    goal: str,
    llm: Any,
) -> Plan:
    """
    Generate and validate the complete DAG before execution.

    The model is only responsible for proposing the structure.

    Plan validation is performed by the toolkit's Plan model, which checks:
        - unique ids
        - known dependencies
        - self-dependencies
        - cycles

    This is the decomposition-first branch.
    """

    prompt = f"""
{PLANNER_SYSTEM}

User request:{goal}

Create a 3-6 node DAG.

Use this JSON shape:

{{
  "goal": "...",
  "tasks": [
    {{
      "id": "t1",
      "instruction": "...",
      "depends_on": []
    }}
  ]
}}

The final synthesis node must depend on every branch needed
to produce the final answer.

Preserve the exact user goal in the goal field.
"""
    raw = llm.generate(prompt)

    generated = _parse_generated_plan(raw)

    # The user's original goal is authoritative.
    generated["goal"] = goal

    # Toolkit's Plan performs the actual DAG validation.
    return Plan.model_validate(generated)


def _parse_generated_plan(raw: str) -> dict[str, Any]:
    """
    Parse Gemini's JSON response.

    GeminiClient returns plain text, so we extract the JSON object.
    """

    text = raw.strip()

    # Remove markdown fences if Gemini returns them.
    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Gemini returned an invalid decomposition plan. "
            f"Raw response:\n{raw}"
        ) from exc

# ---------------------------------------------------------------------------
# DAG execution
# ---------------------------------------------------------------------------
async def execute_plan(
    plan: Plan,
    executor: MCPToolExecutor,
    llm: Any | None = None,
    max_workers: int = 4,
) -> dict[str, Any]:
    """
    Execute the validated DAG in dependency-safe batches.

    Independent nodes are executed in the same batch.

    MCP-backed nodes call the real Brightpeak MCP server.

    Nodes that require reasoning/synthesis are handled by the LLM.
    """

    outputs: dict[str, Any] = {}

    for batch in plan.execution_batches():

        # ---------------------------------------------------------------
        # Build the work for this dependency-safe batch.
        # ---------------------------------------------------------------

        async_tasks: dict[str, Awaitable[Any]] = {}

        for task_id in batch:

            task = plan.task(task_id)
            dependency_context = "\n\n".join(
                (
                    f"OUTPUT FROM {dependency}:\n"
                    f"{json.dumps(outputs[dependency], ensure_ascii=False)}"
                )
                for dependency in task.depends_on
            )

            dependency_context = (
                dependency_context
                if dependency_context
                else "No prerequisite outputs."
            )

            mcp_call = _select_mcp_tool(task.instruction)

            if mcp_call is not None:
                tool_name, arguments = mcp_call

                async_tasks[task_id] = executor.call(
                    tool_name,
                    arguments,
                )
            else:
                if llm is None:
                    raise RuntimeError(
                        f"Task {task_id} requires reasoning but no LLM "
                        "was supplied."
                    )

                async_tasks[task_id] = _run_reasoning_task(
                    plan.goal,
                    task.instruction,
                    dependency_context,
                    llm,
                )
# ---------------------------------------------------------------
# Execute this batch concurrently.
# ---------------------------------------------------------------
        results = await asyncio.gather(
            *async_tasks.values(),
            return_exceptions=True,
        )

        for task_id, result in zip(
            async_tasks.keys(),
            results,
        ):

            if isinstance(result, Exception):
                raise RuntimeError(
                    f"Task {task_id} failed: {result}"
                ) from result

            outputs[task_id] = result

    return outputs


async def _run_reasoning_task(
    goal: str,
    instruction: str,
    dependency_context: str,
    llm: Any,
) -> dict[str, Any]:

    prompt = f"""
You are the Brightpeak Academy planning agent.

Overall goal:
{goal}

Current reasoning task:
{instruction}

Prerequisite results:
{dependency_context}

Use ONLY the supplied prerequisite results.

Do not invent student data, grades, attendance, policies, or database facts.

Return a concise recommendation or analysis.
"""
    # Existing GeminiClient is synchronous, so execute it outside the
    # event loop when called from async DAG execution.
    answer = await asyncio.to_thread(
        llm.generate,
        prompt,
    )

    return {
        "type": "reasoning",
        "answer": answer.strip(),
    }


# ---------------------------------------------------------------------------
# Final synthesis
# ---------------------------------------------------------------------------
def final_output(
    plan: Plan,
    outputs: dict[str, Any],
) -> Any:
    """
    Return the single terminal node.

    The toolkit requires exactly one terminal synthesis task.
    """

    terminals = plan.terminal_tasks()

    if len(terminals) != 1:
        raise ValueError(
            "Expected exactly one terminal synthesis task, "
            f"found {terminals}"
        )

    return outputs[terminals[0]]

# ---------------------------------------------------------------------------
# Convenience integration function
# ---------------------------------------------------------------------------

async def run_decomposition_first(
    goal: str,
    llm: Any,
    mcp_session: Any,
) -> dict[str, Any]:
    """
    Main entry point for the Brightpeak Planning Agent.

    Flow:

        user request
             ↓
        Gemini generates DAG
             ↓
        Plan validates DAG / rejects cycles
             ↓
        topological batches
             ↓
        real MCP tool calls
             ↓
        reasoning nodes
             ↓
        final synthesis
    """

    plan = decompose_goal(
        goal,
        llm,
    )

    executor = MCPToolExecutor(
        session=mcp_session,
    )

    outputs = await execute_plan(
        plan=plan,
        executor=executor,
        llm=llm,
    )

    final = final_output(
        plan,
        outputs,
    )

    return {
        "method": "decomposition_first",
        "goal": goal,
        "plan": plan.model_dump(),
        "execution_batches": plan.execution_batches(),
        "outputs": outputs,
        "final": final,
    }
