import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';
import '../services/student_api_service.dart';
import '../screens/student/document_feedback_screen.dart';
import '../theme/app_theme.dart';

import 'tr.dart';
/// Full-page notifications inbox (mobile student bottom-nav tab).
///
/// Reuses the same API + list tiles as [NotificationsPanelButton]; shell only —
/// no new notification features.
class StudentNotificationsPage extends StatefulWidget {
  const StudentNotificationsPage({super.key});

  @override
  State<StudentNotificationsPage> createState() =>
      _StudentNotificationsPageState();
}

class _StudentNotificationsPageState extends State<StudentNotificationsPage> {
  final StudentApiService _api = StudentApiService();
  List<Map<String, dynamic>> _notifications = const [];
  bool _loading = false;
  String? _error;

  static const _border = Color(0x22FFFFFF);

  String? get _email {
    final auth = context.read<AuthProvider>();
    final email = (auth.userEmail ?? auth.email ?? '').trim();
    return email.isEmpty ? null : email;
  }

  int? get _userId => context.read<AuthProvider>().userId;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
  }

  Future<void> _refresh() async {
    final email = _email;
    final userId = _userId;
    if (email == null || userId == null) return;

    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await _api.fetchNotifications(userId: userId, email: email);
      if (!mounted) return;
      setState(() {
        _notifications = List<Map<String, dynamic>>.from(
          (data['notifications'] as List? ?? const []).map(
            (e) => Map<String, dynamic>.from(e as Map),
          ),
        );
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
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
      await _refresh();
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  int? _asInt(dynamic value) {
    if (value is int) return value;
    if (value == null) return null;
    return int.tryParse(value.toString());
  }

  bool _isDocumentComment(Map<String, dynamic> n) {
    final type = (n['type'] ?? '').toString().toLowerCase();
    final related = (n['related_type'] ?? '').toString().toLowerCase();
    return type == 'document_comment' || related == 'document_comment';
  }

  Future<void> _onNotificationTap(Map<String, dynamic> n) async {
    final id = n['id'];
    if (n['is_read'] != true && id is int) {
      await _markRead(id);
    }

    if (!_isDocumentComment(n) || !mounted) return;

    final groupId = _asInt(n['group_id']);
    final documentId = _asInt(n['document_id']);
    final commentId = _asInt(n['comment_id'] ?? n['related_id']);

    if (groupId == null || documentId == null) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Tr('Could not open feedback — missing document link on this notification.',
          ),
        ),
      );
      return;
    }

    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DocumentFeedbackScreen(
          groupId: groupId,
          documentId: documentId,
          focusCommentId: commentId,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final accent = context.watch<ThemeProvider>().palette.accent;
    if (_loading && _notifications.isEmpty) {
      return Center(
        child: CircularProgressIndicator(color: accent, strokeWidth: 2),
      );
    }
    if (_error != null && _notifications.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _error!,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.white.withOpacity(0.65),
                  fontSize: 13,
                ),
              ),
              const SizedBox(height: 12),
              TextButton(
                onPressed: _refresh,
                child: const Tr('Retry'),
              ),
            ],
          ),
        ),
      );
    }
    if (_notifications.isEmpty) {
      return Center(
        child: Tr('No notifications yet.',
          style: TextStyle(
            color: Colors.white.withOpacity(0.5),
            fontSize: 14,
          ),
        ),
      );
    }

    return RefreshIndicator(
      color: accent,
      onRefresh: _refresh,
      child: ListView.separated(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: _notifications.length,
        separatorBuilder: (_, __) => const Divider(height: 1, color: _border),
        itemBuilder: (context, index) {
          final n = _notifications[index];
          return _NotificationTile(
            notification: n,
            onTap: () => _onNotificationTap(n),
          );
        },
      ),
    );
  }
}

/// AppBar notifications dropdown — lists rows from `notifications` by recipient_email.
///
/// Uses a screen-positioned [OverlayEntry] (not CompositedTransformFollower) so
/// parent rebuilds (e.g. document list fetch) cannot trigger RenderFollowerLayer
/// / debugNeedsLayout assertion loops.
class NotificationsPanelButton extends StatefulWidget {
  const NotificationsPanelButton({super.key});

  @override
  State<NotificationsPanelButton> createState() =>
      _NotificationsPanelButtonState();
}

