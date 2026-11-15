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

import '../../widgets/tr.dart';
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
  bool _busy = false;

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
          title: const Tr('Discard group?'),
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
              child: const Tr('Cancel'),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AdminColors.danger,
                foregroundColor: Colors.white,
              ),
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Tr('Discard'),
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

  String _phaseLabel(int? semester) {
    switch (semester) {
      case 6:
        return 'Proposal';
      case 7:
        return 'FYP-1';
      case 8:
        return 'FYP-2';
      default:
        return semester == null ? '—' : 'Semester $semester';
    }
  }

  String _nextPhaseLabel(int? semester) {
    switch (semester) {
      case 6:
        return 'FYP-1';
      case 7:
        return 'FYP-2';
      case 8:
        return 'Graduation';
      default:
        return 'the next semester';
    }
  }

  Future<void> _promoteGroup() async {
    final sem = _detail?.group.currentSemester;
    final next = _nextPhaseLabel(sem);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AdminColors.surface,
        shape: adminDialogShape(),
        title: Text('Promote to $next?'),
        content: Text(
          'All milestones of ${_phaseLabel(sem)} will be marked completed and the group '
          'moves to $next. Group members are notified.',
          style: TextStyle(color: Colors.white.withOpacity(0.75), height: 1.4),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Tr('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AdminColors.success,
              foregroundColor: Colors.white,
            ),
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Tr('Promote'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _busy = true);
    try {
      final r = await _api.promoteGroup(userId: userId, groupId: widget.groupId);
      if (!mounted) return;
      showAdminSnackBar(context, (r['message'] ?? 'Group promoted.').toString());
      await _loadDetail();
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _markRework() async {
    final controller = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AdminColors.surface,
        shape: adminDialogShape(),
        title: const Tr('Not promoted — rework needed'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'The current milestones stay incomplete and the students see '
              '"You have to rework on this milestone".',
              style: TextStyle(color: Colors.white.withOpacity(0.75), height: 1.4),
            ),
            const SizedBox(height: 14),
            TextField(
              controller: controller,
              maxLines: 3,
              style: const TextStyle(color: Colors.white),
              decoration: adminFieldDecoration(label: 'Reason for not promoting (required)'),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Tr('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AdminColors.warning,
              foregroundColor: Colors.white,
            ),
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Tr('Mark for rework'),
          ),
        ],
      ),
    );
    final note = controller.text.trim();
    controller.dispose();
    if (confirmed != true || !mounted) return;
    if (note.isEmpty) {
      showAdminSnackBar(context, 'Please write the reason for not promoting.', isError: true);
      return;
    }
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _busy = true);
    try {
      await _api.markGroupRework(
        userId: userId,
        groupId: widget.groupId,
        note: note.isEmpty ? null : note,
      );
      if (!mounted) return;
      showAdminSnackBar(context, 'Marked for rework. Students were notified.');
      await _loadDetail();
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _extendMilestone(GroupMilestoneModel m) async {
    final current = DateTime.tryParse(m.deadlineDate ?? '');
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final picked = await showDatePicker(
      context: context,
      firstDate: today,
      lastDate: DateTime(2100),
      initialDate: (current != null && !current.isBefore(today)) ? current : today,
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(
            colorScheme: const ColorScheme.dark(
              primary: AdminColors.primary,
              surface: AdminColors.surface,
            ),
          ),
          child: child!,
        );
      },
    );
    if (picked == null || !mounted) return;
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _busy = true);
    try {
      await _api.extendMilestone(
        userId: userId,
        groupId: widget.groupId,
        milestoneId: m.id,
        deadlineDate: picked.toIso8601String().split('T').first,
      );
      if (!mounted) return;
      showAdminSnackBar(context, 'Deadline extended.');
      await _loadDetail();
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _buildPromotionCard(SupervisorGroupDetailModel detail) {
    final sem = detail.group.currentSemester;
    final graduated = detail.group.isGraduated;
    final managed = detail.milestones.any((m) => m.isManaged);
    return AdminSectionCard(
      title: 'Semester & Promotion',
      subtitle: graduated
          ? 'This group has graduated'
          : 'Current phase: ${_phaseLabel(sem)}${sem == null ? '' : ' (Semester $sem)'}',
      icon: Icons.trending_up_rounded,
      child: graduated
          ? const Align(
              alignment: Alignment.centerLeft,
              child: AdminPill(label: 'Graduated', color: AdminColors.success),
            )
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Promote this group to ${_nextPhaseLabel(sem)} to complete the milestones of '
                  '${_phaseLabel(sem)}. If the work is not good enough, mark it for rework instead.',
                  style: TextStyle(color: Colors.white.withOpacity(0.7), height: 1.45),
                ),
                const SizedBox(height: 14),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    ElevatedButton.icon(
                      onPressed: _busy ? null : _promoteGroup,
                      icon: const Icon(Icons.arrow_circle_up_rounded, size: 18),
                      label: Text('Promote to ${_nextPhaseLabel(sem)}'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AdminColors.success,
                        foregroundColor: Colors.white,
                      ),
                    ),
                      OutlinedButton.icon(
                        onPressed: _busy ? null : _markRework,
                        icon: const Icon(Icons.replay_rounded, size: 18),
                        label: const Tr('Not promoted / Rework'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: AdminColors.warning,
                          side: BorderSide(color: AdminColors.warning.withOpacity(0.55)),
                      ),
                    ),
                  ],
                ),
              ],
            ),
    );
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
                        Tr('Group overview',
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
                    label: const Tr('Discard'),
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
          AdminPageMeta(
            text: detail.group.projectTitle.isEmpty
                ? 'Milestones and latest submission'
                : detail.group.projectTitle,
          ),
          const SizedBox(height: 18),
          _buildPromotionCard(detail),
          const SizedBox(height: 18),
          AdminSectionCard(
            title: 'Milestones',
            subtitle: '${detail.milestones.where((m) => m.isCompleted).length} of ${detail.milestones.length} completed',
            icon: Icons.flag_rounded,
            child: Column(
              children: [
                for (var i = 0; i < detail.milestones.length; i++) ...[
                  if (i > 0) const SizedBox(height: 12),
                  _MilestoneRowV2(
                    milestone: detail.milestones[i],
                    onExtend: (_busy || detail.group.isGraduated)
                        ? null
                        : () => _extendMilestone(detail.milestones[i]),
                  ),
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
                ? Tr('No document has been submitted yet.',
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
                label: const Tr('Document Review'),
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
                label: const Tr('Meeting Notes'),
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
                label: const Tr('Plagiarism Monitor'),
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
                    label: const Tr('Document Review'),
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
                    label: const Tr('Meeting Notes'),
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
                label: const Tr('Plagiarism Monitor'),
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



class _MilestoneRowV2 extends StatelessWidget {
  final GroupMilestoneModel milestone;
  final VoidCallback? onExtend;

  const _MilestoneRowV2({required this.milestone, this.onExtend});

  Color get _color {
    switch (milestone.status) {
      case 'completed':
        return AdminColors.success;
      case 'rework':
      case 'overdue':
        return AdminColors.danger;
      case 'due_soon':
        return AdminColors.warning;
      default:
        return AdminColors.primary;
    }
  }

  String get _label {
    switch (milestone.status) {
      case 'completed':
        return 'Completed';
      case 'rework':
        return 'Rework';
      case 'overdue':
        return 'Overdue';
      case 'due_soon':
        return 'Due soon';
      case 'upcoming':
        return 'Upcoming';
      default:
        return milestone.isCompleted ? 'Completed' : 'Pending';
    }
  }

  String? get _daysText {
    final d = milestone.daysLeft;
    if (d == null || milestone.isCompleted) return null;
    if (d > 1) return '$d days left';
    if (d == 1) return 'Due tomorrow';
    if (d == 0) return 'Due today';
    return '${-d} day(s) overdue';
  }

  @override
  Widget build(BuildContext context) {
    final done = milestone.isCompleted;
    final color = _color;
    final meta = <String>[
      if (milestone.semester != null)
        'Semester ${milestone.semester}${milestone.phase.isEmpty ? '' : ' · ${milestone.phase}'}',
      if ((milestone.deadlineDate ?? '').isNotEmpty) 'Due ${milestone.deadlineDate}',
      if (_daysText != null) _daysText!,
      if (milestone.extended) 'Extended',
    ];
    final showRework = milestone.status == 'rework';

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: done ? AdminColors.success.withOpacity(0.08) : AdminColors.surfaceAlt,
        borderRadius: BorderRadius.circular(adminTileRadius),
        border: Border.all(
          color: (done || showRework || milestone.status == 'overdue')
              ? color.withOpacity(0.4)
              : AdminColors.borderStrong,
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
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
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  milestone.name,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: done ? Colors.white : Colors.white.withOpacity(0.85),
                  ),
                ),
                if (meta.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    meta.join('  ·  '),
                    style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.55)),
                  ),
                ],
                if (showRework) ...[
                  const SizedBox(height: 6),
                  Text(
                    milestone.reworkNote.isEmpty
                        ? 'Marked for rework.'
                        : 'Rework: ${milestone.reworkNote}',
                    style: const TextStyle(fontSize: 12, color: AdminColors.danger, height: 1.35),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: 8),
          AdminPill(label: _label, color: color),
          if (milestone.isManaged && !done && onExtend != null)
            IconButton(
              tooltip: 'Extend deadline',
              onPressed: onExtend,
              icon: const Icon(Icons.event_repeat_rounded, size: 20, color: Colors.white70),
            ),
        ],
      ),
    );
  }
}
