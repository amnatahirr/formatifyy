import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:frontend/models/supervisor_models.dart';
import 'package:frontend/providers/auth_provider.dart';
import 'package:frontend/providers/lang_provider.dart';
import 'package:frontend/screens/supervisor/submission_review_screen.dart';
import 'package:frontend/services/supervisor_api_service.dart';

FinalSubmissionModel _submission(int id, String title) {
  return FinalSubmissionModel(
    id: id,
    groupId: 1,
    groupTitle: 'Test Group',
    projectTitle: 'Topic',
    title: title,
    filename: title,
    status: 'pending',
    submittedAt: '2026-01-01 10:00:00',
    decisionNote: '',
    analysisSummary: const AnalysisSummaryModel(
      grammarIssues: 0,
      plagiarismIssues: 0,
      plagiarismScore: 0,
      totalIssues: 0,
      majorIssues: 0,
      minorIssues: 0,
      complianceScore: 100,
      structureStatus: '',
    ),
    grammarIssues: const [],
    plagiarismIssues: const [],
  );
}

class _FakeSupervisorApi extends SupervisorApiService {
  int fetchCalls = 0;
  final List<List<FinalSubmissionModel>> pages;

  _FakeSupervisorApi(this.pages);

  @override
  Future<List<FinalSubmissionModel>> fetchSubmissions(
    int userId, {
    String status = 'pending',
  }) async {
    fetchCalls++;
    final index = (fetchCalls - 1).clamp(0, pages.length - 1);
    return pages[index];
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets(
      'successful decision removes the item and updates the pending count',
      (tester) async {
    final item = _submission(7, 'FORMATIFY.docx');
    // First load returns the pending submission; the refetch after the
    // decision returns an empty queue (server-side status=pending filter).
    final api = _FakeSupervisorApi([
      [item],
      const [],
    ]);

    await tester.pumpWidget(
      MaterialApp(
        home: MultiProvider(
          providers: [
            ChangeNotifierProvider<AuthProvider>.value(
              value: AuthProvider(devUserKey: 'test'),
            ),
            ChangeNotifierProvider<LangProvider>.value(
              value: LangProvider(),
            ),
          ],
          child: Scaffold(
            body: SubmissionReviewScreen(
              api: api,
              detailBuilder: (context, submission) => Scaffold(
                body: Center(
                  child: ElevatedButton(
                    onPressed: () => Navigator.of(context).pop(true),
                    child: const Text('Approve'),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('1 final submission awaiting decision'), findsOneWidget);
    expect(find.text('FORMATIFY.docx'), findsOneWidget);

    // Open the detail screen and simulate a successful decision (pop(true)).
    await tester.tap(find.text('FORMATIFY.docx'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Approve'));
    await tester.pumpAndSettle();

    // Item removed from the in-memory list, count decremented, list refetched.
    expect(find.text('No pending final submissions'), findsOneWidget);
    expect(find.text('FORMATIFY.docx'), findsNothing);
    expect(api.fetchCalls, 2);
  });
}
