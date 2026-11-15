import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';

class LocalNotificationService {
  static final _plugin = FlutterLocalNotificationsPlugin();
  static bool _ready = false;

  // Sirf phone par chale, desktop interface affect na ho.
  static bool get _supported =>
      !kIsWeb && (Platform.isIOS || Platform.isAndroid);

  static Future<void> init() async {
    if (!_supported || _ready) return;
    const ios = DarwinInitializationSettings(
      requestAlertPermission: false,
      requestBadgePermission: false,
      requestSoundPermission: false,
    );
    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    await _plugin.initialize(
      settings: const InitializationSettings(iOS: ios, android: android),
    );
    _ready = true;
  }

  /// Login ke baad ek baar call karein.
  static Future<void> requestPermission() async {
    if (!_supported) return;
    await _plugin
        .resolvePlatformSpecificImplementation<
            IOSFlutterLocalNotificationsPlugin>()
        ?.requestPermissions(alert: true, badge: true, sound: true);
    await _plugin
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.requestNotificationsPermission();
  }

  static Future<void> show(int id, String title, String body) async {
    if (!_supported || !_ready) return;
    const details = NotificationDetails(
      iOS: DarwinNotificationDetails(
        presentAlert: true,
        presentBanner: true,
        presentList: true,
        presentSound: true,
        presentBadge: true,
      ),
      android: AndroidNotificationDetails(
        'formatify_default',
        'Formatify Notifications',
        importance: Importance.high,
        priority: Priority.high,
      ),
    );
    await _plugin.show(
  id: id,
  title: title,
  body: body,
  notificationDetails: details,
);
  }

  /// Polling ke har result par call karein.
  /// items = backend se aayi notifications ki list (read + unread dono).
  static Future<void> showNewOnes(
      int userId, List<Map<String, dynamic>> items) async {
    if (!_supported || items.isEmpty) return;

    final prefs = await SharedPreferences.getInstance();
    final key = 'last_notified_id_$userId';
    final last = prefs.getInt(key);

    int maxId = 0;
    for (final n in items) {
      final id = (n['id'] as num).toInt();
      if (id > maxId) maxId = id;
    }

    // Pehli dafa: purani notifications ka flood na ho, sirf baseline set karein.
    if (last == null) {
      await prefs.setInt(key, maxId);
      return;
    }

    final fresh = items.where((n) {
      final id = (n['id'] as num).toInt();
      final isRead = n['is_read'] == 1 || n['is_read'] == true;
      return id > last && !isRead;
    }).toList()
      ..sort((a, b) => (a['id'] as num).compareTo(b['id'] as num));

    // Zyada hon to 3 alag, baqi ka ek summary.
    for (final n in fresh.take(3)) {
      await show(
        (n['id'] as num).toInt(),
        (n['title'] ?? 'Formatify').toString(),
        (n['body'] ?? n['message'] ?? '').toString(),
      );
    }
    if (fresh.length > 3) {
      await show(0, 'Formatify', '${fresh.length - 3} more new notifications');
    }

    if (maxId > last) await prefs.setInt(key, maxId);
  }

    /// Logout par call hota hai.
  static Future<void> resetBaseline() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('last_notified_id_0');
  }
}