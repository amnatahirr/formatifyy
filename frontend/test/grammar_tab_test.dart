// Renders the real AnalyzeScreen with an analysis payload and checks the
// Grammar tab shows local grammar suggestions with their type label.
//
// By default uses a small built-in payload. To render a real saved result:
//   GRAMMAR_RESULT_JSON=/path/to/analysis_result.json flutter test test/grammar_tab_test.dart
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:frontend/providers/analysis_job_provider.dart';
import 'package:frontend/providers/auth_provider.dart';
import 'package:frontend/providers/document_provider.dart';
import 'package:frontend/providers/lang_provider.dart';
import 'package:frontend/theme/app_theme.dart';
import 'package:frontend/screens/analyze_screen.dart';

class _FakeJobs extends AnalysisJobProvider {
  final Map<String, dynamic> data;
  _FakeJobs(this.data);

  @override
  Future<Map<String, dynamic>> startOrAttach({
    required int documentId,
    required int userId,
    required String name,
    bool freeform = false,
    bool force = false,
    VoidCallback? onOpen,
  }) async =>
      data;
}

Map<String, dynamic> _grammarIssue(String id, String type, String orig, String sugg) => {
      'issue_id': id,
      'function': 'grammar',
      'category': 'Grammar',
      'type': 'grammar',
      'severity': 'minor',
      'paragraph_id': 'p1',
      'page': 1,
      'reason': 'Possible $type issue',
      'description': 'Possible $type issue',
      'original': orig,
      'suggestion': sugg,
      'source': 'both',
      'grammar_type': type,
      'char_start': id.length,
      'char_end': id.length + orig.length,
    };

Map<String, dynamic> _payload() {
  final path = Platform.environment['GRAMMAR_RESULT_JSON'];
  if (path != null && path.isNotEmpty) {
    return jsonDecode(File(path).readAsStringSync()) as Map<String, dynamic>;
  }
  return {
    'issues': [
      _grammarIssue('grammar_p1_4', 'spelling', 'sysem', 'system'),
      _grammarIssue('grammar_p1_11', 'grammar', 'open', 'opens'),
    ],
    'structure': {'score': 90},
    'document_blocks': [
      {'paragraph_id': 'p1', 'type': 'paragraph', 'text': 'The sysem open my profile window.', 'page': 1},
    ],
  };
}

void main() {
  testWidgets('Grammar tab renders local suggestions with type labels', (tester) async {
    final data = _payload();
    final grammar = (data['issues'] as List)
        .where((i) => (i as Map)['function'] == 'grammar')
        .toList();
    tester.view.physicalSize = const Size(1600, 1200);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    // The app sidebar has a known small RenderFlex overflow at test font
    // metrics; it is unrelated to the Grammar tab, so ignore overflow only.
    final prevOnError = FlutterError.onError;
    FlutterError.onError = (details) {
      if (details.exceptionAsString().contains('overflowed')) return;
      prevOnError?.call(details);
    };
    addTearDown(() => FlutterError.onError = prevOnError);

    await tester.pumpWidget(MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider(devUserKey: 'member1')),
        ChangeNotifierProvider(create: (_) => DocumentProvider()),
        ChangeNotifierProvider(create: (_) => ThemeProvider()),
        ChangeNotifierProvider(create: (_) => LangProvider()),
        ChangeNotifierProvider<AnalysisJobProvider>(create: (_) => _FakeJobs(data)),
      ],
      child: const MaterialApp(
        home: AnalyzeScreen(
          documentId: 1,
          documentName: 'report.docx',
          templateId: 1,
          templateName: 'Template',
        ),
      ),
    ));
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 200));
    }

    final tab = find.textContaining('Grammar  (');
    expect(tab, findsOneWidget);
    await tester.tap(tab);
    for (var i = 0; i < 5; i++) {
      await tester.pump(const Duration(milliseconds: 200));
    }

    // ignore: avoid_print
    print('grammar issues in payload: ${grammar.length}; '
        'tab label: ${(tester.widget(tab) as Text).data}');
    expect((tester.widget(tab) as Text).data, contains('${grammar.length}'));
    expect(find.textContaining('suggestions from a local checker'), findsWidgets);
    expect(find.text('Suggestion'), findsWidgets);
    final types = grammar.map((i) => ((i as Map)['grammar_type'] ?? '').toString().toUpperCase()).toSet();
    expect(types.any((t) => t.isNotEmpty && find.text(t).evaluate().isNotEmpty), isTrue);
  });
}
