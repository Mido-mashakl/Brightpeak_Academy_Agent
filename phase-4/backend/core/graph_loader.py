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


def get_case_state(case_id: int):
    """Read-only: current LangGraph state values for one academic-integrity
    case (severity_rationale, appeal_evaluation, decisions, etc.) — none of
    which live in the IntegrityCases table itself (only case_id, student_id,
    course_id, assignment_id, reported_by, description, similarity_score,
    severity, status, created_at, updated_at do). Mirrors the read-only
    get_advisor_request_state / get_assessment_session_state pattern below.
    Used by academic_integrity_router.py so the instructor/student-facing
    case detail responses can include the AI's actual reasoning instead of
    leaving it blank."""
    if "academic_integrity" not in _cache:
        from state_graph.academic_integrity import graph as _mod
        _cache["academic_integrity"] = _mod
    mod = _cache["academic_integrity"]
    config = {"configurable": {"thread_id": mod.thread_id_for_case(case_id)}}
    graph = mod.build_academic_integrity_graph()
    snapshot = graph.get_state(config)
    if snapshot is None or not snapshot.values:
        return None
    return snapshot.values


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
    """NOTE: the module docstring above (written before this pass) called
    this graph a stub. Re-inspected phase-3/state_graph/adaptive_assessment/
    graph.py directly: start_assessment / select_next_question (Task
    Decomposition) / evaluate_answer (Constrained ReAct) / finalize /
    flag_for_review are all real, non-mock nodes with a real interrupt-based
    HITL gate and a real DB-backed cycle. Treating it as real here."""
    if "adaptive_assessment" not in _cache:
        from state_graph.adaptive_assessment import graph as _mod
        _cache["adaptive_assessment"] = _mod
    return _cache["adaptive_assessment"].start_session(*args, **kwargs)


def resume_assessment_session(*args, **kwargs):
    if "adaptive_assessment" not in _cache:
        from state_graph.adaptive_assessment import graph as _mod
        _cache["adaptive_assessment"] = _mod
    return _cache["adaptive_assessment"].resume_session(*args, **kwargs)


def submit_assessment_review_decision(*args, **kwargs):
    """Admin's HITL resolve-task button for the flag_for_review gate."""
    if "adaptive_assessment" not in _cache:
        from state_graph.adaptive_assessment import graph as _mod
        _cache["adaptive_assessment"] = _mod
    from state_graph.adaptive_assessment import hitl as _hitl_mod
    return _hitl_mod.submit_review_decision(*args, **kwargs)


def get_assessment_session_state(session_id: int):
    """Read-only: current values (incl. pending_question) for one session.
    Routed through here rather than a direct `import state_graph...` in the
    router, to preserve the lazy-import rule above (importing this module
    eagerly can crash on a missing GEMINI_API_KEY)."""
    if "adaptive_assessment" not in _cache:
        from state_graph.adaptive_assessment import graph as _mod
        _cache["adaptive_assessment"] = _mod
    mod = _cache["adaptive_assessment"]
    config = {"configurable": {"thread_id": mod.thread_id_for_session(session_id)}}
    graph = mod.build_adaptive_assessment_graph()
    snapshot = graph.get_state(config)
    if snapshot is None:
        return None
    return {"values": snapshot.values, "next": snapshot.next}


# ---------------------------------------------------------------------------
# 4) advisory resume — graph.py only exports start_request(). human_review
#    and wait_for_student both pause with a bare `interrupt()` (not an
#    interrupt_before=[...] compile option), so resuming means invoking the
#    SAME compiled graph object with Command(resume=payload) against the
#    same thread_id — not update_state()+invoke(None) like the integrity/
#    assessment graphs. No such wrapper existed in advisory/graph.py or
#    advisory/hitl.py, so it's added here rather than inside phase-3 (kept
#    the "graph_loader is the only phase-4->phase-3 seam" rule intact).
# ---------------------------------------------------------------------------

def resume_advisor_request(request_id: int, payload: dict):
    """payload shape depends on which interrupt is open:
    - wait_for_student pause: the student's free-text reply (any JSON value)
    - human_review pause: {"decided_by": "...", "decision": "approve"|"reject"|"request_more_info", "notes": "..."}
    """
    if "advisory" not in _cache:
        from state_graph.advisory import graph as _mod
        _cache["advisory"] = _mod
    from langgraph.types import Command
    mod = _cache["advisory"]
    config = {"configurable": {"thread_id": f"student-advisor-{request_id}"}}
    return mod.student_advisor_graph.invoke(Command(resume=payload), config=config)


def get_advisor_request_state(request_id: int):
    """Read-only: current values + any pending interrupt for one request,
    used by GET /advisor/requests/{id} to show the admin what's waiting."""
    if "advisory" not in _cache:
        from state_graph.advisory import graph as _mod
        _cache["advisory"] = _mod
    mod = _cache["advisory"]
    config = {"configurable": {"thread_id": f"student-advisor-{request_id}"}}
    snapshot = mod.student_advisor_graph.get_state(config)
    if snapshot is None:
        return None
    return {
        "values": snapshot.values,
        "next": snapshot.next,
        "interrupts": [i.value for i in (snapshot.interrupts or [])] if hasattr(snapshot, "interrupts") else [],
    }

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


