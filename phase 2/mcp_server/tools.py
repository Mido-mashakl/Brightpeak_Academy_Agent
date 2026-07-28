def register_tools(mcp):

    @mcp.tool()
    def get_student(student_id: int) -> dict:
        """
        Retrieve student information.
        """

        return {
            "student_id": student_id,
            "name": "Demo Student",
            "track": "AI Fundamentals"
        }

    @mcp.tool()
    def list_tracks() -> list:
        """
        List available learning tracks.
        """

        return [
            "AI Fundamentals",
            "Machine Learning",
            "Data Analysis",
            "Full Stack",
            "Flutter"
        ]