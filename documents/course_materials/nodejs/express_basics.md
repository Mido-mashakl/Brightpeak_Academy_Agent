# Express.js Basics

## Course Overview

Express is a minimal web framework built on top of Node.js that simplifies building servers and handling HTTP requests. This material covers routing, middleware, and setting up a basic server.

## Setting Up a Basic Server

```javascript
const express = require("express");
const app = express();

app.get("/", (req, res) => {
  res.send("Welcome to Brightpeak Academy");
});

app.listen(3000, () => {
  console.log("Server running on port 3000");
});
```

`app.listen(3000, ...)` starts the server, and it will respond to requests made to `http://localhost:3000`.

## Routing

Routing defines how the app responds to requests at different URLs and HTTP methods. Express provides methods like `app.get`, `app.post`, `app.put`, and `app.delete` that correspond to the HTTP verbs:

```javascript
app.get("/courses", (req, res) => {
  res.json({ courses: ["Python", "Data Structures"] });
});

app.post("/courses", (req, res) => {
  // create a new course using data from req.body
  res.status(201).send("Course created");
});
```

Each route handler receives a `req` (request) object and a `res` (response) object, used to read incoming data and send a response back.

## Middleware

Middleware functions run between the incoming request and the final route handler. They can inspect or modify the request, end the request early, or pass control to the next function using `next()`.

```javascript
function logRequest(req, res, next) {
  console.log(`${req.method} ${req.url}`);
  next();
}

app.use(logRequest);
```

Common uses for middleware include logging, parsing request bodies (`express.json()`), authentication checks, and error handling. Middleware is applied with `app.use()` and runs for every matching request before the route handler executes.

## Putting It Together

A typical Express app combines routing and middleware: middleware handles cross-cutting concerns like logging or parsing, while routes handle the specific logic for each endpoint.
