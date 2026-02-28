import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_application_1/main.dart';

void main() {
  testWidgets('Counter increments smoke test', (WidgetTester tester) async {
    // build the app (wrap in MaterialApp if the app itself does not)
    await tester.pumpWidget(const CivicEyeApp());

    // verify initial value
    testWidgets('Counter increments test', (WidgetTester tester) async {
  // Build the app
  await tester.pumpWidget(const CivicEyeApp());

  // Verify initial value
  expect(find.text('0'), findsOneWidget);
  expect(find.text('1'), findsNothing);

  // Tap the + button
  await tester.tap(find.byIcon(Icons.add));
  await tester.pump();

  // Verify it incremented
  expect(find.text('0'), findsNothing);
  expect(find.text('1'), findsOneWidget);
});

    // tap the increment button and wait for animations
    await tester.tap(find.byIcon(Icons.add));
    await tester.pumpAndSettle();

    // verify value changed
    expect(find.text('0'), findsNothing);
    expect(find.text('1'), findsOneWidget);
  });

  testWidgets('counter can be incremented multiple times', (WidgetTester tester) async {
    await tester.pumpWidget(const CivicEyeApp());

    expect(find.text('0'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.add));
    await tester.tap(find.byIcon(Icons.add));
    await tester.tap(find.byIcon(Icons.add));
    await tester.pumpAndSettle();

    expect(find.text('3'), findsOneWidget);
  });

  testWidgets('floating action button is present', (WidgetTester tester) async {
    await tester.pumpWidget(const CivicEyeApp());

    expect(find.byType(FloatingActionButton), findsOneWidget);
  });

  testWidgets('app title is shown on startup', (WidgetTester tester) async {
    await tester.pumpWidget(const CivicEyeApp());

    // replace 'CivicEye' with whatever text you expect in your AppBar/title
    expect(find.text('CivicEye'), findsWidgets);
  });

  testWidgets('increment icon has a tooltip', (WidgetTester tester) async {
    await tester.pumpWidget(const CivicEyeApp());

    expect(find.byTooltip('Increment'), findsOneWidget);
  });
}