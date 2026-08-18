# Joins and Relationships

## Course Overview

Relational databases store data across multiple related tables instead of one large table. A **join** combines rows from two or more tables based on a related column, letting you query across those relationships. This material covers `INNER JOIN`, `LEFT JOIN`, and `RIGHT JOIN`.

## Why Joins Are Needed

Consider two tables: `Students` and `Enrollments`. Each enrollment row references a `student_id` that links back to a specific student. To answer a question like "which courses is Sara enrolled in?", you need to combine data from both tables — that's what a join does.

## INNER JOIN

`INNER JOIN` returns only the rows where there's a match in both tables. If a student has no enrollments, they simply won't appear in the result.

```sql
SELECT Students.name, Courses.title
FROM Students
INNER JOIN Enrollments ON Students.student_id = Enrollments.student_id
INNER JOIN Courses ON Enrollments.course_id = Courses.course_id;
```

## LEFT JOIN

`LEFT JOIN` returns all rows from the left table, along with matching rows from the right table. If there's no match, the columns from the right table are filled with `NULL`.

```sql
SELECT Students.name, Courses.title
FROM Students
LEFT JOIN Enrollments ON Students.student_id = Enrollments.student_id
LEFT JOIN Courses ON Enrollments.course_id = Courses.course_id;
```

This is useful when you want to see every student, including those not enrolled in anything.

## RIGHT JOIN

`RIGHT JOIN` is the mirror image of `LEFT JOIN`: it returns all rows from the right table, with matching rows from the left table (or `NULL` if there's no match). It's less commonly used in practice, since most `RIGHT JOIN` queries can be rewritten as a `LEFT JOIN` by swapping the table order.

## Choosing the Right Join

- Use `INNER JOIN` when you only care about rows that have a match in both tables.
- Use `LEFT JOIN` when you want every row from the main table, even without a match.
- Use `RIGHT JOIN` rarely, mainly for readability in specific query structures.
