"""
nodes_intake.py — Student data collection, the missing-data check, and
the Diagnostic Assessment hand-off to the REAL Adaptive Assessment graph.

    collect_student_data
          |
    check_missing_data --(missing prereq course(s))--> prepare_diagnostic
          |(complete)                                        |
          v                                                   v
      rag_node                                await_diagnostic_response
      (nodes_evaluation.py)                                   |
          ^-------------------------------------------------- /
                    (resumes here once every missing course
                     has a real, completed Adaptive Assessment score)

FIXED — CRITICAL BUG #1 (side effects before interrupt()): the old
single-node `awaiting_diagnostic` created DiagnosticAssessments rows
(and started Adaptive Assessment sessions) and THEN called interrupt()
in the same node body, guarded by `pending_diagnostic_ids` — but a
node's return value is only committed to the checkpoint AFTER the node
finishes, and interrupt() unwinds execution before that happens. On
resume, LangGraph re-runs the node from the top with `pending_
diagnostic_ids` back to whatever it was in the LAST COMMITTED
checkpoint (i.e. still empty), so the create-diagnostic call ran again
and produced a second, duplicate DiagnosticAssessments row (and a
second, duplicate Adaptive Assessment session) for the same missing
course.

Fix — same prepare/await split used for the ticket and targeted-
assessment paths (nodes_evaluation.open_ticket_node /
await_ticket_resolution, nodes_hitl.prepare_targeted_assessment /
await_targeted_assessment_response):

  prepare_diagnostic
      - the ONLY node that calls db.create_diagnostic(...) /
        assessment_bridge.start_adaptive_session(...) for a missing
        course
      - returns `pending_diagnostic_ids` (course -> assessment_id) —
        this dict IS committed to the checkpoint before the graph ever
        reaches an interrupt(), because there is no interrupt() in this
        node at all
      - idempotent by construction: a course already present as a key
        in `pending_diagnostic_ids` is skipped, so re-running this node
        (which can legitimately happen if the graph loops back through
        check_missing_data more than once) never creates a second
        session for a course that already has one pending/complete

  await_diagnostic_response
      - the ONLY node that calls interrupt() for this path
      - never creates a DiagnosticAssessments row or an Adaptive
        Assessment session itself
      - idempotency for the "did we already score this one" question
        is NOT taken from graph state written after interrupt() (that
        would repeat CRITICAL BUG #1) — it's taken from
        db.get_diagnostic(assessment_id)['status'], which is only ever
        set to 'completed' by db.complete_diagnostic(), itself only
        ever called from inside this node right after a genuine
        interrupt() resume. That row is committed to brightpeak.db
        directly (outside the LangGraph checkpoint), so it survives a
        node re-run exactly the same way `open_ticket_id` /
        `pending_assessment_id` survive theirs, just via the
        application DB instead of graph state.

Architectural note on multiple missing courses in one pass: if more
than one prerequisite course is missing, `await_diagnostic_response`
calls interrupt() once per remaining course, in a loop, inside a SINGLE
node execution. LangGraph supports this: each call to interrupt() is
resolved by the next `Command(resume=...)` on that thread, in the order
the calls happen; on any resume the node body restarts from the top,
and every already-resolved course is skipped immediately via the
db.get_diagnostic status check above, so execution falls straight
through the already-answered interrupt() calls (LangGraph replays their
recorded resume values automatically) and only genuinely pauses again
at the first STILL-unanswered course. This keeps one prepare/await
node pair for the whole "missing courses" batch instead of needing a
Send()/sub-graph per course, which would be considerably more machinery
for what the demo scenarios actually require (see seed_demo.py).

FIXED — CRITICAL BUG #2: this path now hands off to the REAL Adaptive
Assessment graph via assessment_bridge (see assessment_bridge.py) —
prepare_diagnostic starts a real adaptive_assessment session per
missing course, and await_diagnostic_response reads back a real,
computed final_score from that session (assessment_bridge.
get_completed_score) instead of accepting a bare number handed in on
resume.
"""
import json

from langgraph.types import interrupt

import db
import assessment_bridge
from state import State, log_step


def collect_student_data(state: State) -> dict:
    """Pulls the student's current grades/attendance and the full list
    of candidate tracks fresh from the DB. `recommendation_id` is
    created once here if the caller didn't already supply one (e.g. a
    resumed/replayed run keeps whatever recommendation_id it started
    with)."""
    student_id = state["student_id"]
    student = db.get_student(student_id)
    student_name = student["name"] if student else f"Student #{student_id}"

    recommendation_id = state.get("recommendation_id")
    if recommendation_id is None:
        recommendation_id = db.create_recommendation(student_id)

    update = {
        "student_name": student_name,
        "recommendation_id": recommendation_id,
        "grades": db.get_student_grades(student_id),
        "attendance": db.get_student_attendance(student_id),
        "candidate_tracks": db.list_track_names(),
    }
    update.update(log_step(
        state,
        f"Collected data for {student_name}: {len(update['grades'])} graded course(s), "
        f"{len(update['candidate_tracks'])} candidate track(s)."
    ))
    return update


