# Introduction to Flutter

## Course Overview

Flutter is a framework for building mobile (and cross-platform) applications from a single codebase, using the Dart programming language. This material covers Flutter's architecture, the concept of widgets, and how to set up a new project.

## Flutter's Architecture

Flutter compiles Dart code directly to native machine code for each target platform (iOS, Android, web, desktop), rather than relying on a bridge to native components. This is part of why Flutter apps can achieve near-native performance while sharing a single codebase across platforms.

Everything visible on screen in a Flutter app — text, buttons, layout containers, even the screen padding — is a **widget**.

## Widgets

A widget is a description of part of the user interface. Widgets are combined and nested to build up the full UI, similar to how HTML elements nest to build a webpage.

```dart
import 'package:flutter/material.dart';

void main() {
  runApp(
    MaterialApp(
      home: Scaffold(
        appBar: AppBar(title: Text('Brightpeak Academy')),
        body: Center(
          child: Text('Welcome!'),
        ),
      ),
    ),
  );
}
```

In this example, `MaterialApp`, `Scaffold`, `AppBar`, `Center`, and `Text` are all widgets, each nested inside the one before it.

## Setting Up a Project

A new Flutter project is typically created using the Flutter CLI:

```bash
flutter create my_app
cd my_app
flutter run
```

This generates a starter project with a standard folder structure, including a `lib/main.dart` file (the entry point of the app) and platform-specific folders for iOS and Android.

## Why Flutter Matters

Because a single Dart codebase can target multiple platforms, teams can build and maintain one app instead of separate native apps for iOS and Android, while still getting a UI that feels native and performs well on each platform.
