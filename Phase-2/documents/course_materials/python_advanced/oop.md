# Object-Oriented Programming

## Course Overview

Object-oriented programming (OOP) organizes code around **objects** that bundle data (attributes) and behavior (methods) together. This material covers classes, objects, inheritance, and polymorphism in Python, building on the basics covered in the introductory Python course.

## Classes and Objects

A **class** is a blueprint for creating objects. An **object** (or instance) is a specific realization of that class with its own data.

```python
class Student:
    def __init__(self, name, gpa):
        self.name = name
        self.gpa = gpa

    def is_honor_roll(self):
        return self.gpa >= 3.5

sara = Student("Sara", 3.7)
print(sara.is_honor_roll())  # True
```

`__init__` is the constructor — it runs automatically when a new object is created and sets up its initial attributes.

## Inheritance

Inheritance lets a class reuse and extend the behavior of another class. The new class (subclass) inherits attributes and methods from the existing class (superclass), and can override or add to them.

```python
class GraduateStudent(Student):
    def __init__(self, name, gpa, thesis_title):
        super().__init__(name, gpa)
        self.thesis_title = thesis_title
```

`super().__init__(name, gpa)` calls the parent class's constructor to reuse its setup logic instead of duplicating it.

## Polymorphism

Polymorphism means different classes can be used through the same interface, even if they behave differently internally. In Python, this often shows up as different classes implementing the same method name in their own way:

```python
class Course:
    def describe(self):
        return "A generic course"

class OnlineCourse(Course):
    def describe(self):
        return "An online course with recorded lectures"
```

Code that calls `.describe()` doesn't need to know which specific class it's working with — each object responds according to its own implementation.

## Why OOP Matters

OOP helps organize larger programs by grouping related data and behavior together, and lets code be extended (via inheritance) without rewriting what already works.
