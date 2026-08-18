
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planning.llm_provider import get_planning_llm
from planning.router import classify_task, route_and_solve


def load_case(case_id: str) -> dict:
    path = ROOT / "planning_eval" / "cases" / f"{case_id}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    print("=" * 70)
    print("ROUTER TEST - classify_task (pure logic, no LLM call)")
    print("=" * 70)

    cases = [load_case("case_ps_001"), load_case("case_tot_001"), load_case("case_lats_001")]
    classify_results = []
    for case in cases:
        decision = classify_task(case["instruction"])
        print(f"\n[{case['case_id']}] -> {decision.method.value}")
        print("  reason:", decision.reason)
        expected = case["expected_router_method"]
        assert decision.method.value == expected, (
            f"{case['case_id']}: expected routing to {expected!r}, got {decision.method.value!r}"
        )
        classify_results.append(
            {"case": case["case_id"], "instruction": case["instruction"],
             "routed_to": decision.method.value, "reason": decision.reason}
        )

    print("\n" + "=" * 70)
    print("ROUTER TEST - route_and_solve dispatch (real Gemini call for PS)")
    print("=" * 70)

    llm = get_planning_llm()

    start = time.perf_counter()
    ps_envelope = route_and_solve(cases[0]["instruction"], llm)
    ps_latency_s = round(time.perf_counter() - start, 4)
    print("\nPS envelope method:", ps_envelope["method"])
    print("PS result:", ps_envelope["result"])
    assert ps_envelope["method"] == "plan_and_solve"
    assert isinstance(ps_envelope["result"], str) and ps_envelope["result"].strip()

    # LATS dispatch guard: no environment supplied must raise, not silently
    # fall back - this is free, no LLM call happens before the guard fires.
    raised = False
    try:
        route_and_solve(cases[2]["instruction"], llm)
    except ValueError as exc:
        raised = True
        print("\nLATS-without-environment correctly raised:", exc)
    assert raised, "route_and_solve must refuse to run LATS without an explicit grounded environment"

    artifacts_dir = ROOT / "planning_eval" / "artifacts" / "router"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    output_path = artifacts_dir / "case_router_001_result_live.json"

    evidence = {
        "classify_task": classify_results,
        "route_and_solve": {
            "plan_and_solve": {
                "provider": "ChatGoogleGenerativeAI (real call)",
                "latency_s": ps_latency_s,
                "envelope": ps_envelope,
            },
            "lats_guard_raised": raised,
        },
        "note": (
            "ToT/LATS real dispatch through the router are exercised in "
            "test_tree_of_thoughts.py / test_lats.py, not duplicated here."
        ),
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False)

    print("\nEvidence saved to:", output_path)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()