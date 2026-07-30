"""
Brightpeak Academy - MCP Agent (Stage 5)
==========================================

Builds on Stage 4 and adds:
  1. Reading a Resource (policy://all) via resources/read -- this is
     static reference data the model reads once, NOT a tool it calls.
  2. Using a Prompt template (draft_attendance_warning) via
     prompts/get -- a reusable, parameterised starting point the
     server provides instead of the client hand-writing the wording.
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

AGENT_DIR = Path(__file__).resolve().parent
PHASE2_DIR = AGENT_DIR.parent
SERVER_SCRIPT = PHASE2_DIR / "mcp_server" / "server.py"


async def run_stage5() -> None:
    if not SERVER_SCRIPT.exists():
        raise FileNotFoundError(f"Server not found at: {SERVER_SCRIPT}")

    print("=" * 60)
    print("STAGE 5 — Resources + Prompts")
    print("=" * 60)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            print("\n[1] Sending initialize...")
            init_result = await session.initialize()
            print("    Handshake OK")

            # --- Capability check before relying on resources/prompts ---
            caps = init_result.capabilities
            print(f"\n    resources declared by server: {caps.resources is not None}")
            print(f"    prompts declared by server:   {caps.prompts is not None}")

            # -----------------------------------------------------------
            # === CONCERN: Resources ===
            # -----------------------------------------------------------
            print("\n[2] Listing available resources...")
            resources_result = await session.list_resources()
            for r in resources_result.resources:
                print(f"      - {r.uri}  ({r.name})")

            print("\n[3] Reading resource: policy://all")
            policy_result = await session.read_resource("policy://all")
            for content in policy_result.contents:
                text = getattr(content, "text", None)
                if text:
                    print(text[:600] + ("..." if len(text) > 600 else ""))

            # -----------------------------------------------------------
            # === CONCERN: Prompts ===
            # -----------------------------------------------------------
            print("\n[4] Listing available prompts...")
            prompts_result = await session.list_prompts()
            for p in prompts_result.prompts:
                print(f"      - {p.name}: {p.description}")

            print("\n[5] Fetching prompt: draft_attendance_warning(student_id=7, course_id=1)")
            prompt_result = await session.get_prompt(
                "draft_attendance_warning",
                arguments={"student_id": "7", "course_id": "1"},
            )
            rendered = prompt_result.messages[0].content.text
            print("    Rendered template:")
            print(f"    {rendered}")

            print("\nStage 5 finished successfully.")


if __name__ == "__main__":
    asyncio.run(run_stage5())