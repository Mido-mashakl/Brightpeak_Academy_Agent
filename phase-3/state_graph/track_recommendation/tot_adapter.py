"""
tot_adapter.py — Tree-of-Thought-style track comparison, adapted to the
graph's expected contract.

FIXED: `import tot` in nodes_evaluation.py pointed at nothing. The
project's real Tree-of-Thoughts implementation
(Phase-2/planning/algorithms/tree_of_thoughts.py::tree_of_thoughts) is an
LLM-driven beam search over free-text "thoughts" for open-ended problems
(it calls llm.with_structured_output(...) twice per expansion). It has no
notion of "candidate tracks scored against structured prerequisite data",
so it cannot be called as-is — its signature and output shape (a list of
free-text `Thought`s) don't match what confidence_policy_node needs:

    {"ranked": [(track_name, score), ...], "combined": {track_name: score}}

Design note (documented per the task's requirement to flag architectural
limitations instead of silently working around them): wiring the real
LLM-based tree_of_thoughts() into this graph would require a live LLM
provider (network + API key) for every single recommendation run, which
is neither available in this environment nor necessary for what this
node actually needs to decide (numeric ranking against known prerequisite
thresholds, not open-ended reasoning). This adapter instead implements
the SAME "generate multiple independent reasoning paths, score each, keep
the best-supported view" pattern the docstring in nodes_evaluation.py
already promised ("avg of 3 strategies"), but with three deterministic,
inspectable scoring strategies instead of LLM-generated candidates. If a
live LLM is later wired in, generate_llm_candidates() below is the single
seam to swap in Phase-2's tree_of_thoughts() for candidate generation
without touching the graph's contract.
"""
from __future__ import annotations

from typing import Any


def _prerequisite_strength(grades: dict[str, float], reqs: list[dict[str, Any]]) -> float:
    """Strategy 1: how well the student did on the exact prerequisite
    courses, taken at face value."""
    scores = [grades.get(p["course"], p["min_score"]) for p in reqs]
    return sum(scores) / len(scores) if scores else 0.0


def _prerequisite_margin(grades: dict[str, float], reqs: list[dict[str, Any]]) -> float:
    """Strategy 2: reframes each prerequisite as a pass/fail margin above
    its OWN min_score threshold (a 76 on an 80-min prereq is a weaker
    signal than a 76 on a 65-min prereq) — centered at 70 so an exact
    on-threshold grade doesn't automatically read as a strong signal."""
    margins = []
    for p in reqs:
        grade = grades.get(p["course"], p["min_score"])
        margin = 70 + (grade - p["min_score"])
        margins.append(max(0.0, min(100.0, margin)))
    return sum(margins) / len(margins) if margins else 0.0


def _core_course_readiness(grades: dict[str, float], core_courses: list[str]) -> float:
    """Strategy 3: looks past the prerequisites at the track's own core
    courses — if the student already has grades for any of them (e.g.
    from an earlier enrollment), that's directly relevant signal; courses
    not yet taken fall back to the student's overall average so an empty
    core-course history doesn't zero out the whole track."""
    overall = sum(grades.values()) / len(grades) if grades else 60.0
    scores = [grades.get(c, overall) for c in core_courses]
    return sum(scores) / len(scores) if scores else overall


def generate_llm_candidates(problem_context: dict[str, Any]):  # pragma: no cover
    """Seam for a future live-LLM strategy: import and call Phase-2's
    tree_of_thoughts() here and fold its scored candidates in as a 4th
    strategy, without changing compare_track_candidates()'s return
    contract. Not called by default (see module docstring)."""
    raise NotImplementedError(
        "No LLM provider configured for tot_adapter — falling back to the "
        "deterministic 3-strategy comparison in compare_track_candidates()."
    )


def compare_track_candidates(
    grades: dict[str, float],
    track_requirements: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compares every candidate track using 3 independent scoring
    strategies and averages them per track — the "avg of 3 strategies"
    ToT ranking nodes_evaluation.tot_node already advertises.

    Returns the exact contract confidence_policy_node / hitl_node /
    finalize_node expect:
        {"ranked": [(track, avg_score), ...] sorted desc,
         "combined": {track: avg_score}}
    """
    combined: dict[str, float] = {}
    for track, reqs in track_requirements.items():
        prereqs = reqs.get("prerequisites", [])
        core = reqs.get("core_courses", [])
        s1 = _prerequisite_strength(grades, prereqs)
        s2 = _prerequisite_margin(grades, prereqs)
        s3 = _core_course_readiness(grades, core)
        combined[track] = round((s1 + s2 + s3) / 3, 1)

    ranked = sorted(combined.items(), key=lambda pair: pair[1], reverse=True)
    return {"ranked": ranked, "combined": combined}