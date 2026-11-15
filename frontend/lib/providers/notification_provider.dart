import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';
import '../models/app_notification.dart';
import '../services/local_notification_service.dart';

class NotificationProvider extends ChangeNotifier with WidgetsBindingObserver {
  late final String _baseUrl;
  List<AppNotification> _items = [];
  int _unreadCount = 0;
  bool _loading = false;
  bool _error = false;
  String? _errorMessage;
  Timer? _pollingTimer;
  int? _lastKnownUnreadCount;
  bool _isInForeground = true;
  bool _hasMore = true;
  bool _unreadOnly = false;
  bool _disposed = false;
  Timer? _refreshRetryTimer;
  GlobalKey<ScaffoldMessengerState>? messengerKey;

  /// Test seam: when set, replaces http.get for all provider requests.
  @visibleForTesting
  static Future<http.Response> Function(Uri url,
      {Map<String, String>? headers})? httpGetOverride;

  List<AppNotification> get items => _items;
  int get unreadCount => _unreadCount;
  bool get loading => _loading;
  bool get error => _error;
  String? get errorMessage => _errorMessage;
  bool get hasMore => _hasMore;
  bool get unreadOnly => _unreadOnly;

  NotificationProvider() {
    _baseUrl = ApiConfig.getBaseUrl();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    _disposed = true;
    _refreshRetryTimer?.cancel();
    _pollingTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.resumed:
        _isInForeground = true;
        refreshUnreadCount();
        _checkForBanners();
        break;
      case AppLifecycleState.paused:
      case AppLifecycleState.inactive:
      case AppLifecycleState.detached:
        _isInForeground = false;
        break;
      case AppLifecycleState.hidden:
        _isInForeground = false;
        break;
    }
  }

  void startPolling() {
    unawaited(LocalNotificationService.requestPermission());
    _pollingTimer?.cancel();
        _pollingTimer = Timer.periodic(const Duration(seconds: 10), (_) {
      if (_isInForeground) {
        refreshUnreadCount();
        _checkForBanners();   // NEW
      }
    });
  }

  void stopPolling() {
    _pollingTimer?.cancel();
  }

  void clear() {
    _refreshRetryTimer?.cancel();
    _refreshRetryTimer = null;
    _items.clear();
    _unreadCount = 0;
    _lastKnownUnreadCount = null;
    _loading = false;
    _error = false;
    _errorMessage = null;
    _hasMore = true;
    _unreadOnly = false;
    unawaited(LocalNotificationService.resetBaseline());
    stopPolling();
    notifyListeners();
  }

  /// Switch the list between all notifications and unread-only (server-side).
  Future<void> setUnreadOnly(bool value) async {
    if (_unreadOnly == value) return;
    _unreadOnly = value;
    await loadFirstPage();
  }

  Future<http.Response> _get(String url, Duration timeout) {
    final override = httpGetOverride;
    final uri = Uri.parse(url);
    if (override != null) {
      return override(uri, headers: ApiConfig.getHeaders())
          .timeout(timeout);
    }
    return http
        .get(uri, headers: ApiConfig.getHeaders())
        .timeout(timeout);
  }

  /// Retry a failed unread-count refresh once after a short delay.
  /// [isRetry] prevents retry loops; guards against dispose/clear.
  void _scheduleRefreshRetry({required bool isRetry}) {
    if (isRetry || _disposed) return;
    if (_refreshRetryTimer?.isActive == true) return;
    _refreshRetryTimer = Timer(const Duration(milliseconds: 1500), () {
      _refreshRetryTimer = null;
      if (!_disposed) {
        refreshUnreadCount(isRetry: true);
      }
    });
  }

   Future<void> _checkForBanners() async {
    try {
      final response = await _get(
        '$_baseUrl/notifications?limit=20&unread_only=true',
        const Duration(seconds: 10),
      );
      debugPrint('[banner] status=${response.statusCode}');
      if (response.statusCode != 200) return;
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final list = (data['notifications'] as List?)
              ?.map((j) => AppNotification.fromJson(j as Map<String, dynamic>))
              .toList() ??
          [];
      debugPrint('[banner] unread ids=${list.map((n) => n.id).toList()}');
      await LocalNotificationService.showNewOnes(
        0,
        list
            .map((n) => <String, dynamic>{
                  'id': n.id,
                  'title': n.title,
                  'body': n.body,
                  'is_read': n.isRead,
                })
            .toList(),
      );
    } catch (e) {
      debugPrint('[NotificationProvider] banner check failed: $e');
    }
  }

  Future<void> refreshUnreadCount({bool isRetry = false}) async {
    try {
      final response = await _get(
        '$_baseUrl/notifications/unread-count',
        const Duration(seconds: 10),
      );

      if (response.statusCode == 401) {
        _scheduleRefreshRetry(isRetry: isRetry);
        return;
      }

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final newCount = data['unread_count'] as int? ?? 0;

        final oldCount = _lastKnownUnreadCount ?? 0;
        debugPrint('[poll] ${DateTime.now().toIso8601String()} new=$newCount old=$oldCount');
        _lastKnownUnreadCount = newCount;
        _unreadCount = newCount;

        // State must be committed before any toast attempt — a missing
        // messenger must never abort the refresh.
        _error = false;
        _errorMessage = null;
        notifyListeners();

         if (newCount > 0 && newCount >= oldCount) {
          unawaited(loadFirstPage());
          if (_items.isNotEmpty) {
            final newest = _items.first;
            try {
              final ctx = messengerKey?.currentContext;
              if (ctx != null) {
                ScaffoldMessenger.of(ctx).showSnackBar(
                  SnackBar(
                    content: Text(newest.title),
                    duration: const Duration(seconds: 3),
                    behavior: SnackBarBehavior.floating,
                  ),
                );
              }
            } catch (e) {
              debugPrint('[NotificationProvider] Toast failed (non-fatal): $e');
            }
          }
        }
      }
    } catch (e) {
      debugPrint('[NotificationProvider] Failed to refresh unread count: $e');
      _scheduleRefreshRetry(isRetry: isRetry);
      _error = true;
      _errorMessage = 'Failed to refresh notifications';
      notifyListeners();
    }
  }

  Future<void> loadFirstPage() async {
    _loading = true;
    _error = false;
    _errorMessage = null;
    notifyListeners();

    try {
      final query = _unreadOnly ? '?limit=50&unread_only=true' : '?limit=50';
      final response = await _get(
        '$_baseUrl/notifications$query',
        const Duration(seconds: 15),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final notifications = (data['notifications'] as List?)
                ?.map((json) => AppNotification.fromJson(json as Map<String, dynamic>))
                .toList() ??
            [];
        _items = notifications;
        _hasMore = notifications.length >= 50;
        _unreadCount = notifications.where((n) => !n.isRead).length;
        unawaited(LocalNotificationService.showNewOnes(
          0,
          notifications
              .map((n) => <String, dynamic>{
                    'id': n.id,
                    'title': n.title,
                    'body': n.body,
                    'is_read': n.isRead,
                  })
              .toList(),
        ));
        _error = false;
        _errorMessage = null;
      } else {
        _error = true;
        _errorMessage = 'Failed to load notifications';
      }
    } catch (e) {
      debugPrint('[NotificationProvider] Failed to load notifications: $e');
      _error = true;
      _errorMessage = 'Failed to load notifications';
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<void> loadMore({int? beforeId}) async {
    if (_loading || !_hasMore) return;

    _loading = true;
    notifyListeners();

    try {
      final queryParams = <String, String>{'limit': '50'};
      if (_unreadOnly) queryParams['unread_only'] = 'true';
      if (beforeId != null) {
        queryParams['before_id'] = beforeId.toString();
      }

      final uri = Uri.parse('$_baseUrl/notifications')
          .replace(queryParameters: queryParams);

      final response = await _get(
        uri.toString(),
        const Duration(seconds: 15),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final notifications = (data['notifications'] as List?)
                ?.map((json) => AppNotification.fromJson(json as Map<String, dynamic>))
                .toList() ??
            [];
        _items.addAll(notifications);
        _hasMore = notifications.length >= 50;
        _error = false;
        _errorMessage = null;
      } else {
        _error = true;
        _errorMessage = 'Failed to load more notifications';
      }
    } catch (e) {
      debugPrint('[NotificationProvider] Failed to load more: $e');
      _error = true;
      _errorMessage = 'Failed to load more notifications';
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<bool> markRead(int id) async {
    final oldItem = _items.firstWhere((n) => n.id == id);

    final index = _items.indexWhere((n) => n.id == id);
    if (index == -1) return false;

    _items[index] = AppNotification(
      id: oldItem.id,
      type: oldItem.type,
      title: oldItem.title,
      body: oldItem.body,
      entityType: oldItem.entityType,
      entityId: oldItem.entityId,
      payload: oldItem.payload,
      isRead: true,
      createdAt: oldItem.createdAt,
      readAt: DateTime.now().toIso8601String(),
    );
    _unreadCount = _items.where((n) => !n.isRead).length;
    notifyListeners();

    try {
      final response = await http.post(
        Uri.parse('$_baseUrl/notifications/$id/read'),
        headers: ApiConfig.getHeaders(),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode != 200) {
        throw Exception('Failed to mark as read');
      }
      return true;
    } catch (e) {
      debugPrint('[NotificationProvider] Failed to mark as read: $e');
      _items[index] = oldItem;
      _unreadCount = _items.where((n) => !n.isRead).length;
      notifyListeners();
      return false;
    }
  }

  Future<bool> markAllRead() async {
    final oldItems = List<AppNotification>.from(_items);
    
    _items = _items.map((n) => AppNotification(
      id: n.id,
      type: n.type,
      title: n.title,
      body: n.body,
      entityType: n.entityType,
      entityId: n.entityId,
      payload: n.payload,
      isRead: true,
      createdAt: n.createdAt,
      readAt: DateTime.now().toIso8601String(),
    )).toList();
    _unreadCount = 0;
    notifyListeners();

    try {
      final response = await http.post(
        Uri.parse('$_baseUrl/notifications/read-all'),
        headers: ApiConfig.getHeaders(),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode != 200) {
        throw Exception('Failed to mark all as read');
      }
      return true;
    } catch (e) {
      debugPrint('[NotificationProvider] Failed to mark all as read: $e');
      _items = oldItems;
      _unreadCount = _items.where((n) => !n.isRead).length;
      notifyListeners();
      return false;
    }
  }

  Future<bool> delete(int id) async {
    final oldItems = List<AppNotification>.from(_items);
    final index = _items.indexWhere((n) => n.id == id);
    if (index == -1) return false;

    final wasUnread = !_items[index].isRead;
    _items.removeAt(index);
    if (wasUnread) _unreadCount--;
    notifyListeners();

    try {
      final response = await http.delete(
        Uri.parse('$_baseUrl/notifications/$id'),
        headers: ApiConfig.getHeaders(),
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode != 200) {
        throw Exception('Failed to delete notification');
      }
      return true;
    } catch (e) {
      debugPrint('[NotificationProvider] Failed to delete: $e');
      _items = oldItems;
      _unreadCount = _items.where((n) => !n.isRead).length;
      notifyListeners();
      return false;
    }
  }
}
