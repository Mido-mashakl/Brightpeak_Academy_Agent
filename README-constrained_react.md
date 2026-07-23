# Constrained ReAct Architecture

## Model

Gemini Flash-Lite

## How It Works

This is the **constrained ReAct** approach — the most structured of the four architectures. The agent reasons in a loop (classic ReAct: **Thought → Action → Observation**, repeated) until it produces a final recommendation, but with three hard guardrails:

1. **Validation Schema** (`schema.py`) — every single response from the model must conform to the `AgentResponse` Pydantic model. If the model returns malformed or inconsistent output (e.g. calling a tool but also giving a final answer), it's rejected as a validation error, not silently accepted.
2. **Allow List** (`config.py`) — the agent may only call tools listed in `ALLOWED_TOOLS`. Any tool name outside that list is rejected before it's ever executed, even if the model asks for it.
3. **MAX_STEPS** (`config.py`) — the loop is hard-capped. If the agent hasn't reached a final answer within `MAX_STEPS` cycles, the run stops with `status: "stopped_at_max_steps"` instead of looping forever.

This sits between:
- **Unconstrained ReAct** — same reasoning loop, but no schema, no allow-list, no step limit → can loop indefinitely or hallucinate tool calls.
- **Routing** — a single classification call, no reasoning loop, no tools at all.

## Files

```text
constrained_react/
├── app.py               ← main ReAct loop
├── schema.py             ← AgentResponse Pydantic schema (validation)
├── tools.py               ← search_courses, student_history, faq
├── config.py               ← MAX_STEPS and ALLOWED_TOOLS
├── tracks_dataset.json      ← the 5 available tracks
├── test_cases.json           ← easy + tricky test inputs
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## How to Run

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Get a free Gemini API key from https://aistudio.google.com/apikey

3. Copy `.env.example` to `.env` and add your real key:

```text
GEMINI_API_KEY=your-real-key-here
```

**Never commit your real `.env` file or paste your real key anywhere public** — it's already excluded in `.gitignore`.

4. Run against all test cases in `test_cases.json`:

```bash
python app.py
```

5. Or test a single custom input:

```bash
python app.py "I'm a beginner and want to learn AI, I have 8 hours a week and a low budget"
```

## Example Output

```json
{
  "status": "completed",
  "steps_used": 2,
  "final_answer": "I'd recommend the AI Fundamentals track — it matches your beginner level, 8 hours/week availability, and low budget.",
  "history": [
    {
      "thought": "I should search the catalog for AI-related beginner tracks first.",
      "action": "use_tool",
      "tool": "search_courses",
      "tool_input": "AI beginner",
      "observation": "[{...ai_fundamentals track details...}]"
    },
    {
      "thought": "AI Fundamentals matches all stated constraints.",
      "action": "final_answer",
      "final_answer": "I'd recommend the AI Fundamentals track..."
    }
  ]
}
```

## Known Weakness

Because the loop is hard-capped at `MAX_STEPS`, a genuinely ambiguous or multi-part request (e.g. `tc_11`, which describes two different students in one message) can exhaust its steps calling tools and reasoning without ever converging on a clean final answer — the run then stops with `status: "stopped_at_max_steps"` and no recommendation at all, even though useful partial reasoning happened along the way (visible in `history`).
