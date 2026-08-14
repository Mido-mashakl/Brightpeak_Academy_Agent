

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI


class PlanningLLMError(Exception):
    """Raised when the planning LLM provider cannot be constructed."""


def get_planning_llm(
    *,
    model: str | None = None,
    temperature: float | None = None,
    env_path: str | None = None,
) -> ChatGoogleGenerativeAI:
    """Build the langchain-compatible chat model used by every planning
    algorithm (Plan-and-Solve, Tree of Thoughts, LATS).

    This is the ONLY place the provider is constructed; router.py and
    the algorithm modules just receive the resulting object, so
    swapping providers again later means editing one function, not
    every call site.
    """
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise PlanningLLMError(
            "GEMINI_API_KEY is missing. Add it to your .env file, e.g.:\n"
            "  GEMINI_API_KEY=your-key-here"
        )

    resolved_model = model or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    resolved_temperature = (
        temperature
        if temperature is not None
        else float(os.getenv("GEMINI_TEMPERATURE", "0.2"))
    )

    return ChatGoogleGenerativeAI(
        model=resolved_model,
        google_api_key=api_key,
        temperature=resolved_temperature,
    )