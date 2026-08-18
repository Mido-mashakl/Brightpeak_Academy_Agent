# State Management in Flutter

## Course Overview

As a Flutter app grows beyond a single widget, keeping track of state — and sharing it between widgets that aren't directly connected — becomes more challenging. This material covers the problem state management solves and how the Provider pattern addresses it.

## The Problem: Sharing State Across Widgets

Using `setState()` (covered in the previous material) works well for state that belongs to a single widget. But often, several widgets in different parts of the app need access to the same data — for example, a logged-in student's profile, or a shopping cart in an e-commerce app. Passing that data down manually through many layers of widget constructors ("prop drilling") quickly becomes unwieldy.

## The Provider Pattern

Provider is a popular Flutter package that lets you place a piece of state high up in the widget tree and access or update it from any widget below, without manually passing it down through every layer.

```dart
class StudentModel extends ChangeNotifier {
  String name = '';

  void updateName(String newName) {
    name = newName;
    notifyListeners();
  }
}
```

`ChangeNotifier` is a class that can notify listening widgets whenever its data changes, via `notifyListeners()`.

## Providing and Consuming State

The state is made available to the widget tree using a `ChangeNotifierProvider`:

```dart
ChangeNotifierProvider(
  create: (context) => StudentModel(),
  child: MyApp(),
)
```

Any widget below `MyApp` in the tree can then read or watch that state:

```dart
Consumer<StudentModel>(
  builder: (context, student, child) {
    return Text('Student: ${student.name}');
  },
)
```

Whenever `updateName()` is called and `notifyListeners()` runs, any `Consumer` widget watching `StudentModel` automatically rebuilds with the new value.

## Why This Matters

As an app grows, managing state well — deciding what belongs to a single widget versus what needs to be shared more broadly — has a big impact on how maintainable the codebase stays. Provider is one of several popular approaches (others include Riverpod and Bloc), but the underlying idea across all of them is the same: separate the app's data from the widgets that display it, and notify widgets automatically when that data changes.
