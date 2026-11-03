import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/notification_provider.dart';
import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';
import '../screens/notifications_screen.dart';
import '../utils/notification_router.dart';
import '../utils/responsive.dart';

class NotificationBell extends StatelessWidget {
  const NotificationBell({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final palette = context.watch<ThemeProvider>().palette;
    final provider = context.watch<NotificationProvider>();
    final unreadCount = provider.unreadCount;

    return IconButton(
      icon: Stack(
        clipBehavior: Clip.none,
        children: [
          Icon(
            Icons.notifications_outlined,
            color: palette.iconMuted,
          ),
          if (unreadCount > 0)
            Positioned(
              right: -6,
              top: -6,
              child: _Badge(count: unreadCount),
            ),
        ],
      ),
      onPressed: () => _showPanel(context, palette),
    );
  }

  void _showPanel(BuildContext context, AppPalette palette) {
    final compact = isCompact(context);
    
    if (compact) {
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const NotificationsScreen()),
      );
    } else {
      _showDesktopPanel(context, palette);
    }
  }

  void _showDesktopPanel(BuildContext context, AppPalette palette) {
    final RenderBox button = context.findRenderObject() as RenderBox;
    final Offset offset = button.localToGlobal(Offset.zero);
    final Size size = button.size;

    showMenu(
      context: context,
      position: RelativeRect.fromLTRB(
        offset.dx + size.width - 300,
        offset.dy + size.height + 8,
        offset.dx,
        offset.dy + size.height + 8,
      ),
      items: [
        PopupMenuItem(
          enabled: false,
          child: SizedBox(
            width: 300,
            height: 400,
            child: _NotificationPanel(),
          ),
        ),
      ],
    );
  }
}

class _Badge extends StatelessWidget {
  final int count;

  const _Badge({required this.count});

  @override
  Widget build(BuildContext context) {
    final palette = context.watch<ThemeProvider>().palette;
    final displayCount = count > 99 ? '99+' : count.toString();

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: palette.accent,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: palette.surface, width: 2),
      ),
      child: Text(
        displayCount,
        style: TextStyle(
          color: Colors.white,
          fontSize: 10,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }
}

class _NotificationPanel extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final palette = context.watch<ThemeProvider>().palette;
    final provider = context.watch<NotificationProvider>();

    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            border: Border(bottom: BorderSide(color: palette.border)),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Notifications',
                style: TextStyle(
                  color: palette.textPrimary,
                  fontWeight: FontWeight.w600,
                  fontSize: 16,
                ),
              ),
              Row(
                children: [
                  if (provider.unreadCount > 0)
                    TextButton(
                      onPressed: () => provider.markAllRead(),
                      child: Text(
                        'Mark all read',
                        style: TextStyle(color: palette.accent, fontSize: 12),
                      ),
                    ),
                  TextButton(
                    onPressed: () {
                      Navigator.of(context).pop();
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => const NotificationsScreen(),
                        ),
                      );
                    },
                    child: Text(
                      'View all',
                      style: TextStyle(color: palette.accent, fontSize: 12),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        Expanded(
          child: provider.loading
              ? const Center(child: CircularProgressIndicator())
              : provider.error
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text(
                            'Failed to load',
                            style: TextStyle(color: palette.textSecondary),
                          ),
                          const SizedBox(height: 8),
                          ElevatedButton(
                            onPressed: () => provider.loadFirstPage(),
                            child: const Text('Retry'),
                          ),
                        ],
                      ),
                    )
                  : provider.items.isEmpty
                      ? Center(
                          child: Text(
                            'No notifications',
                            style: TextStyle(color: palette.textSecondary),
                          ),
                        )
                      : ListView.builder(
                          itemCount: provider.items.length > 5 ? 5 : provider.items.length,
                          itemBuilder: (context, index) {
                            final item = provider.items[index];
                            return _NotificationTile(notification: item);
                          },
                        ),
        ),
      ],
    );
  }
}

class _NotificationTile extends StatelessWidget {
  final dynamic notification;

  const _NotificationTile({required this.notification});

  @override
  Widget build(BuildContext context) {
    final palette = context.watch<ThemeProvider>().palette;
    final provider = context.watch<NotificationProvider>();
    final auth = context.watch<AuthProvider>();
    final isRead = notification.isRead as bool? ?? false;
    final title = notification.title as String? ?? '';
    final body = notification.body as String? ?? '';
    final type = notification.type as String? ?? '';

    return InkWell(
      onTap: () async {
        final id = notification.id as int?;
        if (id != null && !isRead) {
          await provider.markRead(id);
        }

        final route = routeNotification(notification, auth.userRole ?? 'student');
        Navigator.of(context).pop();

        if (route != null) {
          Navigator.of(context).pushNamed(route.routeName, arguments: route.arguments);
        } else {
          final errorMessage = getErrorMessageForType(type);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(errorMessage)),
          );
        }
      },
      child: Container(
        padding: const EdgeInsets.all(12),
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
              _iconForType(type),
              size: 20,
              color: isRead ? palette.iconMuted : palette.accent,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      color: palette.textPrimary,
                      fontWeight: isRead ? FontWeight.normal : FontWeight.w600,
                      fontSize: 14,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Text(
                    body,
                    style: TextStyle(
                      color: palette.textSecondary,
                      fontSize: 12,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ],
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
      case 'student_submitted':
        return Icons.upload_file_outlined;
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
      default:
        return Icons.notifications_outlined;
    }
  }
}
