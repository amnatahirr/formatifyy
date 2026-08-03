import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/screens/super_admin/super_admin_screen.dart';

void main() {
  testWidgets('Overview mock growth chart paints bars and month labels', (tester) async {
    const counts = [1, 1, 2, 2, 3, 4];
    const labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];

    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          backgroundColor: Color(0xFF0F1419),
          body: Padding(
            padding: EdgeInsets.all(24),
            child: SizedBox(
              width: 640,
              child: SuperAdminMockGrowthChart(counts: counts, labels: labels),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('sa_mock_growth_chart')), findsOneWidget);
    expect(find.text('Jan'), findsOneWidget);
    expect(find.text('Jun'), findsOneWidget);

    for (var i = 0; i < counts.length; i++) {
      expect(tester.getSize(find.byKey(Key('sa_mock_growth_bar_$i'))).height, greaterThan(8));
    }

    final firstH = tester.getSize(find.byKey(const Key('sa_mock_growth_bar_0'))).height;
    final lastH = tester.getSize(find.byKey(const Key('sa_mock_growth_bar_5'))).height;
    expect(lastH, greaterThan(firstH));
    expect(lastH, closeTo(86, 0.5)); // (4/4)*78 + 8
  });
}
