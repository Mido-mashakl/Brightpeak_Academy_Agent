import json
from pathlib import Path

from planning.algorithms.environment import Environment
from planning.algorithms.reflexion import reflexion
from planning.algorithms.self_refine import reflect_and_refine


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "brightpeak.db"


def state(student_id: int, decision: str) -> str:
    return json.dumps({
        "student_id": student_id,
        "decision": decision,
    })


def run_self_refine(environment: Environment) -> None:
    task = "Decide scholarship eligibility for student 2."

    def llm_generate(_: str) -> str:
        return state(2, "eligible")

    def llm_revise(_: str, draft: str, feedback) -> str:
        print("Grounded feedback:")
        print(feedback.details[0])
        print()

        return state(2, "not_eligible")

    result = reflect_and_refine(
        task,
        llm_generate,
        llm_revise,
        environment,
    )

    print("=== SELF-REFINE ===")
    print("Initial draft:")
    print(result.draft)
    print()

    print("Final draft:")
    print(result.final)
    print()

    print("Final environment result:")
    print("PASS" if result.feedback.success else "FAIL")
    print()


def run_reflexion(environment: Environment) -> None:
    task = "Decide scholarship eligibility for student 2."
    seen_memories = []

    def llm_act(_: str, memories: list[str]) -> str:
        seen_memories.append(list(memories))

        if memories:
            return state(2, "not_eligible")

        return state(2, "eligible")

    def llm_reflect(_: str, state_text: str, feedback) -> str:
        reflection = (
            "Verify the student's average before deciding scholarship eligibility."
        )

        print("Reflection after failed trial:")
        print(reflection)
        print()

        return reflection

    result = reflexion(
        task,
        llm_act,
        llm_reflect,
        environment,
        max_trials=3,
        memory_size=2,
    )

    print("=== REFLEXION ===")
    print("Trial 1 memories:")
    print(seen_memories[0])
    print()

    print("Trial 2 memories:")
    print(seen_memories[1])
    print()

    print("Trials:", result.trials)
    print("Final state:")
    print(result.final_state)
    print()

    print("Final environment result:")
    print("PASS" if result.success else "FAIL")
    print()


if __name__ == "__main__":
    environment = Environment(db_path=DB_PATH)

    run_self_refine(environment)
    run_reflexion(environment)