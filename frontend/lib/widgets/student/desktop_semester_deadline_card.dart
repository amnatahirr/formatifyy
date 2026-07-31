import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../providers/fyp_provider.dart';
import '../../theme/app_theme.dart';

/// Desktop Dashboard semester deadline strip (admin-managed global deadline).
class DesktopSemesterDeadlineCard extends StatefulWidget {
  const DesktopSemesterDeadlineCard({super.key});

  @override
  State<DesktopSemesterDeadlineCard> createState() =>
      _DesktopSemesterDeadlineCardState();
}

class _DesktopSemesterDeadlineCardState
    extends State<DesktopSemesterDeadlineCard> {
  bool _loading = true;

  static const _warn = Color(0xFFF59E0B);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _load();
    });
  }

  Future<void> _load() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) {
      if (mounted) setState(() => _loading = false);
      return;
    }
    setState(() => _loading = true);
    await context.read<FypProvider>().fetchSemesterDeadline(userId: userId);
    if (mounted) setState(() => _loading = false);
  }

  String _formatDate(dynamic raw) {
    final s = (raw ?? '').toString();
    if (s.isEmpty) return '—';
    final d = DateTime.tryParse(s.length >= 10 ? s.substring(0, 10) : s);
    if (d == null) return s.length >= 10 ? s.substring(0, 10) : s;
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    return '${d.day} ${months[d.month - 1]} ${d.year}';
  }

  @override
  Widget build(BuildContext context) {
    final fyp = context.watch<FypProvider>();
    final p = context.watch<ThemeProvider>().palette;
    final semDl = fyp.semesterDeadline;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: p.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: p.border),
        boxShadow: p.cardShadow,
      ),
      child: _loading || fyp.isSemesterDeadlineLoading
          ? SizedBox(
              height: 28,
              child: Center(
                child: CircularProgressIndicator(
                  color: p.accent,
                  strokeWidth: 2,
                ),
              ),
            )
          : _buildContent(semDl, p),
    );
  }

  Widget _buildContent(Map<String, dynamic>? semDl, AppPalette p) {
    final found = semDl?['found'] == true;
    if (!found) {
      return Row(
        children: [
          Icon(Icons.event_outlined, color: p.iconMuted, size: 20),
          const SizedBox(width: 12),
          Text(
            'Semester deadline not set',
            style: TextStyle(color: p.textMuted, fontSize: 14),
          ),
        ],
      );
    }

    final isPassed = semDl?['is_passed'] == true;
    final daysRemaining = (semDl?['days_remaining'] as num?)?.toInt();
    final semester = (semDl?['semester'] as num?)?.toInt();
    final deadlineRaw = semDl?['deadline_date'];
    final urgent = isPassed || daysRemaining == 0;

    String status;
    if (isPassed) {
      status = 'Deadline passed';
    } else if (daysRemaining == null) {
      status = _formatDate(deadlineRaw);
    } else if (daysRemaining > 1) {
      status = '${_formatDate(deadlineRaw)} · $daysRemaining days left';
    } else if (daysRemaining == 1) {
      status = '${_formatDate(deadlineRaw)} · 1 day left';
    } else {
      status = '${_formatDate(deadlineRaw)} · Due today';
    }

    return Row(
      children: [
        Icon(
          isPassed ? Icons.event_busy : Icons.event_available,
          color: urgent ? _warn : p.accent,
          size: 22,
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                semester != null
                    ? 'Semester $semester submission deadline'
                    : 'Submission deadline',
                style: TextStyle(
                  color: p.textMuted,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                status,
                style: TextStyle(
                  color: urgent ? _warn : p.textPrimary,
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
