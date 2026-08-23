"""
ai_assistant_router.py
=======================
Student AI Assistant ("Nova") — the general, cross-topic chatbot on the
student dashboard, distinct from Teaching (teaching_router.py), which is
scoped to one enrolled course's material.

This is a NORMAL RAG CHATBOT, NOT a state graph — same architectural
family as Teaching:

    Student -> ask a question
        -> rag.rag_tool.search_policies(query)   (real retrieval + Self-RAG
           verification over Brightpeak's policy documents — academic
           integrity, hiring, general academy policy, etc.)
        -> Gemini, instructed to answer ONLY from the retrieved context
        -> {answer, sources}

No new retrieval or business logic is written here — search_policies and
GeminiClient already exist in phase-3 (rag/rag_tool.py, agent/client.py)
and are reused exactly as teaching_router.py reuses them for course
material.

Contract matches phase-4/frontend/student/ai-assistant/ai-assistant.js
exactly (that file already existed expecting this router):
    POST /ai/chat
    headers: X-User-Id, X-User-Role  (see core/auth.py)
    body:    { "message": "..." }
    200:     { "answer": "...", "sources": [...] }

If self-RAG verification fails or nothing relevant is retrieved, this
returns an honest "couldn't find enough information" answer with an
empty sources list — never a hallucinated answer dressed up as real.
If the LLM provider itself is unavailable (e.g. missing GEMINI_API_KEY),
this raises a clean 502 rather than faking a response.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth import require_role, CurrentUser

router = APIRouter(prefix="/ai", tags=["ai-assistant"])

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
    message: str


@router.post("/chat")
def chat(body: ChatRequest, user: CurrentUser = Depends(require_role("student"))):
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="message is required.")

    from rag.rag_tool import search_policies

    result = search_policies(query=body.message)

    if not result.get("prompt_for_llm"):
        # Either nothing relevant was retrieved, or Self-RAG verification
        # failed — report that honestly instead of guessing an answer.
        return {
            "answer": result.get("message")
            or "I couldn't find enough information to answer that reliably.",
            "sources": [],
        }

    try:
        answer = _get_gemini_client().generate(result["prompt_for_llm"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI Assistant is currently unavailable: {e}")

    sources = sorted({h.get("source") for h in result.get("hits", []) if h.get("source")})
    return {"answer": answer, "sources": sources}