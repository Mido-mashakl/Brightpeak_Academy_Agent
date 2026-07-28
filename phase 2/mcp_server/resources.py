def register_resources(mcp):

    @mcp.resource("academy://policies")
    def academy_policies():

        return """
Brightpeak Academy Policies

• Complete assignments.
• Respect deadlines.
• Attend sessions regularly.
"""