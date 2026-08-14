
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planning.algorithms.plan_and_solve import plan_and_solve
from planning.llm_provider import get_planning_llm


def load_case(case_id: str) -> dict:
    path = ROOT / "planning_eval" / "cases" / f"{case_id}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    case = load_case("case_ps_001")
    instruction = case["instruction"]

    print("=" * 70)
    print("PLAN-AND-SOLVE TEST (real Gemini call)")
    print("=" * 70)
    print("\nInstruction:")
    print(instruction)

    llm = get_planning_llm()

    start = time.perf_counter()
    result = plan_and_solve(instruction, llm)
    latency_s = round(time.perf_counter() - start, 4)

    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)
    print(result)
    print("\nLatency (s):", latency_s)

    # Loose structural checks only - real model output is not deterministic,
    # so we check shape/non-emptiness, not exact wording.
    assert isinstance(result, str) and result.strip(), "plan_and_solve returned empty output"

    artifacts_dir = ROOT / "planning_eval" / "artifacts" / "plan_and_solve"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    output_path = artifacts_dir / "case_ps_001_result_live.json"

    evidence = {
        "case": case["case_id"],
        "method": "plan_and_solve",
        "provider": "ChatGoogleGenerativeAI (real call)",
        "instruction": instruction,
        "latency_s": latency_s,
        "result": result,
        "note": (
            "Token counts are not captured here: plan_and_solve() only "
            "returns response.content (a plain string), not the full "
            "response object, so usage metadata isn't reachable from "
            "outside without editing the toolkit function itself, which "
            "the assignment says not to do. Capture tokens via a callback "
            "bound in llm_provider.py if the comparison table needs them."
        ),
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False)

    print("\nEvidence saved to:", output_path)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()