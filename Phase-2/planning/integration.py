def execute_brightpeak_task(task: str):
    """
    Translate a generated planning task into a real
    Brightpeak MCP tool call.
    """

    task_lower = task.lower()

    if "profile" in task_lower:
        return mcp_client.call_tool(
            "get_student_profile",
            {"student_id": 1},
        )

    if "grade" in task_lower:
        return mcp_client.call_tool(
            "get_student_grades",
            {"student_id": 1},
        )

    if "attendance" in task_lower:
        return mcp_client.call_tool(
            "get_student_attendance",
            {"student_id": 1},
        )

    if "enrollment" in task_lower or "course" in task_lower:
        return mcp_client.call_tool(
            "get_student_enrollments",
            {"student_id": 1},
        )

    if "policy" in task_lower:
        return mcp_client.call_tool(
            "search_policies",
            {"query": task},
        )

    raise ValueError(
        f"No Brightpeak MCP tool mapped to task: {task}"
    )