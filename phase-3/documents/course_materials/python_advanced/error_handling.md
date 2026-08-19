# Error Handling and Testing

## Course Overview

Real-world programs need to handle unexpected situations gracefully and be verified to work correctly. This material covers exceptions and `try`/`except` for error handling, and the basics of writing unit tests.

## Exceptions

An exception is Python's way of signaling that something went wrong while a program is running — for example, dividing by zero or accessing a key that doesn't exist in a dictionary.

```python
def get_grade(scores, index):
    return scores[index]

get_grade([90, 85, 92], 10)  # IndexError: list index out of range
```

Without handling, an exception stops the program immediately and prints a traceback.

## try/except

`try`/`except` lets a program catch an exception and respond instead of crashing:

```python
def get_grade(scores, index):
    try:
        return scores[index]
    except IndexError:
        return None

get_grade([90, 85, 92], 10)  # returns None instead of crashing
```

You can catch specific exception types (like `IndexError` or `ValueError`) to handle different failure cases differently, or use a general `except Exception` to catch anything unexpected. An optional `finally` block runs regardless of whether an exception occurred, often used for cleanup.

## Writing Unit Tests

A unit test checks that a small piece of code (a "unit," usually a function) behaves as expected. Python's built-in `unittest` module is a common way to write these:

```python
import unittest

def add(a, b):
    return a + b

class TestAdd(unittest.TestCase):
    def test_add_positive_numbers(self):
        self.assertEqual(add(2, 3), 5)

    def test_add_negative_numbers(self):
        self.assertEqual(add(-1, -1), -2)

if __name__ == "__main__":
    unittest.main()
```

Each `test_` method checks one specific behavior. Running the test suite regularly catches bugs early, especially when changing existing code, since a broken test immediately signals something no longer works as expected.
