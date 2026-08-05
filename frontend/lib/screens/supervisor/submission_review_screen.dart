import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../widgets/admin/admin_ui.dart';
import 'submission_detail_screen.dart';

class SubmissionReviewScreen extends StatefulWidget {
  const SubmissionReviewScreen({super.key});

  @override
  State<SubmissionReviewScreen> createState() => _SubmissionReviewScreenState();
}

class _SubmissionReviewScreenState extends State<SubmissionReviewScreen> {
  final SupervisorApiService _api = SupervisorApiService();
  List<FinalSubmissionModel> _submissions = const [];
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadSubmissions();
  }

  Future<void> _loadSubmissions() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await _api.fetchSubmissions(userId);
      if (mounted) setState(() => _submissions = data);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _openDetail(FinalSubmissionModel item) {
    Navigator.of(context)
        .push(
          MaterialPageRoute(
            builder: (_) => SubmissionDetailScreen(submissionId: item.id, titleHint: item.title),
          ),
        )
        .then((_) {
      if (mounted) _loadSubmissions();
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const AdminPage(child: AdminLoadingView(label: 'Loading submissions...'));
    }
    if (_error != null) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _loadSubmissions));
    }

    return AdminPage(
      onRefresh: _loadSubmissions,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageMeta(
            text: _submissions.isEmpty
                ? 'No pending final submissions'
                : '${_submissions.length} final submission${_submissions.length == 1 ? '' : 's'} awaiting decision',
          ),
          const SizedBox(height: 20),
          if (_submissions.isEmpty)
            const AdminEmptyView(
              icon: Icons.fact_check_outlined,
              title: 'Nothing to review',
              message: 'When students submit a final document, it will appear here with the Formatify AI analysis report.',
            )
          else
            ..._submissions.map(
              (item) => Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: InkWell(
                  onTap: () => _openDetail(item),
                  borderRadius: BorderRadius.circular(adminCardRadius),
                  child: _SubmissionListCard(item: item),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _SubmissionListCard extends StatelessWidget {
  final FinalSubmissionModel item;

  const _SubmissionListCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final summary = item.analysisSummary;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: adminCardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const AdminIconBadge(
                icon: Icons.fact_check_outlined,
                color: AdminColors.warning,
                size: 22,
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.title,
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Colors.white),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      item.groupTitle.isEmpty ? 'Group submission' : item.groupTitle,
                      style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.55)),
                    ),
                  ],
                ),
              ),
              AdminPill(label: item.statusLabel, color: AdminColors.warning),
            ],
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 8,
            children: [
              _MiniStat(
                label: 'Grammar',
                value: '${summary.grammarIssues}',
                icon: Icons.spellcheck_rounded,
              ),
              _MiniStat(
                label: 'Plagiarism risk',
                value: '${summary.plagiarismScore.toStringAsFixed(0)}%',
                icon: Icons.policy_outlined,
              ),
              _MiniStat(
                label: 'Compliance',
                value: '${summary.complianceScore.toStringAsFixed(0)}%',
                icon: Icons.rule_rounded,
              ),
            ],
          ),
          if (item.submittedAt.isNotEmpty) ...[
            const SizedBox(height: 14),
            Row(
              children: [
                Icon(Icons.schedule_rounded, size: 13, color: Colors.white.withOpacity(0.4)),
                const SizedBox(width: 6),
                Text(
                  'Submitted ${item.submittedAt}',
                  style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.45)),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  final String label;
  final String value;
  final IconData? icon;

  const _MiniStat({required this.label, required this.value, this.icon});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
      decoration: BoxDecoration(
        color: AdminColors.surfaceAlt,
        borderRadius: BorderRadius.circular(adminTileRadius - 2),
        border: Border.all(color: AdminColors.borderStrong),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 13, color: AdminColors.accent.withOpacity(0.8)),
            const SizedBox(width: 6),
          ],
          Text(
            label,
            style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.55)),
          ),
          const SizedBox(width: 5),
          Text(
            value,
            style: const TextStyle(
              fontSize: 12.5,
              color: Colors.white,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}
