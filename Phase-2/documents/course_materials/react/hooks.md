# Hooks in React

## Course Overview

Hooks are functions that let functional components use features like state and lifecycle behavior that were previously only available in class components. This material covers the two most commonly used hooks, `useState` and `useEffect`, and how to write a simple custom hook.

## useState

`useState` was introduced in the State and Props material — it lets a component declare a piece of state and a function to update it:

```jsx
const [count, setCount] = useState(0);
```

Every time `setCount` is called, React re-renders the component with the updated value.

## useEffect

`useEffect` lets a component run code in response to rendering — for example, fetching data when the component first appears, or updating the page title whenever a value changes:

```jsx
import { useState, useEffect } from "react";

function StudentProfile({ studentId }) {
  const [student, setStudent] = useState(null);

  useEffect(() => {
    fetch(`/api/students/${studentId}`)
      .then((res) => res.json())
      .then((data) => setStudent(data));
  }, [studentId]);

  return <p>{student ? student.name : "Loading..."}</p>;
}
```

The array at the end, `[studentId]`, is the **dependency array**. It tells React to re-run the effect only when `studentId` changes, rather than on every render.

## Rules of Hooks

Hooks must follow two rules:

1. Only call hooks at the top level of a component — never inside loops, conditions, or nested functions.
2. Only call hooks from React function components or from other custom hooks.

## Building a Custom Hook

A custom hook is just a regular JavaScript function, prefixed with `use`, that calls other hooks inside it. For example, a hook to track whether the window is scrolled:

```jsx
function useIsScrolled() {
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const handler = () => setIsScrolled(window.scrollY > 0);
    window.addEventListener("scroll", handler);
    return () => window.removeEventListener("scroll", handler);
  }, []);

  return isScrolled;
}
```

Custom hooks let you extract and reuse stateful logic across multiple components without duplicating code.
