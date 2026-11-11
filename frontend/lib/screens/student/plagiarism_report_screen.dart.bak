import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../providers/fyp_provider.dart';
import '../../theme/app_theme.dart';

/// Read-only plagiarism report from final_submissions.analysis_report (no recompute).
class PlagiarismReportScreen extends StatefulWidget {
  final VoidCallback? onChooseSupervisor;
  final VoidCallback? onOpenMySupervisor;
  final VoidCallback? onOpenNewReport;

  const PlagiarismReportScreen({
    super.key,
    this.onChooseSupervisor,
    this.onOpenMySupervisor,
    this.onOpenNewReport,
  });

  @override
  State<PlagiarismReportScreen> createState() => _PlagiarismReportScreenState();
}

class _PlagiarismReportScreenState extends State<PlagiarismReportScreen> {
  AppPalette get _p => context.watch<ThemeProvider>().palette;
  String? _error;
  bool _loading = true;
  static const _safe = Color(0xFF10B981);
  static const _some = Color(0xFFF59E0B);
  static const _high = Color(0xFFEF4444);

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
      final report = await fyp.fetchPlagiarismReport(
        userId: userId,
        groupId: groupId,
      );
      if (!mounted) return;
      if (report == null && fyp.errorMessage != null) {
        setState(() => _error = fyp.errorMessage);
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Color _riskColor(String risk) {
    switch (risk.toLowerCase()) {
      case 'high':
        return _high;
      case 'some':
        return _some;
      default:
        return _safe;
    }
  }

  @override
  Widget build(BuildContext context) {
    final fyp = context.watch<FypProvider>();
    final groupId = fyp.fypGroupId;

    if (_loading || fyp.isPlagiarismLoading) {
      return Center(child: CircularProgressIndicator(color: _p.accent));
    }

    if (groupId == null) {
      return _emptyState(
        title: 'No active supervisor',
        body:
            'Plagiarism scores appear after you have an accepted FYP group and submit a report for supervisor review.',
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
                backgroundColor: _p.accent,
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
                style: TextStyle(color: _p.textSecondary),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              TextButton(onPressed: _load, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }

    final report = fyp.plagiarismReport ?? const <String, dynamic>{};
    final score = (report['plagiarism_score'] as num?)?.toDouble() ?? 0;
    final risk = (report['risk_level'] ?? 'safe').toString();
    final matches = List<Map<String, dynamic>>.from(
      (report['matches'] as List? ?? const []).map(
        (e) => Map<String, dynamic>.from(e as Map),
      ),
    );
    final flagged = report['flagged'] == true;
    final flagReason = (report['flag_reason'] ?? '').toString();
    final hasSubmission = report['submission_id'] != null;
    final riskColor = _riskColor(risk);

    return RefreshIndicator(
      color: _p.accent,
      backgroundColor: _p.surface,
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(32),
        children: [
          Text(
            'From your latest supervisor submission (AI Tools analysis snapshot — not recomputed).',
            style: TextStyle(color: _p.textSecondary, fontSize: 13),
          ),
          const SizedBox(height: 18),
          if (flagged) ...[
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: _high.withOpacity(0.12),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: _high.withOpacity(0.45)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.warning_amber_rounded, color: _high, size: 22),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Flagged by supervisor',
                          style: TextStyle(
                            color: _high,
                            fontWeight: FontWeight.w700,
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          flagReason.isNotEmpty
                              ? flagReason
                              : 'Your supervisor flagged this group for plagiarism risk. Review matched sources and revise.',
                          style: TextStyle(
                            color: _p.textSecondary,
                            height: 1.4,
                            fontSize: 13,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
          ],
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: _p.surface,
              borderRadius: BorderRadius.circular(_p.isDark ? _p.cardRadius : 12),
              border: Border.all(color: riskColor.withOpacity(0.4)),
              boxShadow: _p.isDark ? _p.cardShadow : null,
            ),
            child: Row(
              children: [
                Container(
                  width: 72,
                  height: 72,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: riskColor.withOpacity(0.15),
                    border: Border.all(color: riskColor.withOpacity(0.5)),
                  ),
                  child: Text(
                    '${score.toStringAsFixed(score == score.roundToDouble() ? 0 : 1)}%',
                    style: TextStyle(
                      color: riskColor,
                      fontWeight: FontWeight.w800,
                      fontSize: 16,
                    ),
                  ),
                ),
                const SizedBox(width: 18),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Plagiarism score',
                        style: TextStyle(
                          color: _p.textSecondary,
                          fontSize: 12,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        risk == 'high'
                            ? 'High risk'
                            : risk == 'some'
                                ? 'Some risk'
                                : 'Safe',
                        style: TextStyle(
                          color: riskColor,
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        hasSubmission
                            ? '${matches.length} matched source${matches.length == 1 ? '' : 's'}'
                            : 'No final submission yet — submit from New Report to attach an analysis snapshot.',
                        style: TextStyle(
                          color: _p.textSecondary,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          if (!hasSubmission) ...[
            const SizedBox(height: 16),
            if (widget.onOpenNewReport != null)
              Align(
                alignment: Alignment.centerLeft,
                child: ElevatedButton(
                  onPressed: widget.onOpenNewReport,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _p.accent,
                    foregroundColor: Colors.white,
                  ),
                  child: const Text('Go to New Report'),
                ),
              ),
          ],
          const SizedBox(height: 24),
          Text(
            'Matched sources',
            style: TextStyle(
              color: _p.textSecondary,
              fontWeight: FontWeight.w700,
              fontSize: 15,
            ),
          ),
          const SizedBox(height: 12),
          if (matches.isEmpty)
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: _p.surface,
                borderRadius: BorderRadius.circular(_p.isDark ? _p.cardRadius : 12),
                border: Border.all(color: _p.isDark ? _p.borderStrong : _p.border),
                boxShadow: _p.isDark ? _p.cardShadow : null,
              ),
              child: Text(
                hasSubmission
                    ? 'No plagiarism matches in the stored analysis report.'
                    : 'Sources will appear after you submit a report that includes AI analysis.',
                style: TextStyle(color: _p.textSecondary),
              ),
            )
          else
            ...matches.map(_matchTile),
        ],
      ),
    );
  }

  Widget _matchTile(Map<String, dynamic> m) {
    final similarity = (m['similarity'] as num?)?.toDouble() ?? 0;
    final source = (m['source'] ?? 'Unknown source').toString();
    final sentence = (m['sentence'] ?? '').toString();
    final reason = (m['reason'] ?? '').toString();

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: _p.surface,
          borderRadius: BorderRadius.circular(_p.isDark ? _p.cardRadius : 12),
          border: Border.all(color: _p.isDark ? _p.borderStrong : _p.border),
          boxShadow: _p.isDark ? _p.cardShadow : null,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    source,
                    style: TextStyle(
                      color: _p.textPrimary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                Text(
                  '${similarity.toStringAsFixed(similarity == similarity.roundToDouble() ? 0 : 1)}%',
                  style: const TextStyle(
                    color: _some,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            if (sentence.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                sentence,
                style: TextStyle(
                  color: _p.textSecondary,
                  height: 1.4,
                  fontSize: 13,
                ),
              ),
            ],
            if (reason.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                reason,
                style: TextStyle(
                  color: _p.textMuted,
                  fontSize: 12,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _emptyState({
    required String title,
    required String body,
    required List<Widget> actions,
  }) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Container(
          width: double.infinity,
          constraints: const BoxConstraints(maxWidth: 480),
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: _p.surface,
            borderRadius: BorderRadius.circular(_p.isDark ? _p.cardRadius : 12),
            border: Border.all(color: _p.isDark ? _p.borderStrong : _p.border),
            boxShadow: _p.isDark ? _p.cardShadow : null,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: TextStyle(
                  color: _p.textPrimary,
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                body,
                style: TextStyle(
                  color: _p.textSecondary,
                  height: 1.45,
                ),
              ),
              if (actions.isNotEmpty) ...[
                const SizedBox(height: 18),
                Wrap(spacing: 10, runSpacing: 10, children: actions),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
