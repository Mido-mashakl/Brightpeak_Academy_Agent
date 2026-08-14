import json
from pathlib import Path

from planning.algorithms.environment import Environment


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "brightpeak.db"


def ungrounded_critic(draft: str) -> str:
    return "The response is clear, consistent, and well-structured."


def main():
    environment = Environment(db_path=DB_PATH)

    draft = json.dumps({
        "student_id": 2,
        "decision": "eligible",
    })

    ungrounded_feedback = ungrounded_critic(draft)
    grounded_feedback = environment.evaluate(draft)

    print("=== GROUNDED VS UNGROUNDED ===")
    print()
    print("Draft:")
    print(draft)
    print()

    print("Ungrounded critique:")
    print(ungrounded_feedback)
    print("Ungrounded result: PASS")
    print()

    print("Grounded feedback:")
    print(grounded_feedback.details[0])
    print("Grounded result:", "PASS" if grounded_feedback.success else "FAIL")
    print()

    if not grounded_feedback.success:
        print("Grounded evaluation caught a failure that the ungrounded critique missed.")


if __name__ == "__main__":
    main()