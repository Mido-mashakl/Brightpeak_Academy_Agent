"""
Brightpeak Academy - MCP Agent (Stage 4)
==========================================

Builds on Stage 3 and adds:
  1. A sampling_callback: when the server needs a piece of text
     generated (sampling/createMessage), the mcp SDK calls this
     function instead of the server doing it itself. We answer using
     OUR OWN Gemini client -- proving the narrative comes from the
     client's model, not a model the server owns.
  2. Calling generate_academic_advisory, which triggers exactly that
     request on the server side.
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
from mcp.types import CreateMessageResult, ElicitResult, TextContent

AGENT_DIR = Path(__file__).resolve().parent
PHASE2_DIR = AGENT_DIR.parent
SERVER_SCRIPT = PHASE2_DIR / "mcp_server" / "server.py"

# ---------------------------------------------------------------------
# Gemini setup
# ---------------------------------------------------------------------
load_dotenv(AGENT_DIR / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing from .env")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)


# ---------------------------------------------------------------------
# Elicitation callback (same as Stage 3, kept so record_grade etc.
# still work if we call them later)
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
        print("-> Declined.\n")
        return ElicitResult(action="decline")
    print("-> Confirmed.\n")
    return ElicitResult(action="accept", content=answers)


# ---------------------------------------------------------------------
# === Sampling callback ===
# Called by the mcp SDK whenever the server sends sampling/createMessage.
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


def print_tool_result(result) -> None:
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            try:
                data = json.loads(text)
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                print(text)


async def run_stage4() -> None:
    if not SERVER_SCRIPT.exists():
        raise FileNotFoundError(f"Server not found at: {SERVER_SCRIPT}")

    print("=" * 60)
    print("STAGE 4 — Sampling (client's Gemini model does the reasoning)")
    print("=" * 60)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(
            read,
            write,
            elicitation_callback=elicitation_callback,
            sampling_callback=sampling_callback,
        ) as session:

            print("\n[1] Sending initialize...")
            await session.initialize()
            print("    Handshake OK")

            print("\n[2] Calling generate_academic_advisory(student_id=3)...")
            result = await session.call_tool(
                "generate_academic_advisory",
                arguments={"student_id": 3},
            )
            print("\n[3] Final tool result:")
            print_tool_result(result)

            print("\nStage 4 finished successfully.")


if __name__ == "__main__":
    asyncio.run(run_stage4())