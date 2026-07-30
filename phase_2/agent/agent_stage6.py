"""
Brightpeak Academy - MCP Agent (Stage 6)
==========================================

Builds on Stage 5 and adds:
  1. A progress_callback passed into session.call_tool(). The mcp SDK
     calls this function every time the server sends a progress
     notification mid tool-call, instead of the client sitting there
     blocked with no feedback.
  2. Calling generate_course_report(course_id=1), which loops over
     every student enrolled in the course and reports progress as it
     goes (see mcp_server/tools.py / notifications.py on the server).
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

AGENT_DIR = Path(__file__).resolve().parent
PHASE2_DIR = AGENT_DIR.parent
SERVER_SCRIPT = PHASE2_DIR / "mcp_server" / "server.py"


# ---------------------------------------------------------------------
# === CONCERN: Progress tracking ===
# Called by the mcp SDK every time the server reports progress
# (e.g. "Processing Ahmed Mostafa (1/3)").
# ---------------------------------------------------------------------
async def progress_callback(progress: float, total: float | None, message: str | None) -> None:
    if total:
        pct = int((progress / total) * 100)
        print(f"    [progress] {pct:3d}% - {message or ''}")
    else:
        print(f"    [progress] {progress} - {message or ''}")


def print_tool_result(result) -> None:
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            try:
                data = json.loads(text)
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                print(text)


async def run_stage6() -> None:
    if not SERVER_SCRIPT.exists():
        raise FileNotFoundError(f"Server not found at: {SERVER_SCRIPT}")

    print("=" * 60)
    print("STAGE 6 — Progress Tracking")
    print("=" * 60)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            print("\n[1] Sending initialize...")
            await session.initialize()
            print("    Handshake OK")

            print("\n[2] Calling generate_course_report(course_id=1)...")
            print("    (this loops over every student enrolled in course 1)\n")

            result = await session.call_tool(
                "generate_course_report",
                arguments={"course_id": 1},
                progress_callback=progress_callback,
            )

            print("\n[3] Final report:")
            print_tool_result(result)

            print("\nStage 6 finished successfully.")


if __name__ == "__main__":
    asyncio.run(run_stage6())