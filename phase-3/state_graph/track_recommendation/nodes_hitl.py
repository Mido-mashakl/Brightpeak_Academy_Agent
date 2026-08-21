"""
nodes_hitl.py — Human-in-the-loop: the Academic Advisor review, the
targeted-assessment follow-up it can trigger, and the final write.

      hitl_node --(approve / choose_other)------------------------> finalize_node
          |(request_assessment)
          v
      prepare_targeted_assessment -> await_targeted_assessment_response
                                          --(student completes it)--> tot_node
                                              (nodes_evaluation.py) --(forced
                                               re-review)--> hitl_node
"""
from langgraph.types import interrupt

import db
import assessment_bridge
from state import State, log_step, CONFIDENCE_GAP_THRESHOLD


def hitl_node(state: State) -> dict:
    """TRUE waiting state #2 (HITL): the agent stops and hands the
    decision to a human Academic Advisor. It never guesses on the
    advisor's behalf.

    `force_hitl_review` (set by await_targeted_assessment_response) is
    cleared HERE, after this review has actually happened — not in
    tot_node before route_confidence even reads it. That's what keeps
    confidence_gap/policy_ok from ever being stale: confidence_policy_node
    always runs and recomputes them, and route_confidence just checks
    the still-live flag to decide whether to force this node anyway.

    No DB writes happen before interrupt() here (unlike the diagnostic/
    ticket/targeted-assessment nodes) — hitl_node has nothing to persist
    until the advisor actually responds, so there's no prepare/await
    split needed for it specifically. The recommendation's status write
    for 'awaiting_advisor' happens in route paths that land here (see
    nodes_evaluation.confidence_policy_node's caller and
    await_targeted_assessment_response below)."""
    ranked = state["ranked"]
    top_track, top_score = ranked[0]
    alt_track, alt_score = ranked[1] if len(ranked) > 1 else (None, None)
    concerns = []
    if not state["policy_ok"]:
        concerns.append(f"'{top_track}' prerequisite minimum not fully satisfied.")
    if state["confidence_gap"] < CONFIDENCE_GAP_THRESHOLD:
        concerns.append(f"Top two tracks are close ({state['confidence_gap']} pt gap).")

    db.update_recommendation(state["recommendation_id"], status="awaiting_advisor")
    print(f"\n  ⏸  PAUSED — hitl_node. Awaiting Academic Advisor decision for "
          f"{state['student_name']}.")
    decision = interrupt({
        "type": "advisor_review",
        "student": state["student_name"],
        "top_recommendation": {"track": top_track, "score": top_score},
        "alternative": {"track": alt_track, "score": alt_score} if alt_track else None,
        "concerns": concerns,
        "actions": ["approve", "choose_other", "request_assessment"],
    })
    # decision: {"action": ..., "advisor_name": ..., "track": ..., "subject": ...}
    update = {"advisor_decision": decision}
    if state.get("force_hitl_review"):
        update["force_hitl_review"] = False
    update.update(log_step(state, f"Advisor decision: {decision}"))
    return update


def route_hitl(state: State) -> str:
    action = state["advisor_decision"]["action"]
    if action == "request_assessment":
        return "prepare_targeted_assessment"
    return "finalize_node"


def prepare_targeted_assessment(state: State) -> dict:
    """DB-write half of the targeted-assessment pause.

    FIXED — CRITICAL BUG #1: the old single-node version guarded on
    `pending_assessment_id`, but that guard was only returned AFTER
    interrupt(), so it was never committed before the pause — on resume
    the node re-ran from the top and created a SECOND assessment for the
    same advisor request. Splitting into prepare/await fixes this the
    same way as the diagnostic and ticket paths: this node's return
    value (pending_assessment_id, prior_evidence_count) IS committed
    before the graph reaches the interrupt() in the next node.

    FIXED — CRITICAL BUG #2: starts the REAL Adaptive Assessment graph
    for this subject (via assessment_bridge) instead of pausing for a
    bare score. If a diagnostic already exists for this subject, that
    prior result is READ (for prior_evidence_count) but never
    overwritten — a brand-new DiagnosticAssessments row (trigger=
    'advisor_request') and a brand-new Adaptive Assessment session are
    always created for a fresh advisor request, so both attempts remain
    available as evidence."""
    subject = state["advisor_decision"]["subject"]
    new_id = state.get("pending_assessment_id")
    if new_id is not None:
        return {}  # already prepared on an earlier pass — nothing to do

    prior = db.get_diagnostics_for_subject(state["recommendation_id"], subject)
    prior_count = len(prior)
    new_id = db.create_diagnostic(state["recommendation_id"], state["student_id"],
                                   subject, trigger="advisor_request")
    assessment_bridge.start_adaptive_session(new_id, state["student_id"], subject)
    db.update_recommendation(state["recommendation_id"], status="awaiting_assessment")

    update = {"pending_assessment_id": new_id, "prior_evidence_count": prior_count}
    update.update(log_step(
        state,
        f"New targeted Adaptive Assessment session #{new_id} started on '{subject}' "
        f"({prior_count} prior assessment(s) kept as historical evidence)."
    ))
    return update


