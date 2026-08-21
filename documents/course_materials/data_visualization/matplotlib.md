# Plotting with Matplotlib

## Course Overview

Matplotlib is one of the most widely used Python libraries for creating charts. This material covers how to create line, bar, and scatter plots — the three chart types introduced in the previous material.

## Line Plot

A line plot is created with `plot()` and is ideal for showing a trend over time:

```python
import matplotlib.pyplot as plt

months = ["Jan", "Feb", "Mar", "Apr"]
enrollments = [120, 135, 150, 142]

plt.plot(months, enrollments)
plt.title("Monthly Enrollments")
plt.xlabel("Month")
plt.ylabel("Number of Students")
plt.show()
```

## Bar Chart

A bar chart is created with `bar()` and works well for comparing values across categories:

```python
courses = ["Python", "Data Structures", "Machine Learning"]
students = [80, 65, 50]

plt.bar(courses, students)
plt.title("Students per Course")
plt.ylabel("Number of Students")
plt.show()
```

## Scatter Plot

A scatter plot is created with `scatter()` and is useful for visualizing the relationship between two numeric variables:

```python
study_hours = [2, 4, 6, 8, 10]
exam_scores = [55, 65, 75, 85, 95]

plt.scatter(study_hours, exam_scores)
plt.title("Study Hours vs. Exam Score")
plt.xlabel("Study Hours")
plt.ylabel("Exam Score")
plt.show()
```

## Customizing Plots

All three chart types share common customization options:

- `plt.title()`, `plt.xlabel()`, `plt.ylabel()` — add labels for context
- `plt.legend()` — display a legend when plotting multiple data series
- `plt.grid(True)` — add gridlines to make values easier to read

## Saving a Plot

Instead of (or in addition to) `plt.show()`, a chart can be saved to a file:

```python
plt.savefig("enrollments.png")
```

Matplotlib's consistent API across chart types — set up the data, choose the plot function, add labels, then display or save — makes it straightforward to move between different chart types once you're comfortable with the basics.
