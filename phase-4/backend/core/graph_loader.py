"""
graph_loader.py
================
The ONLY file that knows phase-3 even exists. Nothing else in phase-4
should import from phase-3 directly — always come through here.

GOOD NEWS (found by actually reading phase-3's code): the graph authors
already built clean entry-point functions for the platform to call.
You do NOT need to write low-level `graph.invoke(...)` / `Command(resume=...)`
code yourself for 4 out of 5 graphs. This file just re-exports what
already exists, with phase-3 correctly added to sys.path first.

    faculty_hiring        -> start_job, add_cv, close_applications,
                              resume_job, submit_hire_decision,
                              submit_interview_request, submit_rescore_request,
                              submit_interview_result
    academic_integrity     -> start_case, resume_case,
                              submit_committee_decision, submit_final_decision
    advisory (Certificate/
    Scholarship)           -> start_request
                              (docstring literally says:
                              "Entry point used by the platform's user surface")
    adaptive_assessment
    (STUB — not the real graph yet, see phase-3/README.md)
                            -> start_session, resume_session

    track_recommendation   -> ONLY build_graph() exists. No start_/resume_
                              wrapper has been written for this one yet.
                              You (or whoever owns it) will need to add one,
                              OR call track_recommendation_graph.invoke(...)
                              directly for now (see bottom of this file).
"""

import sys
import importlib
from pathlib import Path

# ---------------------------------------------------------------------------
# 1) Point Python at phase-3/, from wherever phase-4/backend happens to run.
# ---------------------------------------------------------------------------
THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[3]          # core -> backend -> phase-4 -> repo root
PHASE3_ROOT = REPO_ROOT / "phase-3"

if not PHASE3_ROOT.exists():
    raise RuntimeError(
        f"Can't find phase-3 at {PHASE3_ROOT}. "
        "Check that phase-3/ and phase-4/ are still siblings in the repo."
    )

if str(PHASE3_ROOT) not in sys.path:
    sys.path.insert(0, str(PHASE3_ROOT))

# ---------------------------------------------------------------------------
# 2) faculty_hiring — public Hiring surface (no auth needed)
# ---------------------------------------------------------------------------
from state_graph.faculty_hiring.graph import (   # noqa: E402
    start_job,
    add_cv,
    close_applications,
    resume_job,
)
from state_graph.faculty_hiring.hitl import (    # noqa: E402
    submit_hire_decision,
    submit_interview_request,
    submit_rescore_request,
    submit_interview_result,
)

# ---------------------------------------------------------------------------
# 3) academic_integrity, advisory, adaptive_assessment
#
# LAZY on purpose: academic_integrity/graph.py imports mcp_server/tools.py,
# which builds a Gemini client THE MOMENT IT'S IMPORTED and crashes if
# GEMINI_API_KEY isn't set yet (phase-3's own design, not something we can
# fix from phase-4). If we imported it eagerly here like faculty_hiring
# above, ANY missing key would block the whole platform — including
# features (like Hiring) that don't need Gemini at import time at all.
#
# So: these three are only actually imported the first time you call the
# wrapper function below, and cached after that. Add GEMINI_API_KEY to
# phase-3/.env whenever you're ready to actually use these three features;
# until then, Hiring keeps working fine on its own.
# ---------------------------------------------------------------------------

_cache: dict = {}


def start_case(*args, **kwargs):
    if "academic_integrity" not in _cache:
        from state_graph.academic_integrity import graph as _mod
        _cache["academic_integrity"] = _mod
    return _cache["academic_integrity"].start_case(*args, **kwargs)


def resume_case(*args, **kwargs):
    if "academic_integrity" not in _cache:
        from state_graph.academic_integrity import graph as _mod
        _cache["academic_integrity"] = _mod
    return _cache["academic_integrity"].resume_case(*args, **kwargs)


def submit_committee_decision(*args, **kwargs):
    from state_graph.academic_integrity import hitl as _mod
    return _mod.submit_committee_decision(*args, **kwargs)


def submit_final_decision(*args, **kwargs):
    from state_graph.academic_integrity import hitl as _mod
    return _mod.submit_final_decision(*args, **kwargs)


def start_advisor_request(*args, **kwargs):
    if "advisory" not in _cache:
        from state_graph.advisory import graph as _mod
        _cache["advisory"] = _mod
    return _cache["advisory"].start_request(*args, **kwargs)


def start_assessment_session(*args, **kwargs):
    """STUB graph — see phase-3 README. Placeholder data, not a real graph yet."""
    if "adaptive_assessment" not in _cache:
        from state_graph.adaptive_assessment import graph as _mod
        _cache["adaptive_assessment"] = _mod
    return _cache["adaptive_assessment"].start_session(*args, **kwargs)


def resume_assessment_session(*args, **kwargs):
    if "adaptive_assessment" not in _cache:
        from state_graph.adaptive_assessment import graph as _mod
        _cache["adaptive_assessment"] = _mod
    return _cache["adaptive_assessment"].resume_session(*args, **kwargs)

# ---------------------------------------------------------------------------
# 6) track_recommendation — only the raw compiled graph exists so far.
#    Loaded in isolation because its files (state.py, checkpointing.py...)
#    use BARE imports and would collide with the other graphs' same-named
#    files if left on sys.path permanently.
# ---------------------------------------------------------------------------
def get_track_recommendation_graph():
    folder = PHASE3_ROOT / "state_graph" / "track_recommendation"
    sys.path.insert(0, str(folder))
    try:
        module = importlib.import_module("graph")
        importlib.reload(module)
        return module.build_graph()
    finally:
        sys.path.remove(str(folder))
        sys.modules.pop("graph", None)