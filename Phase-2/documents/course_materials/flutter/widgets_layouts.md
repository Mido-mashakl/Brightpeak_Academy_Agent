# Widgets and Layouts

## Course Overview

Flutter widgets fall into two broad categories based on whether they hold changeable state: stateless and stateful. This material covers that distinction and how widgets are composed into layouts.

## Stateless Widgets

A **stateless widget** describes part of the UI that doesn't change once it's built — it depends only on the data passed into it when it's created.

```dart
class WelcomeMessage extends StatelessWidget {
  final String name;

  const WelcomeMessage({required this.name});

  @override
  Widget build(BuildContext context) {
    return Text('Welcome, $name!');
  }
}
```

If `name` never changes for the lifetime of this widget, a stateless widget is the right choice — it's simpler and slightly more efficient.

## Stateful Widgets

A **stateful widget** can change its appearance in response to user interaction or other events, by holding onto mutable state:

```dart
class CounterButton extends StatefulWidget {
  @override
  State<CounterButton> createState() => _CounterButtonState();
}

class _CounterButtonState extends State<CounterButton> {
  int count = 0;

  void _increment() {
    setState(() {
      count++;
    });
  }

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: _increment,
      child: Text('Clicked $count times'),
    );
  }
}
```

Calling `setState()` tells Flutter that the widget's state has changed and it needs to rebuild the affected part of the UI.

## Layout Composition

Flutter uses a small set of layout widgets to arrange other widgets on screen:

- **Column**: arranges children vertically
- **Row**: arranges children horizontally
- **Container**: adds padding, margin, sizing, or decoration around a single child
- **Stack**: layers children on top of one another

```dart
Column(
  children: [
    Text('Course: Introduction to Flutter'),
    Row(
      children: [
        Icon(Icons.check_circle),
        Text('Completed'),
      ],
    ),
  ],
)
```

## Choosing Stateless vs. Stateful

The general rule: start with a stateless widget, and only switch to stateful if the widget genuinely needs to hold and update its own data over time. This keeps the widget tree simpler and easier to reason about.
