import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../providers/document_provider.dart';
import '../../providers/fyp_provider.dart';
import '../../theme/app_theme.dart';
import 'document_feedback_screen.dart';

import '../../widgets/tr.dart';

/// Status Tracker — reads final_submissions (not remarks).
class StatusTrackerScreen extends StatefulWidget {
  final VoidCallback? onChooseSupervisor;
  final VoidCallback? onOpenMySupervisor;
  final VoidCallback? onUploadNewVersion;

  const StatusTrackerScreen({
    super.key,
    this.onChooseSupervisor,
    this.onOpenMySupervisor,
    this.onUploadNewVersion,
  });

  @override
  State<StatusTrackerScreen> createState() => _StatusTrackerScreenState();
}

class _StatusTrackerScreenState extends State<StatusTrackerScreen> {
  AppPalette get _p => context.watch<ThemeProvider>().palette;
  String? _error;
  bool _loading = true;

  static const _done = Color(0xFF10B981);
  static const _warn = Color(0xFFF59E0B);
  static const _bad = Color(0xFFEF4444);

  static const _stageLabels = ['Submitted', 'Under Review', 'Decision'];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _load();
    });
  }

  // ───────────────────────── Data / logic (unchanged) ─────────────────────

  Future<void> _ensureGroupId() async {
    final fyp = context.read<FypProvider>();
    if (fyp.fypGroupId != null) return;
    final auth = context.read<AuthProvider>();
    final userId = auth.userId;
    final email = (auth.userEmail ?? auth.email ?? '').trim();
    if (userId == null || email.isEmpty) return;
    await fyp.fetchAssignmentStatus(userId: userId, email: email);
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await _ensureGroupId();
      if (!mounted) return;
      final fyp = context.read<FypProvider>();
      final groupId = fyp.fypGroupId;
      final userId = context.read<AuthProvider>().userId;
      if (groupId == null || userId == null) {
        setState(() => _loading = false);
        return;
      }
      await fyp.fetchSubmissions(userId: userId, groupId: groupId);
      if (!mounted) return;
      if (fyp.errorMessage != null && fyp.submissions.isEmpty) {
        setState(() => _error = fyp.errorMessage);
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'approved':
        return _done;
      case 'revision':
        return _warn;
      case 'rejected':
        return _bad;
      default:
        return _p.accent;
    }
  }

  IconData _statusIcon(String status) {
    switch (status) {
      case 'approved':
        return Icons.check_circle_outline;
      case 'revision':
        return Icons.edit_note;
      case 'rejected':
        return Icons.cancel_outlined;
      default:
        return Icons.hourglass_top_rounded;
    }
  }

  String _statusText(String status) {
    switch (status) {
      case 'approved':
        return 'Approved';
      case 'revision':
        return 'Revision requested';
      case 'rejected':
        return 'Rejected';
      default:
        return 'Under review';
    }
  }

  String _date(dynamic raw) {
    final s = (raw ?? '').toString();
    return s.length >= 10 ? s.substring(0, 10) : s;
  }

  int? _asInt(dynamic value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value == null) return null;
    return int.tryParse(value.toString());
  }

  void _uploadNewVersion(Map<String, dynamic> submission) {
    final sourceId = submission['source_document_id'];
    int? sourceDocumentId;
    if (sourceId is int) {
      sourceDocumentId = sourceId;
    } else if (sourceId != null) {
      sourceDocumentId = int.tryParse(sourceId.toString());
    }

    context.read<DocumentProvider>().beginResubmitFromSubmission(
      sourceDocumentId: sourceDocumentId,
      priorSubmissionId: submission['id'] as int,
      title: (submission['title'] ?? 'Revised submission').toString(),
      filename: (submission['filename'] ?? 'document.docx').toString(),
    );
    widget.onUploadNewVersion?.call();
  }

  void _openResolveComments(Map<String, dynamic> submission) {
    final groupId = context.read<FypProvider>().fypGroupId;
    final documentId = _asInt(submission['group_document_id']);
    if (groupId == null || documentId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Tr('No review document linked to this submission yet.'),
        ),
      );
      return;
    }
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DocumentFeedbackScreen(
          groupId: groupId,
          documentId: documentId,
        ),
      ),
    );
  }

  // ───────────────────────────── Build ─────────────────────────────────────

  BoxDecoration _cardDeco({Color? borderColor}) => BoxDecoration(
        color: _p.surface,
        borderRadius: BorderRadius.circular(_p.isDark ? _p.cardRadius : 14),
        border: Border.all(
          color: borderColor ?? (_p.isDark ? _p.borderStrong : _p.border),
        ),
        boxShadow: _p.isDark ? _p.cardShadow : null,
      );

  @override
  Widget build(BuildContext context) {
    final fyp = context.watch<FypProvider>();
    final groupId = fyp.fypGroupId;

    if (_loading || fyp.isSubmissionsLoading) {
      return Center(child: CircularProgressIndicator(color: _p.accent));
    }

    if (groupId == null) {
      return _centered(
        _emptyCard(
          icon: Icons.person_search_outlined,
          title: 'No active supervisor',
          body:
              'Status appears after your supervisor accepts your request and you submit a report for review.',
          actions: [
            if (widget.onOpenMySupervisor != null)
              OutlinedButton(
                onPressed: widget.onOpenMySupervisor,
                child: const Tr('My Supervisor'),
              ),
            if (widget.onChooseSupervisor != null)
              ElevatedButton(
                onPressed: widget.onChooseSupervisor,
                style: ElevatedButton.styleFrom(
                  backgroundColor: _p.accent,
                  foregroundColor: Colors.white,
                ),
                child: const Tr('Choose Supervisor'),
              ),
          ],
        ),
      );
    }

    if (_error != null) {
      return _centered(
        _emptyCard(
          icon: Icons.error_outline,
          iconColor: _bad,
          title: 'Something went wrong',
          body: _error!,
          actions: [
            ElevatedButton.icon(
              onPressed: _load,
              icon: const Icon(Icons.refresh, size: 16),
              label: const Tr('Retry'),
              style: ElevatedButton.styleFrom(
                backgroundColor: _p.accent,
                foregroundColor: Colors.white,
              ),
            ),
          ],
        ),
      );
    }

    final latest = fyp.latestSubmission;
    final history = fyp.submissions;

    return RefreshIndicator(
      color: _p.accent,
      backgroundColor: _p.surface,
      onRefresh: _load,
      child: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 820),
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(28),
            children: [
              _header(history.length),
              const SizedBox(height: 22),
              if (latest == null)
                _emptyCard(
                  icon: Icons.inbox_outlined,
                  title: 'No submissions yet',
                  body:
                      'Submit a report from New Report → Submit for Supervisor Review to start tracking status here.',
                  actions: const [],
                )
              else ...[
                _sectionLabel('Latest submission'),
                const SizedBox(height: 10),
                _latestCard(latest),
                if (history.length > 1) ...[
                  const SizedBox(height: 30),
                  _sectionLabel('History'),
                  const SizedBox(height: 10),
                  Container(
                    decoration: _cardDeco(),
                    child: Column(
                      children: [
                        for (var i = 1; i < history.length; i++) ...[
                          if (i > 1) Divider(height: 1, color: _p.border),
                          _historyRow(history[i]),
                        ],
                      ],
                    ),
                  ),
                ],
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _centered(Widget child) => Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: Padding(padding: const EdgeInsets.all(28), child: child),
        ),
      );

  Widget _header(int total) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Tr('Submission status',
                  style: TextStyle(
                    color: _p.textPrimary,
                    fontSize: 20,
                    fontWeight: FontWeight.w700,
                  )),
              const SizedBox(height: 4),
              Tr('Track your final submissions through review and decision.',
                  style: TextStyle(color: _p.textSecondary, fontSize: 13)),
            ],
          ),
        ),
        if (total > 0)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: _p.accentSoft,
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text(
              '$total submission${total == 1 ? '' : 's'}',
              style: TextStyle(
                color: _p.accent,
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        const SizedBox(width: 8),
        IconButton(
          tooltip: 'Refresh',
          onPressed: _load,
          icon: Icon(Icons.refresh, color: _p.textSecondary),
        ),
      ],
    );
  }

  Widget _sectionLabel(String text) => Tr(
        text.toUpperCase(),
        style: TextStyle(
          color: _p.textSecondary,
          fontSize: 11.5,
          letterSpacing: 0.8,
          fontWeight: FontWeight.w700,
        ),
      );

  // ───────────────────────── Latest submission card ───────────────────────

  Widget _latestCard(Map<String, dynamic> s) {
    final status = (s['status'] ?? 'pending').toString();
    final stage = (s['stage'] ?? 'Under Review').toString();
    final note = (s['decision_note'] ?? '').toString();
    final needsResubmit = s['needs_resubmit'] == true;
    final color = _statusColor(status);
    final stageIndex = (s['stage_index'] as num?)?.toInt() ?? 1;
    final hasDoc = _asInt(s['group_document_id']) != null;

    return Container(
      decoration: _cardDeco(borderColor: color.withOpacity(0.4)),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Status banner
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            color: color.withOpacity(0.10),
            child: Row(
              children: [
                Icon(_statusIcon(status), color: color, size: 18),
                const SizedBox(width: 8),
                Tr(_statusText(status),
                    style: TextStyle(
                      color: color,
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                    )),
                const Spacer(),
                if (_date(s['submitted_at']).isNotEmpty)
                  Text('Submitted ${_date(s['submitted_at'])}',
                      style: TextStyle(color: _p.textSecondary, fontSize: 11.5)),
              ],
            ),
          ),

          Padding(
            padding: const EdgeInsets.all(22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Title + file
                Row(
                  children: [
                    Container(
                      width: 42,
                      height: 42,
                      decoration: BoxDecoration(
                        color: _p.accentSoft,
                        borderRadius: BorderRadius.circular(11),
                      ),
                      child: Icon(Icons.description_outlined,
                          color: _p.accent, size: 21),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            (s['title'] ?? 'Submission').toString(),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: _p.textPrimary,
                              fontSize: 16,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            (s['filename'] ?? '').toString(),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style:
                                TextStyle(color: _p.textMuted, fontSize: 12),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 26),
                _stepper(
                    activeIndex: stageIndex, status: status, stageLabel: stage),

                // Supervisor note
                if (note.isNotEmpty) ...[
                  const SizedBox(height: 24),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: _p.surfaceAlt,
                      borderRadius: BorderRadius.circular(10),
                      border: Border(
                        left: BorderSide(color: color, width: 3),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(Icons.chat_bubble_outline,
                                size: 14, color: _p.textSecondary),
                            const SizedBox(width: 6),
                            Tr('Supervisor note',
                                style: TextStyle(
                                  color: _p.textSecondary,
                                  fontSize: 11.5,
                                  fontWeight: FontWeight.w700,
                                )),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          note,
                          style: TextStyle(
                            color: _p.textPrimary,
                            height: 1.5,
                            fontSize: 13.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],

                if (s['resolved_at'] != null &&
                    s['resolved_at'].toString().isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Icon(Icons.task_alt, size: 14, color: _done),
                      const SizedBox(width: 6),
                      Text('Resolved ${_date(s['resolved_at'])}',
                          style: TextStyle(color: _p.textMuted, fontSize: 11.5)),
                    ],
                  ),
                ],

                // Actions
                if (needsResubmit || hasDoc) ...[
                  const SizedBox(height: 22),
                  Divider(height: 1, color: _p.border),
                  const SizedBox(height: 18),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: [
                      if (needsResubmit)
                        ElevatedButton.icon(
                          onPressed: widget.onUploadNewVersion == null
                              ? null
                              : () => _uploadNewVersion(s),
                          icon: const Icon(Icons.upload_file, size: 18),
                          label: const Tr('Upload new version'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: _warn,
                            foregroundColor: Colors.black,
                            padding: const EdgeInsets.symmetric(
                                horizontal: 18, vertical: 14),
                            shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(10)),
                          ),
                        ),
                      if (hasDoc)
                        OutlinedButton.icon(
                          onPressed: () => _openResolveComments(s),
                          icon:
                              const Icon(Icons.rate_review_outlined, size: 18),
                          label: Text(
                            status == 'revision'
                                ? 'Open document & resolve comments'
                                : 'Open document & comments',
                          ),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: _p.textPrimary,
                            side: BorderSide(color: _p.borderStrong),
                            padding: const EdgeInsets.symmetric(
                                horizontal: 18, vertical: 14),
                            shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(10)),
                          ),
                        ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ───────────────────────────── Stepper ──────────────────────────────────

  /// stage_index: pending=1, revision=2, approved/rejected=3
  Widget _stepper({
    required int activeIndex,
    required String status,
    required String stageLabel,
  }) {
    final color = _statusColor(status);
    final finished = status == 'approved' || status == 'rejected';

    Widget node(int n) {
      final isDone = n < activeIndex || (finished && n < 3);
      final isCurrent = n == activeIndex;
      final reached = isDone || isCurrent;

      IconData icon;
      if (isDone) {
        icon = Icons.check;
      } else if (isCurrent && n == 3) {
        icon = status == 'rejected' ? Icons.close : Icons.check;
      } else if (isCurrent && status == 'revision') {
        icon = Icons.edit;
      } else {
        icon = Icons.circle;
      }

      return Container(
        width: 30,
        height: 30,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: reached ? color : _p.surfaceAlt,
          border: Border.all(
            color: reached ? color : _p.border,
            width: 1.5,
          ),
          boxShadow: isCurrent && !finished
              ? [BoxShadow(color: color.withOpacity(0.35), blurRadius: 10)]
              : null,
        ),
        child: Icon(
          icon,
          size: icon == Icons.circle ? 8 : 16,
          color: reached ? Colors.white : _p.textMuted,
        ),
      );
    }

    Widget line(bool filled) => Expanded(
          child: Container(
            height: 3,
            decoration: BoxDecoration(
              color: filled ? color.withOpacity(0.75) : _p.border,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
        );

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: List.generate(3, (i) {
        final n = i + 1;
        final label = n == 3 ? stageLabel : _stageLabels[i];
        final reached = n <= activeIndex || (finished && n <= 3);
        final isCurrent = n == activeIndex;

        return Expanded(
          child: Column(
            children: [
              Row(
                children: [
                  if (i == 0)
                    const Expanded(child: SizedBox())
                  else
                    line(n <= activeIndex || finished),
                  node(n),
                  if (i == 2)
                    const Expanded(child: SizedBox())
                  else
                    line(n < activeIndex || (finished && n < 3)),
                ],
              ),
              const SizedBox(height: 8),
              Tr(
                label,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: isCurrent
                      ? _p.textPrimary
                      : (reached ? _p.textSecondary : _p.textMuted),
                  fontSize: 11.5,
                  fontWeight: isCurrent ? FontWeight.w700 : FontWeight.w500,
                ),
              ),
            ],
          ),
        );
      }),
    );
  }

  // ───────────────────────────── History ──────────────────────────────────

  Widget _historyRow(Map<String, dynamic> s) {
    final status = (s['status'] ?? 'pending').toString();
    final color = _statusColor(status);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: color.withOpacity(0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(_statusIcon(status), color: color, size: 18),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  (s['title'] ?? 'Submission').toString(),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: _p.textPrimary,
                    fontWeight: FontWeight.w600,
                    fontSize: 13.5,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  _date(s['submitted_at']),
                  style: TextStyle(color: _p.textMuted, fontSize: 11.5),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: color.withOpacity(0.12),
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text(
              (s['stage'] ?? _statusText(status)).toString(),
              style: TextStyle(
                color: color,
                fontSize: 11.5,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ───────────────────────────── Empty state ──────────────────────────────

  Widget _emptyCard({
    required IconData icon,
    required String title,
    required String body,
    required List<Widget> actions,
    Color? iconColor,
  }) {
    final c = iconColor ?? _p.accent;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 34),
      decoration: _cardDeco(),
      child: Column(
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: c.withOpacity(0.12),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: c, size: 26),
          ),
          const SizedBox(height: 16),
          Tr(title,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: _p.textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w700,
              )),
          const SizedBox(height: 8),
          Text(
            body,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: _p.textSecondary,
              fontSize: 13,
              height: 1.5,
            ),
          ),
          if (actions.isNotEmpty) ...[
            const SizedBox(height: 22),
            Wrap(
              alignment: WrapAlignment.center,
              spacing: 10,
              runSpacing: 10,
              children: actions,
            ),
          ],
        ],
      ),
    );
  }
}