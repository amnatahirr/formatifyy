import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../theme/app_theme.dart';
import '../../utils/responsive.dart';
import '../../widgets/admin/admin_ui.dart';
import 'document_review_screen.dart';
import 'meeting_notes_screen.dart';
import 'plagiarism_monitor_detail_screen.dart';

class GroupDetailScreen extends StatefulWidget {
  final int groupId;
  final String? groupTitle;

  const GroupDetailScreen({
    super.key,
    required this.groupId,
    this.groupTitle,
  });

  @override
  State<GroupDetailScreen> createState() => _GroupDetailScreenState();
}

class _GroupDetailScreenState extends State<GroupDetailScreen> {
  final SupervisorApiService _api = SupervisorApiService();
  SupervisorGroupDetailModel? _detail;
  String? _error;
  bool _loading = true;
  bool _discarding = false;

  @override
  void initState() {
    super.initState();
    _loadDetail();
  }

  Future<void> _loadDetail() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final detail = await _api.fetchGroupDetail(userId, widget.groupId);
      if (mounted) setState(() => _detail = detail);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _discardGroup() async {
    final title = _detail?.group.title.isNotEmpty == true
        ? _detail!.group.title
        : (widget.groupTitle ?? 'this group');
    final reasonController = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          backgroundColor: AdminColors.surface,
          shape: adminDialogShape(),
          title: const Text('Discard group?'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Remove "$title" from My Groups and free one supervision slot.',
                style: TextStyle(color: Colors.white.withOpacity(0.75), height: 1.4),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: reasonController,
                maxLines: 2,
                style: const TextStyle(color: Colors.white),
                decoration: adminFieldDecoration(label: 'Reason (optional)'),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AdminColors.danger,
                foregroundColor: Colors.white,
              ),
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Discard'),
            ),
          ],
        );
      },
    );
    final reason = reasonController.text.trim();
    reasonController.dispose();
    if (confirmed != true || !mounted) return;

    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _discarding = true);
    try {
      final result = await _api.discardGroup(
        userId: userId,
        groupId: widget.groupId,
        reason: reason.isEmpty ? null : reason,
      );
      if (!mounted) return;
      final slots = result['slots_used'];
      final max = result['max_groups'];
      showAdminSnackBar(
        context,
        slots != null && max != null
            ? 'Group discarded. Slots used: $slots / $max'
            : 'Group discarded. Slot freed.',
      );
      Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _discarding = false);
    }
  }

  void _openDocumentReview() {
    final doc = _detail?.latestDocument;
    if (doc == null) {
      showAdminSnackBar(context, 'No submitted document is available to review yet.', isError: true);
      return;
    }
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DocumentReviewScreen(
          groupId: widget.groupId,
          documentId: doc.id,
          documentTitle: doc.title,
        ),
      ),
    );
  }

  void _openMeetingNotes() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => MeetingNotesScreen(
          groupId: widget.groupId,
          groupTitle: widget.groupTitle ?? _detail?.group.title,
        ),
      ),
    );
  }

  void _openPlagiarismMonitor() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => PlagiarismMonitorDetailScreen(
          groupId: widget.groupId,
          titleHint: widget.groupTitle ?? _detail?.group.title,
        ),
      ),
    );
  }

  Color _statusColor(String status) {
    switch (status.toLowerCase()) {
      case 'approved':
        return AdminColors.success;
      case 'revision':
        return AdminColors.warning;
      default:
        return AdminColors.primary;
    }
  }

  @override
  Widget build(BuildContext context) {
    final title = _detail?.group.title.isNotEmpty == true
        ? _detail!.group.title
        : (widget.groupTitle ?? 'Group Detail');

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: AppPalette.dark.innerGlowBackdrop(
        child: Column(
          children: [
            Container(
              height: 72,
              decoration: BoxDecoration(
                color: AdminColors.surface,
                border: Border(bottom: BorderSide(color: AdminColors.borderStrong)),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  IconButton(
                    tooltip: 'Back to My Groups',
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.arrow_back_rounded, color: Colors.white),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title,
                          style: const TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                            letterSpacing: -0.2,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 2),
                        Text(
                          'Group overview',
                          style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.5)),
                        ),
                      ],
                    ),
                  ),
                  TextButton.icon(
                    onPressed: (_discarding || _loading) ? null : _discardGroup,
                    icon: _discarding
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2, color: AdminColors.danger),
                          )
                        : const Icon(Icons.delete_outline_rounded, size: 18),
                    label: const Text('Discard'),
                    style: TextButton.styleFrom(foregroundColor: AdminColors.danger),
                  ),
                ],
              ),
            ),
            Expanded(child: _buildBody()),
          ],
        ),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const AdminPage(child: AdminLoadingView(label: 'Loading group...'));
    }
    if (_error != null) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _loadDetail));
    }
    final detail = _detail;
    if (detail == null) {
      return const AdminPage(
        child: AdminEmptyView(
          icon: Icons.groups_outlined,
          title: 'Group unavailable',
          message: 'Group details are not available.',
        ),
      );
    }

    final doc = detail.latestDocument;
    return AdminPage(
      onRefresh: _loadDetail,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageHeader(
            title: detail.group.title,
            subtitle: detail.group.projectTitle.isEmpty
                ? 'Milestones and latest submission'
                : detail.group.projectTitle,
          ),
          const SizedBox(height: 22),
          AdminSectionCard(
            title: 'Milestones',
            subtitle: '${detail.milestones.where((m) => m.isCompleted).length} of ${detail.milestones.length} completed',
            icon: Icons.flag_rounded,
            child: Column(
              children: [
                for (var i = 0; i < detail.milestones.length; i++) ...[
                  if (i > 0) const SizedBox(height: 12),
                  _MilestoneRow(milestone: detail.milestones[i]),
                ],
              ],
            ),
          ),
          const SizedBox(height: 18),
          AdminSectionCard(
            title: 'Latest Document',
            icon: Icons.description_outlined,
            accent: AdminColors.accent,
            child: doc == null
                ? Text(
                    'No document has been submitted yet.',
                    style: TextStyle(color: Colors.white.withOpacity(0.65), height: 1.45),
                  )
                : Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const AdminIconBadge(icon: Icons.description_outlined, size: 20),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              doc.title,
                              style: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w600,
                                color: Colors.white,
                              ),
                            ),
                            if (doc.filename.isNotEmpty) ...[
                              const SizedBox(height: 4),
                              Text(
                                doc.filename,
                                style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.5)),
                              ),
                            ],
                            if (doc.submittedAt.isNotEmpty) ...[
                              const SizedBox(height: 6),
                              Text(
                                'Submitted: ${doc.submittedAt}',
                                style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.45)),
                              ),
                            ],
                          ],
                        ),
                      ),
                      AdminPill(
                        label: doc.statusLabel,
                        color: _statusColor(doc.status),
                      ),
                    ],
                  ),
          ),
          const SizedBox(height: 24),
          if (isCompact(context)) ...[
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _openDocumentReview,
                icon: const Icon(Icons.rate_review_outlined, size: 18),
                label: const Text('Document Review'),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _openMeetingNotes,
                icon: const Icon(Icons.sticky_note_2_outlined, size: 18),
                label: const Text('Meeting Notes'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: const BorderSide(color: AdminColors.borderStrong),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _openPlagiarismMonitor,
                icon: const Icon(Icons.policy_rounded, size: 18),
                label: const Text('Plagiarism Monitor'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AdminColors.warning,
                  side: BorderSide(color: AdminColors.warning.withOpacity(0.55)),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
          ] else ...[
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _openDocumentReview,
                    icon: const Icon(Icons.rate_review_outlined, size: 18),
                    label: const Text('Document Review'),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _openMeetingNotes,
                    icon: const Icon(Icons.sticky_note_2_outlined, size: 18),
                    label: const Text('Meeting Notes'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.white,
                      side: const BorderSide(color: AdminColors.borderStrong),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _openPlagiarismMonitor,
                icon: const Icon(Icons.policy_rounded, size: 18),
                label: const Text('Plagiarism Monitor'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AdminColors.warning,
                  side: BorderSide(color: AdminColors.warning.withOpacity(0.55)),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _MilestoneRow extends StatelessWidget {
  final GroupMilestoneModel milestone;

  const _MilestoneRow({required this.milestone});

  @override
  Widget build(BuildContext context) {
    final done = milestone.isCompleted;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: done ? AdminColors.success.withOpacity(0.08) : AdminColors.surfaceAlt,
        borderRadius: BorderRadius.circular(adminTileRadius),
        border: Border.all(
          color: done ? AdminColors.success.withOpacity(0.35) : AdminColors.borderStrong,
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              color: done ? AdminColors.success : Colors.white.withOpacity(0.08),
              shape: BoxShape.circle,
              border: done ? null : Border.all(color: Colors.white.withOpacity(0.25)),
            ),
            child: Icon(
              done ? Icons.check_rounded : Icons.circle_outlined,
              size: 16,
              color: done ? Colors.white : Colors.white.withOpacity(0.45),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              milestone.name,
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: done ? Colors.white : Colors.white.withOpacity(0.78),
              ),
            ),
          ),
          AdminPill(
            label: done ? 'Completed' : 'Pending',
            color: done ? AdminColors.success : AdminColors.primary,
          ),
        ],
      ),
    );
  }
}
