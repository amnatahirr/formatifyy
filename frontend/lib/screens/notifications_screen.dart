import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/notification_provider.dart';
import '../theme/app_theme.dart';
import '../models/app_notification.dart';
import '../utils/notification_router.dart';
import '../widgets/tr.dart';
import '../config/dev_user_config.dart';
import '../providers/auth_provider.dart';

class NotificationsScreen extends StatefulWidget {
  /// When true the screen is hosted inside a dashboard tab — taps must not
  /// pop the host route before navigating.
  final bool embedded;

  const NotificationsScreen({Key? key, this.embedded = false}) : super(key: key);

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<NotificationProvider>().loadFirstPage();
    });
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 200) {
      final provider = context.read<NotificationProvider>();
      if (provider.items.isNotEmpty && provider.hasMore) {
        final lastId = provider.items.last.id;
        provider.loadMore(beforeId: lastId);
      }
    }
  }

  void _handleTap(AppNotification notification) {
    final auth = context.read<AuthProvider>();
    final provider = context.read<NotificationProvider>();
    final route = routeNotification(notification, auth.userRole ?? 'student');

    provider.markRead(notification.id);

    if (route != null) {
      if (!widget.embedded) {
        Navigator.of(context).pop();
      }
      Navigator.of(context).pushNamed(route.routeName, arguments: route.arguments);
    } else {
      final errorMessage = getErrorMessageForType(notification.type);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(errorMessage)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final palette = context.watch<ThemeProvider>().palette;
    final provider = context.watch<NotificationProvider>();
    final auth = context.watch<AuthProvider>();

    return Scaffold(
      backgroundColor: palette.scaffold,
      appBar: AppBar(
        backgroundColor: palette.topBarBg,
        elevation: 0,
        title: Tr(
          'Notifications',
          style: TextStyle(color: palette.textPrimary),
        ),
        actions: [
          if (provider.unreadCount > 0)
            TextButton(
              onPressed: () => provider.markAllRead(),
              child: Tr(
                'Mark all read',
                style: TextStyle(color: palette.accent),
              ),
            ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => provider.loadFirstPage(),
        child: Column(
          children: [
            _buildFilterChips(palette, provider),
            Expanded(
              child: provider.loading && provider.items.isEmpty
                  ? const Center(child: CircularProgressIndicator())
                  : provider.error
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Tr(
                                'Failed to load notifications',
                                style: TextStyle(color: palette.textSecondary),
                              ),
                              const SizedBox(height: 8),
                              ElevatedButton(
                                onPressed: () => provider.loadFirstPage(),
                                child: Tr('Retry'),
                              ),
                            ],
                          ),
                        )
                      : _buildList(palette, provider, auth),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFilterChips(AppPalette palette, NotificationProvider provider) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          FilterChip(
            label: Tr('All'),
            selected: !provider.unreadOnly,
            onSelected: (selected) {
              if (selected) provider.setUnreadOnly(false);
            },
            selectedColor: palette.accentSoft,
            checkmarkColor: palette.accent,
            labelStyle: TextStyle(color: palette.textPrimary),
          ),
          const SizedBox(width: 8),
          FilterChip(
            label: Tr('Unread'),
            selected: provider.unreadOnly,
            onSelected: (selected) {
              if (selected) provider.setUnreadOnly(true);
            },
            selectedColor: palette.accentSoft,
            checkmarkColor: palette.accent,
            labelStyle: TextStyle(color: palette.textPrimary),
          ),
        ],
      ),
    );
  }

  static String _dayGroup(String isoString) {
    try {
      final date = DateTime.parse(isoString).toLocal();
      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day);
      final day = DateTime(date.year, date.month, date.day);
      if (day == today) return 'Today';
      if (day == today.subtract(const Duration(days: 1))) return 'Yesterday';
      return 'Earlier';
    } catch (_) {
      return 'Earlier';
    }
  }

  Widget _buildList(AppPalette palette, NotificationProvider provider, dynamic auth) {
    // Server already filters when unreadOnly is set — items arrive newest-first.
    final items = provider.items;

    if (items.isEmpty) {
      return Center(
        child: Tr(
          provider.unreadOnly ? 'No unread notifications' : 'No notifications',
          style: TextStyle(color: palette.textSecondary),
        ),
      );
    }

    // Flatten into [header, item, item, header, item, ...] entries.
    final entries = <Object>[];
    String? lastGroup;
    for (final n in items) {
      final group = _dayGroup(n.createdAt);
      if (group != lastGroup) {
        entries.add(group);
        lastGroup = group;
      }
      entries.add(n);
    }

    return ListView.builder(
      controller: _scrollController,
      itemCount: entries.length + (provider.loading ? 1 : 0),
      itemBuilder: (context, index) {
        if (index >= entries.length) {
          return const Center(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: CircularProgressIndicator(),
            ),
          );
        }

        final entry = entries[index];
        if (entry is String) {
          return Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 6),
            child: Tr(
              entry,
              style: TextStyle(
                color: palette.textMuted,
                fontSize: 11,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.8,
              ),
            ),
          );
        }

        final item = entry as AppNotification;
        return _NotificationListItem(
          notification: item,
          onTap: () => _handleTap(item),
          onDelete: () => _handleDelete(item, provider),
          palette: palette,
          hasFyp: DevUserConfig.hasFypModule,
        );
      },
    );
  }

  void _handleDelete(AppNotification notification, NotificationProvider provider) {
    provider.delete(notification.id);
  }
}

