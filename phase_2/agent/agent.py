"""
Brightpeak Academy - MCP Agent (Stage 1)
========================================

Stage 1 responsibilities:
  1. Connect to the MCP server over stdio
  2. Perform capability negotiation (declare elicitation + sampling)
  3. Discover available tools
  4. Call one read-only tool successfully (get_student_profile)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

AGENT_DIR = Path(__file__).resolve().parent
PHASE2_DIR = AGENT_DIR.parent
SERVER_SCRIPT = PHASE2_DIR / "mcp_server" / "server.py"

logger = logging.getLogger(__name__)


async def run_stage1() -> None:
    if not SERVER_SCRIPT.exists():
        raise FileNotFoundError(
            f"MCP server not found at: {SERVER_SCRIPT}\n"
            "Make sure the mcp_server folder is next to the agent folder."
        )

    print("=" * 60)
    print("STAGE 1 — Connect / Handshake / Discover / Call")
    print("=" * 60)
    print(f"Server script: {SERVER_SCRIPT}")
    print()

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
        env=os.environ.copy(),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # ---------------------------------------------------------------
            # 1. Capability negotiation (handshake)
            # ---------------------------------------------------------------
            print("[1] Sending initialize (capability negotiation)...")
            init_result = await session.initialize()
            print(f"    Server name : {init_result.serverInfo.name}")
            print(f"    Protocol    : {init_result.protocolVersion}")
            print("    Handshake OK")
            print()

            # ---------------------------------------------------------------
            # 2. Tool discovery
            # ---------------------------------------------------------------
            print("[2] Listing tools...")
            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            print(f"    Found {len(tool_names)} tools:")
            for name in sorted(tool_names):
                print(f"      - {name}")
            print()

            # ---------------------------------------------------------------
            # 3. One read-only tool call (smoke test)
            # ---------------------------------------------------------------
            print("[3] Calling get_student_profile(student_id=1)...")
            result = await session.call_tool(
                "get_student_profile",
                arguments={"student_id": 1},
            )

            for block in result.content:
                text = getattr(block, "text", None)
                if text:
                    try:
                        data = json.loads(text)
                        print("    Response:")
                        print(json.dumps(data, indent=2, ensure_ascii=False))
                    except json.JSONDecodeError:
                        print(f"    Raw text: {text}")
                else:
                    print(f"    Content block: {block}")

            print()
            print("=" * 60)
            print("STAGE 1 completed successfully.")
            print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(run_stage1())