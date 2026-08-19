# React Components

## Course Overview

React is a JavaScript library for building user interfaces out of reusable pieces called components. This material covers what a component is, how functional components are written, and the basics of JSX.

## What Is a Component?

A component is a self-contained, reusable piece of UI. It takes some input and returns what should appear on the screen. Large applications are built by composing many small components together, similar to how HTML pages are built from nested elements.

## Functional Components

Modern React apps are built almost entirely with **functional components**: plain JavaScript functions that return UI markup. For example:

```jsx
function Greeting() {
  return <h1>Welcome to Brightpeak Academy</h1>;
}
```

This function is a valid React component. It can be reused anywhere in the app just by referencing `<Greeting />`.

## JSX

The markup returned by a component (`<h1>Welcome...</h1>` above) is written in **JSX**, a syntax extension that lets you write HTML-like code directly inside JavaScript. Under the hood, JSX is converted into regular JavaScript function calls that build the UI.

A few JSX rules to keep in mind:

- A component must return a single top-level element (or a fragment `<>...</>` wrapping multiple elements).
- JavaScript expressions can be embedded inside curly braces, e.g. `<p>{studentName}</p>`.
- Attributes use camelCase, e.g. `className` instead of `class`.

## Composing Components

Components can be nested inside other components, passing data between them (covered in the next material, State and Props). This composition is what lets React apps scale from a single button to a full dashboard while keeping each piece small and easy to reason about.
