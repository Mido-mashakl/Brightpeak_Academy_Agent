# Brightpeak Agent Project

## About the Company

Brightpeak Academy is an educational institution that provides professional training programs in technology and digital skills. It offers structured learning paths, mentorship, and practical projects to help students prepare for careers in software development, data science, and AI.

## The Problem

New students often struggle to choose the most suitable learning track because their backgrounds, goals, and experience levels differ significantly. A student's ideal track depends on multiple interacting factors:

- Prior experience (beginner, intermediate, advanced)
- Career goal (web development, data science, AI, etc.)
- Time available per week
- Budget
- Existing skills and preferences (e.g., dislike of math-heavy content)
  
## Why an Agent (and not a simple script)?

A simple `if/else` script can only handle rigid, predictable combinations of inputs. For example:

```python
if experience == "beginner" and goal == "AI":
    recommend("AI Fundamentals Track")
```

This breaks down quickly once real students provide messy, overlapping, or incomplete information — such as:

> "I know some Python, but I also want AI, I only have two hours per week, and I hate math."

Answering this well requires **reasoning**, not pattern matching:
- Weighing competing constraints (limited time vs. ambitious goal)
- Deciding whether to ask a clarifying question or make a best-effort recommendation
- Choosing which tool/knowledge source to consult (course catalog, student history, FAQ)
- Justifying the recommendation in natural language

This is exactly the kind of open-ended decision-making that an LLM-based agent is suited for, and a fixed script is not.

## Project Structure

```text
Brightpeak-Agent-Project/
│
├── README.md
│
├── reactive/
│     ├── app.py
│     └── README.md
│
├── unconstrained_react/
│     ├── app.py
│     └── README.md
│
├── routing/
│     ├── app.py
│     └── README.md
│
├── constrained_react/
│     ├── app.py
│     ├── schema.py
│     ├── tools.py
│     ├── config.py      ← MAX_STEPS and ALLOWED_TOOLS
│     └── README.md
│
└── presentation/
      └── slides.pptx
```

Each folder is a **standalone, runnable mini-project** it can be run independently without depending on the other folders. Each folder contains its own README with setup and run instructions.

## Architecture Comparison

| Architecture  | Model Calls | Cost (rough) | Latency   | Weakness                          |
| ------------- | ----------- | ------------ | --------- | ---------------------------------- |
| Reactive      | 0           | Free         | Very Fast | Cannot handle complex/edge cases   |
| Unconstrained | Multiple    | High         | Slow      | May loop or hallucinate            |
| Routing       | 1           | Low          | Fast      | Limited flexibility                |
| Constrained   | Multiple    | Medium       | Medium    | Stops at MAX_STEPS                 |

## Stress Test: A Tricky Input

To evaluate the four architectures, we tested them all with the same intentionally messy input:

> "I know some Python, but I also want AI, I only have two hours per week, and I hate math."

| Architecture  | Result                                                                                    |
| ------------- | ------------------------------------------------------------------------------------------ |
| Reactive      | Fails gives an incorrect or generic answer, cannot reason over conflicting constraints    |
| Unconstrained | Solves it, but takes multiple exploratory steps and calls                                  |
| Routing       | Classifies the request into the closest matching track category                            |
| Constrained   | Reasons step by step but halts once `MAX_STEPS` is reached                                  |

*(See each folder's README for the actual transcript/output of this test.)*

## Team & Contributions

| Member  | Responsibility                                              |
| ------- | ------------------------------------------------------------ |
| Ahmed   | Reactive + contribution to README and comparison table       |
| Omar    | Unconstrained ReAct                                          |
| Fareeda | Routing                                                      |
| All     | Constrained ReAct (most complex) + final presentation        |

No team member owns more than two components, and no one is responsible for the presentation only — every member contributed code.
