"""
Unconstrained ReAct Agent - Brightpeak Academy Track Recommender
-----------------------------------------------------------------
How it works:
  The agent runs a free-form Thought → Action → Observation loop.
  At each step the model decides:
    - whether to call a tool (and which one)
    - what arguments to pass
    - when it has enough information to give a final answer

  There is NO schema validation, NO tool allow-list, and NO step limit.
  This gives the model full freedom to reason across ambiguous cases,
  ask follow-up questions, handle multiple profiles, and flag mismatches —
  but it also means the loop can run longer and cost more tokens.

Tools available to the agent (described in the system prompt):
  1. search_tracks(goal, level, max_hours, budget)
       → returns tracks that match the given filters
  2. get_track_details(track_id)
       → returns full details for one track
"""

import os
import json
from pyexpat.errors import messages
import re
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()

MODEL_NAME = "gemini-flash-lite-latest"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRACKS_PATH = os.path.join(BASE_DIR, "tracks_dataset.json")
TEST_CASES_PATH = os.path.join(BASE_DIR, "test_cases.json")
RESULTS_PATH = os.path.join(BASE_DIR, "results.json")
SUMMARY_PATH = os.path.join(BASE_DIR, "summary.json")

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_tracks():
    with open(TRACKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["tracks"]


def load_test_cases():
    with open(TEST_CASES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["test_cases"]


# ---------------------------------------------------------------------------
# Tool implementations  (pure Python, no model involved)
# ---------------------------------------------------------------------------

def search_tracks(tracks, goal=None, level=None, max_hours=None, budget=None):
    results = []
    for t in tracks:
        if goal and goal.lower() not in t["goal"].lower() and goal.lower() not in t["name"].lower():
            continue
        if level and level.lower() != t["required_level"].lower():
            continue
        if max_hours is not None and t["hours_per_week"] > max_hours:
            continue
        budget_rank = {"low": 1, "medium": 2, "high": 3}
        if budget:
            student_rank = budget_rank.get(budget.lower(), 0)
            track_rank = budget_rank.get(t["budget"].lower(), 0)
            if track_rank > student_rank:
                continue
        results.append(t)
    return results


def get_track_details(tracks, track_id):
    for t in tracks:
        if t["id"] == track_id:
            return t
    return {"error": f"Track '{track_id}' not found."}




# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

def dispatch_tool(tool_name, tool_args, tracks):
    if tool_name == "search_tracks":
        results = search_tracks(
            tracks,
            goal=tool_args.get("goal"),
            level=tool_args.get("level"),
            max_hours=tool_args.get("max_hours"),
            budget=tool_args.get("budget"),
        )
        return results if results else [{"message": "No tracks matched those filters."}]

    elif tool_name == "get_track_details":
        return get_track_details(tracks, tool_args.get("track_id", ""))

    else:
        return {"error": f"Unknown tool: {tool_name}"}


# ---------------------------------------------------------------------------
# System prompt  — now asks for terse Thoughts/Observations
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an intelligent academic advisor for Brightpeak Academy.
Your job is to recommend the best learning track(s) for each student.

You reason step by step using a Thought → Action → Observation loop.

At each step write:
  Thought: <your reasoning>
  Action: <tool_name>(<JSON args>)

After you see the Observation for that action, continue with the next
Thought/Action pair, or end with:
  Final Answer: <your recommendation in plain English>

Available tools:
  search_tracks(goal, level, max_hours, budget)
      goal      – e.g. "AI", "Web", "Data", "Mobile"  (optional)
      level     – "Beginner", "Intermediate", or "Advanced"  (optional)
      max_hours – integer, student's available hours/week  (optional)
      budget    – "Low", "Medium", or "High"  (optional)

  get_track_details(track_id)
      track_id  – the id field from a search result

Rules:
- Keep each Thought to ONE sentence — no lengthy explanations.
- Keep each Observation summary to ONE sentence.
- Never explain obvious reasoning; move straight to the next action.
"""

# ---------------------------------------------------------------------------
# Pretty console printer
# ---------------------------------------------------------------------------

SEP  = "=" * 50
DASH = "-" * 50


def _print_step(step_num, thought, action_raw, obs_raw):
    """Print one ReAct step in the structured format."""
    print(f"\n{DASH}")
    print(f"STEP {step_num}")
    print(DASH)

    print("\nThought")
    print("-------")
    print(thought.strip() if thought else "(none)")

    if action_raw:
        print("\nAction")
        print("------")
        print(action_raw.strip())

    if obs_raw:
        print("\nObservation")
        print("-----------")
        print(obs_raw.strip())


def _print_case_header(case_id, student_input):
    print(f"\n{SEP}")
    print(f"TEST CASE : {case_id}")
    print(SEP)
    print(f"\nStudent:\n{student_input}")
    print(f"\n{DASH}")


def _print_final(answer, steps, tool_calls):
    print(f"\n{DASH}")
    print("FINAL RECOMMENDATION")
    print(SEP)
    print(answer)
    print(f"\nSteps      : {steps}")
    print(f"Tool Calls : {tool_calls}")
    print(SEP)

# ---------------------------------------------------------------------------
# ReAct loop
# ---------------------------------------------------------------------------

def parse_action(text):
    m = re.search(r"Action:\s*(\w+)\((\{.*?\})\)", text, re.DOTALL)
    if m:
        tool_name = m.group(1)
        try:
            args = json.loads(m.group(2))
            return tool_name, args
        except json.JSONDecodeError:
            pass

    m = re.search(r"Action:\s*(\w+)\(([^)]*)\)", text, re.DOTALL)
    if m:
        tool_name = m.group(1)
        raw_args = m.group(2).strip()
        args = {}
        for part in re.findall(r'(\w+)\s*=\s*(".*?"|\'.*?\'|\d+|None)', raw_args):
            key = part[0]
            val = part[1].strip('"\'')
            if val == "None":
                val = None
            elif val.isdigit():
                val = int(val)
            args[key] = val
        return tool_name, args

    return None, None


def _extract_section(text, label):
    """Pull the text after a label like 'Thought:' up to the next label or end."""
    m = re.search(rf"{label}:\s*(.*?)(?=\n(?:Thought|Action|Observation|Final Answer):|$)",
                  text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def run_react_agent(student_input, tracks, verbose=True):
    """
    Run the unconstrained ReAct loop for a single student input.
    Returns (final_answer, steps, model_calls, tool_calls).
    """
    messages = [
        {
            "role": "user",
            "content": (
                f"{SYSTEM_PROMPT}\n\n"
                f"Student message:\n\"\"\"{student_input}\"\"\"\n\n"
                "Begin your Thought → Action → Observation loop now."
            ),
        }
    ]

    step = 0
    model_calls = 0
    tool_calls = 0
    final_answer = None

    while True:
        step += 1

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[{"role": m["role"], "parts": [{"text": m["content"]}]} for m in messages],
            config={"temperature": 0},
        )
        model_calls += 1

        assistant_text = (response.text or "").strip()
        messages.append({"role": "model", "content": assistant_text})

        # Extract sections for pretty printing
        thought_text = _extract_section(assistant_text, "Thought")
        action_text  = _extract_section(assistant_text, "Action")

        # Check for final answer
        if "Final Answer:" in assistant_text:
            fa_match = re.search(r"Final Answer:(.*)", assistant_text, re.DOTALL)
            final_answer = fa_match.group(1).strip() if fa_match else assistant_text
            if verbose:
                _print_step(step, thought_text, action_text, None)
            break

        # Parse and dispatch tool call
        tool_name, tool_args = parse_action(assistant_text)

        if tool_name:
            tool_calls += 1

            observation = dispatch_tool(tool_name, tool_args, tracks)

            if verbose:
                _print_step(
                    step,
                    thought_text,
                    action_text,
                    json.dumps(observation, ensure_ascii=False, indent=2)
                )

            messages.append({
                "role": "user",
                "content": f"Observation: {json.dumps(observation, ensure_ascii=False)}"
            })

        else:
            if verbose:
                _print_step(
                    step,
                    thought_text,
                    None,
                    "[No action detected]"
                )

            messages.append({
                "role": "user",
                "content": (
                    "Observation: [No action detected]. "
                    "Please continue with a Thought and Action or provide your Final Answer."
                )
            })

    return final_answer, step, model_calls, tool_calls

# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def run_single(student_input):
    tracks = load_tracks()
    _print_case_header("SINGLE RUN", student_input)
    t0 = time.time()
    answer, steps, model_calls, tool_calls = run_react_agent(student_input, tracks, verbose=True)
    latency = round(time.time() - t0, 2)
    _print_final(answer, steps, tool_calls)
    print(f"Latency    : {latency}s  |  Model calls: {model_calls}")


def run_all_test_cases():
    tracks = load_tracks()
    test_cases = load_test_cases()
    all_results = []

    for case in test_cases:
        _print_case_header(case["id"], case["student_input"])

        t0 = time.time()
        answer, steps, model_calls, tool_calls = run_react_agent(
            case["student_input"], tracks, verbose=True
        )
        latency = round(time.time() - t0, 2)

        _print_final(answer, steps, tool_calls)
        print(f"Latency    : {latency}s  |  Model calls: {model_calls}")

        # ── Determine pass/fail ──────────────────────────────────────────
        expected = case.get("expected_track", "")

        if expected:
            expected_tracks = [
                track.strip().lower()
                for track in expected.split("+")
            ]

            answer_lower = answer.lower()

            matched = sum(track in answer_lower for track in expected_tracks)

            status = "PASS" if matched == len(expected_tracks) else "FAIL"
        else:
            status = "N/A"

        result = {
            "id":                case["id"],
            "type":              case.get("type", ""),
            "steps":             steps,
            "model_calls":       model_calls,
            "tool_calls":        tool_calls,
            "latency_sec":       latency,
            "expected_track":    expected,
            "recommended_track": answer[:200],   # first 200 chars of final answer
            "status":            status,
        }
        all_results.append(result)

        # Write results.json after every case so partial runs are saved
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)

        time.sleep(15)   # stay within free-tier rate limits

    # ── Summary stats ────────────────────────────────────────────────────
    evaluated = [r for r in all_results if r["status"] != "N/A"]
    passed     = sum(1 for r in evaluated if r["status"] == "PASS")
    failed     = len(evaluated) - passed

    avg_steps   = round(sum(r["steps"]       for r in all_results) / len(all_results), 2)
    avg_latency = round(sum(r["latency_sec"] for r in all_results) / len(all_results), 2)
    avg_tools   = round(sum(r["tool_calls"]  for r in all_results) / len(all_results), 2)
    avg_models  = round(sum(r["model_calls"] for r in all_results) / len(all_results), 2)
    total_model_calls = sum(r["model_calls"] for r in all_results)

    summary = {
        "total_cases":       len(all_results),
        "evaluated":         len(evaluated),
        "passed":            passed,
        "failed":            failed,
        "average_steps":     avg_steps,
        "average_latency":   avg_latency,
        "average_tools":     avg_tools,
        "average_model_calls": avg_models,
        "total_model_calls": total_model_calls,
    }

    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{SEP}")
    print("SUMMARY")
    print(SEP)
    for k, v in summary.items():
        print(f"  {k:<24}: {v}")
    print(f"\nResults  → {RESULTS_PATH}")
    print(f"Summary  → {SUMMARY_PATH}")
    print(SEP)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        run_single(" ".join(sys.argv[1:]))
    else:
        run_all_test_cases()