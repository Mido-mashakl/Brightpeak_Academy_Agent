from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planning.algorithms.environment import Environment
from planning.algorithms.lats import flatten_lats_tree, lats
from planning.llm_provider import get_planning_llm
from planning.models import EnvironmentFeedback

ITERATIONS = 1
N_ACTIONS = 1


class RecordingEnvironment:
    """Thin pass-through around the real, DB-grounded Environment.

    This exists only to keep an ordered log of every candidate state that
    was evaluated, for the evidence file. It never computes success/score
    itself -- every EnvironmentFeedback comes straight from Environment,
    which queries db/brightpeak.db. Swap this for `environment` directly
    if you don't need the call log.
    """

    def __init__(self, environment: Environment):
        self._environment = environment
        self.calls: list[str] = []

    def evaluate(self, state: str) -> EnvironmentFeedback:
        self.calls.append(state)
        return self._environment.evaluate(state)


def load_case(case_id: str) -> dict:
    path = ROOT / "planning_eval" / "cases" / f"{case_id}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    case = load_case("case_lats_001")
    instruction = case["instruction"]

    db_path = Path(ROOT) / "db" / "brightpeak.db"
    if not db_path.exists():
        raise FileNotFoundError(
            f"Expected the real Brightpeak DB at {db_path}. "
            "This test does not fall back to a mock/stub environment."
        )

    print("=" * 70)
    print(f"LATS TEST (real Gemini calls + real grounded Environment, "
          f"iterations={ITERATIONS}, n_actions={N_ACTIONS})")
    print("=" * 70)
    print("\nInstruction:")
    print(instruction)

    llm = get_planning_llm()
    environment = Environment(db_path=db_path)
    recording_environment = RecordingEnvironment(environment)

    start = time.perf_counter()
    outcome = lats(
        instruction,
        llm,
        recording_environment,
        iterations=ITERATIONS,
        n_actions=N_ACTIONS,
    )
    latency_s = round(time.perf_counter() - start, 4)

    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)
    print("success:", outcome.success)
    print("output:", outcome.output)
    print("best_score:", outcome.best_score)
    print("iterations run:", outcome.iterations)
    print("\nLatency (s):", latency_s)

    assert isinstance(outcome.output, str) and outcome.output.strip()
    assert 0.0 <= outcome.best_score <= 1.0

    tree = flatten_lats_tree(outcome.root)
    candidate_feedback = [r["feedback"] for r in tree if r["feedback"] is not None]
    failed_before_result = sum(1 for fb in candidate_feedback if not fb["success"])

    print("candidates evaluated:", len(candidate_feedback))
    print("failed before final result:", failed_before_result)

    artifacts_dir = ROOT / "planning_eval" / "artifacts" / "lats"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    output_path = artifacts_dir / "case_lats_001_result_live.json"

    evidence = {
        "case": case["case_id"],
        "method": "lats",
        "provider": "ChatGoogleGenerativeAI (real call)",
        "environment": "planning.algorithms.environment.Environment (real, grounded)",
        "db_path": str(db_path),
        "instruction": instruction,
        "iterations_configured": ITERATIONS,
        "n_actions_configured": N_ACTIONS,
        "latency_s": latency_s,
        "success": outcome.success,
        "output": outcome.output,
        "best_score": outcome.best_score,
        "iterations_run": outcome.iterations,
        "candidates_evaluated": len(candidate_feedback),
        "failed_before_result": failed_before_result,
        "environment_calls": recording_environment.calls,
        "tree": tree,
        "note": (
            "environment is the real grounded Environment "
            "(planning/algorithms/environment.py), querying db/brightpeak.db "
            "directly. No stub or mock is used anywhere in this run; "
            "EnvironmentFeedback is produced by an independent SQL check "
            "against the student's recorded grades, not by the LLM judging "
            "its own output."
        ),
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False)

    print("\nEvidence saved to:", output_path)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()