def check_missing_data(state: State) -> dict:
    """Determines which prerequisite courses the student has NO grade
    for, across every candidate track — using the DB's own authoritative
    Tracks.prerequisites_json (NOT the RAG documents; RAG hasn't run
    yet, and is a separate, independently-validated source consulted
    later in rag_node/rag_adapter for the full requirements contract).

    A course only needs to appear once even if it's a prerequisite for
    several tracks — hence `seen`."""
    grades = state["grades"]
    missing: list[str] = []
    seen: set[str] = set()

    for track_name in state["candidate_tracks"]:
        track_row = db.get_track_row(track_name)
        if track_row is None:
            continue
        for prereq in json.loads(track_row["prerequisites_json"]):
            course = prereq["course"]
            if course in seen:
                continue
            seen.add(course)
            if course not in grades:
                missing.append(course)

    update = {"missing_courses": missing}
    if missing:
        msg = (f"Missing grade data for prerequisite course(s): {', '.join(missing)} — "
               f"Diagnostic Assessment required before Track Recommendation can proceed.")
    else:
        msg = "Student has grade data for every prerequisite course across all candidate tracks."
    update.update(log_step(state, msg))
    return update


def route_missing_data(state: State) -> str:
    return "prepare_diagnostic" if state.get("missing_courses") else "rag_node"


def prepare_diagnostic(state: State) -> dict:
    """DB-write half of the diagnostic pause — see module docstring for
    why this must be the ONLY node that creates DiagnosticAssessments
    rows / starts Adaptive Assessment sessions for missing courses."""
    pending = dict(state.get("pending_diagnostic_ids") or {})
    created = []
    for course in state["missing_courses"]:
        if course in pending:
            continue  # already prepared on an earlier pass — nothing to do
        assessment_id = db.create_diagnostic(
            state["recommendation_id"], state["student_id"], course, trigger="missing_data",
        )
        assessment_bridge.start_adaptive_session(assessment_id, state["student_id"], course)
        pending[course] = assessment_id
        created.append(course)

    if created:
        db.update_recommendation(state["recommendation_id"], status="awaiting_assessment")

    update = {"pending_diagnostic_ids": pending}
    if created:
        update.update(log_step(
            state,
            f"Diagnostic Adaptive Assessment session(s) started for: {', '.join(created)}."
        ))
    return update


def await_diagnostic_response(state: State) -> dict:
    """TRUE waiting state #1: pauses once per still-unscored missing
    course until each one's REAL Adaptive Assessment session genuinely
    completes, then reads its real final_score (assessment_bridge.
    get_completed_score — never a fabricated number) straight into
    `grades` before Track Recommendation resumes into rag_node.

    Idempotency for "already scored this course" comes from
    db.get_diagnostic(...)['status'], not from anything only set after
    interrupt() — see module docstring."""
    pending = state["pending_diagnostic_ids"]
    new_grades = dict(state["grades"])
    completed_now = []

    for course in state["missing_courses"]:
        assessment_id = pending[course]
        diagnostic = db.get_diagnostic(assessment_id)
        if diagnostic is not None and diagnostic["status"] == "completed":
            new_grades[course] = diagnostic["score"]
            continue

        print(f"\n  ⏸  PAUSED — await_diagnostic_response. Diagnostic Adaptive Assessment "
              f"#{assessment_id} on '{course}' awaiting the student.")
        interrupt({
            "type": "awaiting_student",
            "subject": course,
            "assessment_id": assessment_id,
            "adaptive_thread_id": assessment_bridge.adaptive_thread_id(assessment_id),
            "message": f"Missing prerequisite data — Diagnostic Adaptive Assessment in {course}.",
        })
        # Resume value is just a completion signal; the real score is
        # read from the Adaptive Assessment session itself.
        score = assessment_bridge.get_completed_score(assessment_id)
        db.complete_diagnostic(assessment_id, score)
        new_grades[course] = score
        completed_now.append((course, score))

    db.update_recommendation(state["recommendation_id"], status="pending")
    update = {
        "grades": new_grades,
        "missing_courses": [],
        "pending_diagnostic_ids": {},
    }
    if completed_now:
        lines = [f"{c}={s}%" for c, s in completed_now]
        update.update(log_step(state, f"Diagnostic Assessment(s) completed: {', '.join(lines)}. "
                                       f"Resuming Track Recommendation."))
    else:
        update.update(log_step(state, "All missing-course diagnostics already completed — resuming."))
    return update
