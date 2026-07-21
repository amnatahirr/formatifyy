import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';
import '../services/student_api_service.dart';

/// AppBar notifications dropdown — lists rows from `notifications` by recipient_email.
class NotificationsPanelButton extends StatefulWidget {
  const NotificationsPanelButton({super.key});

  @override
  State<NotificationsPanelButton> createState() =>
      _NotificationsPanelButtonState();
}

class _NotificationsPanelButtonState extends State<NotificationsPanelButton> {
  final StudentApiService _api = StudentApiService();
  final LayerLink _layerLink = LayerLink();
  OverlayEntry? _overlay;
  List<Map<String, dynamic>> _notifications = const [];
  int _unreadCount = 0;
  bool _loading = false;
  String? _error;

  static const _card = Color(0xFF161B22);
  static const _border = Color(0x22FFFFFF);
  static const _accent = Color(0xFF3B82F6);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh(silent: true));
  }

  @override
  void dispose() {
    _removeOverlay();
    super.dispose();
  }

  String? get _email {
    final auth = context.read<AuthProvider>();
    final email = (auth.userEmail ?? auth.email ?? '').trim();
    return email.isEmpty ? null : email;
  }

  int? get _userId => context.read<AuthProvider>().userId;

  Future<void> _refresh({bool silent = false}) async {
    final email = _email;
    final userId = _userId;
    if (email == null || userId == null) return;

    if (!silent) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final data = await _api.fetchNotifications(userId: userId, email: email);
      if (!mounted) return;
      setState(() {
        _notifications = List<Map<String, dynamic>>.from(
          (data['notifications'] as List? ?? const []).map(
            (e) => Map<String, dynamic>.from(e as Map),
          ),
        );
        _unreadCount = (data['unread_count'] as num?)?.toInt() ??
            _notifications.where((n) => n['is_read'] != true).length;
        _error = null;
      });
      _overlay?.markNeedsBuild();
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
      _overlay?.markNeedsBuild();
    } finally {
      if (mounted && !silent) setState(() => _loading = false);
    }
  }

  void _togglePanel() {
    if (_overlay != null) {
      _removeOverlay();
      return;
    }
    _refresh();
    _overlay = OverlayEntry(
      builder: (context) => Stack(
        children: [
          Positioned.fill(
            child: GestureDetector(
              behavior: HitTestBehavior.translucent,
              onTap: _removeOverlay,
              child: const SizedBox.expand(),
            ),
          ),
          CompositedTransformFollower(
            link: _layerLink,
            showWhenUnlinked: false,
            offset: const Offset(-280, 44),
            child: Material(
              color: Colors.transparent,
              child: _NotificationsDropdown(
                notifications: _notifications,
                loading: _loading,
                error: _error,
                onRefresh: () => _refresh(),
                onMarkRead: _markRead,
              ),
            ),
          ),
        ],
      ),
    );
    Overlay.of(context).insert(_overlay!);
  }

  void _removeOverlay() {
    _overlay?.remove();
    _overlay = null;
  }

  Future<void> _markRead(int id) async {
    final email = _email;
    final userId = _userId;
    if (email == null || userId == null) return;
    try {
      await _api.markNotificationRead(
        userId: userId,
        email: email,
        notificationId: id,
      );
      await _refresh(silent: true);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    return CompositedTransformTarget(
      link: _layerLink,
      child: Container(
        decoration: BoxDecoration(
          color: const Color(0xFF0D1117),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: Colors.white.withOpacity(0.1)),
        ),
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            IconButton(
              icon: const Icon(Icons.notifications_outlined),
              onPressed: _togglePanel,
              color: Colors.white.withOpacity(0.6),
              tooltip: 'Notifications',
            ),
            if (_unreadCount > 0)
              Positioned(
                right: 8,
                top: 8,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                  decoration: BoxDecoration(
                    color: const Color(0xFFEF4444),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  constraints: const BoxConstraints(minWidth: 16),
                  child: Text(
                    _unreadCount > 9 ? '9+' : '$_unreadCount',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _NotificationsDropdown extends StatelessWidget {
  final List<Map<String, dynamic>> notifications;
  final bool loading;
  final String? error;
  final VoidCallback onRefresh;
  final Future<void> Function(int id) onMarkRead;

  const _NotificationsDropdown({
    required this.notifications,
    required this.loading,
    required this.error,
    required this.onRefresh,
    required this.onMarkRead,
  });

  static const _card = Color(0xFF161B22);
  static const _border = Color(0x22FFFFFF);
  static const _accent = Color(0xFF3B82F6);

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 340,
      constraints: const BoxConstraints(maxHeight: 420),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _border),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.45),
            blurRadius: 18,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 8, 10),
            child: Row(
              children: [
                const Expanded(
                  child: Text(
                    'Notifications',
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.refresh, size: 18),
                  color: Colors.white54,
                  tooltip: 'Refresh',
                  onPressed: onRefresh,
                ),
              ],
            ),
          ),
          const Divider(height: 1, color: _border),
          Expanded(
            child: loading
                ? const Center(
                    child: Padding(
                      padding: EdgeInsets.all(24),
                      child: CircularProgressIndicator(color: _accent, strokeWidth: 2),
                    ),
                  )
                : error != null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(20),
                          child: Text(
                            error!,
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.65),
                              fontSize: 12,
                            ),
                          ),
                        ),
                      )
                    : notifications.isEmpty
                        ? Center(
                            child: Padding(
                              padding: const EdgeInsets.all(24),
                              child: Text(
                                'No notifications yet.',
                                style: TextStyle(
                                  color: Colors.white.withOpacity(0.5),
                                  fontSize: 13,
                                ),
                              ),
                            ),
                          )
                        : ListView.separated(
                            padding: const EdgeInsets.symmetric(vertical: 8),
                            itemCount: notifications.length,
                            separatorBuilder: (_, __) =>
                                const Divider(height: 1, color: _border),
                            itemBuilder: (context, index) {
                              final n = notifications[index];
                              return _NotificationTile(
                                notification: n,
                                onTap: () {
                                  if (n['is_read'] != true) {
                                    onMarkRead(n['id'] as int);
                                  }
                                },
                              );
                            },
                          ),
          ),
        ],
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  final Map<String, dynamic> notification;
  final VoidCallback onTap;

  const _NotificationTile({
    required this.notification,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final unread = notification['is_read'] != true;
    final title = (notification['title'] ?? '').toString();
    final message = (notification['message'] ?? '').toString();
    final createdAt = (notification['created_at'] ?? '').toString();

    return InkWell(
      onTap: onTap,
      child: Container(
        color: unread ? const Color(0xFF3B82F6).withOpacity(0.08) : null,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (unread)
              Container(
                margin: const EdgeInsets.only(top: 5, right: 8),
                width: 7,
                height: 7,
                decoration: const BoxDecoration(
                  color: Color(0xFF3B82F6),
                  shape: BoxShape.circle,
                ),
              )
            else
              const SizedBox(width: 15),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: unread ? FontWeight.w700 : FontWeight.w500,
                      fontSize: 13,
                    ),
                  ),
                  if (message.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      message,
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.65),
                        fontSize: 12,
                        height: 1.35,
                      ),
                    ),
                  ],
                  if (createdAt.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      createdAt.length >= 16
                          ? createdAt.substring(0, 16)
                          : createdAt,
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.35),
                        fontSize: 11,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