class _NotificationsPanelButtonState extends State<NotificationsPanelButton> {
  final StudentApiService _api = StudentApiService();
  final GlobalKey _buttonKey = GlobalKey();
  OverlayEntry? _overlay;
  List<Map<String, dynamic>> _notifications = const [];
  int _unreadCount = 0;
  bool _loading = false;
  String? _error;
  Offset _panelOffset = Offset.zero;

  static const double _panelWidth = 340;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh(silent: true));
  }

  @override
  void dispose() {
    _removeOverlay(updateState: false);
    super.dispose();
  }

  String? get _email {
    final auth = context.read<AuthProvider>();
    final email = (auth.userEmail ?? auth.email ?? '').trim();
    return email.isEmpty ? null : email;
  }

  int? get _userId => context.read<AuthProvider>().userId;

  bool get _panelOpen => _overlay != null;

  void _syncOverlay() {
    if (_overlay == null) return;
    // Rebuild only the overlay entry — never setState the button while open.
    _overlay!.markNeedsBuild();
  }

  Future<void> _refresh({bool silent = false}) async {
    final email = _email;
    final userId = _userId;
    if (email == null || userId == null) return;

    if (!silent) {
      _loading = true;
      _error = null;
      if (_panelOpen) {
        _syncOverlay();
      } else if (mounted) {
        setState(() {});
      }
    }

    try {
      final data = await _api.fetchNotifications(userId: userId, email: email);
      if (!mounted) return;
      _notifications = List<Map<String, dynamic>>.from(
        (data['notifications'] as List? ?? const []).map(
          (e) => Map<String, dynamic>.from(e as Map),
        ),
      );
      _unreadCount = (data['unread_count'] as num?)?.toInt() ??
          _notifications.where((n) => n['is_read'] != true).length;
      _error = null;
      _loading = false;

      if (_panelOpen) {
        // Update dropdown only; badge refreshes when the panel closes.
        _syncOverlay();
      } else if (mounted) {
        setState(() {});
      }
    } catch (e) {
      if (!mounted) return;
      _error = e.toString();
      _loading = false;
      if (_panelOpen) {
        _syncOverlay();
      } else {
        setState(() {});
      }
    }
  }

  bool _computePanelOffset() {
    final box = _buttonKey.currentContext?.findRenderObject() as RenderBox?;
    if (box == null || !box.hasSize) return false;
    final origin = box.localToGlobal(Offset.zero);
    final size = box.size;
    final screen = MediaQuery.sizeOf(context);
    const gap = 6.0;
    const maxHeight = 420.0;

    var left = origin.dx + size.width - _panelWidth;
    left = left.clamp(8.0, screen.width - _panelWidth - 8.0);
    var top = origin.dy + size.height + gap;
    if (top + maxHeight > screen.height - 8) {
      top = (origin.dy - maxHeight - gap).clamp(8.0, screen.height - maxHeight - 8.0);
    }
    _panelOffset = Offset(left, top);
    return true;
  }

  void _togglePanel() {
    if (_overlay != null) {
      _removeOverlay();
      return;
    }
    if (!_computePanelOffset()) return;

    _overlay = OverlayEntry(
      builder: (overlayContext) {
        return Stack(
          children: [
            Positioned.fill(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: _removeOverlay,
                child: const ColoredBox(color: Color(0x01000000)),
              ),
            ),
            Positioned(
              left: _panelOffset.dx,
              top: _panelOffset.dy,
              child: Material(
                color: Colors.transparent,
                elevation: 0,
                child: _NotificationsDropdown(
                  notifications: _notifications,
                  loading: _loading,
                  error: _error,
                  onRefresh: () => _refresh(),
                  onMarkRead: _markRead,
                  onOpenComment: _openDocumentComment,
                ),
              ),
            ),
          ],
        );
      },
    );
    Overlay.of(context, rootOverlay: true).insert(_overlay!);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _panelOpen) _refresh();
    });
  }

  void _removeOverlay({bool updateState = true}) {
    _overlay?.remove();
    _overlay = null;
    if (updateState && mounted) setState(() {});
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
      if (!mounted) return;
      _error = e.toString();
      _syncOverlay();
    }
  }

  int? _asInt(dynamic value) {
    if (value is int) return value;
    if (value == null) return null;
    return int.tryParse(value.toString());
  }

  Future<void> _openDocumentComment(Map<String, dynamic> n) async {
    final type = (n['type'] ?? '').toString().toLowerCase();
    final related = (n['related_type'] ?? '').toString().toLowerCase();
    final isComment = type == 'document_comment' || related == 'document_comment';
    if (!isComment) return;

    final groupId = _asInt(n['group_id']);
    final documentId = _asInt(n['document_id']);
    final commentId = _asInt(n['comment_id'] ?? n['related_id']);
    if (groupId == null || documentId == null) return;

    _removeOverlay();
    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DocumentFeedbackScreen(
          groupId: groupId,
          documentId: documentId,
          focusCommentId: commentId,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = context.watch<ThemeProvider>().palette;
    return Container(
      key: _buttonKey,
      decoration: BoxDecoration(
        color: p.surfaceAlt,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: p.border),
      ),
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: _togglePanel,
            color: p.iconMuted,
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
    );
  }
}

