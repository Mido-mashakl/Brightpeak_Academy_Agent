# Database Schema Design

## Course Overview

A database schema defines the tables, columns, and relationships that make up a database. Good schema design keeps data consistent, avoids unnecessary duplication, and makes queries easier to write. This material covers normalization, keys, and the basics of designing a relational schema.

## Primary and Foreign Keys

A **primary key** is a column (or set of columns) that uniquely identifies each row in a table, such as `student_id` in a `Students` table. No two rows can share the same primary key value.

A **foreign key** is a column in one table that references the primary key of another table, creating a relationship between them. For example, `Enrollments.course_id` is a foreign key referencing `Courses.course_id`.

## Why Normalization Matters

**Normalization** is the process of organizing tables to reduce redundant data. Instead of repeating a course's title and duration on every enrollment row, those details are stored once in a `Courses` table, and each enrollment just references the `course_id`.

Benefits of normalization:

- Avoids inconsistent data (updating a course title in one place instead of many)
- Reduces storage of duplicate information
- Makes relationships between entities explicit

## A Simple Example

Instead of one large table mixing student info, course info, and enrollment info together, a normalized design splits it into separate tables:

```
Students(student_id, name, email)
Courses(course_id, title, duration)
Enrollments(enrollment_id, student_id, course_id, status)
```

Each table has a clear, single responsibility, and the foreign keys in `Enrollments` tie everything together.

## Designing a Schema

When designing a schema, start by identifying the main entities (Students, Courses, Assignments, etc.), decide what attributes belong to each, and figure out how they relate — one-to-many (one course has many enrollments) or many-to-many (handled with a join table like `Enrollments`). Getting this structure right early makes the rest of the application, including querying and reporting, much simpler.