def await_targeted_assessment_response(state: State) -> dict:
    """TRUE waiting state #3: advisor asked for more evidence on a
    specific subject; pauses until that new Adaptive Assessment session
    genuinely completes, then reads its REAL final score (never a
    fabricated one — see assessment_bridge.get_completed_score) and
    always routes back through tot_node -> confidence_policy_node ->
    hitl_node so the advisor reviews fresh, non-stale numbers."""
    subject = state["advisor_decision"]["subject"]
    new_id = state["pending_assessment_id"]
    prior_count = state.get("prior_evidence_count") or 0

    prior_note = (f"{prior_count} prior assessment(s) on record for '{subject}' "
                  f"(kept as historical evidence, not reused as the answer)."
                  if prior_count else f"No prior assessment on '{subject}' — this is the first.")
    print(f"\n  ⏸  PAUSED — await_targeted_assessment_response. New assessment #{new_id} on "
          f"'{subject}'. {prior_note}")

    interrupt({
        "type": "awaiting_student",
        "subject": subject,
        "assessment_id": new_id,
        "adaptive_thread_id": assessment_bridge.adaptive_thread_id(new_id),
        "prior_evidence_count": prior_count,
        "message": f"Advisor requested a targeted Adaptive Assessment session in {subject}.",
    })
    # Resume value is just a completion signal — the real score is read
    # from the Adaptive Assessment session itself.
    score = assessment_bridge.get_completed_score(new_id)
    db.complete_diagnostic(new_id, score)
    db.update_recommendation(state["recommendation_id"], status="pending")

    new_grades = dict(state["grades"])
    new_grades[subject] = score
    update = {
        "grades": new_grades,
        "targeted_subject": subject,
        "force_hitl_review": True,  # per design: always go back to the advisor after this
        "pending_assessment_id": None,     # cleared — this cycle is done
        "prior_evidence_count": None,
    }
    update.update(log_step(state, f"New targeted assessment on '{subject}' = {score}%. "
                                   f"{prior_note} Re-evaluating."))
    return update


def finalize_node(state: State) -> dict:
    ranked = state["ranked"]
    decision = state.get("advisor_decision")

    if decision is None:
        final_track, final_score = ranked[0]
        runner_up = ranked[1][0] if len(ranked) > 1 else None
        advisor_decision_label = None
        decided_by = "system (auto, high confidence)"
    else:
        action = decision["action"]
        if action == "approve":
            final_track, final_score = ranked[0]
        elif action == "choose_other":
            final_track = decision["track"]
            final_score = state["tot_result"]["combined"].get(final_track)
        else:
            final_track, final_score = ranked[0]  # fallback, shouldn't hit finalize directly
        runner_up = next((t for t, s in ranked if t != final_track), None)
        advisor_decision_label = action
        decided_by = decision.get("advisor_name", "Academic Advisor")

    db.finalize_recommendation(
        state["recommendation_id"], final_track, runner_up, final_score,
        advisor_decision_label, decided_by,
    )
    update = {"final_track": final_track, "final_confidence": final_score}
    update.update(log_step(
        state,
        f"🎯 FINALIZED — Recommended Track: {final_track} ({final_score}%), "
        f"decided_by={decided_by}"
    ))
    return update