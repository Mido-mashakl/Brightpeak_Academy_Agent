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

from planning.algorithms.dynamic_decomposition import dynamic_decomposition

# ---------------------------------------------------------
# Fake LLM
# ---------------------------------------------------------

class FakeDecision:
    def __init__(self, done, next_task):
        self.done = done
        self.next_task = next_task


class FakeDynamicLLM:

    def __init__(self):
        self.step = 0

    def with_structured_output(self, *args, **kwargs):
        return self

    def invoke(self, messages, **kwargs):

        self.step += 1

        class Response:
            pass

        response = Response()

        # First decision
        if self.step == 1:
            response.done = False
            response.next_task = "Get the student's attendance"
            return response

        # After observing low attendance,
        # dynamically change the plan.
        if self.step == 2:
            response.done = False
            response.next_task = "Search the attendance policy"
            return response

        # Final
        response.done = True
        response.next_task = ""

        return response


# ---------------------------------------------------------
# Fake MCP executor
# ---------------------------------------------------------

def fake_executor(task):

    if "attendance" in task.lower():
        return {
            "student_id": 1,
            "attendance": 62.0
        }

    if "policy" in task.lower():
        return {
            "minimum_attendance": 75
        }

    return {
        "result": "ok"
    }


# ---------------------------------------------------------
# Test
# ---------------------------------------------------------

def main():

    goal = (
        "Create an academic intervention plan for "
        "student 1."
    )

    llm = FakeDynamicLLM()

    result = dynamic_decomposition(
        goal=goal,
        llm=llm,
        task_executor=fake_executor,
        max_steps=4,
    )

    print("\n=== DYNAMIC DECOMPOSITION TEST ===\n")

    for task, observation in result:

        print(f"TASK: {task}")
        print(f"OBSERVATION: {observation}")
        print("-" * 60)

    # We expect the dynamic planner to inspect attendance
    # and then search the policy.
    tasks = [task for task, _ in result]

    assert any(
        "attendance" in task.lower()
        for task in tasks
    )

    assert any(
        "policy" in task.lower()
        for task in tasks
    )

    print("\nPASS")


if __name__ == "__main__":
    main()