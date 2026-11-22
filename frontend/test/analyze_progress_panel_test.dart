import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/providers/lang_provider.dart';
import 'package:frontend/widgets/analyze_progress_panel.dart';
import 'package:provider/provider.dart';

Widget _panel({Map<String, dynamic>? progress, bool complete = false}) =>
    ChangeNotifierProvider(
      create: (_) => LangProvider(),
      child: MaterialApp(
      home: Scaffold(
        body: AnalyzeProgressPanel(
          documentName: 'report.docx',
          accent: Colors.blue,
          textPrimary: Colors.white,
          textSecondary: Colors.grey,
          surface: Colors.black,
          border: Colors.grey,
          track: Colors.black12,
          isComplete: complete,
          progress: progress,
        ),
      ),
    ),
    );

void main() {
  testWidgets('shows the real backend stage, detail and percent', (tester) async {
    await tester.pumpWidget(_panel(progress: {
      'stage': 'grammar',
      'percent': 57,
      'detail': 'Grammar: sentence 40 of 96',
    }));
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.text('57%'), findsOneWidget);
    expect(find.text('Grammar: sentence 40 of 96'), findsOneWidget);
    // title appears in the header and in the stage list
    expect(find.text('Checking grammar & content'), findsNWidgets(2));
    // earlier stages are done, later ones pending
    expect(find.byIcon(Icons.check_circle_rounded), findsNWidgets(3));
    expect(find.byIcon(Icons.circle_outlined), findsNWidgets(2));
  });

  testWidgets('without backend progress it never runs ahead', (tester) async {
    await tester.pumpWidget(_panel());
    await tester.pump(const Duration(seconds: 10));
    expect(find.byIcon(Icons.check_circle_rounded), findsNothing);
    expect(find.text('Preparing document'), findsNWidgets(2));
  });

  testWidgets('complete fills to 100%', (tester) async {
    await tester.pumpWidget(_panel(progress: {'stage': 'finalizing', 'percent': 97}, complete: true));
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('100%'), findsOneWidget);
  });
}
