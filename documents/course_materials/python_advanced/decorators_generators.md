# Decorators and Generators

## Course Overview

Decorators and generators are two features that let Python code be more expressive and memory-efficient. This material covers how to write a decorator to modify a function's behavior, and how to use generators for lazy evaluation.

## Decorators

A decorator is a function that wraps another function to add behavior before or after it runs, without changing the original function's code.

```python
def log_call(func):
    def wrapper(*args, **kwargs):
        print(f"Calling {func.__name__}")
        result = func(*args, **kwargs)
        print(f"{func.__name__} finished")
        return result
    return wrapper

@log_call
def calculate_average(scores):
    return sum(scores) / len(scores)

calculate_average([90, 85, 92])
```

The `@log_call` syntax is shorthand for `calculate_average = log_call(calculate_average)`. Every time `calculate_average` is called, it now also prints the log messages from `wrapper`.

Decorators are commonly used for logging, timing functions, checking permissions, or caching results.

## Generators

A generator is a special kind of function that produces a sequence of values one at a time, instead of computing and storing them all in memory at once. It uses `yield` instead of `return`:

```python
def count_up_to(n):
    current = 1
    while current <= n:
        yield current
        current += 1

for number in count_up_to(5):
    print(number)
```

Each call to `yield` pauses the function and hands back a value; the function resumes right where it left off the next time a value is requested.

## Why Lazy Evaluation Matters

Because generators produce values on demand rather than all at once, they're much more memory-efficient for large or even infinite sequences. Reading a huge file line by line, or generating an endless sequence of numbers, are both practical use cases where a generator avoids loading everything into memory upfront.
