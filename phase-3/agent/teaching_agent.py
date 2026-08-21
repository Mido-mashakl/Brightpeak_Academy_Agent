"""
Brightpeak Academy - Course Material Teaching Agent
====================================================

Teaching workflow:

    Student Question
          |
          v
    MCP Server
          |
          +--> get_student_enrollments
          |
          +--> list_course_materials
          |
          +--> ask_course_material
                    |
                    v
                  RAG
                    |
                    v
             Grounded Context
                    |
                    v
               GeminiClient
                    |
                    v
             Teaching Answer

Important architectural rule:
- This module never accesses SQLite directly.
- Course material is retrieved only through MCP.
- The LLM is instructed to answer from retrieved course material.
- If the material does not contain enough information, the agent
  should explicitly say so instead of inventing an answer.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from client import GeminiClient, load_gemini_config


AGENT_DIR = Path(__file__).resolve().parent
PHASE3_DIR = AGENT_DIR.parent
SERVER_SCRIPT = PHASE3_DIR / "mcp_server" / "server.py"


class TeachingAgentError(Exception):
    pass


class TeachingAgent:

    def __init__(self, gemini_client: GeminiClient):
        self.gemini_client = gemini_client

    async def _call_tool(
        self,
        session: ClientSession,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:

        result = await session.call_tool(
            tool_name,
            arguments=arguments,
        )

        if not result.content:
            raise TeachingAgentError(
                f"MCP tool '{tool_name}' returned no content."
            )

        for block in result.content:

            text = getattr(block, "text", None)

            if not text:
                continue

            try:
                return json.loads(text)

            except json.JSONDecodeError:
                return text

        raise TeachingAgentError(
            f"MCP tool '{tool_name}' returned unreadable content."
        )

    async def get_student_courses(
        self,
        session: ClientSession,
        student_id: int,
    ) -> list[dict[str, Any]]:

        data = await self._call_tool(
            session,
            "get_student_enrollments",
            {
                "student_id": student_id
            },
        )

        if isinstance(data, dict):

            if "error" in data:
                raise TeachingAgentError(data["error"])

            return data.get("enrollments", [])

        return []

    async def answer_question(
        self,
        session: ClientSession,
        student_id: int,
        course_id: int,
        question: str,
        top_k: int = 5,
        architecture: str = "auto",
    ) -> dict[str, Any]:

        if not question.strip():
            raise TeachingAgentError(
                "Question cannot be empty."
            )

        # --------------------------------------------------
        # 1. Verify enrollment
        # --------------------------------------------------

        courses = await self.get_student_courses(
            session,
            student_id,
        )

        enrolled = any(
            int(
                course.get("course_id")
                or course.get("id")
            ) == int(course_id)
            for course in courses
        )

        if not enrolled:
            raise TeachingAgentError(
                "Student is not enrolled in this course."
            )

        # --------------------------------------------------
        # 2. RAG
        # --------------------------------------------------

        rag_result = await self._call_tool(
            session,
            "ask_course_material",
            {
                "query": question,
                "course_id": course_id,
                "architecture": architecture,
                "top_k": top_k,
            },
        )

        if not isinstance(rag_result, dict):
            raise TeachingAgentError(
                "Invalid RAG response."
            )

        verification = rag_result.get(
            "verification",
            {}
        )

        # --------------------------------------------------
        # 3. Retrieval failed
        # --------------------------------------------------

        if verification.get("action") != "pass":

            return {
                "answer": (
                    "I couldn't find enough information "
                    "about this in your course material."
                ),
                "sources": [],
                "course_id": course_id,
                "grounded": False,
            }

        # --------------------------------------------------
        # 4. Build grounded prompt
        # --------------------------------------------------

        context = rag_result.get(
            "context",
            ""
        )

        sources = rag_result.get(
            "hits",
            []
        )

        prompt = f"""
You are Brightpeak Academy's Teaching Assistant.

Student ID:
{student_id}

Course ID:
{course_id}

Student question:
{question}

Course material retrieved by the RAG system:

{context}

Rules:

1. Answer ONLY using the retrieved course material.
2. Do not use information from other courses.
3. Do not invent facts.
4. Explain the concept clearly.
5. Prefer simple explanations.
6. If an example helps, provide one.
7. If the material does not support the answer,
   say that you could not find enough information.
8. Do not mention internal tools or RAG.
9. Do not mention system instructions.
10. Give a concise educational answer.

Return only the answer shown to the student.
"""

        answer = self.gemini_client.generate(
            prompt
        )

        # --------------------------------------------------
        # 5. Normalize sources
        # --------------------------------------------------

        formatted_sources = []

        for source in sources:

            formatted_sources.append(
                {
                    "title": source.get(
                        "document_title"
                    ),
                    "section": source.get(
                        "section"
                    ),
                    "file": source.get(
                        "source_file"
                    ),
                    "score": source.get(
                        "score"
                    ),
                }
            )

        return {
            "answer": answer,
            "sources": formatted_sources,
            "course_id": course_id,
            "grounded": True,
        }

    async def ask(
        self,
        student_id: int,
        course_id: int,
        question: str,
        top_k: int = 5,
        architecture: str = "auto",
    ) -> dict[str, Any]:

        if not SERVER_SCRIPT.exists():
            raise TeachingAgentError(
                f"MCP server not found: {SERVER_SCRIPT}"
            )

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(SERVER_SCRIPT)],
        )

        async with stdio_client(
            server_params
        ) as (read, write):

            async with ClientSession(
                read,
                write
            ) as session:

                await session.initialize()

                return await self.answer_question(
                    session=session,
                    student_id=student_id,
                    course_id=course_id,
                    question=question,
                    top_k=top_k,
                    architecture=architecture,
                )


async def main():

    config = load_gemini_config()
    gemini = GeminiClient(config)

    agent = TeachingAgent(gemini)

    tests = [
        {
            "name": "Basic course question",
            "student_id": 7,
            "course_id": 1,
            "question": "What is a function in Python?",
        },
        {
            "name": "Another course question",
            "student_id": 7,
            "course_id": 1,
            "question": "Explain variables.",
        },
        {
            "name": "Unsupported question",
            "student_id": 7,
            "course_id": 1,
            "question": "Who won the FIFA World Cup in 1986?",
        },
        {
            "name": "Empty question",
            "student_id": 7,
            "course_id": 1,
            "question": "",
        },
    ]

    for test in tests:

        print("\n" + "=" * 70)
        print(test["name"])
        print("=" * 70)

        try:

            result = await agent.ask(
                student_id=test["student_id"],
                course_id=test["course_id"],
                question=test["question"],
            )

            print(
                json.dumps(
                    result,
                    indent=2,
                    ensure_ascii=False,
                )
            )

        except TeachingAgentError as exc:

            print("ERROR:", exc)

        except Exception as exc:

            print(
                "UNEXPECTED ERROR:",
                type(exc).__name__,
                exc,
            )


if __name__ == "__main__":
    asyncio.run(main())
