import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:frontend/models/app_notification.dart';
import 'package:frontend/providers/auth_provider.dart';
import 'package:frontend/providers/notification_provider.dart';
import 'package:frontend/theme/app_theme.dart';
import 'package:frontend/widgets/notification_bell.dart';

class _FakeNotificationProvider extends NotificationProvider {
  _FakeNotificationProvider(this._fakeItems, this._fakeUnread);

  final List<AppNotification> _fakeItems;
  final int _fakeUnread;

  @override
  List<AppNotification> get items => _fakeItems;

  @override
  int get unreadCount => _fakeUnread;

  @override
  bool get loading => false;

  @override
  bool get error => false;
}

List<AppNotification> _unreadItems() => [
      for (var i = 0; i < 3; i++)
        AppNotification(
          id: i + 1,
          type: 'student_submitted',
          title: 'Notification title $i',
          body: 'Body text for notification $i',
          isRead: false,
          createdAt: '2026-01-01T00:00:00Z',
        ),
    ];

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

  for (final width in [240.0, 320.0, 400.0]) {
    testWidgets('NotificationPanel has no overflow at ${width}px',
        (tester) async {
      final provider = _FakeNotificationProvider(_unreadItems(), 3);
      final themeProvider = ThemeProvider();

      await tester.pumpWidget(
        MaterialApp(
          theme: AppPalette.dark.themeData,
          home: MultiProvider(
            providers: [
              ChangeNotifierProvider<NotificationProvider>.value(value: provider),
              ChangeNotifierProvider<ThemeProvider>.value(value: themeProvider),
              ChangeNotifierProvider<AuthProvider>.value(
                  value: AuthProvider(devUserKey: 'test')),
            ],
            child: Scaffold(
              body: Center(
                child: SizedBox(
                  width: width,
                  height: 400,
                  child: const NotificationPanel(),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('View all'), findsOneWidget);
      if (width < 300) {
        // Narrow header collapses "Mark all read" to an icon button.
        expect(find.byIcon(Icons.done_all), findsOneWidget);
      } else {
        expect(find.text('Mark all read'), findsOneWidget);
      }

      provider.dispose();
      themeProvider.dispose();
    });
  }
}

