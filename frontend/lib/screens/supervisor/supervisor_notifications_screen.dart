import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../widgets/admin/admin_ui.dart';
import 'document_review_screen.dart';
import 'submission_detail_screen.dart';

/// Supervisor inbox — submissions, student replies, and other alerts.
class SupervisorNotificationsScreen extends StatefulWidget {
  const SupervisorNotificationsScreen({super.key});

  @override
  State<SupervisorNotificationsScreen> createState() =>
      _SupervisorNotificationsScreenState();
}

class _SupervisorNotificationsScreenState
    extends State<SupervisorNotificationsScreen> {
  final SupervisorApiService _api = SupervisorApiService();
  List<Map<String, dynamic>> _items = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _load();
    });
  }

  Future<void> _load() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await _api.fetchNotifications(userId);
      if (!mounted) return;
      setState(() => _items = data);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  int? _asInt(dynamic value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value == null) return null;
    return int.tryParse(value.toString());
  }

  Future<void> _openItem(Map<String, dynamic> n) async {
    final userId = context.read<AuthProvider>().userId;
    final id = _asInt(n['id']);
    if (userId != null && id != null && n['is_read'] != true) {
      try {
        await _api.markNotificationRead(userId: userId, notificationId: id);
      } catch (_) {}
    }

    final relatedType = (n['related_type'] ?? n['type'] ?? '').toString().toLowerCase();
    final groupId = _asInt(n['group_id']);
    final documentId = _asInt(n['document_id']);
    final submissionId = _asInt(n['submission_id'] ?? n['related_id']);

    if (!mounted) return;

    if (relatedType.contains('final_submission') && submissionId != null) {
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => SubmissionDetailScreen(
            submissionId: submissionId,
            titleHint: (n['submission_title'] ?? n['title'] ?? '').toString(),
          ),
        ),
      );
    } else if ((relatedType.contains('document_comment') ||
            relatedType.contains('student_reply')) &&
        groupId != null &&
        documentId != null) {
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => DocumentReviewScreen(
            groupId: groupId,
            documentId: documentId,
            documentTitle: (n['document_title'] ?? n['title'] ?? '').toString(),
          ),
        ),
      );
    } else {
      showAdminSnackBar(context, 'Opened notification. No linked screen available.');
    }

    if (mounted) _load();
  }

  IconData _iconFor(Map<String, dynamic> n) {
    final type = (n['type'] ?? n['related_type'] ?? '').toString().toLowerCase();
    if (type.contains('submission')) return Icons.fact_check_rounded;
    if (type.contains('reply') || type.contains('comment')) {
      return Icons.chat_bubble_outline_rounded;
    }
    if (type.contains('assignment')) return Icons.assignment_ind_rounded;
    return Icons.notifications_outlined;
  }

  @override
  Widget build(BuildContext context) {
    if (_loading && _items.isEmpty) {
      return const AdminPage(child: AdminLoadingView(label: 'Loading notifications...'));
    }
    if (_error != null && _items.isEmpty) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _load));
    }

    return AdminPage(
      onRefresh: _load,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageMeta(
            text: _items.isEmpty
                ? 'No alerts yet'
                : '${_items.where((n) => n['is_read'] != true).length} unread · tap to open',
          ),
          const SizedBox(height: 16),
          if (_items.isEmpty)
            const AdminEmptyView(
              icon: Icons.notifications_none_rounded,
              title: 'Inbox is empty',
              message:
                  'New submissions and student replies to your comments will appear here.',
            )
          else
            ..._items.map((n) {
              final unread = n['is_read'] != true;
              return Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: InkWell(
                  onTap: () => _openItem(n),
                  borderRadius: BorderRadius.circular(adminCardRadius),
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: adminCardDecoration(
                      borderColor: unread
                          ? AdminColors.accent.withOpacity(0.5)
                          : null,
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        AdminIconBadge(
                          icon: _iconFor(n),
                          color: unread ? AdminColors.accent : AdminColors.primary,
                          size: 20,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: Text(
                                      (n['title'] ?? 'Notification').toString(),
                                      style: TextStyle(
                                        color: Colors.white,
                                        fontWeight:
                                            unread ? FontWeight.w700 : FontWeight.w600,
                                        fontSize: 14,
                                      ),
                                    ),
                                  ),
                                  if (unread)
                                    Container(
                                      width: 9,
                                      height: 9,
                                      decoration: BoxDecoration(
                                        color: AdminColors.accentBright,
                                        shape: BoxShape.circle,
                                        boxShadow: [
                                          BoxShadow(
                                            color: AdminColors.accent.withOpacity(0.6),
                                            blurRadius: 8,
                                          ),
                                        ],
                                      ),
                                    ),
                                ],
                              ),
                              const SizedBox(height: 6),
                              Text(
                                (n['message'] ?? '').toString(),
                                style: TextStyle(
                                  color: Colors.white.withOpacity(0.65),
                                  fontSize: 13,
                                  height: 1.4,
                                ),
                                maxLines: 3,
                                overflow: TextOverflow.ellipsis,
                              ),
                              if ((n['created_at'] ?? '').toString().isNotEmpty) ...[
                                const SizedBox(height: 8),
                                Text(
                                  n['created_at'].toString(),
                                  style: TextStyle(
                                    color: Colors.white.withOpacity(0.4),
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
                ),
              );
            }),
        ],
      ),
    );
  }
}
