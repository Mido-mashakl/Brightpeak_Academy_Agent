"""
Brightpeak Academy - Memory Add-On Demo
========================================

=== CONCERN (Add-On Lab): Option B -- Agent Memory ===

Proves the memory is REAL persistence, not a scripted illusion: this
file spawns the MCP server as a fresh subprocess TWICE, once per
"session". Session 2 has no shared Python state with session 1 at
all -- the only thing connecting them is advisor_notes.json on disk.

SESSION 1: authenticate as instructor, leave a note about a student
           ("family emergency, be lenient on deadlines this month").
SESSION 2: brand-new server process, no note added again -- just ask
           for that student's academic advisory. The note shows up in
           the result on its own.

Run:
    cd Phase-2/agent
    python demo_memory.py
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

# The student this demo writes/recalls a note for. Change if your seed
# data uses a different id -- must be a real student_id in brightpeak.db.
DEMO_STUDENT_ID = 3


def print_tool_result(result) -> None:
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            try:
                data = json.loads(text)
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                print(text)


async def run_session_1() -> None:
    print("=" * 70)
    print("SESSION 1 (fresh server process) — advisor leaves a note")
    print("=" * 70)

    server_params = StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            auth_result = await session.call_tool(
                "authenticate_staff",
                arguments={"role": "instructor", "instructor_id": 1},
            )
            print_tool_result(auth_result)

            note_result = await session.call_tool(
                "add_advisor_note",
                arguments={
                    "student_id": DEMO_STUDENT_ID,
                    "note_text": (
                        "Family emergency reported this month; be lenient on "
                        "assignment deadlines through the end of the term."
                    ),
                },
            )
            print("\nadd_advisor_note result:")
            print_tool_result(note_result)

    print("\n[Session 1 process exits here -- no Python state carries over]\n")


async def run_session_2() -> None:
    print("=" * 70)
    print("SESSION 2 (brand-new server process) — note recalled on its own")
    print("=" * 70)

    server_params = StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # No authentication, no add_advisor_note call here -- this is
            # exactly what demo.py's Step 8 already does. The only
            # difference from a plain run is that the note from Session 1
            # now shows up under "advisor_notes" without asking for it.
            result = await session.call_tool(
                "generate_academic_advisory",
                arguments={"student_id": DEMO_STUDENT_ID},
            )
            print_tool_result(result)


async def main() -> None:
    await run_session_1()
    await run_session_2()
    print("\nDEMO COMPLETE — the note written in Session 1 (a separate process)")
    print("was recalled automatically in Session 2 with no explicit search call.")


if __name__ == "__main__":
    asyncio.run(main())
