````markdown
# Arrays and Lists in Python
## Learning Objectives
By the end of this material, students should be able to:
- Explain how Python lists are used to store collections of values.
- Create and access elements in a list.
- Use indexing and slicing.
- Add, update, and remove elements.
- Iterate through a list.
- Apply common list operations and methods.
## Introduction to Lists
Python provides a built-in data structure called a list for storing an ordered collection of values.
A list can contain multiple values, and the values do not have to be of the same type.
```python
students = ["Sara", "Omar", "Mona"]

A list can also contain numeric values:

scores = [85, 92, 78, 90]

Lists are ordered and mutable. This means that elements have a defined position and the contents of a list can be changed after the list is created.

Creating a List

A list is created using square brackets.

courses = ["Python", "Data Structures", "Databases"]

An empty list can be created as follows:

courses = []

Elements can be added later.

courses.append("Python")
courses.append("Databases")

Indexing

Each element in a list has an index. Python uses zero-based indexing, meaning that the first element has index 0.

students = ["Sara", "Omar", "Mona"]
print(students[0])
print(students[1])
print(students[2])

The output is:

Sara
Omar
Mona

The index of the last element can also be accessed using -1.

print(students[-1])

This returns "Mona".

Negative indexes count backward from the end of the list.

Updating Elements

Because lists are mutable, an existing element can be replaced by assigning a new value to its index.

scores = [80, 75, 90]
scores[1] = 85

The list is now:

[80, 85, 90]

Only the element at index 1 was changed.

List Length

The built-in len() function returns the number of elements in a list.

students = ["Sara", "Omar", "Mona"]
number_of_students = len(students)
print(number_of_students)

The result is 3.

The length of a list can also be used when working with indexes and loops.

Adding Elements

The append() method adds an element to the end of a list.

courses = ["Python", "Databases"]
courses.append("Data Structures")

The resulting list is:

["Python", "Databases", "Data Structures"]

The insert() method adds an element at a specific position.

courses.insert(1, "Algorithms")

The resulting list is:

["Python", "Algorithms", "Databases", "Data Structures"]

Removing Elements

The remove() method removes the first occurrence of a specified value.

courses = ["Python", "Databases", "Python"]
courses.remove("Python")

The resulting list is:

["Databases", "Python"]

The pop() method removes an element using its index and returns the removed value.

scores = [80, 75, 90]
removed_score = scores.pop(1)

The value 75 is removed and stored in removed_score.

Calling pop() without an index removes the last element.

scores.pop()

The del statement can also be used to remove an element.

del scores[0]

Slicing

List slicing is used to retrieve a portion of a list.

The general syntax is:

list[start:stop]

The start index is included, while the stop index is excluded.

For example:

scores = [70, 80, 90, 85, 95]
print(scores[1:4])

The result is:

[80, 90, 85]

A slice can also omit the start or stop index.

print(scores[:3])
print(scores[2:])

The first expression returns the first three elements, while the second returns all elements from index 2 onward.

Iterating Through a List

A for loop can be used to process each element in a list.

students = ["Sara", "Omar", "Mona"]
for student in students:
    print(student)

The loop executes once for each element.

Lists can also be processed using indexes when the position of each element is needed.

scores = [80, 90, 75]
for index in range(len(scores)):
    print(index, scores[index])

Searching a List

The in operator can be used to determine whether a value exists in a list.

courses = ["Python", "Databases", "Algorithms"]
if "Python" in courses:
    print("Python is available.")

The not in operator checks whether a value is absent.

if "Java" not in courses:
    print("Java is not available.")

Sorting Lists

The sort() method sorts the elements of a list in ascending order by default.

scores = [85, 70, 95, 80]
scores.sort()

The resulting list is:

[70, 80, 85, 95]

The list can be sorted in descending order by using the reverse argument.

scores.sort(reverse=True)

The built-in sorted() function can also be used to create a sorted version of a list without modifying the original list.

scores = [85, 70, 95, 80]
sorted_scores = sorted(scores)

Useful List Operations

Python provides several useful operations for working with lists.

The count() method counts how many times a value occurs.

scores = [80, 90, 80, 75]
print(scores.count(80))

The index() method returns the index of the first occurrence of a value.

courses = ["Python", "Databases", "Algorithms"]
print(courses.index("Databases"))

The min() and max() functions can be used with numeric lists.

scores = [80, 90, 75, 95]
print(min(scores))
print(max(scores))

The sum() function calculates the total of numeric values.

total = sum(scores)

Nested Lists

A list can contain other lists. This creates a nested list.

class_scores = [
    [80, 85, 90],
    [75, 88, 92],
    [90, 95, 87]
]

An element inside a nested list can be accessed using multiple indexes.

print(class_scores[0][1])

The first index selects the first inner list, and the second index selects an element from that inner list.

Common Errors

A common error occurs when accessing an index that does not exist.

students = ["Sara", "Omar"]
print(students[2])

This raises an IndexError because the valid indexes are 0 and 1.

Another common issue is confusing an index with a value.

scores = [70, 80, 90]
scores[80] = 100

This attempts to use 80 as an index rather than searching for the value 80. It results in an IndexError.

If the goal is to replace the value at index 1, the correct code is:

scores[1] = 100

Summary

Python lists are ordered, mutable collections that can store multiple values. Lists use zero-based indexing, so the first element is at index 0.

Important operations include:

* append() for adding an element to the end.
* insert() for adding an element at a specific position.
* remove() for removing a specified value.
* pop() for removing and returning an element.
* sort() for sorting a list in place.
* len() for finding the number of elements.
* Slicing for retrieving part of a list.

Lists are one of the most commonly used data structures in Python and provide a foundation for working with more advanced data structures and algorithms.