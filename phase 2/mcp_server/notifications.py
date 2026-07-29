"""
notifications.py
================
=== CONCERN: Progress tracking ===
Thin wrapper around ctx.report_progress so tools that loop over many
records (e.g. generate_course_report) don't inline the boilerplate and
can be tested without a live MCP session.

The tool-list-changed helper lives in auth.py (where role escalation
happens) rather than here, because it's tightly coupled to the
authentication flow rather than to progress reporting.
"""

from __future__ import annotations

from mcp.server.fastmcp import Context


async def report_progress(
    ctx: Context,
    *,
    current: int,
    total: int,
    label: str = "",
) -> None:
    """Emit a progress notification to the connected client.

    Args:
        ctx: MCP context supplied by FastMCP.
        current: items processed so far (1-based is fine).
        total: total item count.
        label: optional human-readable message shown in the client UI.
    """
    await ctx.report_progress(
        progress=current,
        total=total,
        message=label,
    )