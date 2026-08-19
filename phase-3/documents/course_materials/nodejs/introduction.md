# Introduction to Node.js

## Course Overview

Node.js is a runtime that lets JavaScript run outside the browser, most commonly on a server. This material covers what the Node.js runtime is, how modules work, and the event loop that powers Node's non-blocking behavior.

## What Is the Node.js Runtime?

Traditionally, JavaScript only ran inside web browsers. Node.js takes the same JavaScript engine used by Chrome (V8) and lets it run as a standalone program on a server or a local machine, with access to the file system, network, and other system resources that a browser normally restricts.

## Modules

Node.js organizes code into **modules** — reusable files that export functionality to be used elsewhere. The built-in `module.exports` (or, with ES modules, `export`) makes values from one file available in another:

```javascript
// math.js
function add(a, b) {
  return a + b;
}
module.exports = { add };

// app.js
const { add } = require("./math");
console.log(add(2, 3)); // 5
```

Node also ships with built-in modules (like `fs` for file access and `http` for creating servers) and supports installing third-party modules via npm.

## The Event Loop

Node.js is designed to handle many operations — like reading a file or querying a database — without blocking the rest of the program while it waits. This is managed by the **event loop**: instead of pausing execution until a slow operation finishes, Node registers a callback to run once the operation completes and moves on to other work in the meantime.

```javascript
console.log("Start");

setTimeout(() => {
  console.log("This runs later");
}, 1000);

console.log("End");
```

This prints `Start`, then `End`, and only after about a second, `This runs later` — the program didn't pause and wait for the timeout.

## Why This Matters

The event loop is what lets a single Node.js process handle many simultaneous requests efficiently, which is central to why Node.js is popular for building web servers and APIs.
