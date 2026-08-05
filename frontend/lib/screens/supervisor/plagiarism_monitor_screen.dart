import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../widgets/admin/admin_ui.dart';
import 'plagiarism_monitor_detail_screen.dart';

class PlagiarismMonitorScreen extends StatefulWidget {
  const PlagiarismMonitorScreen({super.key});

  @override
  State<PlagiarismMonitorScreen> createState() => _PlagiarismMonitorScreenState();
}

class _PlagiarismMonitorScreenState extends State<PlagiarismMonitorScreen> {
  final SupervisorApiService _api = SupervisorApiService();
  List<PlagiarismMonitorGroup> _groups = const [];
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await _api.fetchPlagiarismMonitor(userId);
      if (mounted) setState(() => _groups = data);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _openDetail(PlagiarismMonitorGroup group) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => PlagiarismMonitorDetailScreen(
          groupId: group.groupId,
          titleHint: group.title,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const AdminPage(child: AdminLoadingView(label: 'Checking similarity scores...'));
    }
    if (_error != null) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _load));
    }

    return AdminPage(
      onRefresh: _load,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageHeader(
            title: 'Plagiarism Monitor',
            subtitle: _groups.isEmpty
                ? 'No accepted groups yet'
                : '${_groups.length} group${_groups.length == 1 ? '' : 's'} · scores from Formatify plagiarism detection',
          ),
          const SizedBox(height: 18),
          const Wrap(
            spacing: 10,
            runSpacing: 8,
            children: [
              AdminPill(
                label: 'Safe (< 30%)',
                color: AdminColors.success,
                icon: Icons.check_circle_rounded,
              ),
              AdminPill(
                label: 'Some risk (30–59%)',
                color: AdminColors.warning,
                icon: Icons.error_outline_rounded,
              ),
              AdminPill(
                label: 'High risk (60%+)',
                color: AdminColors.danger,
                icon: Icons.warning_amber_rounded,
              ),
            ],
          ),
          const SizedBox(height: 22),
          if (_groups.isEmpty)
            const AdminEmptyView(
              icon: Icons.policy_outlined,
              title: 'No groups monitored yet',
              message: 'Accepted groups will appear here with plagiarism scores from the detection module.',
            )
          else
            ..._groups.map(
              (group) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: InkWell(
                  onTap: () => _openDetail(group),
                  borderRadius: BorderRadius.circular(adminCardRadius),
                  child: _PlagiarismGroupCard(group: group),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _PlagiarismGroupCard extends StatelessWidget {
  final PlagiarismMonitorGroup group;

  const _PlagiarismGroupCard({required this.group});

  Color get _riskColor {
    switch (group.riskLevel) {
      case 'high':
        return AdminColors.danger;
      case 'some':
        return AdminColors.warning;
      default:
        return AdminColors.success;
    }
  }

  String get _riskLabel {
    switch (group.riskLevel) {
      case 'high':
        return 'High risk';
      case 'some':
        return 'Some risk';
      default:
        return 'Safe';
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _riskColor;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: adminCardDecoration(borderColor: color.withOpacity(0.45)),
      child: Row(
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: color.withOpacity(0.16),
              borderRadius: BorderRadius.circular(adminTileRadius + 2),
              border: Border.all(color: color.withOpacity(0.35)),
            ),
            child: Center(
              child: Text(
                '${group.plagiarismScore.round()}%',
                style: TextStyle(color: color, fontWeight: FontWeight.w800, fontSize: 15),
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  group.title,
                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 15),
                ),
                if (group.projectTitle.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    group.projectTitle,
                    style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 12),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
                const SizedBox(height: 8),
                Text(
                  '${group.matchCount} matched source${group.matchCount == 1 ? '' : 's'}',
                  style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 12),
                ),
              ],
            ),
          ),
          AdminPill(label: _riskLabel, color: color),
          const SizedBox(width: 6),
          Icon(Icons.chevron_right_rounded, color: Colors.white.withOpacity(0.4)),
        ],
      ),
    );
  }
}
