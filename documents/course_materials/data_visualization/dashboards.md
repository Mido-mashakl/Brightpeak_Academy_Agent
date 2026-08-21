# Building Dashboards

## Course Overview

A dashboard combines multiple charts and summary figures into a single view, giving a quick, comprehensive picture of a dataset. This material covers how to plan a dashboard and combine several charts using Matplotlib's subplot feature.

## What Makes a Good Dashboard

A good dashboard doesn't just cram every possible chart onto one screen — it's built around a specific goal, showing only the charts that answer the questions the audience actually cares about. Before building one, it helps to ask:

- Who is this dashboard for, and what decision are they trying to make?
- What are the 3-5 most important metrics or trends to show?
- Which chart type best represents each of those metrics?

## Combining Charts with Subplots

Matplotlib's `subplots()` function creates a grid of individual charts within one figure:

```python
import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 2, figsize=(10, 8))

# Top-left: enrollments over time
axes[0, 0].plot(["Jan", "Feb", "Mar"], [120, 135, 150])
axes[0, 0].set_title("Monthly Enrollments")

# Top-right: students per course
axes[0, 1].bar(["Python", "Data Structures"], [80, 65])
axes[0, 1].set_title("Students per Course")

# Bottom-left: study hours vs. score
axes[1, 0].scatter([2, 4, 6, 8], [55, 65, 75, 85])
axes[1, 0].set_title("Study Hours vs. Score")

# Bottom-right: grade distribution
axes[1, 1].hist([70, 75, 80, 85, 90, 95, 100])
axes[1, 1].set_title("Grade Distribution")

plt.tight_layout()
plt.show()
```

`subplots(2, 2, ...)` creates a 2x2 grid of individual chart areas (`axes`), each of which can be populated with a different chart type. `plt.tight_layout()` automatically adjusts spacing so the titles and labels don't overlap.

## From Static Dashboards to Interactive Ones

The example above produces a static image. For dashboards that need interactivity — filtering by date range, hovering for details — tools like Plotly or dedicated dashboard frameworks (e.g., Streamlit, Dash) are typically used instead, though the underlying principle of combining focused, purposeful charts remains the same.