class _NotificationsDropdown extends StatelessWidget {
  final List<Map<String, dynamic>> notifications;
  final bool loading;
  final String? error;
  final VoidCallback onRefresh;
  final Future<void> Function(int id) onMarkRead;
  final Future<void> Function(Map<String, dynamic> n) onOpenComment;

  const _NotificationsDropdown({
    required this.notifications,
    required this.loading,
    required this.error,
    required this.onRefresh,
    required this.onMarkRead,
    required this.onOpenComment,
  });

  @override
  Widget build(BuildContext context) {
    final p = context.watch<ThemeProvider>().palette;
    return Container(
      width: 340,
      constraints: const BoxConstraints(maxHeight: 420),
      decoration: BoxDecoration(
        color: p.surface,
        borderRadius: BorderRadius.circular(p.isDark ? p.cardRadius : 12),
        border: Border.all(color: p.isDark ? p.borderStrong : p.border),
        boxShadow: p.cardShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 8, 10),
            child: Row(
              children: [
                Expanded(
                  child: Tr('Notifications',
                    style: TextStyle(
                      color: p.textPrimary,
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                    ),
                  ),
                ),
                IconButton(
                  icon: loading
                      ? SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: p.accent,
                          ),
                        )
                      : const Icon(Icons.refresh, size: 18),
                  color: p.iconMuted,
                  tooltip: 'Refresh',
                  onPressed: loading ? null : onRefresh,
                ),
              ],
            ),
          ),
          Divider(height: 1, color: p.border),
          Expanded(
            child: loading && notifications.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: CircularProgressIndicator(color: p.accent, strokeWidth: 2),
                    ),
                  )
                : error != null && notifications.isEmpty
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(20),
                          child: Text(
                            error!,
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: p.textSecondary,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      )
                    : notifications.isEmpty
                        ? Center(
                            child: Padding(
                              padding: const EdgeInsets.all(24),
                              child: Tr('No notifications yet.',
                                style: TextStyle(
                                  color: p.textMuted,
                                  fontSize: 13,
                                ),
                              ),
                            ),
                          )
                        : ListView.separated(
                            padding: const EdgeInsets.symmetric(vertical: 8),
                            itemCount: notifications.length,
                            separatorBuilder: (_, __) =>
                                Divider(height: 1, color: p.border),
                            itemBuilder: (context, index) {
                              final n = notifications[index];
                              return _NotificationTile(
                                notification: n,
                                onTap: () async {
                                  final id = n['id'];
                                  if (n['is_read'] != true && id is int) {
                                    await onMarkRead(id);
                                  }
                                  await onOpenComment(n);
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
    final p = context.watch<ThemeProvider>().palette;
    final unread = notification['is_read'] != true;
    final title = (notification['title'] ?? '').toString();
    final message = (notification['message'] ?? '').toString();
    final createdAt = (notification['created_at'] ?? '').toString();

    return InkWell(
      onTap: onTap,
      child: Container(
        color: unread ? p.accentSoft : null,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (unread)
              Container(
                margin: const EdgeInsets.only(top: 5, right: 8),
                width: 7,
                height: 7,
                decoration: BoxDecoration(
                  color: p.accent,
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
                      color: p.textPrimary,
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
                        color: p.textSecondary,
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
                        color: p.textMuted,
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
