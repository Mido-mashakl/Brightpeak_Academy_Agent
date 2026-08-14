import asyncio
import json
import sys
from pathlib import Path


# ============================================================
# Make project root importable
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from planning.algorithms.decomposition import run_decomposition_first


# ============================================================
# Fake planner
# Compatible with decomposition.py
# ============================================================

class FakePlanner:
    def __init__(self):
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1

        return """
{
    "goal": "Review Student 2's academic situation and produce a prioritized intervention plan.",
    "tasks": [
        {
            "id": "get_profile",
            "instruction": "Get Student 2's profile from the Brightpeak Academy database.",
            "depends_on": []
        },
        {
            "id": "get_enrollments",
            "instruction": "Get Student 2's enrolled courses from the database.",
            "depends_on": ["get_profile"]
        },
        {
            "id": "get_grades",
            "instruction": "Get Student 2's grades from the database.",
            "depends_on": ["get_profile"]
        },
        {
            "id": "get_attendance",
            "instruction": "Get Student 2's attendance records from the database.",
            "depends_on": ["get_profile"]
        },
        {
            "id": "check_attendance_policy",
            "instruction": "Search the Brightpeak attendance policy for rules relevant to Student 2.",
            "depends_on": []
        },
        {
            "id": "check_scholarship_policy",
            "instruction": "Search the Brightpeak scholarship policy for rules relevant to Student 2.",
            "depends_on": []
        },
        {
            "id": "create_intervention_plan",
            "instruction": "Combine the student's courses, grades, attendance, attendance policy, and scholarship policy to produce a prioritized intervention plan for the academic advisor.",
            "depends_on": [
                "get_enrollments",
                "get_grades",
                "get_attendance",
                "check_attendance_policy",
                "check_scholarship_policy"
            ]
        }
    ]
}
"""

class FakeMCPSession:
    """
    Fake MCP session for decomposition testing.

    It simulates the MCP session that the planning algorithm
    uses to execute the generated DAG tasks.
    """

    def __init__(self):
        self.calls = []

    async def call_tool(self, tool_name, arguments=None):
        self.calls.append({
            "tool": tool_name,
            "arguments": arguments or {},
        })

        return {
            "status": "success",
            "tool": tool_name,
            "arguments": arguments or {},
            "result": f"Fake result from {tool_name}",
        }
# ============================================================
# Fake task executor
# ============================================================

async def fake_executor(task):
    """
    Simulates execution of a DAG node.

    This represents the place where later we can connect
    the real MCP tools/database.
    """

    # Toolkit versions may pass different node structures.
    if hasattr(task, "description"):
        description = task.description
        task_id = getattr(task, "id", "unknown")
    elif isinstance(task, dict):
        task_id = task.get("id", "unknown")
        description = task.get("description", "")
    else:
        task_id = "unknown"
        description = str(task)

    return {
        "task_id": task_id,
        "status": "success",
        "result": f"Successfully executed: {description}",
    }


# ============================================================
# Load test case
# ============================================================

def load_case():
    case_path = ROOT / "planning_eval" / "cases" / "case_001.json"

    if not case_path.exists():
        raise FileNotFoundError(
            f"Test case not found:\n{case_path}"
        )

    with open(case_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# Main test
# ============================================================

async def main():

    case = load_case()

    goal = case.get("goal") or case.get("prompt")

    if not goal:
        raise ValueError(
            "case_001.json must contain either 'goal' or 'prompt'."
        )

    print("=" * 70)
    print("DECOMPOSITION-FIRST TEST")
    print("=" * 70)

    print("\nGoal:")
    print(goal)

    planner = FakePlanner()
    mcp_session = FakeMCPSession()

    print("\nRunning decomposition...\n")

    result = await run_decomposition_first(
        goal,
        planner,
        mcp_session,
    )

    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)

    print(result)

    print("\n" + "=" * 70)
    print("LLM CALLS")
    print("=" * 70)

    print(planner.calls)

    print("\n" + "=" * 70)
    print("MCP CALLS")
    print("=" * 70)

    print(len(mcp_session.calls))

    for i, call in enumerate(mcp_session.calls, 1):
        print(f"\n{i}. {call}")

    artifacts_dir = (
        ROOT
        / "planning_eval"
        / "artifacts"
        / "decomposition_first"
    )

    artifacts_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = artifacts_dir / "case_001_result.json"

    evidence = {
        "case": "case_001",
        "goal": goal,
        "method": "decomposition-first",
        "llm_calls": planner.calls,
        "mcp_calls": len(mcp_session.calls),
        "result": str(result),
    }

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            evidence,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print("\nEvidence saved to:")
    print(output_path)


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())