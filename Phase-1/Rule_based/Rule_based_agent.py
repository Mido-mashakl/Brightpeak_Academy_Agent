"""
Brightpeak Academy - Reactive (Rule-Based) Agent
=================================================

Architecture 1 of 4: pure if/elif decision tree. No model call, no AI
involved anywhere in this file.

The agent pulls four things out of the student's message using simple
keyword/number checks -- level, goal, hours per week, budget -- and
then runs them through a fixed if/elif chain, one branch per track,
that checks all four conditions before recommending it.

It still has real limits (this is a rule-based agent, not a smart
one): it can't handle two goals or two different students mentioned in
the same message, and it can't explain *why* something is a partial
match -- if a track's conditions aren't all met, it returns
"No suitable track found based on the provided information."  Those limits are exactly what the other
three architectures in the project are meant to improve on.
"""


def get_level(text: str):
    text = text.lower()
    if "beginner" in text:
        return "beginner"
    if "intermediate" in text:
        return "intermediate"
    if "advanced" in text:
        return "advanced"
    return None


def get_goal(text: str):
    """Returns every goal keyword found, in a fixed priority order.

    If a message mentions more than one goal, all of them are kept so
    the if/elif chain below can check each one in turn and recommend
    the first track whose conditions are actually satisfied.
    """
    text = text.lower()
    goals = []
    if "machine learning" in text:
        goals.append("machine_learning")
    if "ai" in text and "machine_learning" not in goals:
        goals.append("ai")
    if "data" in text:
        goals.append("data")
    if "web" in text:
        goals.append("web")
    if "mobile" in text or "flutter" in text:
        goals.append("mobile")
    return goals


def get_hours(text: str):
    import re
    match = re.search(r"(\d+)\s*hours?", text.lower())
    if match:
        return int(match.group(1))
    return None


def get_budget(text: str):
    text = text.lower()
    if "low" in text or "limited" in text or "tight" in text or "small budget" in text:
        return "low"
    if "medium" in text:
        return "medium"
    if "high" in text or "large budget" in text or "big budget" in text:
        return "high"
    if "free" in text:
        return "low"
    return None


# A one-hour buffer so a student who is 1 hour short of a track's
# usual requirement isn't treated the same as someone way off (e.g. 2
# hours vs. an 8-hour requirement). Still a plain number, no model.
HOURS_BUFFER = 1


def recommend_track(student_input: str) -> str:
    """Fixed if/elif chain. Checks each mentioned goal in turn and
    returns the first track whose level/hours/budget conditions are
    all satisfied. If nothing fully qualifies, says so directly."""

    level = get_level(student_input)
    hours = get_hours(student_input)
    budget = get_budget(student_input)
    goals = get_goal(student_input)


    if not goals:
        return "No learning goal was identified in the student's message."

    if level is None or hours is None or budget is None:
        return "Insufficient information to recommend a track."

    for goal in goals:

        if goal == "ai":
            if (level == "beginner"
                    and hours is not None and hours + HOURS_BUFFER >= 8
                    and budget == "low"):
                return "AI Fundamentals"

        elif goal == "data":
            if (level == "beginner"
                    and hours is not None and hours + HOURS_BUFFER >= 6
                    and budget == "low"):
                return "Data Analysis"

        elif goal == "web":
            if (level == "intermediate"
                    and hours is not None and hours + HOURS_BUFFER >= 10
                    and budget == "medium"):
                return "Full Stack Web"

        elif goal == "mobile":
            if (level == "beginner"
                    and hours is not None and hours + HOURS_BUFFER >= 8
                    and budget in ("medium", "high")):
                return "Flutter"

        elif goal == "machine_learning":
            if (level == "advanced"
                    and hours is not None and hours + HOURS_BUFFER >= 12
                    and budget == "high"):
                return "Machine Learning"

    return "No suitable track found based on the provided information."


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:])
    else:
        message = input("Student message: ")

    print(recommend_track(message))