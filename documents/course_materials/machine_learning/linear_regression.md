# Linear Regression

## Course Overview

Linear regression is one of the simplest and most widely used supervised learning algorithms. It models the relationship between one or more input features and a continuous numeric output by fitting a straight line (or a flat plane, in higher dimensions) to the data.

## The Basic Idea

For a single feature, linear regression tries to find the line that best fits the data points:

```
y = m*x + b
```

Where `x` is the input feature, `y` is the predicted value, `m` is the slope, and `b` is the intercept. The model learns the values of `m` and `b` that make the line's predictions as close as possible to the actual training values.

## Fitting a Line to Data

The most common way to measure how well a line fits is **mean squared error (MSE)**: for each data point, calculate the difference between the actual value and the predicted value, square it, and average the result across all points. A lower MSE means a better fit.

Training the model means searching for the `m` and `b` that minimize this error, often using an optimization method called gradient descent.

## Interpreting Coefficients

Once trained, the coefficients have a direct meaning:

- The **slope (m)** tells you how much the predicted output changes for a one-unit increase in the input feature.
- The **intercept (b)** is the predicted value when the input feature is zero.

For example, if a model predicting house price from square footage has a slope of 150, it means each additional square foot is associated with an estimated $150 increase in price.

## When to Use Linear Regression

Linear regression works best when the relationship between features and the target is roughly linear. It's a good first model to try because it's fast, easy to interpret, and gives a useful baseline before trying more complex models.
