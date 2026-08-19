# State and Props

## Course Overview

Once a React app has more than one component, those components need ways to store data that can change over time and to share data with each other. This material covers **props**, which pass data from a parent component to a child, and **state**, which lets a component keep track of data that changes.

## Props

Props (short for "properties") are how a parent component passes data down to a child component. They work like function arguments:

```jsx
function Greeting({ name }) {
  return <h1>Welcome, {name}!</h1>;
}

function App() {
  return <Greeting name="Sara" />;
}
```

Here, `App` passes the value `"Sara"` as the `name` prop to `Greeting`. Props are **read-only** from the child's perspective — a child component should never modify the props it receives.

## State

State is data that belongs to a component and can change over time, typically in response to user interaction. Unlike props, state is managed inside the component itself using the `useState` hook:

```jsx
import { useState } from "react";

function Counter() {
  const [count, setCount] = useState(0);

  return (
    <button onClick={() => setCount(count + 1)}>
      Clicked {count} times
    </button>
  );
}
```

`useState(0)` creates a state variable `count` starting at `0`, along with a function `setCount` to update it. Calling `setCount` tells React to re-render the component with the new value.

## Props vs. State

- **Props** come from outside the component (passed by a parent) and are read-only.
- **State** lives inside the component and can be changed by the component itself.

Together, props and state let data flow down through the component tree while individual components still respond to user actions on their own.
