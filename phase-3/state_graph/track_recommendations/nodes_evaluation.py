"""
nodes_evaluation.py — RAG retrieval (+ its Ticket failure path), ToT
comparison, and the confidence/policy check that decides whether we
can auto-finalize or need the Advisor.

      rag_node <--------------------------------------\
          |(doc invalid)-> ticket_node --(admin fixes)-/   [resumes from checkpoint]
          |(all ok)
          v
      tot_node
          |
    confidence_policy_node --(clear)--> finalize_node
          |(unclear / policy issue / forced review)
          v
      hitl_node   (defined in nodes_hitl.py)
"""
from langgraph.types import interrupt

import db
import rag
import tot
from state import State, log_step, CONFIDENCE_GAP_THRESHOLD


def rag_node(state: State) -> dict:
    """RAG: retrieve + validate each candidate track's requirements from
    the documents source. Stops at the first invalid document so the
    Ticket path can be demoed without losing progress on tracks already
    resolved — that's exactly what `rag_pending_tracks` preserves."""
    pending = state.get("rag_pending_tracks")
    if pending is None:
        pending = list(state["candidate_tracks"])
    reqs = dict(state.get("track_requirements", {}))
    force_broken = state.get("force_broken_track")

    while pending:
        track = pending[0]
        try:
            reqs[track] = rag.retrieve_track_requirements(track, force_broken=(track == force_broken))
            pending = pending[1:]
        except rag.DocumentValidationError as e:
            update = {
                "track_requirements": reqs,
                "rag_pending_tracks": pending,
                "rag_failed_track": track,
            }
            update.update(log_step(state, f"❌ RAG validation FAILED for '{track}': {e.reason}"))
            return update

    update = {"track_requirements": reqs, "rag_pending_tracks": pending, "rag_failed_track": None}
    update.update(log_step(state, f"RAG retrieved & validated requirements for: {list(reqs.keys())}"))
    return update


def route_rag(state: State) -> str:
    return "ticket_node" if state.get("rag_failed_track") else "tot_node"


def ticket_node(state: State) -> dict:
    """Independent failure/recovery path — NOT a human decision, just a
    broken document being flagged for an admin. Resuming here continues
    the SAME rag_node loop (via rag_pending_tracks), not a restart.

    Idempotency guard: `open_ticket_id` is only opened the first time
    this node body runs; on resume after interrupt() the guard sees a
    non-None id and skips re-opening a duplicate ticket."""
    track = state["rag_failed_track"]
    ticket_id = state.get("open_ticket_id")
    if ticket_id is None:
        ticket_id = db.open_ticket(
            source_id=state["recommendation_id"],
            thread_id=state["thread_id"],
            failure_type="schema_validation_failed",
            details=f"Track document for '{track}' is missing required fields.",
        )
        db.update_recommendation(state["recommendation_id"], status="failed")

    print(f"\n  ⏸  PAUSED — ticket_node. 🎫 Ticket #{ticket_id} open for admin: "
          f"'{track}' document incomplete.")
    resolution = interrupt({
        "type": "ticket_needs_admin",
        "ticket_id": ticket_id,
        "track": track,
        "message": f"Track document '{track}' failed validation. Admin must fix it.",
    })
    # resolution: {"fixed": True}
    db.resolve_ticket(ticket_id)
    db.update_recommendation(state["recommendation_id"], status="pending")
    update = {
        "open_ticket_id": None,
        "rag_failed_track": None,
        "force_broken_track": None,  # admin's fix = document no longer broken
    }
    update.update(log_step(state, f"🎫 Ticket #{ticket_id} resolved by admin. Resuming RAG from checkpoint."))
    return update


def tot_node(state: State) -> dict:
    """Always flows straight into confidence_policy_node now — no more
    `_route_hint` branch that used to skip the confidence/policy check
    (and therefore leave a stale confidence_gap/policy_ok in state) when
    `force_hitl_review` was set. The forced-review flag is still honored,
    just later: confidence_policy_node recomputes gap/policy on the new
    `ranked` first, and route_confidence (below) checks the flag to
    force a trip back to the Advisor regardless of how clear the new
    numbers look."""
    result = tot.compare_track_candidates(state["grades"], state["track_requirements"])
    update = {"tot_result": result, "ranked": result["ranked"]}
    lines = [f"{t}: {s}%" for t, s in result["ranked"]]
    update.update(log_step(state, f"ToT ranking (avg of 3 strategies) → {', '.join(lines)}"))
    return update


def confidence_policy_node(state: State) -> dict:
    ranked = state["ranked"]
    top_track, top_score = ranked[0]
    gap = (top_score - ranked[1][1]) if len(ranked) > 1 else 100.0
    reqs = state["track_requirements"][top_track]["prerequisites"]
    policy_ok = all(state["grades"].get(p["course"], -1) >= p["min_score"] for p in reqs)
    clear = (gap >= CONFIDENCE_GAP_THRESHOLD) and policy_ok

    update = {"confidence_gap": gap, "policy_ok": policy_ok, "decision_clear": clear}
    msg = (f"Confidence gap={gap}pts, policy_ok={policy_ok} → "
           f"{'CLEAR, auto-finalizing' if clear else 'needs Advisor review'}")
    update.update(log_step(state, msg))
    return update


def route_confidence(state: State) -> str:
    if state.get("force_hitl_review"):
        return "hitl_node"
    return "finalize_node" if state["decision_clear"] else "hitl_node"