"""
Brightpeak Academy - Stage 7
============================

Course Material Teaching Assistant

Demonstrates:

    Student
      ↓
    TeachingAgent
      ↓
    MCP
      ↓
    Course Material RAG
      ↓
    Gemini
      ↓
    Grounded Teaching Answer
"""

from __future__ import annotations

import asyncio

from client import GeminiClient, load_gemini_config
from teaching_agent import TeachingAgent


async def run_stage7() -> None:
    print("=" * 70)
    print("STAGE 7 — COURSE MATERIAL TEACHING ASSISTANT")
    print("=" * 70)

    # ---------------------------------------------------------------
    # 1. Gemini
    # ---------------------------------------------------------------
    print("\n[1] Initializing Gemini client...")

    config = load_gemini_config()
    gemini_client = GeminiClient(config)

    print("    Gemini client ready.")

    # ---------------------------------------------------------------
    # 2. Teaching Agent
    # ---------------------------------------------------------------
    print("\n[2] Initializing Teaching Agent...")

    agent = TeachingAgent(gemini_client)

    print("    Teaching agent ready.")

    # ---------------------------------------------------------------
    # 3. Student question
    # ---------------------------------------------------------------
    student_id = 7
    course_id = 1

    question = (
        "Can you explain Python functions in a simple way "
        "and give me an example?"
    )

    print("\n[3] Student:")
    print(f"    student_id = {student_id}")
    print(f"    course_id  = {course_id}")
    print(f"    question   = {question}")

    # ---------------------------------------------------------------
    # 4. Course-material RAG + Gemini
    # ---------------------------------------------------------------
    print("\n[4] Asking the course-material Teaching Assistant...")

    try:
        answer = await agent.run(
            student_id=student_id,
            course_id=course_id,
            question=question,
            top_k=5,
            architecture="auto",
        )

    except Exception as exc:
        print("\n[ERROR]")
        print(exc)
        return

    # ---------------------------------------------------------------
    # 5. Final answer
    # ---------------------------------------------------------------
    print("\n[5] Teaching Assistant Answer:")
    print("-" * 70)
    print(answer)
    print("-" * 70)

    print("\nStage 7 finished successfully.")


if __name__ == "__main__":
    asyncio.run(run_stage7())