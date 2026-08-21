from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.teaching_agent import (
    TeachingAgent,
    TeachingAgentError,
)

from agent.client import (
    GeminiClient,
    load_gemini_config,
)


router = APIRouter(
    prefix="/teaching",
    tags=["Teaching"],
)


class TeachingRequest(BaseModel):

    student_id: int
    course_id: int
    question: str

    top_k: int = 5

    architecture: str = "auto"


def get_agent() -> TeachingAgent:

    config = load_gemini_config()

    gemini = GeminiClient(config)

    return TeachingAgent(gemini)


@router.post("/ask")
async def ask_teaching(
    request: TeachingRequest,
):

    try:

        agent = get_agent()

        result = await agent.ask(
            student_id=request.student_id,
            course_id=request.course_id,
            question=request.question,
            top_k=request.top_k,
            architecture=request.architecture,
        )

        return result

    except TeachingAgentError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail="Teaching service failed.",
        )