# ---------------------------------------------------------------------------
# 7) track_recommendation start_/resume_ wrappers.
#    Only build_graph() existed (see module docstring) — no start_/resume_
#    functions had been written anywhere in phase-3 for this graph, unlike
#    the other four. Written here, following the exact pattern seed_demo.py
#    already uses to drive this same graph (bare interrupt(), so resume is
#    Command(resume=...), not update_state()).
#
#    IMPORTANT ISOLATION CAVEAT (inherited, not introduced): this graph's
#    files use bare imports and collide with same-named files in the other
#    four graphs (state.py, checkpointing.py, db.py all exist in more than
#    one graph folder) if left on sys.path together. get_track_recommendation_graph()
#    already handles this per-call by inserting/removing the folder around a
#    single import. The wrappers below do the same for every call rather than
#    caching a module-level graph object (unlike the other four graphs),
#    which is slightly slower per call but avoids reintroducing the sys.path
#    collision the isolation was built to prevent.
# ---------------------------------------------------------------------------

def _with_track_recommendation_module():
    folder = PHASE3_ROOT / "state_graph" / "track_recommendation"
    sys.path.insert(0, str(folder))
    try:
        graph_mod = importlib.import_module("graph")
        importlib.reload(graph_mod)
        from langgraph.types import Command  # noqa: F401 (re-exported to caller via closure below)
        return graph_mod, Command
    finally:
        sys.path.remove(str(folder))
        sys.modules.pop("graph", None)
        for _m in ("state", "checkpointing", "db", "nodes_intake", "nodes_evaluation", "nodes_hitl"):
            sys.modules.pop(_m, None)


def start_track_recommendation(student_id: int, thread_id: str | None = None):
    """Entry point the platform calls when a student requests a track
    recommendation. No start_ wrapper existed in track_recommendation/
    (see module docstring) so this mirrors seed_demo.py's own invocation
    pattern: fresh thread_id, first invoke carries {student_id, thread_id}."""
    import uuid
    graph_mod, _Command = _with_track_recommendation_module()
    thread_id = thread_id or f"track-rec-{uuid.uuid4().hex[:12]}"
    config = {"configurable": {"thread_id": thread_id}}
    graph = graph_mod.build_graph()
    result = graph.invoke({"student_id": student_id, "thread_id": thread_id}, config=config)
    result = dict(result)
    result["thread_id"] = thread_id

    # Write thread_id back onto the row the graph just created (or is about
    # to create — collect_student_data/db.create_recommendation runs before
    # the first pause) so the advisor UI can find "which thread do I resume
    # for this row?" from TrackRecommendations alone, without the platform
    # having to persist thread_id anywhere itself. See db/schema.sql's
    # TrackRecommendations.thread_id comment for why this exists.
    recommendation_id = result.get("recommendation_id")
    if recommendation_id is not None:
        import mcp_server.database as db
        db.execute(
            "UPDATE TrackRecommendations SET thread_id = ? WHERE recommendation_id = ?",
            (thread_id, recommendation_id),
        )
    return result


def resume_track_recommendation(thread_id: str, resume_payload: dict):
    """Entry point the platform calls after: a missing-course Adaptive
    Assessment completes, an admin 'fixes' a RAG-failure ticket, or an
    Advisor makes a HITL decision (approve top track / choose other /
    request targeted assessment). resume_payload shape depends on which
    interrupt is open — mirrors seed_demo.py's Command(resume=...) calls:
      - diagnostic/targeted assessment done: {"completed": True}
      - ticket resolved:                     {"fixed": True}
      - advisor decision:                    {"action": "approve"|"choose_other"|"request_targeted",
                                               "advisor_name": "...", "track": "...", "subject": "..."}
    """
    graph_mod, Command = _with_track_recommendation_module()
    config = {"configurable": {"thread_id": thread_id}}
    graph = graph_mod.build_graph()
    result = graph.invoke(Command(resume=resume_payload), config=config)
    return dict(result)


def get_track_recommendation_state(thread_id: str):
    """Returns the graph's committed state PLUS the live interrupt payload,
    if the thread is currently paused.

    graph.get_state() (unlike graph.invoke()) does NOT put the interrupt
    payload under a "__interrupt__" key in snapshot.values — it lives on
    snapshot.tasks[*].interrupts[*].value instead, since interrupt() args
    are never committed to state. hitl_node's advisor_review payload
    (student, top_recommendation, alternative, concerns, actions) is built
    from local variables and only exists there, so without this extraction
    the advisor UI would see recommended_track/confidence etc. from
    `values` but never the concerns list or the allowed actions — this
    mirrors the "_interrupt" convention _safe_state() already uses for the
    other four graphs, for a consistent shape across routers."""
    graph_mod, _Command = _with_track_recommendation_module()
    config = {"configurable": {"thread_id": thread_id}}
    graph = graph_mod.build_graph()
    snapshot = graph.get_state(config)
    if snapshot is None:
        return None
    out = {"values": snapshot.values, "next": snapshot.next}
    interrupts = [
        getattr(iv, "value", iv)
        for task in snapshot.tasks
        for iv in (getattr(task, "interrupts", None) or ())
    ]
    if interrupts:
        out["_interrupt"] = interrupts
    return out