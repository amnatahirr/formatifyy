import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:frontend/providers/fyp_provider.dart';

/// Regression: notifyListeners must not run in the same sync turn as build.
void main() {
  testWidgets('FypProvider fetchAssignmentStatus does not notify during build',
      (tester) async {
    final fyp = FypProvider();
    var buildCount = 0;
    FlutterError? captured;

    FlutterError.onError = (details) {
      if (details.exception is FlutterError) {
        captured = details.exception as FlutterError;
      }
    };

    await tester.pumpWidget(
      ChangeNotifierProvider<FypProvider>.value(
        value: fyp,
        child: MaterialApp(
          home: Builder(
            builder: (context) {
              buildCount++;
              // Simulate initState calling fetch during first build frame.
              if (buildCount == 1) {
                // ignore: discarded_futures
                context.read<FypProvider>().fetchAssignmentStatus(
                      userId: 1,
                      email: 'student@test.edu',
                    );
              }
              context.watch<FypProvider>().isStatusLoading;
              return const Scaffold(body: Text('ok'));
            },
          ),
        ),
      ),
    );

    // Allow Duration.zero gap + network attempt to settle.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    final msg = captured?.message ?? '';
    expect(
      msg.contains('setState() or markNeedsBuild() called during build'),
      isFalse,
      reason: 'Unexpected build-phase notify: $msg',
    );
  });
}
