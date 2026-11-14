import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:frontend/providers/notification_provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('NotificationProvider', () {
    late NotificationProvider provider;

    setUp(() {
      provider = NotificationProvider();
    });

    tearDown(() {
      NotificationProvider.httpGetOverride = null;
      provider.dispose();
    });

    test('starts with empty state', () {
      expect(provider.items, isEmpty);
      expect(provider.unreadCount, 0);
      expect(provider.loading, false);
      expect(provider.error, false);
    });

    test('clear resets all state', () {
      provider.clear();

      expect(provider.items, isEmpty);
      expect(provider.unreadCount, 0);
      expect(provider.loading, false);
      expect(provider.error, false);
    });

    test('polling starts and stops', () {
      provider.startPolling();
      provider.stopPolling();
    });

    test('polling respects app lifecycle', () {
      provider.didChangeAppLifecycleState(AppLifecycleState.paused);
      provider.didChangeAppLifecycleState(AppLifecycleState.resumed);
      provider.didChangeAppLifecycleState(AppLifecycleState.detached);
    });

    testWidgets('toast failure does not stop unread count update',
        (tester) async {
      // messengerKey.currentContext points at the ScaffoldMessenger element
      // itself, so ScaffoldMessenger.of(ctx) throws — reproducing the
      // "No ScaffoldMessenger widget found" login-time failure.
      final messengerKey = GlobalKey<ScaffoldMessengerState>();
      provider.messengerKey = messengerKey;

      NotificationProvider.httpGetOverride = (uri, {headers}) async {
        if (uri.path.endsWith('/notifications/unread-count')) {
          return http.Response(jsonEncode({'unread_count': 2}), 200);
        }
        // loadFirstPage() recomputes unreadCount from the list — return two
        // unread items so the count stays consistent.
        return http.Response(
          jsonEncode({
            'notifications': [
              for (var i = 1; i <= 2; i++)
                {
                  'id': i,
                  'type': 'student_submitted',
                  'title': 'New submission $i',
                  'body': 'body',
                  'is_read': false,
                  'created_at': '2026-01-01T00:00:00Z',
                }
            ]
          }),
          200,
        );
      };

      await tester.pumpWidget(
        MaterialApp(
          home: ScaffoldMessenger(
            key: messengerKey,
            child: const SizedBox(),
          ),
        ),
      );

      await provider.refreshUnreadCount();
      await tester.pump();

      expect(provider.unreadCount, 2);
      expect(provider.error, isFalse);
      expect(provider.items, hasLength(2));
    });

    testWidgets('failed first refresh retries exactly once', (tester) async {
      var calls = 0;
      NotificationProvider.httpGetOverride = (uri, {headers}) async {
        calls++;
        return http.Response('unauthorized', 401);
      };

      await provider.refreshUnreadCount();
      await tester.pump();
      expect(calls, 1);

      // Retry fires ~1.5s later.
      await tester.pump(const Duration(milliseconds: 1600));
      await tester.pump();
      expect(calls, 2);

      // No further retries — the retried call itself must not reschedule.
      await tester.pump(const Duration(seconds: 3));
      await tester.pump();
      expect(calls, 2);
    });
  });
}



