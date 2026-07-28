# Brightpeak Academy — Unconstrained ReAct Agent

An **Unconstrained ReAct Agent** that recommends the most suitable learning track for Brightpeak Academy students using a free-form **Thought → Action → Observation** loop.

Unlike constrained agents, the model freely decides how to reason, which tools to use, and when to stop.

---

## Project Structure

```
.
├── app.py                  # Main agent + ReAct loop
├── tracks_dataset.json     # Available learning tracks
├── test_cases.json         # 11 test cases (easy + tricky)
├── results.json            # Per-case output (auto-generated)
└── summary.json            # Aggregate stats  (auto-generated)

---

## Architecture

```
Student Input
      │
      ▼
Thought → Action → Observation
      ▲              │
      └──── repeat ──┘
             │
             ▼
      Final Answer
```

### Characteristics

- Free-form reasoning
- No schema validation
- No tool restrictions
- No MAX_STEPS limit
- Model decides when to stop

---

## Tools

| Tool | Purpose |
|------|---------|
| `search_tracks()` | Find matching learning tracks |
| `get_track_details()` | Retrieve detailed track information |

---

## Setup

```bash
pip install google-generativeai python-dotenv
```

Create a `.env` file:

```
GEMINI_API_KEY=your_api_key
```

---

## Usage

Run one query:

```bash
python app.py "I'm a beginner interested in AI with 8 hrs/week."
```

Run all test cases:

```bash
python app.py
```

---

## Results

Each execution records:

- Reasoning steps
- Model calls
- Tool calls
- Latency
- Recommended track
- PASS / FAIL status

A test passes when **all expected tracks** appear in the final recommendation, including multi-track cases.

Example summary:

```json
{
  "evaluated": 8,
  "passed": 8,
  "failed": 0,
  "average_steps": 4.09,
  "average_latency": 3.28
}
```

---
## Known Limitations

- **Missing information handling** *(tc_04_missing_information)*  
  The agent may recommend tracks even when the student's profile is incomplete instead of asking for clarification.

- **Prompt injection overhead** *(tc_08_adversarial_input)*  
  The agent correctly ignores malicious instructions but requires multiple reasoning steps, increasing latency and token usage.

- **Constraint prioritization** *(tc_06_multiple_valid_goals)*  
  When multiple tracks partially match the student's profile, the agent may not clearly prioritize the best overall recommendation.

- **Redundant tool calls** *(tc_01_easy_match, tc_02_easy_match)*  
  The agent sometimes calls `get_track_details()` even when the search results already contain enough information for a recommendation.

## Model

| Property | Value |
|----------|-------|
| Provider | Google Gemini |
| Model | `gemini-flash-lite-latest` |
| Temperature | 0.0 |