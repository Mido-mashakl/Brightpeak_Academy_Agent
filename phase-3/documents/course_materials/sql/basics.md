# SQL Basics

## Course Overview

SQL (Structured Query Language) is the standard language for interacting with relational databases. This material covers the most fundamental SQL statement, `SELECT`, along with filtering and sorting results.

## The SELECT Statement

`SELECT` retrieves data from one or more tables. The basic form specifies which columns to return and which table to read from:

```sql
SELECT title, category
FROM Courses;
```

To retrieve every column, use `*`:

```sql
SELECT * FROM Courses;
```

## Filtering with WHERE

The `WHERE` clause filters rows based on a condition, so only matching rows are returned:

```sql
SELECT title
FROM Courses
WHERE category = 'Programming';
```

Common comparison operators include `=`, `!=`, `>`, `<`, `>=`, `<=`, and `LIKE` for pattern matching (e.g., `WHERE title LIKE '%Python%'`). Conditions can be combined with `AND` and `OR`.

## Sorting with ORDER BY

`ORDER BY` sorts the result set by one or more columns. By default, sorting is ascending; add `DESC` for descending order:

```sql
SELECT title, duration
FROM Courses
ORDER BY duration DESC;
```

## Putting It Together

A single query can combine filtering and sorting:

```sql
SELECT title, duration
FROM Courses
WHERE category = 'Programming'
ORDER BY duration ASC;
```

This retrieves the title and duration of every course in the "Programming" category, sorted from shortest to longest. These three building blocks — `SELECT`, `WHERE`, and `ORDER BY` — cover the majority of everyday queries used to explore and filter data in a relational database.
