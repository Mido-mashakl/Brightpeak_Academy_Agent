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
PHASE2_DIR = AGENT_DIR.parent
SERVER_SCRIPT = PHASE2_DIR / "mcp_server" / "server.py"


class TeachingAgentError(Exception):
    """Raised when the teaching agent cannot complete a request."""


class TeachingAgent:
    """
    Course-material teaching assistant.

    The agent uses MCP as the only interface to Academy data and
    uses Gemini only for generating the final natural-language answer.
    """

    def __init__(self, gemini_client: GeminiClient):
        self.gemini_client = gemini_client

    async def _get_tool_result(
        self,
        session: ClientSession,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        """
        Call an MCP tool and convert its first text block into Python data.
        """
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
            f"MCP tool '{tool_name}' returned no readable text."
        )

    async def get_student_courses(
        self,
        session: ClientSession,
        student_id: int,
    ) -> list[dict[str, Any]]:
        """
        Retrieve the courses associated with a student.

        The exact MCP response shape can vary, so this method normalizes
        the common response formats.
        """
        data = await self._get_tool_result(
            session,
            "get_student_enrollments",
            {
                "student_id": student_id,
            },
        )

        if isinstance(data, dict):
            if "error" in data:
                raise TeachingAgentError(data["error"])

            for key in (
                "enrollments",
                "courses",
                "data",
                "results",
            ):
                value = data.get(key)

                if isinstance(value, list):
                    return value

            return []

        if isinstance(data, list):
            return data

        return []

    async def list_materials(
        self,
        session: ClientSession,
        course_id: int,
    ) -> list[dict[str, Any]]:
        """
        Return the available study materials for a course.
        """
        data = await self._get_tool_result(
            session,
            "list_course_materials",
            {
                "course_id": course_id,
            },
        )

        if isinstance(data, dict):
            if "error" in data:
                raise TeachingAgentError(data["error"])

            materials = data.get("materials", [])

            if isinstance(materials, list):
                return materials

        return []

    async def retrieve_course_context(
        self,
        session: ClientSession,
        question: str,
        course_id: int,
        top_k: int = 5,
        architecture: str = "auto",
    ) -> dict[str, Any]:
        """
        Retrieve grounded course material through the MCP RAG tool.
        """
        if not question.strip():
            raise TeachingAgentError(
                "The student's question must not be empty."
            )

        data = await self._get_tool_result(
            session,
            "ask_course_material",
            {
                "query": question,
                "course_id": course_id,
                "architecture": architecture,
                "top_k": top_k,
            },
        )

        if isinstance(data, dict) and "error" in data:
            raise TeachingAgentError(data["error"])

        if not isinstance(data, dict):
            return {
                "answer": str(data),
                "contexts": [],
            }

        return data

    def build_teaching_prompt(
        self,
        question: str,
        course_id: int,
        rag_result: dict[str, Any],
    ) -> str:
        """
        Build the final grounded teaching prompt.

        The retrieved RAG result is treated as the authoritative
        course-material context.
        """

        serialized_context = json.dumps(
            rag_result,
            indent=2,
            ensure_ascii=False,
        )

        return f"""
You are the Brightpeak Academy Teaching Assistant.

You are helping a student understand material from ONE specific course.

Course ID:
{course_id}

Student question:
{question}

Retrieved course-material context:
{serialized_context}

Teaching rules:

1. Answer the student's question using the retrieved course material.
2. Do not invent information that is not supported by the retrieved
   course material.
3. Do not use knowledge from another course.
4. Explain the concept clearly and in a student-friendly way.
5. Prefer a simple explanation before giving technical details.
6. Give an example only when it is supported by the retrieved material
   or can be clearly presented as a simple explanation of the same
   retrieved concept.
7. If the retrieved material does not contain enough information to
   answer confidently, explicitly say:

   "I couldn't find enough information about this in your course
   material."

8. When source information is available, mention the relevant material
   or source at the end of the answer.
9. Never claim that something is present in the course material unless
   the retrieved context supports it.

Return only the answer that should be shown to the student.
""".strip()

    async def answer_question(
        self,
        session: ClientSession,
        question: str,
        course_id: int,
        top_k: int = 5,
        architecture: str = "auto",
    ) -> str:
        """
        Complete course-material teaching workflow.
        """

        rag_result = await self.retrieve_course_context(
            session=session,
            question=question,
            course_id=course_id,
            top_k=top_k,
            architecture=architecture,
        )

        prompt = self.build_teaching_prompt(
            question=question,
            course_id=course_id,
            rag_result=rag_result,
        )

        return self.gemini_client.generate(prompt)

    async def run(
        self,
        student_id: int,
        question: str,
        course_id: int | None = None,
        top_k: int = 5,
        architecture: str = "auto",
    ) -> str:
        """
        Run the teaching assistant.

        If course_id is supplied, use it directly.

        If course_id is omitted, retrieve the student's enrollments.
        If exactly one course is available, use that course.

        If multiple courses exist, the agent asks the caller to specify
        the course rather than guessing.
        """

        if not SERVER_SCRIPT.exists():
            raise TeachingAgentError(
                f"MCP server not found at: {SERVER_SCRIPT}"
            )

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(SERVER_SCRIPT)],
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:

                await session.initialize()

                selected_course_id = course_id

                if selected_course_id is None:
                    courses = await self.get_student_courses(
                        session,
                        student_id,
                    )

                    if not courses:
                        raise TeachingAgentError(
                            f"No courses found for student {student_id}."
                        )

                    if len(courses) > 1:
                        course_lines = []

                        for course in courses:
                            cid = (
                                course.get("course_id")
                                or course.get("id")
                            )

                            title = (
                                course.get("course_name")
                                or course.get("title")
                                or course.get("name")
                                or f"Course {cid}"
                            )

                            course_lines.append(
                                f"- {cid}: {title}"
                            )

                        raise TeachingAgentError(
                            "The student is enrolled in multiple courses. "
                            "Please specify course_id.\n"
                            + "\n".join(course_lines)
                        )

                    selected_course_id = (
                        courses[0].get("course_id")
                        or courses[0].get("id")
                    )

                if selected_course_id is None:
                    raise TeachingAgentError(
                        "Could not determine the student's course."
                    )

                return await self.answer_question(
                    session=session,
                    question=question,
                    course_id=int(selected_course_id),
                    top_k=top_k,
                    architecture=architecture,
                )


async def main() -> None:
    """
    Small CLI example.
    """

    gemini_config = load_gemini_config()
    gemini_client = GeminiClient(gemini_config)

    agent = TeachingAgent(gemini_client)

    answer = await agent.run(
        student_id=7,
        course_id=1,
        question="What are Python functions?",
        top_k=5,
        architecture="auto",
    )

    print("\n" + "=" * 70)
    print("BRIGHTPEAK TEACHING ASSISTANT")
    print("=" * 70)
    print(answer)
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())