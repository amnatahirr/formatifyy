import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../providers/document_provider.dart';
import '../../providers/fyp_provider.dart';
import 'document_feedback_screen.dart';

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
  String? _error;
  bool _loading = true;

  static const _card = Color(0xFF161B22);
  static const _border = Color(0x22FFFFFF);
  static const _accent = Color(0xFF3B82F6);
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
        return _accent;
    }
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

  int? _asInt(dynamic value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value == null) return null;
    return int.tryParse(value.toString());
  }

  void _openResolveComments(Map<String, dynamic> submission) {
    final groupId = context.read<FypProvider>().fypGroupId;
    final documentId = _asInt(submission['group_document_id']);
    if (groupId == null || documentId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No review document linked to this submission yet.'),
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

  @override
  Widget build(BuildContext context) {
    final fyp = context.watch<FypProvider>();
    final groupId = fyp.fypGroupId;

    if (_loading || fyp.isSubmissionsLoading) {
      return const Center(child: CircularProgressIndicator(color: _accent));
    }

    if (groupId == null) {
      return _emptyCard(
        title: 'No active supervisor',
        body:
            'Status appears after your supervisor accepts your request and you submit a report for review.',
        actions: [
          if (widget.onOpenMySupervisor != null)
            OutlinedButton(
              onPressed: widget.onOpenMySupervisor,
              child: const Text('My Supervisor'),
            ),
          if (widget.onChooseSupervisor != null)
            ElevatedButton(
              onPressed: widget.onChooseSupervisor,
              style: ElevatedButton.styleFrom(
                backgroundColor: _accent,
                foregroundColor: Colors.white,
              ),
              child: const Text('Choose Supervisor'),
            ),
        ],
      );
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _error!,
                style: TextStyle(color: Colors.white.withOpacity(0.75)),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              TextButton(onPressed: _load, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }

    final latest = fyp.latestSubmission;
    final history = fyp.submissions;

    return RefreshIndicator(
      color: _accent,
      backgroundColor: _card,
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(32),
        children: [
          Text(
            'Tracks your final submissions to the supervisor (approve / revision / reject).',
            style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 13),
          ),
          const SizedBox(height: 20),
          if (latest == null)
            _emptyCard(
              title: 'No submissions yet',
              body:
                  'Submit a report from New Report → Submit for Supervisor Review to start tracking status here.',
              actions: const [],
            )
          else ...[
            _latestCard(latest),
            if (history.length > 1) ...[
              const SizedBox(height: 28),
              Text(
                'History',
                style: TextStyle(
                  color: Colors.white.withOpacity(0.9),
                  fontWeight: FontWeight.w700,
                  fontSize: 15,
                ),
              ),
              const SizedBox(height: 12),
              ...history.skip(1).map(_historyTile),
            ],
          ],
        ],
      ),
    );
  }

  Widget _latestCard(Map<String, dynamic> s) {
    final status = (s['status'] ?? 'pending').toString();
    final stage = (s['stage'] ?? 'Under Review').toString();
    final note = (s['decision_note'] ?? '').toString();
    final needsResubmit = s['needs_resubmit'] == true;
    final color = _statusColor(status);
    final stageIndex = (s['stage_index'] as num?)?.toInt() ?? 1;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            (s['title'] ?? 'Submission').toString(),
            style: const TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            (s['filename'] ?? '').toString(),
            style: TextStyle(color: Colors.white.withOpacity(0.45), fontSize: 12),
          ),
          const SizedBox(height: 20),
          _progressBar(activeIndex: stageIndex, status: status, stageLabel: stage),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: color.withOpacity(0.15),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              stage,
              style: TextStyle(
                color: color,
                fontWeight: FontWeight.w700,
                fontSize: 13,
              ),
            ),
          ),
          if (note.isNotEmpty) ...[
            const SizedBox(height: 16),
            Text(
              'Supervisor note',
              style: TextStyle(
                color: Colors.white.withOpacity(0.5),
                fontSize: 12,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              note,
              style: TextStyle(
                color: Colors.white.withOpacity(0.85),
                height: 1.45,
                fontSize: 14,
              ),
            ),
          ],
          if (s['resolved_at'] != null &&
              s['resolved_at'].toString().isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              'Resolved ${s['resolved_at']}',
              style: TextStyle(
                color: Colors.white.withOpacity(0.4),
                fontSize: 11,
              ),
            ),
          ],
          if (needsResubmit) ...[
            const SizedBox(height: 18),
            SizedBox(
              height: 44,
              child: ElevatedButton.icon(
                onPressed: widget.onUploadNewVersion == null
                    ? null
                    : () => _uploadNewVersion(s),
                icon: const Icon(Icons.upload_file, size: 18),
                label: const Text('Upload New Version'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: _warn,
                  foregroundColor: Colors.black,
                ),
              ),
            ),
          ],
          if (_asInt(s['group_document_id']) != null) ...[
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              height: 44,
              child: OutlinedButton.icon(
                onPressed: () => _openResolveComments(s),
                icon: const Icon(Icons.rate_review_outlined, size: 18),
                label: Text(
                  status == 'revision'
                      ? 'Open document & resolve comments'
                      : 'Open document & comments',
                ),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: BorderSide(color: Colors.white.withOpacity(0.28)),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _progressBar({
    required int activeIndex,
    required String status,
    required String stageLabel,
  }) {
    // stage_index: pending=1, revision=2, approved/rejected=3
    final color = _statusColor(status);
    return Column(
      children: [
        Row(
          children: List.generate(_stageLabels.length * 2 - 1, (i) {
            if (i.isOdd) {
              final leftStage = (i ~/ 2) + 1;
              final filled = activeIndex > leftStage ||
                  (status == 'approved' && leftStage < 3) ||
                  (status == 'rejected' && leftStage < 3);
              return Expanded(
                child: Container(
                  height: 3,
                  color: filled ? color.withOpacity(0.7) : Colors.white12,
                ),
              );
            }
            final stageNum = (i ~/ 2) + 1;
            final active = stageNum <= activeIndex || status == 'approved';
            final isCurrent = stageNum == activeIndex;
            return Container(
              width: 28,
              height: 28,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: active ? color.withOpacity(isCurrent ? 1 : 0.85) : Colors.white12,
              ),
              child: Text(
                '$stageNum',
                style: TextStyle(
                  color: active ? Colors.white : Colors.white38,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            );
          }),
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: _stageLabels
              .map(
                (label) => Text(
                  label == 'Decision' ? stageLabel : label,
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.5),
                    fontSize: 11,
                  ),
                ),
              )
              .toList(),
        ),
      ],
    );
  }

  Widget _historyTile(Map<String, dynamic> s) {
    final status = (s['status'] ?? 'pending').toString();
    final color = _statusColor(status);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: _card,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: _border),
        ),
        child: Row(
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(color: color, shape: BoxShape.circle),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    (s['title'] ?? 'Submission').toString(),
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                      fontSize: 13,
                    ),
                  ),
                  Text(
                    (s['stage'] ?? status).toString(),
                    style: TextStyle(color: color, fontSize: 12),
                  ),
                ],
              ),
            ),
            Text(
              (s['submitted_at'] ?? '').toString().length >= 10
                  ? s['submitted_at'].toString().substring(0, 10)
                  : (s['submitted_at'] ?? '').toString(),
              style: TextStyle(
                color: Colors.white.withOpacity(0.35),
                fontSize: 11,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _emptyCard({
    required String title,
    required String body,
    required List<Widget> actions,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            body,
            style: TextStyle(
              color: Colors.white.withOpacity(0.65),
              height: 1.45,
            ),
          ),
          if (actions.isNotEmpty) ...[
            const SizedBox(height: 18),
            Wrap(spacing: 10, runSpacing: 10, children: actions),
          ],
        ],
      ),
    );
  }
}
