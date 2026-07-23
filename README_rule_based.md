# Brightpeak Academy - Rule-Based Agent

## Overview

This project implements a **Rule-Based Agent** for recommending learning tracks at Brightpeak Academy.

Unlike AI-based agents, this implementation does not use any language model or machine learning. It relies entirely on predefined rules (`if/elif` statements) to analyze a student's message and recommend the most suitable learning track.

---

## How It Works

The agent extracts the following information from the student's input:

- Programming level (Beginner, Intermediate, Advanced)
- Learning goal (AI, Data, Web, Mobile, Machine Learning)
- Available study hours per week
- Budget level (Low, Medium, High)

After extracting these values, the agent compares them against a fixed set of rules and recommends a track only if all required conditions are satisfied.

---

## Supported Learning Tracks

- AI Fundamentals
- Data Analysis
- Full Stack Web
- Flutter
- Machine Learning

---

## Decision Logic

The recommendation is based on four conditions:

1. Programming Level
2. Learning Goal
3. Study Hours per Week
4. Budget

If all conditions match a specific track, that track is returned.

Otherwise, the agent returns an appropriate message indicating that no suitable track could be found or that the provided information is insufficient.

---

## Limitations

Because this is a rule-based system, it has several limitations:

- It only recognizes predefined keywords.
- It cannot understand context or synonyms.
- It cannot reason about partial matches.
- It cannot explain recommendations beyond the implemented rules.
- It cannot learn from previous interactions.

These limitations are expected and are intended to be addressed by the other agent architectures in the project.

---

## Running the Agent

Run the program using:

```bash
python rule_based_agent.py
```

Or provide the student's message directly:

```bash
python rule_based_agent.py "I'm a beginner, interested in AI, with 8 hours per week and a low budget."
```

---

## Example

**Input**

```
I'm a beginner, interested in AI, with 8 hours per week and a low budget.
```

**Output**

```
AI Fundamentals
```

---

## Author

**Farida Elhoussiny**
Rule-Based Agent — Brightpeak Academy AI Agent Architectures Project