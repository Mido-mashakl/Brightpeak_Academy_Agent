"""
server.py
=========
Brightpeak Academy MCP Server — entry point.

Wires FastMCP together with the split modules:
  auth.py          capability guards + role escalation
  notifications.py progress helpers
  prompts.py       @mcp.prompt() definitions
  resources.py     @mcp.resource() definitions (policies)
  schemas.py       Pydantic elicitation models
  tools.py         all tool implementations (read-only + write)
  validation.py    server-side input validators

=== CONCERN: Transport ===
Local development uses stdio (default).  A multi-campus deployment needs
Streamable HTTP behind auth so multiple staff sessions can connect over
the network at once; run with `python server.py --http` once the team is
ready (see README "Transport" section).

Run (dev / local):
    python server.py

Run (production):
    python server.py --http

=== CONCERN: Capability negotiation ===
FastMCP declares its own capabilities during `initialize` based on what's
registered below.  The pieces this server cares about explicitly:
  - elicitation : record_grade + change_enrollment_status check before
    calling ctx.elicit() and return a safe error if unsupported.
  - sampling    : generate_academic_advisory degrades to raw facts if the
    client didn't declare sampling support.
Both guards live in auth.py.
"""

from __future__ import annotations

import sys
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

import database as db
import roles
from auth import authenticate_staff_impl
from prompts import register_prompts
from resources import register_resources
from tools import get_write_tools, register_readonly_tools

# ------------------------------------------------------------------
# Bootstrap
# ------------------------------------------------------------------

db.init_db_if_needed()

mcp = FastMCP("brightpeak-academy")

# Register static endpoints
register_readonly_tools(mcp)
register_resources(mcp)
register_prompts(mcp)


# ------------------------------------------------------------------
# === CONCERN: Notifications + role escalation ===
# authenticate_staff is the single gate that promotes a front-desk
# (read-only) session to instructor or registrar and then fires
# tools/list_changed so the client discovers the new write tools
# without polling.
# ------------------------------------------------------------------

@mcp.tool()
async def authenticate_staff(
    role: str,
    ctx: Context,
    instructor_id: int | None = None,
    passcode: str | None = None,
) -> dict[str, Any]:
    """Authenticate as 'instructor' (requires instructor_id) or 'registrar'
    (requires passcode) to unlock write tools for this session.

    Args:
        role: 'instructor' or 'registrar'.
        instructor_id: required if role is 'instructor'.
        passcode: required if role is 'registrar'.
    """
    return await authenticate_staff_impl(
        role=role,
        ctx=ctx,
        mcp_instance=mcp,
        write_tool_fns=get_write_tools(),
        instructor_id=instructor_id,
        passcode=passcode,
    )


# ------------------------------------------------------------------
# Transport
# ------------------------------------------------------------------

if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")