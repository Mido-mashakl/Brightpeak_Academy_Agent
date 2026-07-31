"""
Brightpeak Academy - MCP Agent (Stage 2)
==========================================

Builds on Stage 1 and adds:
  1. authenticate_staff (role escalation from front-desk to instructor)
  2. Listening for the tools/list_changed notification the server
     sends after a successful authentication
  3. Re-listing tools to see the new write tools that appeared
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import ToolListChangedNotification

AGENT_DIR = Path(__file__).resolve().parent
PHASE2_DIR = AGENT_DIR.parent
SERVER_SCRIPT = PHASE2_DIR / "mcp_server" / "server.py"

# This flag gets flipped to True the moment the notification arrives.
notification_received = False


async def message_handler(message) -> None:
    """Called by the mcp SDK for every message coming from the server,
    notifications included. We only care about one type here.
    """
    global notification_received
    root = getattr(message, "root", message)
    if isinstance(root, ToolListChangedNotification):
        notification_received = True
        print("\n>>> notifications/tools/list_changed RECEIVED <<<")


def print_tool_result(result) -> None:
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            try:
                data = json.loads(text)
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                print(text)


async def run_stage2() -> None:
    if not SERVER_SCRIPT.exists():
        raise FileNotFoundError(f"Server not found at: {SERVER_SCRIPT}")

    print("=" * 60)
    print("STAGE 2 — Authenticate + Notification + Updated Tool List")
    print("=" * 60)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(
            read, write, message_handler=message_handler
        ) as session:

            # 1. Handshake
            print("\n[1] Sending initialize...")
            await session.initialize()
            print("    Handshake OK")

            # 2. Tool list BEFORE authentication
            print("\n[2] Tool list BEFORE authentication:")
            tools_before = await session.list_tools()
            for t in tools_before.tools:
                print(f"      - {t.name}")

            # 3. Authenticate as instructor #1 (Laila Hassan, seed data)
            print("\n[3] Calling authenticate_staff(role='instructor', instructor_id=1)...")
            auth_result = await session.call_tool(
                "authenticate_staff",
                arguments={"role": "instructor", "instructor_id": 1},
            )
            print_tool_result(auth_result)

            # Give the notification a moment to arrive.
            await asyncio.sleep(0.3)
            print(f"\n    notification_received = {notification_received}")

            # 4. Tool list AFTER authentication
            print("\n[4] Tool list AFTER authentication:")
            tools_after = await session.list_tools()
            for t in tools_after.tools:
                print(f"      - {t.name}")

            print("\nStage 2 finished successfully.")


if __name__ == "__main__":
    asyncio.run(run_stage2())