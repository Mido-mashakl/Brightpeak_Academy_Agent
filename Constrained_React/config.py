"""
Configuration for the Constrained ReAct agent.

Kept in its own file (not buried inside app.py) so it's easy to find and tune.
"""

# Maximum number of Thought -> Action -> Observation cycles the agent
# is allowed to run before it is forced to stop, even without a final answer.
MAX_STEPS = 6

# The only tools the agent is permitted to call. Any tool name outside
# this list is rejected at execution time, even if the model asks for it.
ALLOWED_TOOLS = [
    "search_courses",
    "student_history",
    "faq",
]
