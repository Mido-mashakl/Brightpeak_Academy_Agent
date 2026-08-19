"""
Brightpeak Academy - MCP Agent (Final Demo)
=============================================

One repeatable, fixed-input walkthrough of every protocol concern,
in the order required by the project README:

  1. Handshake
  2. Tool Call
  3. Notification
  4. Resource
  5. Prompt
  6. Elicitation
  7. Progress Tracking
  8.Course Material Teaching / RAG
  9. Final Result

This file does not introduce anything new -- it just wires together
what was already proven working in agent_stage1.py through
agent_stage6.py, in one place, so the whole system can be shown to a
grader without jumping between six separate scripts.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import (
    CreateMessageResult,
    ElicitResult,
    TextContent,
    ToolListChangedNotification,
)

AGENT_DIR = Path(__file__).resolve().parent
PHASE2_DIR = AGENT_DIR.parent
SERVER_SCRIPT = PHASE2_DIR / "mcp_server" / "server.py"

# ---------------------------------------------------------------------
# Gemini setup
# ---------------------------------------------------------------------

# Try both common project locations.
ENV_CANDIDATES = [
    PHASE2_DIR / ".env",
    AGENT_DIR / ".env",
]

for env_file in ENV_CANDIDATES:
    if env_file.exists():
        load_dotenv(env_file)
        break

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-flash-latest",
)

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing.\n"
        "Create a .env file in Phase-2 or Phase-2/agent with:\n\n"
        "GEMINI_API_KEY=your_api_key_here\n"
    )

gemini_client = genai.Client(
    api_key=GEMINI_API_KEY
)


def print_tool_result(result) -> None:
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            try:
                data = json.loads(text)
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                print(text)


def find_tool_name(tools, keyword: str) -> str:
    for t in tools:
        if keyword in t.name:
            return t.name
    raise RuntimeError(f"No tool found matching '{keyword}'")


# ---------------------------------------------------------------------
# === CONCERN: Notifications ===
# ---------------------------------------------------------------------
async def message_handler(message) -> None:
    root = getattr(message, "root", message)
    if isinstance(root, ToolListChangedNotification):
        print("\n>>> notifications/tools/list_changed RECEIVED <<<")


# ---------------------------------------------------------------------
# === CONCERN: Elicitation ===
# ---------------------------------------------------------------------
async def elicitation_callback(context, params):
    print("\n" + "!" * 60)
    print("HUMAN CONFIRMATION REQUIRED (elicitation/create)")
    print("!" * 60)
    print(params.message)

    schema_props = (params.requestedSchema or {}).get("properties", {})
    answers = {}
    for field_name, field_schema in schema_props.items():
        description = field_schema.get("description", field_name)
        field_type = field_schema.get("type", "string")
        if field_type == "boolean":
            raw = input(f"  {description} [y/N]: ").strip().lower()
            answers[field_name] = raw in ("y", "yes")
        else:
            raw = input(f"  {description} (optional, press Enter to skip): ").strip()
            answers[field_name] = raw or None

    if not answers.get("confirmed"):
        print("-> Declined. No change will be made.\n")
        return ElicitResult(action="decline")
    print("-> Confirmed by human operator.\n")
    return ElicitResult(action="accept", content=answers)


# ---------------------------------------------------------------------
# === CONCERN: Sampling ===
# ---------------------------------------------------------------------
async def sampling_callback(context, params):
    prompt_parts = []
    for msg in params.messages:
        text = getattr(msg.content, "text", str(msg.content))
        prompt_parts.append(text)
    prompt = "\n".join(prompt_parts)

    print("\n" + "-" * 60)
    print("SAMPLING REQUEST FROM SERVER (sampling/createMessage)")
    print("Generating the narrative using the AGENT's own Gemini client...")
    print("-" * 60)

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    narrative = response.text or "(no text generated)"
    print("Generated narrative:")
    print(narrative)

    return CreateMessageResult(
        role="assistant",
        content=TextContent(type="text", text=narrative),
        model=GEMINI_MODEL,
        stopReason="endTurn",
    )


# ---------------------------------------------------------------------
# === CONCERN: Progress tracking ===
# ---------------------------------------------------------------------
async def progress_callback(progress, total, message) -> None:
    if total:
        pct = int((progress / total) * 100)
        print(f"    [progress] {pct:3d}% - {message or ''}")
    else:
        print(f"    [progress] {progress} - {message or ''}")


async def main() -> None:
    if not SERVER_SCRIPT.exists():
        raise FileNotFoundError(f"Server not found at: {SERVER_SCRIPT}")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(
            read,
            write,
            message_handler=message_handler,
            elicitation_callback=elicitation_callback,
            sampling_callback=sampling_callback,
        ) as session:

            # ---- 1. Handshake -----------------------------------------
            print("=" * 70)
            print("STEP 1 — Handshake (initialize)")
            print("=" * 70)
            init_result = await session.initialize()
            print(f"Server: {init_result.serverInfo.name} (protocol {init_result.protocolVersion})")
            caps = init_result.capabilities
            print(f"resources declared: {caps.resources is not None}")
            print(f"prompts declared:   {caps.prompts is not None}")

            # ---- 2. Tool Call (read-only, front-desk / guest role) -----
            print("\n" + "=" * 70)
            print("STEP 2 — Tool Call (read-only, no authentication)")
            print("=" * 70)
            result = await session.call_tool(
                "get_student_profile", arguments={"student_id": 1}
            )
            print_tool_result(result)

            # ---- 3. Notification (role escalation) ---------------------
            print("\n" + "=" * 70)
            print("STEP 3 — Notification (authenticate_staff -> tools/list_changed)")
            print("=" * 70)
            auth_result = await session.call_tool(
                "authenticate_staff",
                arguments={"role": "instructor", "instructor_id": 1},
            )
            print_tool_result(auth_result)
            await asyncio.sleep(0.3)

            # ---- 4. Resource --------------------------------------------
            print("\n" + "=" * 70)
            print("STEP 4 — Resource (resources/read, not a tool)")
            print("=" * 70)
            policy_result = await session.read_resource("policy://all")
            for content in policy_result.contents:
                text = getattr(content, "text", None)
                if text:
                    print(text[:400] + "...")

            # ---- 5. Prompt ------------------------------------------------
            print("\n" + "=" * 70)
            print("STEP 5 — Prompt (prompts/get, a reusable template)")
            print("=" * 70)
            prompt_result = await session.get_prompt(
                "draft_attendance_warning",
                arguments={"student_id": "7", "course_id": "1"},
            )
            print(prompt_result.messages[0].content.text)

            # ---- 6. Elicitation --------------------------------------------
            print("\n" + "=" * 70)
            print("STEP 6 — Elicitation (dropping enrollment requires human confirmation)")
            print("=" * 70)

            tools = (await session.list_tools()).tools
            enrollment_tool = find_tool_name(tools, "change_enrollment_status")

            result = await session.call_tool(
            enrollment_tool,
            arguments={
               "student_id": 2,
               "course_id": 1,
               "status": "dropped",
            },
            )

            print_tool_result(result)
            # ---- 7. Progress Tracking -----------------------------------
            print("\n" + "=" * 70)
            print("STEP 7 — Progress Tracking (generate_course_report)")
            print("=" * 70)
            result = await session.call_tool(
                "generate_course_report",
                arguments={"course_id": 1},
                progress_callback=progress_callback,
            )
            # ---------------------------------------------------------
            # STEP 8 — NEW
            # Course Material Teaching
            # ---------------------------------------------------------

            print("\n" + "=" * 70)
            print(
                "STEP 8 — Course Material Teaching Assistant"
            )
            print("=" * 70)

            student_id = 7
            course_id = 1

            question = (
                "Can you explain Python functions "
                "in a simple way?"
            )

            print(
                f"Student ID : {student_id}"
            )

            print(
                f"Course ID  : {course_id}"
            )

            print(
                f"Question   : {question}"
            )

            print(
                "\nCalling ask_course_material..."
            )

            teaching_result = await session.call_tool(
                "ask_course_material",
                arguments={
                    "query": question,
                    "course_id": course_id,
                    "architecture": "auto",
                    "top_k": 5,
                },
            )

            print(
                "\nCourse Material RAG Result:"
            )

            print_tool_result(
                teaching_result
            )

            # ---------------------------------------------------------
            # STEP 9 — Final Sampling
            # ---------------------------------------------------------

            print("\n" + "=" * 70)
            print(
                "STEP 9 — Final Result "
                "(generate_academic_advisory / sampling)"
            )
            print("=" * 70)

            result = await session.call_tool(
                "generate_academic_advisory",
                arguments={
                    "student_id": 3
                },
            )

            print_tool_result(result)

            print("\n" + "=" * 70)
            print(
                "DEMO COMPLETE"
            )
            print(
                "MCP protocol + Course Material Teaching "
                "were demonstrated."
            )
            print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())