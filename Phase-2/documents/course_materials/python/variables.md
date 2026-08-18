
# Python Variables and Data Types

## Learning Objectives

By the end of this material, students should be able to:

- Explain what a variable is in Python.
- Assign and update values stored in variables.
- Identify common built-in Python data types.
- Use the `type()` function to inspect a value's type.
- Apply basic type conversion when working with different data types.

## Variables

A variable is a name that refers to a value in a Python program. Variables allow programs to store, access, and modify information during execution.

A variable is created when a value is assigned to a name using the assignment operator (`=`).

```python
student_name = "Sara"
age = 20
gpa = 3.7
````

In this example, `student_name` refers to a string value, `age` refers to an integer value, and `gpa` refers to a floating-point value.

Python does not require a programmer to declare a variable's data type before assigning a value. The type of the value is determined at runtime.

## Assignment and Reassignment

A variable can be assigned a new value after it has been created.

```python
score = 75
score = 90
```

After the second assignment, `score` refers to the integer value `90`.

Variables can also be used in expressions.

```python
midterm = 85
final_exam = 92

total = midterm + final_exam
```

The value of `total` is calculated using the current values stored in `midterm` and `final_exam`.

## Dynamic Typing

Python is dynamically typed. This means that a variable name can refer to values of different types during the execution of a program.

For example:

```python
value = 10
value = "Python"
```

Initially, `value` refers to an integer. After the second assignment, it refers to a string.

Dynamic typing provides flexibility, but programmers should still choose meaningful variable names and keep track of the types of values used in their programs.

## Numeric Data Types

Python provides several numeric data types. Two commonly used types in introductory programming are `int` and `float`.

The `int` type represents whole numbers.

```python
student_count = 120
year = 2026
```

The `float` type represents numbers that contain a decimal component.

```python
average_grade = 87.5
temperature = 21.4
```

Python also provides the `complex` type for complex numbers, although it is less commonly required in introductory programming.

## Strings

The `str` type represents text.

Strings can be created using single or double quotation marks.

```python
first_name = "Sara"
course_name = 'Introduction to Python'
```

Strings can contain letters, numbers, spaces, and other characters.

```python
student_id = "ST2026"
```

Although `student_id` contains digits, it is a string because it is enclosed in quotation marks.

## Boolean Values

The `bool` type represents a logical value. It has two possible values:

* `True`
* `False`

Boolean values are commonly used when representing conditions or states.

```python
is_enrolled = True
has_completed_course = False
```

Boolean expressions are particularly important when working with conditional statements and control flow.

## Checking Data Types

The built-in `type()` function can be used to determine the type of a value.

```python
score = 95
print(type(score))
```

The output indicates that `score` is an integer.

The same function can be used with other values:

```python
name = "Sara"
gpa = 3.7
is_enrolled = True

print(type(name))
print(type(gpa))
print(type(is_enrolled))
```

## Type Conversion

Type conversion is the process of converting a value from one data type to another.

Python provides built-in functions such as:

* `int()` for converting values to integers
* `float()` for converting values to floating-point numbers
* `str()` for converting values to strings
* `bool()` for converting values to Boolean values

For example:

```python
age_text = "20"
age = int(age_text)
```

After the conversion, `age` contains the integer value `20`.

A string containing a decimal number can be converted to a floating-point value:

```python
grade_text = "87.5"
grade = float(grade_text)
```

An integer can also be converted into a string:

```python
student_id = 2026
student_id_text = str(student_id)
```

## Input and Variable Types

The `input()` function always returns the user's input as a string.

For example:

```python
age = input("Enter your age: ")
```

Even if the user enters `20`, the value stored in `age` is a string.

If the program needs to perform arithmetic using the input, the value should be converted to an appropriate numeric type.

```python
age = int(input("Enter your age: "))
```

This converts the entered text into an integer.

## Variable Naming Conventions

Python variable names should be descriptive and follow established naming conventions.

Variable names may contain letters, digits, and underscores, but they cannot begin with a digit.

Good examples include:

```python
student_name = "Sara"
course_count = 5
final_grade = 88
```

Names such as `student_name` are generally preferable to unclear names such as `x` when the purpose of the value is not obvious.

Python variable names are case-sensitive.

For example:

```python
score = 90
Score = 75
```

`score` and `Score` are two different variable names.

## Constants

Python does not enforce constants through a special variable type. However, programmers commonly use uppercase names to indicate that a value is intended to remain unchanged.

For example:

```python
MAX_ATTEMPTS = 3
PASSING_GRADE = 60
```

These naming conventions communicate the intended use of the values to other developers.

## Common Errors

One common error occurs when attempting to convert a value that is not compatible with the target type.

For example:

```python
age = int("twenty")
```

This raises a `ValueError` because `"twenty"` cannot be interpreted as an integer.

Another common issue occurs when a programmer assumes that input from `input()` is already numeric.

```python
first_number = input("Enter the first number: ")
second_number = input("Enter the second number: ")

total = first_number + second_number
```

If the user enters `10` and `20`, the result is the string `"1020"` rather than the numeric value `30`.

The correct approach is to convert the inputs:

```python
first_number = int(input("Enter the first number: "))
second_number = int(input("Enter the second number: "))

total = first_number + second_number
```

## Summary

Variables provide names that allow programs to store and work with values. Python is dynamically typed, so variables do not require explicit type declarations.

Important built-in data types include `int`, `float`, `str`, and `bool`. The `type()` function can be used to inspect the type of a value, while functions such as `int()`, `float()`, and `str()` can be used for type conversion.

Understanding variables and data types is essential before studying control flow, functions, data structures, and more advanced Python programming concepts.