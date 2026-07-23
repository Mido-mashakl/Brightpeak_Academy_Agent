"""
Routing Architecture - Brightpeak Academy Track Recommender
--------------------------------------------------------------
How it works:
1. The student's message is sent to the LLM together with a list of
   all available tracks.
2. The LLM makes exactly ONE call: it classifies the input into the
   single best-matching track id (or "no_match" if nothing fits well).
3. No tools, no loops, no multi-step reasoning - just one classification
   call. This is why routing is fast and cheap, but has limited
   flexibility: it can't ask follow-up questions or explain trade-offs
   in depth.

Model: Gemini Flash-Lite (swap MODEL_NAME below if you use a different provider)
"""

import os
import json
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()  # reads variables from a local .env file, if present

MODEL_NAME = "gemini-flash-lite-latest"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRACKS_PATH = os.path.join(BASE_DIR, "tracks_dataset.json")
TEST_CASES_PATH = os.path.join(BASE_DIR, "test_cases.json")

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def load_tracks():
    with open(TRACKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["tracks"]


def load_test_cases():
    with open(TEST_CASES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["test_cases"]


def build_prompt(tracks, student_input: str) -> str:
    tracks_block = "\n".join(
        f"- id: {t['id']} | name: {t['name']} | level: {t['required_level']} "
        f"| hours/week: {t['hours_per_week']} | budget: {t['budget']} "
        f"| goal: {t['goal']} | description: {t['description']}"
        for t in tracks
    )

    return f"""You are a routing classifier for Brightpeak Academy.

Your ONLY job is to read a student's message and pick the single best
matching track from the list below. You do not ask questions, you do
not explain your reasoning at length, and you make exactly one decision.

Available tracks:
{tracks_block}

Student message:
\"\"\"{student_input}\"\"\"

Respond ONLY with a JSON object in this exact format, nothing else,
no markdown fences:
{{
  "track_id": "<one of the track ids above, or 'no_match' if nothing fits reasonably well>",
  "reason": "<one short sentence explaining the choice>"
}}
"""


def route_student(student_input: str, tracks) -> dict:
    prompt = build_prompt(tracks, student_input)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config={
            "temperature": 0,
            "response_mime_type": "application/json",
            "thinking_config": {"thinking_level": "minimal"},
        },
    )

    raw = (response.text or "").strip()

    # Parse only the first complete, valid JSON object in the text and
    # ignore anything after it (stray braces, trailing text, etc.).
    start = raw.find("{")
    if start == -1:
        return {"track_id": "no_match", "reason": f"Could not parse model output: {raw}"}

    try:
        obj, _ = json.JSONDecoder().raw_decode(raw, start)
        return obj
    except json.JSONDecodeError:
        return {"track_id": "no_match", "reason": f"Could not parse model output: {raw}"}


def run_single(student_input: str):
    tracks = load_tracks()
    result = route_student(student_input, tracks)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def run_all_test_cases():
    tracks = load_tracks()
    test_cases = load_test_cases()

    for case in test_cases:
        result = route_student(case["student_input"], tracks)
        print(f"[{case['id']}] ({case['type']})")
        print(f"  Input:    {case['student_input']}")
        print(f"  Expected: {case.get('expected_track')}")
        print(f"  Routed to: {result.get('track_id')}")
        print(f"  Reason:    {result.get('reason')}")
        print("-" * 60)
        time.sleep(5)  # stay comfortably under Flash-Lite's free-tier per-minute limit


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Run with a custom student input, e.g.:
        # python app.py "I'm a beginner and want to learn AI, 8 hours a week"
        run_single(" ".join(sys.argv[1:]))
    else:
        # Default: run against all test cases in test_cases.json
        run_all_test_cases()