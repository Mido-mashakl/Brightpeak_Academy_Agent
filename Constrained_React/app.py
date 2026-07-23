"""
Constrained ReAct Architecture - Brightpeak Academy Track Recommender
--------------------------------------------------------------------------
How it works:
1. The agent reasons in a loop: Thought -> Action -> Observation, repeated
   until it produces a final answer (classic ReAct pattern).
2. Every single response from the model MUST validate against the
   `AgentResponse` schema (schema.py). Malformed output is treated as a
   failed step, not silently accepted.
3. On each step the agent may only call a tool from `ALLOWED_TOOLS`
   (config.py) — any other tool name is rejected before it ever runs.
4. The loop is hard-capped at `MAX_STEPS` (config.py). If the agent hasn't
   produced a final answer by then, the run stops with status
   "stopped_at_max_steps" instead of looping forever.

This sits between:
- Unconstrained ReAct: same reasoning loop, but no schema / allow-list /
  step limit, so it can loop indefinitely or hallucinate tool calls.
- Routing: a single classification call, no reasoning loop, no tools.

Model: Gemini Flash-Lite
"""

import os
import json
import time
from dotenv import load_dotenv
from google import genai
from pydantic import ValidationError

from schema import AgentResponse
from tools import TOOL_REGISTRY
from config import MAX_STEPS, ALLOWED_TOOLS

load_dotenv()

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


SYSTEM_PROMPT_TEMPLATE = """You are a Constrained ReAct agent for Brightpeak Academy.
You help students pick the right learning track by reasoning step by step.

You may ONLY call these tools: {allowed_tools}
- search_courses(query): search the track catalog by keyword
- student_history(student_id): look up a student's past courses (mock data)
- faq(topic): look up answers to common questions (refund, schedule, prerequisites)

On every turn you MUST respond with ONLY a JSON object matching this exact
schema, no markdown fences, no extra text:
{{
  "thought": "<your reasoning about what to do next>",
  "action": "use_tool" or "final_answer",
  "tool": "<one of {allowed_tools}, or null if action is 'final_answer'>",
  "tool_input": "<input string for the tool, or null>",
  "final_answer": "<your recommendation and explanation, or null if action is 'use_tool'>"
}}

Rules:
- If action is "use_tool": tool and tool_input are required, final_answer must be null.
- If action is "final_answer": final_answer is required, tool and tool_input must be null.
- Only call a tool if you genuinely need information you don't already have.
- You have a maximum of {max_steps} steps. Work efficiently and give a
  final_answer as soon as you have enough information.
"""


def build_transcript(student_input: str, history: list) -> str:
    lines = [f'Student message: "{student_input}"']
    for step in history:
        lines.append(f"Thought: {step['thought']}")
        if step["action"] == "use_tool":
            lines.append(f"Action: call {step['tool']}({step['tool_input']!r})")
            lines.append(f"Observation: {step['observation']}")
        else:
            lines.append(f"Final Answer: {step['final_answer']}")
    return "\n".join(lines)


def call_model(system_prompt: str, transcript: str) -> AgentResponse:
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=f"{system_prompt}\n\n---\nConversation so far:\n{transcript}\n\nRespond with the next JSON step now.",
        config={
            "temperature": 0,
            "response_mime_type": "application/json",
            "thinking_config": {"thinking_level": "minimal"},
        },
    )

    raw = (response.text or "").strip()
    start = raw.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in model output: {raw}")

    obj, _ = json.JSONDecoder().raw_decode(raw, start)
    return AgentResponse(**obj)  # raises pydantic.ValidationError if malformed


def run_agent(student_input: str) -> dict:
    allowed_tools_str = ", ".join(ALLOWED_TOOLS)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        allowed_tools=allowed_tools_str, max_steps=MAX_STEPS
    )

    history = []

    for step_num in range(1, MAX_STEPS + 1):
        transcript = build_transcript(student_input, history)

        try:
            step = call_model(system_prompt, transcript)
        except (ValueError, ValidationError) as e:
            return {
                "status": "error",
                "steps_used": step_num,
                "final_answer": None,
                "error": str(e),
                "history": history,
            }

        if step.action == "final_answer":
            history.append({
                "thought": step.thought,
                "action": "final_answer",
                "final_answer": step.final_answer,
            })
            return {
                "status": "completed",
                "steps_used": step_num,
                "final_answer": step.final_answer,
                "history": history,
            }

        # action == "use_tool"
        if step.tool not in ALLOWED_TOOLS:
            observation = f"Error: tool '{step.tool}' is not in the allowed tool list {ALLOWED_TOOLS}."
        else:
            tool_fn = TOOL_REGISTRY[step.tool]
            try:
                observation = tool_fn(step.tool_input or "")
            except Exception as e:
                observation = f"Error running tool: {e}"

        history.append({
            "thought": step.thought,
            "action": "use_tool",
            "tool": step.tool,
            "tool_input": step.tool_input,
            "observation": observation,
        })

    # Loop exhausted MAX_STEPS without a final answer
    return {
        "status": "stopped_at_max_steps",
        "steps_used": MAX_STEPS,
        "final_answer": None,
        "history": history,
    }


def run_single(student_input: str):
    result = run_agent(student_input)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def run_all_test_cases():
    test_cases = load_test_cases()

    for case in test_cases:
        result = run_agent(case["student_input"])
        print(f"[{case['id']}] ({case['type']})")
        print(f"  Input:      {case['student_input']}")
        print(f"  Expected:   {case.get('expected_track')}")
        print(f"  Status:     {result['status']}")
        print(f"  Steps used: {result['steps_used']}")
        print(f"  Final:      {result.get('final_answer')}")
        print("-" * 60)
        time.sleep(13)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # python app.py "some student message"
        run_single(" ".join(sys.argv[1:]))
    else:
        # Default: run against all test cases in test_cases.json
        run_all_test_cases()
