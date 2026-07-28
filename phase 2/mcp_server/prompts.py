def register_prompts(mcp):

    @mcp.prompt()
    def recommend_track(goal: str):

        return f"""
Recommend the most suitable learning track for a student interested in:

{goal}

Explain the recommendation briefly.
"""