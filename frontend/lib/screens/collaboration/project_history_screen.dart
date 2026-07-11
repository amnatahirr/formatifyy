import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/collaboration_provider.dart';

class ProjectHistoryScreen extends StatefulWidget {
  final int projectId;
  final String projectName;

  const ProjectHistoryScreen({
    super.key,
    required this.projectId,
    required this.projectName,
  });

  @override
  State<ProjectHistoryScreen> createState() => _ProjectHistoryScreenState();
}

class _ProjectHistoryScreenState extends State<ProjectHistoryScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final vc = context.read<CollaborationProvider>();
    await vc.loadProjectHistory(widget.projectId);
  }

  Future<void> _rollback(Map<String, dynamic> commit) async {
    final sectionId = commit['section_id'] as String;
    final sectionName = commit['section_name'] as String? ?? sectionId;
    final commitId = commit['id'] as int;
    final version = commit['version_number'];

    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF1A1F2E),
        title: const Text('Rollback section?', style: TextStyle(color: Colors.white)),
        content: Text(
          'Restore "$sectionName" to version $version? This creates a new rollback commit.',
          style: const TextStyle(color: Color(0xFF94A3B8)),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF6366F1)),
            child: const Text('Rollback'),
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
        content: Text(ok ? 'Section rolled back to v$version' : 'Rollback failed'),
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
    final history = vc.projectHistory;

    return Scaffold(
      backgroundColor: const Color(0xFF0F1419),
      appBar: AppBar(
        backgroundColor: const Color(0xFF141B27),
        title: Text('Version History — ${widget.projectName}'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _load),
        ],
      ),
      body: vc.loading && history.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : history.isEmpty
              ? const Center(
                  child: Text(
                    'No commits yet across any section',
                    style: TextStyle(color: Color(0xFF94A3B8)),
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: history.length,
                    itemBuilder: (_, i) {
                      final c = history[i];
                      final type = c['commit_type'] as String? ?? 'save';
                      final sectionName = c['section_name'] as String? ?? c['section_id'];
                      final typeColor = _typeColor(type);

                      return Card(
                        color: const Color(0xFF1A1F2E),
                        margin: const EdgeInsets.only(bottom: 10),
                        child: ExpansionTile(
                          leading: Container(
                            width: 4,
                            height: 40,
                            decoration: BoxDecoration(
                              color: typeColor,
                              borderRadius: BorderRadius.circular(2),
                            ),
                          ),
                          title: Text(
                            '${c['section_name']} · v${c['version_number']}',
                            style: const TextStyle(color: Colors.white, fontSize: 13),
                          ),
                          subtitle: Text(
                            '${c['author_name']} · ${c['created_at']} · $type',
                            style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
                          ),
                          children: [
                            Padding(
                              padding: const EdgeInsets.all(12),
                              child: Text(
                                c['content'] as String? ?? '',
                                style: const TextStyle(color: Color(0xFFCBD5E1), fontSize: 12),
                                maxLines: 12,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.only(left: 12, right: 12, bottom: 8),
                              child: Row(
                                children: [
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                    decoration: BoxDecoration(
                                      color: typeColor.withOpacity(0.15),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(
                                      sectionName,
                                      style: TextStyle(color: typeColor, fontSize: 10),
                                    ),
                                  ),
                                  const Spacer(),
                                  ElevatedButton.icon(
                                    onPressed: () => _rollback(c),
                                    icon: const Icon(Icons.restore, size: 14),
                                    label: const Text('Rollback', style: TextStyle(fontSize: 12)),
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: const Color(0xFF6366F1),
                                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                ),
    );
  }
}
