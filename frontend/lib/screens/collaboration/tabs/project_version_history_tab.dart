import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../providers/collaboration_provider.dart';

import '../../../widgets/tr.dart';
/// Version History tab — chronological commits with restore confirmation.
class ProjectVersionHistoryTab extends StatefulWidget {
  final int projectId;

  const ProjectVersionHistoryTab({super.key, required this.projectId});

  @override
  State<ProjectVersionHistoryTab> createState() =>
      _ProjectVersionHistoryTabState();
}

class _ProjectVersionHistoryTabState extends State<ProjectVersionHistoryTab> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    await context.read<CollaborationProvider>().loadProjectHistory(widget.projectId);
  }

  int _wordCount(String? text) {
    final t = (text ?? '').trim();
    if (t.isEmpty) return 0;
    return t.split(RegExp(r'\s+')).where((w) => w.isNotEmpty).length;
  }

  String _deltaLabel(List<Map<String, dynamic>> history, int index) {
    final current = history[index];
    final words = _wordCount(current['content'] as String?);
    // History is oldest→newest from API; compare to previous commit in same section.
    Map<String, dynamic>? prev;
    final sectionId = current['section_id'];
    for (var i = index - 1; i >= 0; i--) {
      if (history[i]['section_id'] == sectionId) {
        prev = history[i];
        break;
      }
    }
    if (prev == null) return '$words words';
    final delta = words - _wordCount(prev['content'] as String?);
    final sign = delta > 0 ? '+' : '';
    return '$words words ($sign$delta)';
  }

  Future<void> _restore(Map<String, dynamic> commit) async {
    final sectionId = commit['section_id'] as String;
    final sectionName = commit['section_name'] as String? ?? sectionId;
    final commitId = commit['id'] as int;
    final version = commit['version_number'];

    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF1A1F2E),
        title: const Tr('Restore this version?',
          style: TextStyle(color: Colors.white),
        ),
        content: Text(
          'This will overwrite the current draft of "$sectionName" with version $version. '
          'Your current draft content will be replaced.',
          style: const TextStyle(color: Color(0xFF94A3B8)),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Tr('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(),
            child: const Tr('Restore this version'),
          ),
        ],
      ),
    );
    if (confirm != true) return;

    final vc = context.read<CollaborationProvider>();
    final ok = await vc.rollbackFromProjectHistory(
      widget.projectId,
      sectionId,
      commitId,
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(ok ? 'Restored to v$version' : 'Restore failed'),
        backgroundColor: ok ? const Color(0xFF10B981) : const Color(0xFFEF4444),
      ),
    );
  }

  Color _typeColor(String type) {
    switch (type) {
      case 'import':
        return const Color(0xFF8B5CF6);
      case 'rollback':
        return const Color(0xFFF59E0B);
      default:
        return const Color(0xFF3B82F6);
    }
  }

  @override
  Widget build(BuildContext context) {
    final vc = context.watch<CollaborationProvider>();
    // Show newest first for the Version History UX.
    final history = vc.projectHistory.reversed.toList();

    if (vc.loading && history.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (history.isEmpty) {
      return const Center(
        child: Tr('No versions yet',
          style: TextStyle(color: Color(0xFF94A3B8)),
        ),
      );
    }

    // Keep chronological delta math against API order (oldest→newest).
    final apiOrder = vc.projectHistory;

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: history.length,
        itemBuilder: (_, i) {
          final c = history[i];
          final apiIndex = apiOrder.indexWhere((e) => e['id'] == c['id']);
          final type = c['commit_type'] as String? ?? 'save';
          final typeColor = _typeColor(type);
          final summary = (c['message'] as String?)?.trim().isNotEmpty == true
              ? c['message'] as String
              : _deltaLabel(apiOrder, apiIndex >= 0 ? apiIndex : 0);

          return Card(
            color: const Color(0xFF1A1F2E),
            margin: const EdgeInsets.only(bottom: 10),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 4,
                        height: 36,
                        decoration: BoxDecoration(
                          color: typeColor,
                          borderRadius: BorderRadius.circular(2),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '${c['section_name'] ?? c['section_id']} · v${c['version_number']}',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              '${c['author_name'] ?? 'Unknown'} · ${c['created_at'] ?? ''}',
                              style: const TextStyle(
                                color: Color(0xFF94A3B8),
                                fontSize: 11,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 3,
                        ),
                        decoration: BoxDecoration(
                          color: typeColor.withOpacity(0.15),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          type,
                          style: TextStyle(color: typeColor, fontSize: 10),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Text(
                    summary,
                    style: const TextStyle(color: Color(0xFFCBD5E1), fontSize: 12),
                  ),
                  const SizedBox(height: 12),
                  Align(
                    alignment: Alignment.centerRight,
                    child: ElevatedButton.icon(
                      onPressed: () => _restore(c),
                      icon: const Icon(Icons.restore, size: 14),
                      label: const Tr('Restore this version',
                        style: TextStyle(fontSize: 12),
                      ),
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 6,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
