"""
graph.py
========
Student Advisor: Certificate & Scholarship Eligibility.

One graph handles both request types (state.request_type = "certificate" |
"scholarship") — they differ only in which policy gets retrieved and which
table the final decision is written to (see data.py); the flow itself
(load profile -> retrieve policy -> decompose into requirements -> evaluate ->
loop on missing info / escalate on low confidence -> recommend -> finalize)
is identical, so one StateGraph avoids duplicating that logic.

    START
      |
      v
  load_profile
      |
      v
  retrieve_policy  (RAG)
      |
      v
  decompose_requirements  (Task Decomposition)  -- only runs once per request
      |
      v
  evaluate_eligibility  <---------------------------------------+
      |                                                          |
      +-- missing_info non-empty       --> wait_for_student  ----+  (loop: new
      |                                     (HITL: student)         info -> re-evaluate)
      +-- confidence < REVIEW_THRESHOLD --> human_review       ----+  (loop: admin
      |                                     (HITL: admin)            asks for more -> back
      |                                                              through wait_for_student)
      +-- else                          --> generate_recommendation
                                               |
                                               v
                                           finalize
                                               |
                                               v
                                             END

Genuine cycle: evaluate_eligibility <-> wait_for_student is a real loop bounded
by MAX_EVALUATION_ITERATIONS (state.py), not a single retry — a request can
legitimately go back and forth several times before it has enough information
to decide.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from . import data, llm
from .checkpointing import get_checkpointer
from .hitl import human_review_node, wait_for_student_node
from .state import MAX_EVALUATION_ITERATIONS, RequirementCheck, StudentAdvisorState
from .tickets import run_student_advisor as _run_with_ticket_on_failure

REVIEW_CONFIDENCE_THRESHOLD = 0.6


# -----------------------------------------------------------------------
# Nodes
# -----------------------------------------------------------------------

def load_profile(state: StudentAdvisorState) -> dict:
    profile = data.load_student_profile(state.student_id, state.course_id)
    updates: dict = {"student_profile": profile}
    if state.request_id is None:
        request_id = data.create_request_row(
            state.request_type, state.student_id, state.course_id, state.purpose
        )
        updates["request_id"] = request_id
        updates["thread_id"] = f"student-advisor-{request_id}"
    return updates


def retrieve_policy(state: StudentAdvisorState) -> dict:
    query = state.purpose or f"{state.request_type} eligibility requirements"
    result = data.retrieve_policy(state.request_type, query)
    return {
        "policy_text": result.get("answer") or result.get("text", ""),
        "policy_source": result.get("source"),
    }


def decompose_requirements(state: StudentAdvisorState) -> dict:
    # Only decompose once per request — re-entering evaluate_eligibility after
    # new info shouldn't re-derive the checklist from scratch.
    if state.requirement_checks:
        return {}
    requirements = llm.decompose_policy_into_requirements(
        state.policy_text or "", state.request_type
    )
    return {"requirement_checks": [RequirementCheck(requirement=r) for r in requirements]}


def evaluate_eligibility(state: StudentAdvisorState) -> dict:
    checks: list[RequirementCheck] = []
    missing: list[str] = []
    satisfied_count = 0

    for check in state.requirement_checks:
        result = llm.evaluate_requirement(
            check.requirement, state.student_profile or {}, state.student_response
        )
        updated = RequirementCheck(
            requirement=check.requirement,
            satisfied=result.get("satisfied"),
            evidence=result.get("evidence"),
            note=result.get("note"),
        )
        checks.append(updated)
        if updated.satisfied is None:
            missing.append(updated.note or updated.requirement)
        elif updated.satisfied:
            satisfied_count += 1

    confidence = satisfied_count / len(checks) if checks else 0.0
    any_failed = any(c.satisfied is False for c in checks)

    if any_failed:
        eligibility_status = "ineligible"
    elif missing:
        eligibility_status = "pending"
    else:
        eligibility_status = "eligible"

    return {
        # Replaces this iteration's checks; requirement_checks uses an `add`
        # reducer so we return only the diff-worthy fresh evaluation, keyed by
        # requirement text on the reading side (platform de-dupes by taking
        # the latest entry per requirement when displaying).
        "requirement_checks": checks,
        "missing_info": missing,
        "confidence": confidence,
        "eligibility_status": eligibility_status,
        "student_response": None,  # consumed
        "iteration_count": state.iteration_count + 1,
    }


def generate_recommendation(state: StudentAdvisorState) -> dict:
    summary = {
        "request_type": state.request_type,
        "eligibility_status": state.eligibility_status,
        "requirement_checks": [c.model_dump() for c in state.requirement_checks],
        "confidence": state.confidence,
    }
    recommendation = llm.generate_recommendation(summary)
    return {"recommendation": recommendation}


def finalize(state: StudentAdvisorState) -> dict:
    decided_by = state.decisions[-1].decided_by if state.decisions else "agent"
    data.finalize_request_row(
        state.request_type,
        state.request_id,
        state.eligibility_status,
        state.recommendation,
        decided_by,
    )
    return {"status": "completed"}


# -----------------------------------------------------------------------
# Routing
# -----------------------------------------------------------------------

def route_after_evaluation(state: StudentAdvisorState) -> str:
    if state.iteration_count >= MAX_EVALUATION_ITERATIONS:
        # Cap hit: force a human decision rather than looping forever.
        return "human_review"
    if state.missing_info:
        return "wait_for_student"
    if (state.confidence or 0.0) < REVIEW_CONFIDENCE_THRESHOLD:
        return "human_review"
    return "generate_recommendation"


def route_after_human_review(state: StudentAdvisorState) -> str:
    if state.eligibility_status == "needs_review":
        return "wait_for_student"
    return "generate_recommendation"


# -----------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------

def build_graph():
    builder = StateGraph(StudentAdvisorState)

    builder.add_node("load_profile", load_profile)
    builder.add_node("retrieve_policy", retrieve_policy)
    builder.add_node("decompose_requirements", decompose_requirements)
    builder.add_node("evaluate_eligibility", evaluate_eligibility)
    builder.add_node("wait_for_student", wait_for_student_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("generate_recommendation", generate_recommendation)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "load_profile")
    builder.add_edge("load_profile", "retrieve_policy")
    builder.add_edge("retrieve_policy", "decompose_requirements")
    builder.add_edge("decompose_requirements", "evaluate_eligibility")

    builder.add_conditional_edges(
        "evaluate_eligibility",
        route_after_evaluation,
        {
            "wait_for_student": "wait_for_student",
            "human_review": "human_review",
            "generate_recommendation": "generate_recommendation",
        },
    )
    # Genuine cycle: new student info -> re-evaluate.
    builder.add_edge("wait_for_student", "evaluate_eligibility")

    builder.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "wait_for_student": "wait_for_student",
            "generate_recommendation": "generate_recommendation",
        },
    )

    builder.add_edge("generate_recommendation", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=get_checkpointer())


# Module-level compiled graph, so the platform (admin + user surface) and
# tickets.resume_after_ticket_resolution() share one instance / one
# checkpointer connection instead of recompiling per request.
student_advisor_graph = build_graph()


def start_request(
    student_id: int,
    request_type: str,
    course_id: int | None = None,
    purpose: str | None = None,
) -> dict:
    """Entry point used by the platform's user surface."""
    import uuid

    temp_thread_id = f"student-advisor-new-{uuid.uuid4()}"
    initial_state = StudentAdvisorState(
        student_id=student_id, request_type=request_type, course_id=course_id, purpose=purpose
    )
    result = _run_with_ticket_on_failure(
        student_advisor_graph, initial_state, temp_thread_id, request_id=None
    )
    return result