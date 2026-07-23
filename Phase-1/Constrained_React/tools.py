"""
Tool implementations for the Constrained ReAct agent.

Only the tools listed in config.ALLOWED_TOOLS are ever exposed to the
model or executed. This file defines what each tool actually does.
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRACKS_PATH = os.path.join(BASE_DIR, "tracks_dataset.json")


def _load_tracks():
    with open(TRACKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["tracks"]


def search_courses(query: str) -> str:
    """Search the track catalog by keyword. Matches against name, goal,
    level, or description of each track."""
    tracks = _load_tracks()
    query_lower = query.lower()
    matches = [t for t in tracks if query_lower in json.dumps(t).lower()]
    if not matches:
        return "No tracks matched that query. Try a broader keyword (e.g. 'AI', 'data', 'web', 'mobile')."
    return json.dumps(matches, indent=2)


def student_history(student_id: str) -> str:
    """Look up a student's past course history. This is mock data for the
    project — always returns a stub response since there is no real student
    database."""
    return f"No prior history found for student_id='{student_id}'. Treat as a new student."


def faq(topic: str) -> str:
    """Look up an answer to a common student question (refunds, scheduling,
    prerequisites)."""
    faqs = {
        "refund": "Brightpeak offers a full refund within the first 7 days of any track.",
        "schedule": "Tracks are self-paced but include weekly live sessions.",
        "prerequisites": "No prerequisites beyond the 'required_level' listed for each track.",
    }
    for key, answer in faqs.items():
        if key in topic.lower():
            return answer
    return "No FAQ entry found for that topic. Try 'refund', 'schedule', or 'prerequisites'."


# Maps tool name (string, as the model will request it) to the actual function.
TOOL_REGISTRY = {
    "search_courses": search_courses,
    "student_history": student_history,
    "faq": faq,
}
