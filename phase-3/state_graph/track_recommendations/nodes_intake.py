"""
nodes_intake.py — Everything before we start evaluating track fit:
pull the student's real data, figure out what's missing, and (if
needed) pause for a diagnostic assessment.

    collect_student_data
          |
    check_missing_data --(missing)--> awaiting_diagnostic --(student responds)--\
          |(complete)                                                            |
          v <-----------------------------------------------------------------/
      (continues to rag_node, defined in nodes_evaluation.py)
"""
import json

from langgraph.types import interrupt

import db
from state import State, log_step


def collect_student_data(state: State) -> dict:
    student = db.get_student(state["student_id"])
    grades = db.get_student_grades(state["student_id"])
    attendance = db.get_student_attendance(state["student_id"])
    rec_id = state.get("recommendation_id") or db.create_recommendation(state["student_id"])
    tracks = state.get("candidate_tracks") or db.list_track_names()

    update = {
        "student_name": student["name"] if student else f"#{state['student_id']}",
        "grades": grades,
        "attendance": attendance,
        "recommendation_id": rec_id,
        "candidate_tracks": tracks,
    }
    update.update(log_step(
        state,
        f"Collected data for {update['student_name']}: "
        f"{len(grades)} graded courses on record."
    ))
    return update


def check_missing_data(state: State) -> dict:
    """Union of prerequisite courses across ALL candidate tracks — since
    we don't know yet which track fits, we need grades for anything any
    of them might require."""
    grades = state["grades"]
    needed = set()
    for track in state["candidate_tracks"]:
        row = db.get_track_row(track)
        if not row:
            continue
        for p in json.loads(row["prerequisites_json"]):
            needed.add(p["course"])
    missing = sorted(c for c in needed if c not in grades)
    update = {"missing_courses": missing}
    if missing:
        update.update(log_step(state, f"Missing prerequisite data: {missing}"))
    else:
        update.update(log_step(state, "All prerequisite grades already on record — no wait needed."))
    return update


def route_missing_data(state: State) -> str:
    return "awaiting_diagnostic" if state.get("missing_courses") else "rag_node"


def awaiting_diagnostic(state: State) -> dict:
    """TRUE waiting state #1: pauses until the student completes a
    short diagnostic for each missing subject. Checkpointed — the
    process can restart and this will still be sitting here.

    Idempotency guard: `pending_diagnostic_ids` is read from state (not
    reinitialized to {}) so that when this node body re-runs from the
    top after the interrupt() resume, subjects that already got a
    diagnostic row on the first pass are skipped instead of getting a
    second, duplicate row. Same pattern as ticket_node's `open_ticket_id`
    guard in nodes_evaluation.py.
    """
    subjects = state["missing_courses"]
    pending_ids = dict(state.get("pending_diagnostic_ids") or {})

    is_first_pass = not pending_ids
    for subject in subjects:
        if subject not in pending_ids:
            pending_ids[subject] = db.create_diagnostic(
                state["recommendation_id"], state["student_id"],
                subject, trigger="missing_data")
    if is_first_pass:
        db.update_recommendation(state["recommendation_id"], status="awaiting_diagnostic")

    print(f"\n  ⏸  PAUSED — awaiting_diagnostic. Student must complete: {subjects}")
    answers = interrupt({
        "type": "awaiting_diagnostic",
        "message": f"Please complete a short diagnostic in: {', '.join(subjects)}",
        "subjects": subjects,
    })
    # answers: {"Introduction to Python": 76, ...}
    new_grades = dict(state["grades"])
    for subject, score in answers.items():
        aid = pending_ids.get(subject)
        if aid:
            db.complete_diagnostic(aid, score)
        new_grades[subject] = score

    db.update_recommendation(state["recommendation_id"], status="pending")
    update = {
        "grades": new_grades,
        "missing_courses": [],
        "pending_diagnostic_ids": pending_ids,
    }
    update.update(log_step(state, f"Diagnostic results received: {answers}"))
    return update