class _NotificationListItem extends StatelessWidget {
  final AppNotification notification;
  final VoidCallback onTap;
  final VoidCallback onDelete;
  final AppPalette palette;
  final bool hasFyp;

  const _NotificationListItem({
    required this.notification,
    required this.onTap,
    required this.onDelete,
    required this.palette,
    required this.hasFyp,
  });

  @override
  Widget build(BuildContext context) {
    final isRead = notification.isRead;

    return Dismissible(
      key: Key(notification.id.toString()),
      direction: DismissDirection.endToStart,
      onDismissed: (_) => onDelete(),
      background: Container(
        color: Colors.red,
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 16),
        child: Icon(Icons.delete, color: Colors.white),
      ),
      child: InkWell(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: isRead ? null : palette.accentSoft,
            border: Border(
              bottom: BorderSide(color: palette.border.withOpacity(0.5)),
            ),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                _iconForType(notification.type),
                size: 24,
                color: isRead ? palette.iconMuted : palette.accent,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      notification.title,
                      style: TextStyle(
                        color: palette.textPrimary,
                        fontWeight: isRead ? FontWeight.normal : FontWeight.w600,
                        fontSize: 15,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      notification.body,
                      style: TextStyle(
                        color: palette.textSecondary,
                        fontSize: 13,
                      ),
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _formatTime(notification.createdAt),
                      style: TextStyle(
                        color: palette.textMuted,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  IconData _iconForType(String type) {
    switch (type) {
      case 'analysis_finished':
        return Icons.check_circle_outline;
      case 'analysis_failed':
        return Icons.error_outline;
      case 'submission_approved':
        return Icons.check_circle_outline;
      case 'submission_revision_requested':
        return Icons.edit_note;
      case 'submission_rejected':
        return Icons.cancel_outlined;
      case 'new_assignment_request':
        return Icons.person_add_outlined;
      case 'supervisor_changed':
        return Icons.swap_horiz_rounded;
      case 'group_discarded':
        return Icons.group_off_outlined;
      case 'assignment_accepted':
        return Icons.check_circle_outline;
      case 'assignment_rejected':
        return Icons.cancel_outlined;
      case 'student_submitted':
        return Icons.upload_file_outlined;
      case 'student_resubmitted':
        return Icons.refresh_outlined;
      case 'supervisor_comment':
        return Icons.comment_outlined;
      case 'meeting_note':
        return Icons.note_outlined;
      case 'collaboration_invite':
        return Icons.group_add_outlined;
      case 'merge_conflict':
        return Icons.merge_type_outlined;
      case 'member_commit':
        return Icons.commit_outlined;
      case 'plagiarism_high':
        return Icons.warning_outlined;
      case 'deadline_reminder_3_days':
      case 'deadline_reminder_1_day':
      case 'deadline_today':
        return Icons.calendar_today_outlined;
      case 'supervisor_created':
        return Icons.person_add_outlined;
      case 'new_user_signup':
        return Icons.person_add_outlined;
      default:
        return Icons.notifications_outlined;
    }
  }

  String _formatTime(String isoString) {
    try {
      final date = DateTime.parse(isoString);
      final now = DateTime.now();
      final difference = now.difference(date);

      if (difference.inMinutes < 1) {
        return 'Just now';
      } else if (difference.inMinutes < 60) {
        return '${difference.inMinutes}m ago';
      } else if (difference.inHours < 24) {
        return '${difference.inHours}h ago';
      } else if (difference.inDays < 7) {
        return '${difference.inDays}d ago';
      } else {
        return '${date.day}/${date.month}/${date.year}';
      }
    } catch (e) {
      return isoString;
    }
  }
}
