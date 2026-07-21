import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
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
      backgroundColor: AdminColors.background,
      body: Column(
        children: [
          Container(
            height: 72,
            decoration: BoxDecoration(
              color: AdminColors.surface,
              border: Border(bottom: BorderSide(color: AdminColors.border.withOpacity(0.5))),
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
                        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Colors.white),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      Text(
                        'Group overview',
                        style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.5)),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Expanded(child: _buildBody()),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const AdminPage(child: AdminLoadingView());
    }
    if (_error != null) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _loadDetail));
    }
    final detail = _detail;
    if (detail == null) {
      return const AdminPage(child: AdminEmptyView(message: 'Group details are not available.'));
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
            child: doc == null
                ? Text(
                    'No document has been submitted yet.',
                    style: TextStyle(color: Colors.white.withOpacity(0.65), height: 1.45),
                  )
                : Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: AdminColors.primary.withOpacity(0.14),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(Icons.description_outlined, color: AdminColors.primary, size: 20),
                      ),
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
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: _statusColor(doc.status).withOpacity(0.16),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          doc.statusLabel,
                          style: TextStyle(
                            color: _statusColor(doc.status),
                            fontWeight: FontWeight.w700,
                            fontSize: 12,
                          ),
                        ),
                      ),
                    ],
                  ),
          ),
          const SizedBox(height: 24),
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
                    side: const BorderSide(color: AdminColors.border),
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
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      decoration: BoxDecoration(
        color: done ? AdminColors.success.withOpacity(0.08) : AdminColors.background.withOpacity(0.35),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: done ? AdminColors.success.withOpacity(0.35) : AdminColors.border.withOpacity(0.8),
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
          Text(
            done ? 'Completed' : 'Pending',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: done ? AdminColors.success : Colors.white.withOpacity(0.45),
            ),
          ),
        ],
      ),
    );
  }
}
