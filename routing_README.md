# Routing Architecture

## Model

Gemini Flash-Lite

## How It Works

This is the **routing** approach: the student's message is sent to the LLM exactly once, along with the full list of tracks from `tracks_dataset.json`. The model classifies the input into the single best-matching `track_id` (or `no_match`) and returns a short reason.

There is no tool use, no multi-step loop, and no follow-up questioning — just one classification call per request.

**Trade-off:** this makes routing fast and cheap, but it can struggle with inputs that don't cleanly fit one track (conflicting constraints, missing information, multiple valid goals) since it never gets a chance to ask a clarifying question or reason step by step.

## Files

```text
routing/
├── app.py               ← main script
├── tracks_dataset.json  ← the 5 available tracks
├── test_cases.json      ← easy + tricky test inputs
├── .env.example          ← copy to .env and add your real key
└── README.md
```

## How to Run

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Get a free Gemini API key from https://aistudio.google.com/apikey

3. Set your API key by creating a `.env` file in this folder (copy `.env.example` and fill in your real key):

```text
GEMINI_API_KEY=your-real-key-here
```

The script loads this automatically via `python-dotenv`. **Never commit your real `.env` file, and never paste your real key anywhere public (chat, GitHub, etc.)** — it's already excluded in `.gitignore`.

4. Run against all test cases in `test_cases.json`:

```bash
python app.py
```

5. Or test a single custom input:

```bash
python app.py "I'm a beginner and want to learn AI, I have 8 hours a week and a low budget"
```

### Routing — Full Test Results (11 cases)
 
Model: Gemini Flash-Lite. Full test cases and code in `routing/`.
 
| Test Case | Expected                     | Routed To         | Match? |
| --------- | ----------------------------- | ------------------ | :----: |
| tc_01     | AI Fundamentals                | ai_fundamentals     | ✅ |
| tc_02     | Full Stack Web                 | full_stack_web      | ✅ |
| tc_03     | AI Fundamentals (with caveat)  | no_match            | ⚠️ |
| tc_04     | Ask a clarifying question      | ai_fundamentals     | ⚠️ |
| tc_05     | Machine Learning (with caveat) | no_match            | ⚠️ |
| tc_06     | Flutter                        | flutter             | ✅ |
| tc_07     | Out of scope                   | no_match            | ✅ |
| tc_08     | Resist the injected instruction| no_match            | ✅ |
| tc_09     | AI Fundamentals                | ai_fundamentals     | ✅ |
| tc_10     | Data Analysis                  | data_analysis       | ✅ |
| tc_11     | Full Stack Web + Data Analysis | data_analysis only  | ⚠️ |
 
**7 / 11 correct, 4 revealing real weaknesses of the routing architecture:**
 
1. **Binary, all-or-nothing decisions (tc_03, tc_05).** The model has no way to say "close but not perfect" — it either commits fully to a track or returns `no_match`. Both cases have a clear best-fit track with one violated constraint (hours or budget), but routing discards the recommendation entirely instead of surfacing it with a warning. This is the direct cause of the "Limited flexibility" weakness listed in the comparison table above.
2. **Guesses instead of asking (tc_04).** With zero information given, the correct behavior is a clarifying question. Since routing makes exactly one call with no ability to go back to the student, it defaulted to guessing `ai_fundamentals` as a "safe" beginner option rather than admitting it doesn't have enough information.
3. **Drops information when multiple entities are present (tc_11).** Given a message describing two different people, the model routed only the speaker and silently ignored the second profile instead of returning two recommendations. Single-shot classification isn't built to handle multi-entity inputs.
