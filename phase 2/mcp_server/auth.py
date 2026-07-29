"""
auth.py
=======
=== CONCERN: Capability negotiation ===
Two lightweight helpers that inspect the MCP client's declared
capabilities so every tool can decide at call-time whether elicitation
or sampling is available, rather than assuming it.

=== CONCERN: Notifications + role escalation ===
`authenticate_staff` is the single entry-point for elevating a
front-desk (read-only) session to instructor or registrar.  On success
it registers the write-tool implementations with the FastMCP instance
passed in and fires tools/list_changed so the client doesn't have to
poll.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import Context

import roles

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


# ------------------------------------------------------------------
# Capability guards
# ------------------------------------------------------------------

def client_supports_elicitation(ctx: Context) -> bool:
    """Return True if the connected client declared elicitation support."""
    try:
        caps = ctx.session.client_params.capabilities
        return caps is not None and caps.elicitation is not None
    except Exception:
        return False


def client_supports_sampling(ctx: Context) -> bool:
    """Return True if the connected client declared sampling support."""
    try:
        caps = ctx.session.client_params.capabilities
        return caps is not None and caps.sampling is not None
    except Exception:
        return False


# ------------------------------------------------------------------
# Notification helper
# ------------------------------------------------------------------

async def notify_tool_list_changed(ctx: Context) -> None:
    """Push a tools/list_changed notification to the client.

    Wrapped defensively because the exact session helper has moved between
    mcp-sdk versions.
    """
    try:
        await ctx.session.send_tool_list_changed()
    except AttributeError:
        await ctx.session.send_notification(
            {"method": "notifications/tools/list_changed"}
        )


# ------------------------------------------------------------------
# authenticate_staff tool implementation
# ------------------------------------------------------------------

async def authenticate_staff_impl(
    role: str,
    ctx: Context,
    mcp_instance: "FastMCP",
    write_tool_fns: list,
    instructor_id: int | None = None,
    passcode: str | None = None,
) -> dict[str, Any]:
    """Authenticate as 'instructor' or 'registrar' and unlock write tools.

    Called by the @mcp.tool()-decorated wrapper in server.py which
    forwards the FastMCP instance and the list of write-tool callables
    so this module stays decoupled from the top-level mcp object.

    Args:
        role: 'instructor' or 'registrar'.
        ctx: MCP context from FastMCP.
        mcp_instance: the running FastMCP app (needed to add tools).
        write_tool_fns: list of async callables to register on success.
        instructor_id: required when role == 'instructor'.
        passcode: required when role == 'registrar'.
    """
    ok, message = roles.authenticate(role, instructor_id, passcode)
    if not ok:
        return {"success": False, "message": message}

    for fn in write_tool_fns:
        mcp_instance.add_tool(fn)
    await notify_tool_list_changed(ctx)

    return {"success": True, "message": message, "role": roles.SESSION.role}