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
      return const AdminPage(child: AdminLoadingView());
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
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 8,
            children: const [
              _LegendPill(color: AdminColors.success, label: 'Safe (< 30%)'),
              _LegendPill(color: AdminColors.warning, label: 'Some risk (30–59%)'),
              _LegendPill(color: AdminColors.danger, label: 'High risk (60%+)'),
            ],
          ),
          const SizedBox(height: 22),
          if (_groups.isEmpty)
            const AdminEmptyView(
              message: 'Accepted groups will appear here with plagiarism scores from the detection module.',
            )
          else
            ..._groups.map(
              (group) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: InkWell(
                  onTap: () => _openDetail(group),
                  borderRadius: BorderRadius.circular(14),
                  child: _PlagiarismGroupCard(group: group),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _LegendPill extends StatelessWidget {
  final Color color;
  final String label;

  const _LegendPill({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.14),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.45)),
      ),
      child: Text(label, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
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
      decoration: adminCardDecoration().copyWith(
        border: Border.all(color: color.withOpacity(0.55), width: 1.2),
        color: color.withOpacity(0.08),
      ),
      child: Row(
        children: [
          Container(
            width: 54,
            height: 54,
            decoration: BoxDecoration(
              color: color.withOpacity(0.18),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Center(
              child: Text(
                '${group.plagiarismScore.round()}%',
                style: TextStyle(color: color, fontWeight: FontWeight.w800, fontSize: 14),
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
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: color.withOpacity(0.16),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              _riskLabel,
              style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }
}
