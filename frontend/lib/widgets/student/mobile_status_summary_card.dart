import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../providers/fyp_provider.dart';

/// Compact FYP status summary for the mobile Dashboard tab.
///
/// Loads the same FypProvider sources as My Supervisor + Status Tracker
/// (`fetchAssignmentStatus`, `fetchSubmissions`). Formatting % / issues come
/// from `latest.analysis_summary.compliance_score` and `total_issues`
/// (analysis_report fields already used for supervisor submission lists).
class MobileStatusSummaryCard extends StatefulWidget {
  const MobileStatusSummaryCard({super.key});

  @override
  State<MobileStatusSummaryCard> createState() =>
      _MobileStatusSummaryCardState();
}

class _MobileStatusSummaryCardState extends State<MobileStatusSummaryCard> {
  bool _loading = true;
  String? _error;

  static const _card = Color(0xFF161B22);
  static const _border = Color(0x22FFFFFF);
  static const _accent = Color(0xFF3B82F6);
  static const _done = Color(0xFF10B981);
  static const _warn = Color(0xFFF59E0B);
  static const _bad = Color(0xFFEF4444);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _load();
    });
  }

  Future<void> _load() async {
    final auth = context.read<AuthProvider>();
    final userId = auth.userId;
    final email = (auth.userEmail ?? auth.email ?? '').trim();
    if (userId == null || email.isEmpty) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = null;
        });
      }
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final fyp = context.read<FypProvider>();
      await fyp.fetchAssignmentStatus(userId: userId, email: email);
      if (!mounted) return;

      final groupId = fyp.fypGroupId;
      if (groupId != null) {
        await fyp.fetchSubmissions(userId: userId, groupId: groupId);
      }
      if (!mounted) return;

      // No group is a valid empty state — not an error.
      if (groupId == null) {
        setState(() => _loading = false);
        return;
      }
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

  DateTime? _parseDate(dynamic raw) {
    if (raw == null) return null;
    final s = raw.toString().trim();
    if (s.isEmpty) return null;
    return DateTime.tryParse(s.length >= 10 ? s.substring(0, 10) : s) ??
        DateTime.tryParse(s);
  }

  String _formatDate(dynamic raw) {
    final s = (raw ?? '').toString();
    if (s.isEmpty) return '—';
    return s.length >= 16 ? s.substring(0, 16) : (s.length >= 10 ? s.substring(0, 10) : s);
  }

  String? _daysRemainingLabel(DateTime? deadline) {
    if (deadline == null) return null;
    final today = DateTime.now();
    final start = DateTime(today.year, today.month, today.day);
    final end = DateTime(deadline.year, deadline.month, deadline.day);
    final days = end.difference(start).inDays;
    if (days > 1) return '$days days left';
    if (days == 1) return '1 day left';
    if (days == 0) return 'Due today';
    if (days == -1) return '1 day overdue';
    return '${-days} days overdue';
  }

  @override
  Widget build(BuildContext context) {
    final fyp = context.watch<FypProvider>();

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _border),
      ),
      child: _loading || fyp.isStatusLoading || fyp.isSubmissionsLoading
          ? const SizedBox(
              height: 72,
              child: Center(
                child: CircularProgressIndicator(color: _accent, strokeWidth: 2),
              ),
            )
          : _error != null
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _error!,
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.7),
                        fontSize: 13,
                      ),
                    ),
                    TextButton(
                      onPressed: _load,
                      child: const Text('Retry'),
                    ),
                  ],
                )
              : fyp.fypGroupId == null
                  ? _emptyState()
                  : _filledCard(fyp),
    );
  }

  Widget _emptyState() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'FYP status',
          style: TextStyle(
            color: Colors.white.withOpacity(0.5),
            fontSize: 11,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.4,
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'No active FYP group yet',
          style: TextStyle(
            color: Colors.white,
            fontSize: 15,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          'Status appears after a supervisor accepts your request.',
          style: TextStyle(
            color: Colors.white.withOpacity(0.55),
            fontSize: 12,
            height: 1.35,
          ),
        ),
      ],
    );
  }

  Widget _filledCard(FypProvider fyp) {
    final statusMap = fyp.assignmentStatus;
    final supervisorName =
        ((statusMap?['supervisor'] as Map?)?['name'] ?? '').toString().trim();
    final group = statusMap?['group'] as Map?;
    final groupStatus = (group?['status'] ?? 'accepted').toString();
    final deadlineRaw = group?['deadline_date'];
    final deadline = _parseDate(deadlineRaw);
    final daysLabel = _daysRemainingLabel(deadline);

    final latest = fyp.latestSubmission;
    final subStatus = (latest?['status'] ?? '').toString();
    final stage = (latest?['stage'] ?? '').toString();
    final lastUpdated = latest == null
        ? null
        : (latest['resolved_at'] ?? latest['submitted_at']);

    final summary = latest?['analysis_summary'] as Map?;
    final compliance = (summary?['compliance_score'] as num?)?.toDouble();
    final issues = (summary?['total_issues'] as num?)?.toInt();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'FYP status',
          style: TextStyle(
            color: Colors.white.withOpacity(0.5),
            fontSize: 11,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.4,
          ),
        ),
        const SizedBox(height: 10),
        if (supervisorName.isNotEmpty)
          Text(
            supervisorName,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          )
        else
          Text(
            'Supervisor assigned',
            style: TextStyle(
              color: Colors.white.withOpacity(0.85),
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
        const SizedBox(height: 4),
        Text(
          'Group · ${groupStatus.isEmpty ? 'accepted' : groupStatus}',
          style: TextStyle(
            color: Colors.white.withOpacity(0.55),
            fontSize: 12,
          ),
        ),
        const SizedBox(height: 14),
        const Divider(height: 1, color: _border),
        const SizedBox(height: 12),
        if (latest == null)
          _row('Submission', 'None yet', muted: true)
        else ...[
          _row(
            'Submission',
            stage.isNotEmpty ? stage : subStatus,
            valueColor: _statusColor(subStatus),
          ),
          const SizedBox(height: 8),
          _row('Last updated', _formatDate(lastUpdated), muted: true),
        ],
        const SizedBox(height: 8),
        if (deadline == null)
          _row('Deadline', 'Not set', muted: true)
        else
          _row(
            'Deadline',
            '${_formatDate(deadlineRaw)}${daysLabel != null ? ' · $daysLabel' : ''}',
            valueColor: (daysLabel != null &&
                    (daysLabel.contains('overdue') || daysLabel == 'Due today'))
                ? _warn
                : null,
          ),
        if (latest != null && summary != null) ...[
          const SizedBox(height: 8),
          _row(
            'Formatting',
            compliance == null
                ? '—'
                : '${compliance.toStringAsFixed(compliance == compliance.roundToDouble() ? 0 : 1)}%'
                    '${issues != null ? ' · $issues issues' : ''}',
          ),
        ],
      ],
    );
  }

  Widget _row(String label, String value, {Color? valueColor, bool muted = false}) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 96,
          child: Text(
            label,
            style: TextStyle(
              color: Colors.white.withOpacity(0.45),
              fontSize: 12,
            ),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: TextStyle(
              color: valueColor ??
                  (muted
                      ? Colors.white.withOpacity(0.55)
                      : Colors.white.withOpacity(0.9)),
              fontSize: 13,
              fontWeight: valueColor != null ? FontWeight.w600 : FontWeight.w500,
            ),
          ),
        ),
      ],
    );
  }
}
