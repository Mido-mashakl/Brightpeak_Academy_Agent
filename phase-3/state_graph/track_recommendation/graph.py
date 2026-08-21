"""
graph.py — The Track Recommendation state graph: wiring only.

All node logic lives in nodes_intake.py / nodes_evaluation.py /
nodes_hitl.py. This file just imports them, declares nodes + edges,
and compiles with the SQLite checkpointer from checkpointing.py.

    collect_student_data
          |
    check_missing_data --(missing)--> prepare_diagnostic -> await_diagnostic_response --\
          |(complete)                                                                      |
          v <-------------------------------------------------------------------------- --/
      rag_node <--------------------------------------------------------\
          |(doc invalid)-> open_ticket_node -> await_ticket_resolution -/
          |(all ok)                              [resumes RAG from checkpoint]
          v
      tot_node
          |
    confidence_policy_node --(clear)--> finalize_node --> END
          |(unclear / policy issue / forced review)
          v
      hitl_node --(approve / choose_other)--------------> finalize_node
          |(request_assessment)
          v
      prepare_targeted_assessment -> await_targeted_assessment_response
          --(student completes real Adaptive Assessment session)--> tot_node
          --(forced re-review)--> hitl_node

Every `interrupt()` is a REAL pause: the graph stops, state is
persisted by the checkpointer, and execution only continues when the
caller invokes again with `Command(resume=...)` on the same thread_id —
including after the process restarts, since the checkpointer is a SQLite
file on disk (see checkpointing.py).

Every pause that writes to the database first (diagnostic assessments,
tickets, targeted assessments) is now split into a `prepare_*` node
(the write, committed to the checkpoint) followed by an `await_*` node
(the interrupt()) — see nodes_intake.py / nodes_evaluation.py /
nodes_hitl.py docstrings for why the old single-node version could
duplicate rows on resume.
"""
from langgraph.graph import StateGraph, START, END

from state import State
from checkpointing import get_checkpointer
from nodes_intake import (
    collect_student_data,
    check_missing_data,
    route_missing_data,
    prepare_diagnostic,
    await_diagnostic_response,
)
from nodes_evaluation import (
    rag_node,
    route_rag,
    open_ticket_node,
    await_ticket_resolution,
    tot_node,
    confidence_policy_node,
    route_confidence,
)
from nodes_hitl import (
    hitl_node,
    route_hitl,
    prepare_targeted_assessment,
    await_targeted_assessment_response,
    finalize_node,
)


def build_graph():
    g = StateGraph(State)
    g.add_node("collect_student_data", collect_student_data)
    g.add_node("check_missing_data", check_missing_data)
    g.add_node("prepare_diagnostic", prepare_diagnostic)
    g.add_node("await_diagnostic_response", await_diagnostic_response)
    g.add_node("rag_node", rag_node)
    g.add_node("open_ticket_node", open_ticket_node)
    g.add_node("await_ticket_resolution", await_ticket_resolution)
    g.add_node("tot_node", tot_node)
    g.add_node("confidence_policy_node", confidence_policy_node)
    g.add_node("hitl_node", hitl_node)
    g.add_node("prepare_targeted_assessment", prepare_targeted_assessment)
    g.add_node("await_targeted_assessment_response", await_targeted_assessment_response)
    g.add_node("finalize_node", finalize_node)

    g.add_edge(START, "collect_student_data")
    g.add_edge("collect_student_data", "check_missing_data")
    g.add_conditional_edges("check_missing_data", route_missing_data,
                             {"prepare_diagnostic": "prepare_diagnostic", "rag_node": "rag_node"})
    g.add_edge("prepare_diagnostic", "await_diagnostic_response")
    g.add_edge("await_diagnostic_response", "rag_node")

    g.add_conditional_edges("rag_node", route_rag,
                             {"open_ticket_node": "open_ticket_node", "tot_node": "tot_node"})
    g.add_edge("open_ticket_node", "await_ticket_resolution")
    g.add_edge("await_ticket_resolution", "rag_node")

    # tot_node always flows to confidence_policy_node — no branch that
    # skips it (that's what caused the stale confidence_gap/policy_ok
    # bug; see nodes_hitl.hitl_node).
    g.add_edge("tot_node", "confidence_policy_node")

    g.add_conditional_edges("confidence_policy_node", route_confidence,
                             {"finalize_node": "finalize_node", "hitl_node": "hitl_node"})
    g.add_conditional_edges("hitl_node", route_hitl,
                             {"finalize_node": "finalize_node",
                              "prepare_targeted_assessment": "prepare_targeted_assessment"})
    g.add_edge("prepare_targeted_assessment", "await_targeted_assessment_response")
    g.add_edge("await_targeted_assessment_response", "tot_node")
    g.add_edge("finalize_node", END)

    return g.compile(checkpointer=get_checkpointer())