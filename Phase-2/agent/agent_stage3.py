"""
Brightpeak Academy - MCP Agent (Stage 3)
==========================================

Builds on Stage 2 and adds:
  1. An elicitation_callback: when the server needs human confirmation
     mid tool-call (elicitation/create), this function is called by the
     mcp SDK, prints the server's message, and asks a real human via
     input() -- it never auto-confirms.
  2. Calling the grade-recording write tool with values that trigger a
     "large override" (existing grade 85 -> new grade 60, a difference
     of more than 15 points), which is exactly the kind of change the
     server refuses to apply without confirmation.
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import ElicitResult

AGENT_DIR = Path(__file__).resolve().parent
PHASE2_DIR = AGENT_DIR.parent
SERVER_SCRIPT = PHASE2_DIR / "mcp_server" / "server.py"


async def elicitation_callback(context, params):
    """This is called by the mcp SDK whenever the server sends
    elicitation/create. We show the server's message and the fields it
    is asking for, then collect a real answer from the terminal.
    """
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
    """Looks for a tool whose name contains `keyword`, regardless of
    whatever exact naming Omar's server currently uses
    (e.g. 'record_grade' vs '_record_grade_impl').
    """
    for t in tools:
        if keyword in t.name:
            return t.name
    raise RuntimeError(f"No tool found matching '{keyword}'")


async def run_stage3() -> None:
    if not SERVER_SCRIPT.exists():
        raise FileNotFoundError(f"Server not found at: {SERVER_SCRIPT}")

    print("=" * 60)
    print("STAGE 3 — Elicitation (human-in-the-loop confirmation)")
    print("=" * 60)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(
            read, write, elicitation_callback=elicitation_callback
        ) as session:

            # 1. Handshake
            print("\n[1] Sending initialize...")
            await session.initialize()
            print("    Handshake OK")

            # 2. Authenticate as instructor #1 (owns course 1)
            print("\n[2] Authenticating as instructor #1...")
            auth_result = await session.call_tool(
                "authenticate_staff",
                arguments={"role": "instructor", "instructor_id": 1},
            )
            print_tool_result(auth_result)

            # 3. Find the actual name of the grade-recording tool
            tools = (await session.list_tools()).tools
            record_grade_tool = find_tool_name(tools, "record_grade")
            print(f"\n[3] Using tool name: {record_grade_tool}")

            # 4. Call it with a large override (85 -> 60) to trigger elicitation
            print("\n[4] Calling the grade tool with a large override (85 -> 60)...")
            result = await session.call_tool(
                record_grade_tool,
                arguments={
                    "student_id": 1,
                    "assignment_id": 1,
                    "score": 60,
                },
            )
            print("\n[5] Final result:")
            print_tool_result(result)

            print("\nStage 3 finished successfully.")


if __name__ == "__main__":
    asyncio.run(run_stage3())