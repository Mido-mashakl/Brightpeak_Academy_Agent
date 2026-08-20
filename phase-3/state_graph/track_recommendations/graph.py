"""
graph.py — The Track Recommendation state graph: wiring only.

All node logic lives in nodes_intake.py / nodes_evaluation.py /
nodes_hitl.py. This file just imports them, declares nodes + edges,
and compiles with the SQLite checkpointer from checkpointing.py.

    collect_student_data
          |
    check_missing_data --(missing)--> awaiting_diagnostic --(student responds)--\
          |(complete)                                                            |
          v <-----------------------------------------------------------------/
      rag_node <--------------------------------------\
          |(doc invalid)-> ticket_node --(admin fixes)-/   [resumes from checkpoint]
          |(all ok)
          v
      tot_node
          |
    confidence_policy_node --(clear)--> finalize_node --> END
          |(unclear / policy issue / forced review)
          v
      hitl_node --(approve / choose_other)--------------> finalize_node
          |(request_assessment)
          v
      targeted_assessment_node --(student responds)--> tot_node --(forced re-review)--> hitl_node

Every `interrupt()` is a REAL pause: the graph stops, state is
persisted by the checkpointer, and execution only continues when the
caller invokes again with `Command(resume=...)` on the same thread_id —
including after the process restarts, since the checkpointer is a SQLite
file on disk (see checkpointing.py).
"""
from langgraph.graph import StateGraph, START, END

from state import State
from checkpointing import get_checkpointer
from nodes_intake import (
    collect_student_data,
    check_missing_data,
    route_missing_data,
    awaiting_diagnostic,
)
from nodes_evaluation import (
    rag_node,
    route_rag,
    ticket_node,
    tot_node,
    confidence_policy_node,
    route_confidence,
)
from nodes_hitl import (
    hitl_node,
    route_hitl,
    targeted_assessment_node,
    finalize_node,
)


def build_graph():
    g = StateGraph(State)
    g.add_node("collect_student_data", collect_student_data)
    g.add_node("check_missing_data", check_missing_data)
    g.add_node("awaiting_diagnostic", awaiting_diagnostic)
    g.add_node("rag_node", rag_node)
    g.add_node("ticket_node", ticket_node)
    g.add_node("tot_node", tot_node)
    g.add_node("confidence_policy_node", confidence_policy_node)
    g.add_node("hitl_node", hitl_node)
    g.add_node("targeted_assessment_node", targeted_assessment_node)
    g.add_node("finalize_node", finalize_node)

    g.add_edge(START, "collect_student_data")
    g.add_edge("collect_student_data", "check_missing_data")
    g.add_conditional_edges("check_missing_data", route_missing_data,
                             {"awaiting_diagnostic": "awaiting_diagnostic", "rag_node": "rag_node"})
    g.add_edge("awaiting_diagnostic", "rag_node")

    g.add_conditional_edges("rag_node", route_rag,
                             {"ticket_node": "ticket_node", "tot_node": "tot_node"})
    g.add_edge("ticket_node", "rag_node")

    # tot_node now always flows to confidence_policy_node — no more
    # route_after_tot branch that used to skip it (that's what caused
    # the stale confidence_gap/policy_ok bug; see nodes_hitl.hitl_node).
    g.add_edge("tot_node", "confidence_policy_node")

    g.add_conditional_edges("confidence_policy_node", route_confidence,
                             {"finalize_node": "finalize_node", "hitl_node": "hitl_node"})
    g.add_conditional_edges("hitl_node", route_hitl,
                             {"finalize_node": "finalize_node",
                              "targeted_assessment_node": "targeted_assessment_node"})
    g.add_edge("targeted_assessment_node", "tot_node")
    g.add_edge("finalize_node", END)

    return g.compile(checkpointer=get_checkpointer())