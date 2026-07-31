"""
Brightpeak Academy - MCP Agent (Final Demo, Streamable HTTP transport)
=======================================================================

Identical to demo.py, with ONE difference: this connects to the MCP
server over Streamable HTTP instead of stdio.

=== CONCERN: Transport ===
stdio (demo.py) is fine for local development -- one client, one
server process, no network. A real Brightpeak Academy deployment needs
multiple staff sessions (front-desk, instructors, registrar) connecting
to the SAME running server at once, which stdio can't do (it only
supports a single client per server process). Streamable HTTP lets the
server run once and accept many concurrent client connections over the
network, which is what this file demonstrates.

HOW TO RUN
----------
1. Start the server in HTTP mode, in its own terminal:

       cd Phase-2/mcp_server
       python server.py --http

   It will start listening at http://127.0.0.1:8000/mcp
   (leave this terminal running)

2. In a SECOND terminal, run this file:

       cd Phase-2/agent
       python demo_http.py

Everything else -- the 8 steps, the fixed test inputs, the callbacks
for elicitation/sampling/progress -- is exactly what demo.py already
does. Only the connection at the bottom of main() changed.
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import (
    CreateMessageResult,
    ElicitResult,
    TextContent,
    ToolListChangedNotification,
)

AGENT_DIR = Path(__file__).resolve().parent

# Must match the host/port the server is running on (server.py defaults
# to 127.0.0.1:8000 when started with `python server.py --http`).
SERVER_URL = os.getenv("MCP_HTTP_URL", "http://127.0.0.1:8000/mcp")

# ---------------------------------------------------------------------
# Gemini setup (used by the sampling callback) -- identical to demo.py
# ---------------------------------------------------------------------
load_dotenv(AGENT_DIR / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing from .env")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)


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
    print(f"Connecting to Brightpeak Academy MCP server at {SERVER_URL} ...")

    # ---- CONCERN: Transport (Streamable HTTP) ----------------------
    # This is the ONLY structural change from demo.py: stdio_client()
    # spawns and pipes to a local subprocess; streamablehttp_client()
    # instead opens an HTTP(S) connection to a server that is already
    # running independently and could be serving other clients too.
    async with streamablehttp_client(SERVER_URL) as (read, write, get_session_id):
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
            session_id = get_session_id()
            if session_id is not None:
                print(f"HTTP session id: {session_id}")

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

            # ---- 8. Final Result (Sampling) -----------------------------
            print("\n" + "=" * 70)
            print("STEP 8 — Final Result (generate_academic_advisory / sampling)")
            print("=" * 70)
            result = await session.call_tool(
                "generate_academic_advisory", arguments={"student_id": 3}
            )
            print_tool_result(result)

            print("\n" + "=" * 70)
            print("DEMO COMPLETE (Streamable HTTP) — every protocol concern fired above.")
            print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())