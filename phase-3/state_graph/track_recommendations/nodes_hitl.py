"""
nodes_hitl.py — Human-in-the-loop: the Academic Advisor review, the
targeted-assessment follow-up it can trigger, and the final write.

      hitl_node --(approve / choose_other)--------------> finalize_node
          |(request_assessment)
          v
      targeted_assessment_node --(student responds)--> tot_node (nodes_evaluation.py)
                                                          --(forced re-review)--> hitl_node
"""
from langgraph.types import interrupt

import db
from state import State, log_step, CONFIDENCE_GAP_THRESHOLD


def hitl_node(state: State) -> dict:
    """TRUE waiting state #2 (HITL): the agent stops and hands the
    decision to a human Academic Advisor. It never guesses on the
    advisor's behalf.

    `force_hitl_review` (set by targeted_assessment_node) is cleared
    HERE, after this review has actually happened — not in tot_node
    before route_confidence even reads it. That's what keeps
    confidence_gap/policy_ok from ever being stale: confidence_policy_node
    now always runs and recomputes them, and route_confidence just checks
    the still-live flag to decide whether to force this node anyway."""
    ranked = state["ranked"]
    top_track, top_score = ranked[0]
    alt_track, alt_score = ranked[1] if len(ranked) > 1 else (None, None)
    concerns = []
    if not state["policy_ok"]:
        concerns.append(f"'{top_track}' prerequisite minimum not fully satisfied.")
    if state["confidence_gap"] < CONFIDENCE_GAP_THRESHOLD:
        concerns.append(f"Top two tracks are close ({state['confidence_gap']} pt gap).")

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
        return "targeted_assessment_node"
    return "finalize_node"


def targeted_assessment_node(state: State) -> dict:
    """TRUE waiting state #3: advisor asked for more evidence on a
    specific subject. If a diagnostic already exists for that subject
    (e.g. from the missing-data step), it is kept as prior evidence —
    NOT reused as the answer — and a NEW, distinct assessment is created.

    Idempotency guard: `pending_assessment_id` is read from state instead
    of unconditionally calling db.create_diagnostic(). On re-entry after
    the interrupt() resume it's already set, so we reuse the SAME
    assessment id instead of opening a second one for the same request.
    Once the cycle completes (student answers, score recorded) the guard
    is cleared back to None so a LATER, separate advisor request for a
    different subject starts its own fresh assessment."""
    subject = state["advisor_decision"]["subject"]
    new_id = state.get("pending_assessment_id")
    prior_count = state.get("prior_evidence_count")

    if new_id is None:
        prior = db.get_diagnostics_for_subject(state["recommendation_id"], subject)
        prior_count = len(prior)
        new_id = db.create_diagnostic(state["recommendation_id"], state["student_id"],
                                       subject, trigger="advisor_request")
        db.update_recommendation(state["recommendation_id"], status="awaiting_assessment")

    prior_note = (f"{prior_count} prior assessment(s) on record for '{subject}' "
                  f"(kept as historical evidence, not reused as the answer)."
                  if prior_count else f"No prior assessment on '{subject}' — this is the first.")
    print(f"\n  ⏸  PAUSED — targeted_assessment_node. New assessment #{new_id} on "
          f"'{subject}'. {prior_note}")

    result = interrupt({
        "type": "awaiting_student",
        "subject": subject,
        "assessment_id": new_id,
        "prior_evidence_count": prior_count,
        "message": f"Advisor requested a targeted assessment in {subject}.",
    })
    # result: {"score": 89}
    score = result["score"]
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