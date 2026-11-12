import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:frontend/providers/notification_provider.dart';
import 'package:frontend/theme/app_theme.dart';
import 'package:frontend/widgets/notification_bell.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('NotificationBell renders without crashing', (tester) async {
    final provider = NotificationProvider();
    final themeProvider = ThemeProvider();

    await tester.pumpWidget(
      MaterialApp(
        theme: AppPalette.dark.themeData,
        home: MultiProvider(
          providers: [
            ChangeNotifierProvider.value(value: provider),
            ChangeNotifierProvider.value(value: themeProvider),
          ],
          child: const Scaffold(
            body: NotificationBell(),
          ),
        ),
      ),
    );

    expect(find.byType(NotificationBell), findsOneWidget);
    expect(find.byIcon(Icons.notifications_outlined), findsOneWidget);

    provider.dispose();
  });
}

