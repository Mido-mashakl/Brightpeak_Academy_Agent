````markdown
# Python Functions
## Learning Objectives
By the end of this material, students should be able to:
- Explain what a function is and why functions are useful.
- Define and call functions in Python.
- Distinguish between parameters and arguments.
- Use return statements to produce values from functions.
- Define functions with default and multiple parameters.
- Understand the scope of variables within functions.
## What Is a Function?
A function is a reusable block of code that performs a specific task. Functions help organize programs into smaller, manageable units and reduce code duplication.
A function is defined using the `def` keyword.
```python
def greet():
    print("Hello, welcome to Python!")

The function above defines a function named greet. Defining a function does not execute its code. The function must be called before its statements are executed.

greet()

When greet() is called, Python executes the statements inside the function.

Function Parameters

A parameter is a variable defined in a function’s declaration. Parameters allow a function to receive information from the code that calls it.

For example:

def greet_student(name):
    print("Hello", name)

In this example, name is a parameter.

When the function is called, a value is provided for the parameter:

greet_student("Sara")

The value "Sara" is passed to the parameter name.

Arguments

An argument is the actual value supplied to a function when the function is called.

For example:

def calculate_square(number):
    return number * number
result = calculate_square(5)

In this example, number is the parameter, while 5 is the argument.

The distinction is important:

* A parameter is a variable listed in the function definition.
* An argument is a value supplied when calling the function.

Return Values

A function can use the return statement to send a value back to the code that called it.

def add_numbers(a, b):
    return a + b

The returned value can be stored in a variable:

result = add_numbers(10, 20)
print(result)

The value of result is 30.

A function can return different types of values depending on what the function is designed to calculate.

def get_course_name():
    return "Introduction to Python"

Functions Without a Return Statement

A function does not always need to return a value.

def display_message():
    print("Welcome to the course!")

This function performs an action but does not explicitly return a value.

If a function reaches the end without executing a return statement, Python returns None.

Multiple Parameters

A function can accept more than one parameter.

def calculate_average(first_grade, second_grade):
    return (first_grade + second_grade) / 2

The function can be called with two arguments:

average = calculate_average(80, 90)
print(average)

The first argument is assigned to first_grade, and the second argument is assigned to second_grade.

Positional Arguments

By default, Python matches arguments to parameters according to their position.

def display_student(name, age):
    print(name)
    print(age)
display_student("Sara", 20)

The first argument, "Sara", is assigned to name, while the second argument, 20, is assigned to age.

The order of positional arguments therefore matters.

Keyword Arguments

Arguments can also be passed using parameter names.

def display_student(name, age):
    print(name)
    print(age)
display_student(age=20, name="Sara")

Keyword arguments allow values to be associated explicitly with parameter names, so their order does not need to match the function definition.

Default Parameters

A function parameter can have a default value.

def greet_student(name, course="Python"):
    print(name, "is studying", course)

If the course argument is omitted, Python uses the default value.

greet_student("Sara")

The function uses "Python" as the course.

A different value can still be provided explicitly:

greet_student("Sara", "Data Structures")

Variable Scope

The scope of a variable determines where that variable can be accessed.

A variable created inside a function is generally local to that function.

def calculate_score():
    score = 95
    print(score)
calculate_score()

The variable score exists within the local scope of calculate_score.

Attempting to access the local variable outside the function results in an error:

def calculate_score():
    score = 95
calculate_score()
print(score)

Variables defined outside functions generally belong to the global scope.

Function Documentation

Functions should have clear names that describe their purpose. A docstring can be used to document what a function does.

def calculate_total(price, quantity):
    """Return the total cost for a given price and quantity."""
    return price * quantity

Good documentation helps other developers understand how a function should be used.

Reusing Functions

One of the main advantages of functions is code reuse.

Instead of repeating the same calculation several times:

def calculate_total(price, quantity):
    return price * quantity
first_total = calculate_total(50, 2)
second_total = calculate_total(25, 4)
third_total = calculate_total(100, 3)

The same function can be called with different arguments.

This approach makes programs easier to maintain and reduces duplicated code.

Function Design Principles

A well-designed function should generally have a clear and focused responsibility.

For example:

def calculate_average(grades):
    return sum(grades) / len(grades)

This function has a specific purpose: calculating an average.

Functions that attempt to perform many unrelated tasks can become difficult to understand, test, and maintain.

When designing functions, students should consider:

* Giving functions descriptive names.
* Keeping each function focused on a clear task.
* Using parameters to make functions reusable.
* Returning values when the result needs to be used elsewhere.
* Documenting non-obvious behavior.

Common Errors

A common error is calling a function with the wrong number of arguments.

For example:

def add_numbers(a, b):
    return a + b
result = add_numbers(10)

This raises a TypeError because the function requires two arguments but only one was provided.

Another common mistake is confusing printing with returning a value.

def add_numbers(a, b):
    print(a + b)

The function displays the result, but it does not return it.

If the result needs to be stored or used in another calculation, the function should return the value:

def add_numbers(a, b):
    return a + b
result = add_numbers(10, 20)

Summary

Functions are reusable blocks of code designed to perform specific tasks. They are defined using the def keyword and executed when called.

Parameters are variables defined in a function, while arguments are the values supplied when the function is called. Functions can accept multiple parameters, use default values, and return results using the return statement.

Understanding functions is an essential step toward writing modular, reusable, and maintainable Python programs.