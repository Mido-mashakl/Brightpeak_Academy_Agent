````markdown
# Introduction to Python

## Course Overview

Python is a high-level, general-purpose programming language widely used in software development, data analysis, scientific computing, automation, and artificial intelligence. Its syntax is designed to emphasize readability and reduce unnecessary complexity.

This material introduces fundamental Python concepts that students should understand before moving to more advanced programming topics.

## Variables and Assignment

A variable is a name that refers to a value in a Python program. Variables are created when a value is assigned to a name using the assignment operator (`=`).

For example:

```python
student_name = "Sara"
age = 20
gpa = 3.7
````

In this example, `student_name` refers to a string, `age` refers to an integer, and `gpa` refers to a floating-point number.

Python is dynamically typed, which means that the programmer does not need to declare the type of a variable before assigning a value. The type is determined at runtime from the value currently referenced by the variable.

## Common Data Types

Python provides several built-in data types that are commonly used in introductory programming.

The most frequently used types include:

* `int` for whole numbers
* `float` for decimal numbers
* `str` for text
* `bool` for logical values

Examples:

```python
student_count = 120
average_grade = 87.5
student_name = "Sara"
is_enrolled = True
```

The `type()` function can be used to determine the type of a value or variable.

```python
score = 95
print(type(score))
```

The result identifies `score` as an integer.

## Basic Input and Output

Python uses the `print()` function to display information to the standard output.

```python
print("Welcome to Python")
```

The `input()` function can be used to read text entered by the user.

```python
name = input("Enter your name: ")
print("Hello", name)
```

Values returned by `input()` are strings by default. If a numeric value is required, the input should be converted explicitly.

```python
age = int(input("Enter your age: "))
```

## Arithmetic Operators

Python supports standard arithmetic operations.

The main arithmetic operators are:

* `+` addition
* `-` subtraction
* `*` multiplication
* `/` division
* `//` floor division
* `%` remainder
* `**` exponentiation

For example:

```python
a = 10
b = 3

print(a + b)
print(a - b)
print(a * b)
print(a / b)
print(a // b)
print(a % b)
print(a ** b)
```

The division operator `/` produces a floating-point result, while `//` performs floor division.

## Comparison and Boolean Expressions

Comparison operators are used to compare values. The result of a comparison is a Boolean value: `True` or `False`.

Common comparison operators include:

* `==` equal to
* `!=` not equal to
* `>` greater than
* `<` less than
* `>=` greater than or equal to
* `<=` less than or equal to

Example:

```python
score = 85

print(score >= 60)
print(score == 100)
```

Boolean operators can be used to combine conditions.

The main Boolean operators are `and`, `or`, and `not`.

```python
age = 20
has_id = True

can_enter = age >= 18 and has_id
```

## Comments

Comments are notes written in source code to explain the purpose or behavior of the code. Python ignores comments during program execution.

A single-line comment begins with the `#` character.

```python
# Calculate the student's final score
final_score = 92
```

Comments should be concise and should clarify the intent of the code when necessary.

## Naming Variables

Variable names should be descriptive and follow Python naming conventions.

A variable name can contain letters, digits, and underscores, but it cannot begin with a digit.

Recommended examples:

```python
student_name = "Sara"
course_count = 5
final_grade = 88
```

Names such as `student_name` are generally preferred over unclear names such as `x` when the meaning of the value is important.

Python variable names are case-sensitive. For example, `score`, `Score`, and `SCORE` are treated as different names.

## Type Conversion

Python provides built-in functions for converting values between compatible data types.

Common conversion functions include:

* `int()`
* `float()`
* `str()`
* `bool()`

Example:

```python
age_text = "20"
age = int(age_text)

average = float("87.5")
```

Type conversion is especially important when working with values received from `input()`, since user input is initially returned as a string.

## Summary

The fundamental concepts introduced in this material include variables, assignment, common data types, input and output, arithmetic operations, Boolean expressions, comments, naming conventions, and type conversion.

Students should be comfortable with these concepts before progressing to control flow, functions, collections, and object-oriented programming.

```
```
