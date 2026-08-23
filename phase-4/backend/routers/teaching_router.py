"""
teaching_router.py
===================
Teaching is explicitly NOT a state graph (see phase-3/README.md: "doesn't
hold state across days, wait on an outside reply, or need a human to sign
off mid-run"). This is a plain, single-pass, course-scoped RAG endpoint:

    Student -> pick a course -> ask a question
        -> verify the student is actually enrolled in that course
        -> rag.rag_tool.search_course_material(query, course_id)   (real
           retrieval, already course_id-filtered so one course's material
           can never leak into another course's answer — see rag_tool.py's
           own docstring)
        -> Gemini, instructed to answer ONLY from the retrieved context
        -> {answer, sources}

Reuses phase-3's existing pieces directly (search_course_material,
GeminiClient) rather than going through the MCP stdio protocol
(agent/teaching_agent.py) — spawning an MCP subprocess per HTTP request
would work but is unnecessary process overhead when we're already
in-process with phase-3 (same trick core/graph_loader.py uses for the
five graphs).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import mcp_server.database as db
from core.auth import require_role, CurrentUser

router = APIRouter(prefix="/teaching", tags=["teaching"])

_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        import sys
        from pathlib import Path
        agent_dir = Path(__file__).resolve().parents[3] / "phase-3" / "agent"
        if str(agent_dir) not in sys.path:
            sys.path.insert(0, str(agent_dir))
        from client import GeminiClient, load_gemini_config  # phase-3/agent/client.py
        _gemini_client = GeminiClient(load_gemini_config())
    return _gemini_client


class ChatRequest(BaseModel):
    course_id: int
    question: str


@router.post("/chat")
def chat(body: ChatRequest, user: CurrentUser = Depends(require_role("student"))):
    course = db.get_course(body.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")

    enrollment = db.get_enrollments(user.user_id, body.course_id)
    if not enrollment:
        raise HTTPException(
            status_code=403,
            detail="You are not enrolled in this course, so its material can't be searched for you.",
        )

    from rag.rag_tool import search_course_material

    result = search_course_material(query=body.question, course_id=body.course_id)
    hits = result.get("hits") or []
    if not hits or not result.get("context"):
        return {
            "answer": result.get("message")
            or "I couldn't find enough information in this course's material to answer that.",
            "sources": [],
            "grounded": False,
        }

    prompt = (
        "You are Brightpeak Academy's course-teaching assistant for "
        f"'{course['title']}'. Answer the student's question using ONLY the "
        "course material below. If the material doesn't fully answer the "
        "question, say so explicitly instead of guessing.\n\n"
        f"COURSE MATERIAL:\n{result['context']}\n\n"
        f"STUDENT QUESTION: {body.question}\n\nANSWER:"
    )

    try:
        answer = _get_gemini_client().generate(prompt)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Teaching assistant is temporarily unavailable: {e}")

    sources = sorted({h.get("source") for h in hits if h.get("source")})
    return {"answer": answer, "sources": sources, "grounded": True}


@router.get("/courses")
def my_courses(user: CurrentUser = Depends(require_role("student"))):
    """Populates the course picker on the Teaching page."""
    enrollments = db.get_enrollments(user.user_id)
    out = []
    for e in enrollments:
        c = db.get_course(e["course_id"])
        if c:
            out.append({"course_id": c["course_id"], "title": c["title"]})
    return out