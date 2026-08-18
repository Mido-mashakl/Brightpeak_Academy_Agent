# Classification

## Course Overview

Classification is a supervised learning task where the goal is to predict a discrete category (a label from a fixed set) rather than a continuous number. This material covers what distinguishes classification from regression, the idea of decision boundaries, and how classification models are evaluated.

## Classification vs. Regression

Both are supervised learning tasks, but they differ in the type of output:

- **Regression** predicts a continuous value (e.g., a price, a temperature).
- **Classification** predicts a category (e.g., "spam" or "not spam", "cat" or "dog").

Some algorithms can be adapted for either task, but the way predictions are made and evaluated is different.

## Decision Boundaries

A classification model works by learning a **decision boundary**: a line or surface in the feature space that separates one class from another. When a new data point comes in, the model checks which side of the boundary it falls on and predicts the corresponding class.

For simple two-class problems with two features, this boundary can often be visualized as a line separating two clusters of points on a graph. More complex models can learn curved or highly flexible boundaries.

## Measuring Accuracy

**Accuracy** is the simplest evaluation metric: the percentage of predictions the model got right out of all predictions made.

```
accuracy = correct predictions / total predictions
```

Accuracy is easy to understand, but it can be misleading when the classes are imbalanced. For example, if 95% of emails are not spam, a model that always predicts "not spam" would score 95% accuracy while being useless at catching spam. For imbalanced problems, other metrics such as precision and recall give a more complete picture.

## Summary

Classification problems are everywhere in real applications: detecting fraud, diagnosing whether an image contains a certain object, or filtering spam. Understanding decision boundaries and knowing when accuracy alone isn't enough are key first steps before moving to specific classification algorithms.
