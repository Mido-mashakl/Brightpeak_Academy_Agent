
# Stacks
## Learning Objectives
By the end of this material, students should be able to:
- Explain the concept of a stack data structure.
- Describe the Last In, First Out (LIFO) principle.
- Perform push and pop operations.
- Inspect the top element of a stack.
- Implement a stack using a Python list.
- Analyze the basic time complexity of stack operations.
- Identify common applications of stacks.
## Introduction to Stacks
A stack is a linear data structure that follows the **Last In, First Out (LIFO)** principle.
LIFO means that the most recently added element is the first element to be removed.
A common real-world example is a stack of plates. When a plate is added, it is placed on top of the stack. When a plate is removed, the top plate is removed first.
A stack can be represented as:
```text
Top
 ↓
[30]
[20]
[10]

If 30 is removed, it is removed before 20 or 10.

Stack Operations

The two fundamental operations on a stack are:

* Push — adds an element to the top of the stack.
* Pop — removes the element from the top of the stack.

Other common operations include:

* Peek — returns the top element without removing it.
* is_empty — checks whether the stack contains any elements.
* Size — determines the number of elements in the stack.

Push Operation

The push operation adds a new element to the top of the stack.

Suppose the stack initially contains:

Top
 ↓
[20]
[10]

After pushing 30:

Top
 ↓
[30]
[20]
[10]

When using a Python list, the append() method can be used to implement push.

stack = []
stack.append(10)
stack.append(20)
stack.append(30)

The stack now contains:

[10, 20, 30]

The right side of the list represents the top of the stack.

Pop Operation

The pop operation removes and returns the element at the top of the stack.

stack = [10, 20, 30]
top = stack.pop()
print(top)

The output is:

30

The stack is now:

[10, 20]

The pop() method is suitable for implementing stack behavior because it removes the last element of a Python list.

Peek Operation

A peek operation examines the top element without removing it.

With a Python list, the last element can be accessed using index -1.

stack = [10, 20, 30]
top = stack[-1]
print(top)

The output is:

30

The stack remains unchanged:

[10, 20, 30]

Checking Whether a Stack Is Empty

Before attempting to remove or inspect an element, it is often useful to check whether the stack is empty.

A Python list can be checked using:

if not stack:
    print("The stack is empty.")

Alternatively:

if len(stack) == 0:
    print("The stack is empty.")

The first form is commonly preferred in Python because an empty list evaluates to False.

Implementing a Stack

A simple stack can be implemented using a Python class.

class Stack:
    def __init__(self):
        self.items = []
    def push(self, item):
        self.items.append(item)
    def pop(self):
        if not self.items:
            return None
        return self.items.pop()
    def peek(self):
        if not self.items:
            return None
        return self.items[-1]
    def is_empty(self):
        return not self.items
    def size(self):
        return len(self.items)

The stack can then be used as follows:

stack = Stack()
stack.push(10)
stack.push(20)
stack.push(30)
print(stack.peek())
print(stack.pop())
print(stack.pop())

The output is:

30
30
20

After the operations, the stack contains only 10.

Stack Overflow and Underflow

Two common conditions associated with stacks are overflow and underflow.

Stack Overflow

Stack overflow occurs when a program attempts to add an element to a stack that has reached its maximum capacity.

A Python list can grow dynamically, so a basic list-based implementation does not normally have a fixed stack capacity. However, overflow can occur in stack implementations that use a fixed-size storage area.

Stack Underflow

Stack underflow occurs when a program attempts to remove an element from an empty stack.

For example:

stack = []
item = stack.pop()

This raises an IndexError because there is no element to remove.

A safer implementation checks the stack first:

if stack:
    item = stack.pop()
else:
    print("Cannot pop from an empty stack.")

Stack Time Complexity

When a Python list is used with the end of the list as the top of the stack, the main stack operations are generally efficient.

Operation	Typical Time Complexity
Push	O(1) amortized
Pop	O(1)
Peek	O(1)
Check if empty	O(1)
Size	O(1)

Using the beginning of a Python list as the top of the stack is less efficient because inserting or removing the first element requires shifting the remaining elements.

For example, this approach is generally less suitable for a stack:

stack.insert(0, 10)
stack.pop(0)

Using append() and pop() at the end of the list is usually preferable.

Applications of Stacks

Stacks are widely used in computer science and software development.

Common applications include:

* Function call management.
* Expression evaluation.
* Undo and redo functionality.
* Browser history navigation.
* Backtracking algorithms.
* Depth-first search.
* Parsing nested structures.
* Matching parentheses and other delimiters.

Function Call Stack

Programming languages use a call stack to keep track of active function calls.

Consider the following example:

def first():
    second()
def second():
    third()
def third():
    print("Hello")
first()

When first() is called, it is placed on the call stack. Then second() is called and placed above it. Finally, third() is added.

Conceptually:

Top
 ↓
third()
second()
first()

When third() finishes, it is removed first. Then second() finishes, followed by first().

This follows the LIFO principle.

Undo Operations

Stacks can be used to implement undo functionality.

For example, an application can store previous states:

history = []
history.append("State 1")
history.append("State 2")
history.append("State 3")

To undo the most recent state:

previous_state = history.pop()

The most recently stored state is removed first.

Parentheses Matching

Stacks are useful for checking whether opening and closing parentheses are properly matched.

For example:

(( ))

can be processed by adding opening parentheses to a stack and removing one whenever a matching closing parenthesis is encountered.

A simplified implementation is:

def is_balanced(expression):
    stack = []
    for char in expression:
        if char == "(":
            stack.append(char)
        elif char == ")":
            if not stack:
                return False
            stack.pop()
    return not stack

For example:

print(is_balanced("(a + b)"))

returns:

True

An unmatched closing parenthesis causes the function to return False.

Stack vs Queue

Stacks and queues are both linear data structures, but they process elements differently.

A stack follows LIFO:

Last In → First Out

A queue follows FIFO:

First In → First Out

For example, if the values 10, 20, and 30 are added in that order:

Stack removal order:

30 → 20 → 10

Queue removal order:

10 → 20 → 30

The appropriate structure depends on the problem being solved.

Common Errors

One common mistake is attempting to pop from an empty stack.

stack = []
stack.pop()

This raises an IndexError.

Another common mistake is using the wrong end of a Python list for stack operations.

For example:

stack.insert(0, 10)
stack.pop(0)

These operations can require shifting elements and may be inefficient for large lists.

A better implementation uses the end of the list:

stack.append(10)
stack.pop()

Summary

A stack is a linear data structure that follows the Last In, First Out (LIFO) principle.

The main operations are:

* Push — add an element to the top.
* Pop — remove and return the top element.
* Peek — inspect the top element without removing it.
* is_empty — determine whether the stack contains elements.

In Python, a list can efficiently implement a stack by using append() for push and pop() for removal.

Stacks are important in many areas of computer science, including function calls, undo systems, expression evaluation, backtracking, and depth-first search.