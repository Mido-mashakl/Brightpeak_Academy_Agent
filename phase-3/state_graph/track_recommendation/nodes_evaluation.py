"""
nodes_evaluation.py — RAG retrieval (+ its Ticket failure path), ToT
comparison, and the confidence/policy check that decides whether we
can auto-finalize or need the Advisor.

      rag_node <--------------------------------------------\
          |(doc invalid)-> open_ticket_node -> await_ticket_resolution -/
          |(all ok)                              [resumes RAG from checkpoint]
          v
      tot_node
          |
    confidence_policy_node --(clear)--> finalize_node
          |(unclear / policy issue / forced review)
          v
      hitl_node   (defined in nodes_hitl.py)

FIXED: `import rag` / `import tot` pointed at nothing — no such modules
existed in this package (and the real top-level `rag/` package + Phase-2
`tree_of_thoughts()` don't match this graph's contract — see
rag_adapter.py / tot_adapter.py docstrings for why). Now imports the two
real adapter modules.

FIXED — CRITICAL BUG #1 (side effects before interrupt()), same class of
bug as awaiting_diagnostic in nodes_intake.py: `ticket_node` used to call
db.open_ticket() and then interrupt() in the same node body, guarded by
`open_ticket_id` — but that guard was only returned AFTER interrupt(),
so it was never actually committed before the pause. On resume the node
re-ran from the top, saw open_ticket_id still None, and opened a SECOND
ticket for the same failure.

Fix: split into open_ticket_node (writes the Tickets row, returns
open_ticket_id — committed before the pause) and
await_ticket_resolution (interrupt(), then resolves the ticket and
resumes the same rag_node loop via rag_pending_tracks).
"""
from langgraph.types import interrupt

import db
import rag_adapter as rag
import tot_adapter as tot
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
    return "open_ticket_node" if state.get("rag_failed_track") else "tot_node"


def open_ticket_node(state: State) -> dict:
    """DB-write half of the ticket pause. Idempotent: open_ticket_id is
    read from (committed) state first — on resume after interrupt() this
    node body doesn't even run again unless the graph re-enters it
    through a fresh RAG failure, and even then a track that already has
    an open ticket from this pass is not re-ticketed."""
    ticket_id = state.get("open_ticket_id")
    if ticket_id is not None:
        return {}
    track = state["rag_failed_track"]
    ticket_id = db.open_ticket(
        source_id=state["recommendation_id"],
        thread_id=state["thread_id"],
        failure_type="schema_validation_failed",
        details=f"Track document for '{track}' is missing required fields.",
    )
    db.update_recommendation(state["recommendation_id"], status="failed")
    update = {"open_ticket_id": ticket_id}
    update.update(log_step(state, f"🎫 Ticket #{ticket_id} opened for admin: '{track}' document incomplete."))
    return update


def await_ticket_resolution(state: State) -> dict:
    """TRUE waiting state: pauses until an admin fixes the broken track
    document. Resuming here continues the SAME rag_node loop (via
    rag_pending_tracks), not a restart of the whole workflow."""
    track = state["rag_failed_track"]
    ticket_id = state["open_ticket_id"]

    print(f"\n  ⏸  PAUSED — await_ticket_resolution. 🎫 Ticket #{ticket_id} open for admin: "
          f"'{track}' document incomplete.")
    interrupt({
        "type": "ticket_needs_admin",
        "ticket_id": ticket_id,
        "track": track,
        "message": f"Track document '{track}' failed validation. Admin must fix it.",
    })
    # resume value: {"fixed": True} — the admin's actual fix (re-uploading
    # a corrected document) happens outside this graph; what matters here
    # is that the ticket is now resolvable and RAG can be retried.
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
    """Always flows straight into confidence_policy_node — no branch that
    skips it (that's what caused the stale confidence_gap/policy_ok bug;
    see nodes_hitl.hitl_node). confidence_policy_node recomputes gap/
    policy on the new `ranked` first, and route_confidence checks
    force_hitl_review to decide whether to force a trip back to the
    Advisor regardless of how clear the new numbers look."""
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