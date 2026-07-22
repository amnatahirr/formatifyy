import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../providers/fyp_provider.dart';
import '../../utils/responsive.dart';

/// Read-only FYP milestones — checklist on desktop, progress bars when compact.
class FypMilestonesScreen extends StatefulWidget {
  final VoidCallback? onChooseSupervisor;
  final VoidCallback? onOpenMySupervisor;

  const FypMilestonesScreen({
    super.key,
    this.onChooseSupervisor,
    this.onOpenMySupervisor,
  });

  @override
  State<FypMilestonesScreen> createState() => _FypMilestonesScreenState();
}

class _FypMilestonesScreenState extends State<FypMilestonesScreen> {
  String? _error;
  bool _loading = true;

  static const _card = Color(0xFF161B22);
  static const _border = Color(0x22FFFFFF);
  static const _accent = Color(0xFF3B82F6);
  static const _done = Color(0xFF10B981);
  static const _warn = Color(0xFFF59E0B);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _load();
    });
  }

  /// Ensures fypGroupId + assignmentStatus (deadline) — skips refetch if cached.
  Future<void> _ensureAssignmentContext() async {
    final fyp = context.read<FypProvider>();
    if (fyp.fypGroupId != null && fyp.assignmentStatus != null) return;
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
      await _ensureAssignmentContext();
      if (!mounted) return;
      final fyp = context.read<FypProvider>();
      final groupId = fyp.fypGroupId;
      final userId = context.read<AuthProvider>().userId;
      if (groupId == null || userId == null) {
        setState(() => _loading = false);
        return;
      }
      await fyp.fetchMilestones(userId: userId, groupId: groupId);
      if (!mounted) return;
      if (fyp.errorMessage != null && fyp.milestones.isEmpty) {
        setState(() => _error = fyp.errorMessage);
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
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
    return s.length >= 10 ? s.substring(0, 10) : s;
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
    final groupId = fyp.fypGroupId;
    final compact = isCompact(context);

    if (_loading || fyp.isMilestonesLoading) {
      return const Center(child: CircularProgressIndicator(color: _accent));
    }

    if (groupId == null) {
      return _noSupervisorState();
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

    final milestones = fyp.milestones;
    final doneCount = milestones.where((m) => m['is_completed'] == true).length;

    if (compact) {
      final deadlineRaw =
          (fyp.assignmentStatus?['group'] as Map?)?['deadline_date'];
      return _buildMobileProgressList(milestones, doneCount, deadlineRaw);
    }

    return RefreshIndicator(
      color: _accent,
      backgroundColor: _card,
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(32),
        children: [
          Text(
            'Track Proposal → Literature Review → Final Doc for your FYP group.',
            style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 14),
          ),
          const SizedBox(height: 8),
          Text(
            '$doneCount of ${milestones.length} completed',
            style: TextStyle(color: Colors.white.withOpacity(0.45), fontSize: 12),
          ),
          const SizedBox(height: 22),
          if (milestones.isEmpty)
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: _card,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: _border),
              ),
              child: Text(
                'No milestones yet for this group.',
                style: TextStyle(color: Colors.white.withOpacity(0.65)),
              ),
            )
          else
            ...milestones.map(_milestoneTile),
        ],
      ),
    );
  }

  Widget _buildMobileProgressList(
    List<Map<String, dynamic>> milestones,
    int doneCount,
    dynamic deadlineRaw,
  ) {
    final deadline = _parseDate(deadlineRaw);
    final daysLabel = _daysRemainingLabel(deadline);
    final overall =
        milestones.isEmpty ? 0.0 : doneCount / milestones.length;

    return RefreshIndicator(
      color: _accent,
      backgroundColor: _card,
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: _card,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: _border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        '$doneCount of ${milestones.length} completed',
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                          fontSize: 14,
                        ),
                      ),
                    ),
                    Text(
                      '${(overall * 100).round()}%',
                      style: const TextStyle(
                        color: _accent,
                        fontWeight: FontWeight.w700,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: overall,
                    minHeight: 8,
                    backgroundColor: Colors.white12,
                    color: _accent,
                  ),
                ),
                const SizedBox(height: 12),
                if (deadline == null)
                  Text(
                    'Deadline not set',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.45),
                      fontSize: 12,
                    ),
                  )
                else
                  Text(
                    'Deadline ${_formatDate(deadlineRaw)}'
                    '${daysLabel != null ? ' · $daysLabel' : ''}',
                    style: TextStyle(
                      color: (daysLabel != null &&
                              (daysLabel.contains('overdue') ||
                                  daysLabel == 'Due today'))
                          ? _warn
                          : Colors.white.withOpacity(0.55),
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          if (milestones.isEmpty)
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: _card,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: _border),
              ),
              child: Text(
                'No milestones yet for this group.',
                style: TextStyle(color: Colors.white.withOpacity(0.65)),
              ),
            )
          else
            ...milestones.map(_mobileMilestoneBar),
        ],
      ),
    );
  }

  Widget _mobileMilestoneBar(Map<String, dynamic> m) {
    final done = m['is_completed'] == true;
    final name = (m['name'] ?? 'Milestone').toString();
    final completedAt = (m['completed_at'] ?? '').toString();
    final progress = done ? 1.0 : 0.0;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.fromLTRB(14, 14, 14, 12),
        decoration: BoxDecoration(
          color: _card,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: done ? _done.withOpacity(0.35) : _border,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    name,
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                      fontSize: 14,
                      decoration: done ? TextDecoration.lineThrough : null,
                      decorationColor: Colors.white38,
                    ),
                  ),
                ),
                Text(
                  done ? 'Done' : 'Pending',
                  style: TextStyle(
                    color: done ? _done : Colors.white.withOpacity(0.45),
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: progress,
                minHeight: 7,
                backgroundColor: Colors.white12,
                color: done ? _done : _accent.withOpacity(0.45),
              ),
            ),
            if (done && completedAt.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                'Completed ${_formatDate(completedAt)}',
                style: TextStyle(
                  color: Colors.white.withOpacity(0.4),
                  fontSize: 11,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _noSupervisorState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Container(
          width: double.infinity,
          constraints: const BoxConstraints(maxWidth: 480),
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: _card,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: _border),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'No active supervisor',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                'Milestones appear after your supervisor accepts your assignment request. '
                'Check My Supervisor for status, or submit a request if you haven\'t yet.',
                style: TextStyle(
                  color: Colors.white.withOpacity(0.65),
                  height: 1.45,
                ),
              ),
              const SizedBox(height: 18),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
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
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _milestoneTile(Map<String, dynamic> m) {
    final done = m['is_completed'] == true;
    final name = (m['name'] ?? 'Milestone').toString();
    final completedAt = (m['completed_at'] ?? '').toString();

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: _card,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: done ? _done.withOpacity(0.35) : _border,
          ),
        ),
        child: Row(
          children: [
            Icon(
              done ? Icons.check_circle : Icons.radio_button_unchecked,
              color: done ? _done : Colors.white.withOpacity(0.35),
              size: 26,
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                      decoration: done ? TextDecoration.lineThrough : null,
                      decorationColor: Colors.white38,
                    ),
                  ),
                  if (done && completedAt.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(
                      'Completed ${completedAt.length >= 10 ? completedAt.substring(0, 10) : completedAt}',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.45),
                        fontSize: 12,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            Text(
              '#${m['sort_order'] ?? ''}',
              style: TextStyle(
                color: Colors.white.withOpacity(0.35),
                fontSize: 12,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
