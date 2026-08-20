# Building REST APIs

## Course Overview

REST (Representational State Transfer) is a widely used style for designing web APIs. This material covers the principles behind RESTful design and how to implement basic REST endpoints using Express.

## Core REST Principles

A RESTful API organizes functionality around **resources** (like students, courses, or enrollments), each identified by a URL. Standard HTTP methods indicate the action to perform on that resource:

| Method | Action | Example |
|--------|--------|---------|
| GET | Retrieve a resource | `GET /courses` |
| POST | Create a new resource | `POST /courses` |
| PUT | Replace an existing resource | `PUT /courses/3` |
| DELETE | Remove a resource | `DELETE /courses/3` |

## Designing Endpoints

Good REST endpoints use nouns (resources), not verbs, in their URLs, and rely on the HTTP method to express the action:

```javascript
app.get("/courses/:id", (req, res) => {
  const courseId = req.params.id;
  const course = findCourseById(courseId);
  if (!course) {
    return res.status(404).json({ error: "Course not found" });
  }
  res.json(course);
});
```

`req.params.id` reads the `:id` portion of the URL, letting the same route handler serve requests for any course ID.

## Status Codes

REST APIs communicate the outcome of a request using standard HTTP status codes:

- `200 OK` — the request succeeded
- `201 Created` — a new resource was successfully created
- `400 Bad Request` — the request was malformed
- `404 Not Found` — the requested resource doesn't exist
- `500 Internal Server Error` — something went wrong on the server

## A Complete Example

```javascript
app.post("/courses", (req, res) => {
  const { title, category } = req.body;
  if (!title) {
    return res.status(400).json({ error: "Title is required" });
  }
  const newCourse = createCourse(title, category);
  res.status(201).json(newCourse);
});
```

This endpoint validates the incoming data, returns a `400` if required fields are missing, and returns a `201` along with the newly created resource on success — following REST conventions consistently makes an API predictable and easier for other developers to use.
