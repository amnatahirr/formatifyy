import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/providers/notification_provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('NotificationProvider', () {
    late NotificationProvider provider;

    setUp(() {
      provider = NotificationProvider();
    });

    tearDown(() {
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
  });
}



