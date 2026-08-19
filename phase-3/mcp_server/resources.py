"""
resources.py
============
=== CONCERN: Resources ===
Policies are static reference data — the model should read them once via
resources/read and reason over them, not call a tool on every lookup.
Registering them as @mcp.resource() exposes them through
resources/list + resources/read, keeping them out of the tool namespace.

Import this module in server.py BEFORE calling mcp.run() so the
decorators fire and FastMCP registers these endpoints.
"""

import database as db

# `mcp` is imported from server.py to avoid a circular dependency.
# The preferred pattern is to pass the FastMCP instance in at startup;
# see the `register_resources(mcp)` function at the bottom of this file.


def register_resources(mcp) -> None:
    """Attach all resource endpoints to `mcp`.

    Called once from server.py after the FastMCP instance is created:

        from resources import register_resources
        register_resources(mcp)
    """

    @mcp.resource("policy://all")
    def all_policies() -> str:
        """All Brightpeak Academy policies (attendance, scholarship,
        academic integrity, late submission, course withdrawal)."""
        policies = db.get_all_policies()
        return "\n\n".join(
            f"# {p['title']} ({p['category']})\n{p['content']}"
            for p in policies
        )

    @mcp.resource("policy://{policy_id}")
    def one_policy(policy_id: str) -> str:
        """A single Brightpeak Academy policy document by ID."""
        policy = db.get_policy(int(policy_id))
        if policy is None:
            return f"No policy with id {policy_id}"
        return f"# {policy['title']} ({policy['category']})\n{policy['content']}"

    
    @mcp.resource("course_material://{course_id}")
    def course_material_list(course_id: str) -> str:
        """The list of study materials registered for a course (title,
        type, description) — static reference data, not the material
        content itself. Use the ask_course_material tool to answer
        questions grounded in the actual text."""
        materials = db.get_course_materials(int(course_id))
        if not materials:
            return f"No materials registered for course {course_id}"
        return "\n\n".join(
            f"# {m['title']} ({m['material_type']})\n{m['description'] or ''}"
            for m in materials
        )
