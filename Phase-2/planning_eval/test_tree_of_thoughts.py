
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planning.algorithms.tree_of_thoughts import tree_of_thoughts
from planning.llm_provider import get_planning_llm

DEPTH = 1
BEAM_WIDTH = 1


def load_case(case_id: str) -> dict:
    path = ROOT / "planning_eval" / "cases" / f"{case_id}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    case = load_case("case_tot_001")
    instruction = case["instruction"]

    print("=" * 70)
    print(f"TREE OF THOUGHTS TEST (real Gemini calls, depth={DEPTH}, beam_width={BEAM_WIDTH})")
    print("=" * 70)
    print("\nInstruction:")
    print(instruction)

    llm = get_planning_llm()

    start = time.perf_counter()
    thoughts = tree_of_thoughts(instruction, llm, depth=DEPTH, beam_width=BEAM_WIDTH)
    latency_s = round(time.perf_counter() - start, 4)

    print("\n" + "=" * 70)
    print("FINAL FRONTIER (best first)")
    print("=" * 70)
    for t in thoughts:
        print(f"score={t.score:.2f}  state={t.state}")
        print(f"  rationale: {t.rationale}")
    print("\nLatency (s):", latency_s)

    assert len(thoughts) == BEAM_WIDTH, f"expected {BEAM_WIDTH} thought(s) in the final frontier"
    assert all(0.0 <= t.score <= 1.0 for t in thoughts), "scores must stay in [0, 1]"

    artifacts_dir = ROOT / "planning_eval" / "artifacts" / "tree_of_thoughts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    output_path = artifacts_dir / "case_tot_001_result_live.json"

    evidence = {
        "case": case["case_id"],
        "method": "tree_of_thoughts",
        "provider": "ChatGoogleGenerativeAI (real call)",
        "instruction": instruction,
        "depth": DEPTH,
        "beam_width": BEAM_WIDTH,
        "latency_s": latency_s,
        "final_frontier": [t.model_dump() for t in thoughts],
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False)

    print("\nEvidence saved to:", output_path)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()