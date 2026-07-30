"""
Brightpeak Academy - MCP Agent (Stage 1)
=========================================

This stage only does:
  1. Connect to the server (handshake)
  2. List the available tools
  3. Call one read-only tool and confirm the response
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Path to Omar's server
AGENT_DIR = Path(__file__).resolve().parent
PHASE2_DIR = AGENT_DIR.parent
SERVER_SCRIPT = PHASE2_DIR / "mcp_server" / "server.py"


async def run_stage1() -> None:
    if not SERVER_SCRIPT.exists():
        raise FileNotFoundError(f"Server not found at: {SERVER_SCRIPT}")

    print("=" * 60)
    print("STAGE 1 — Connect + Handshake + List Tools + One Call")
    print("=" * 60)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            # 1. Handshake
            print("\n[1] Sending initialize (first contact with the server)...")
            init_result = await session.initialize()
            print(f"    Server name : {init_result.serverInfo.name}")
            print(f"    Protocol version: {init_result.protocolVersion}")

            # 2. List available tools
            print("\n[2] Fetching the tool list...")
            tools_result = await session.list_tools()
            print(f"    Tool count: {len(tools_result.tools)}")
            for t in tools_result.tools:
                print(f"      - {t.name}")

            # 3. Call one tool (read-only)
            print("\n[3] Calling get_student_profile(student_id=1)...")
            result = await session.call_tool(
                "get_student_profile",
                arguments={"student_id": 1},
            )
            for block in result.content:
                text = getattr(block, "text", None)
                if text:
                    data = json.loads(text)
                    print(json.dumps(data, indent=2, ensure_ascii=False))

            print("\nStage 1 finished successfully.")


if __name__ == "__main__":
    asyncio.run(run_stage1())