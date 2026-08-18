# Introduction to Machine Learning

## Course Overview

Machine learning (ML) is a field of computer science that gives systems the ability to learn patterns from data instead of being explicitly programmed with fixed rules. Instead of writing step-by-step instructions for every scenario, a model is trained on examples and learns to make predictions on new, unseen data.

This material introduces the core vocabulary and the main categories of learning that later lectures (regression, classification) build on.

## Supervised vs. Unsupervised Learning

In **supervised learning**, the training data includes both the input features and the correct output (called the label or target). The model learns a mapping from inputs to outputs by comparing its predictions to the known correct answers and adjusting itself to reduce the error.

Examples of supervised learning tasks:

- Predicting house prices from square footage and location (regression)
- Classifying an email as spam or not spam (classification)

In **unsupervised learning**, the data has no labels. The model looks for structure or patterns on its own, such as grouping similar data points together (clustering) or reducing the number of features while keeping the important information (dimensionality reduction).

## Why the Distinction Matters

Choosing between supervised and unsupervised approaches depends on the problem: if you have historical examples with known outcomes, supervised learning is usually the right starting point. If you're exploring data to find hidden groupings or structure, unsupervised methods are more appropriate.

## Key Terms

- **Feature**: an input variable used to make a prediction (e.g., square footage)
- **Label**: the known correct output in supervised learning (e.g., the actual price)
- **Model**: the mathematical function learned from training data
- **Training**: the process of adjusting a model so its predictions get closer to the correct labels
