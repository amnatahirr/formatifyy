import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/collaboration_provider.dart';

class VersionHistoryScreen extends StatefulWidget {
  final int projectId;
  final String sectionId;
  final String sectionName;

  const VersionHistoryScreen({
    super.key,
    required this.projectId,
    required this.sectionId,
    required this.sectionName,
  });

  @override
  State<VersionHistoryScreen> createState() => _VersionHistoryScreenState();
}

class _VersionHistoryScreenState extends State<VersionHistoryScreen> {
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final vc = context.read<CollaborationProvider>();
    await vc.loadHistory(widget.projectId, widget.sectionId);
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _rollback(int commitId) async {
    final vc = context.read<CollaborationProvider>();

    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Rollback?'),
        content: const Text(
          'This creates a new commit restoring the selected version. The rollback is tracked in history.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          ElevatedButton(onPressed: () => Navigator.pop(context, true), child: const Text('Rollback')),
        ],
      ),
    );
    if (confirm != true) return;

    final ok = await vc.rollback(widget.projectId, widget.sectionId, commitId);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(ok ? 'Rollback commit created' : 'Rollback failed')),
    );
    if (ok) await _load();
  }

  @override
  Widget build(BuildContext context) {
    final vc = context.watch<CollaborationProvider>();
    final history = vc.history;

    return Scaffold(
      backgroundColor: const Color(0xFF0F1419),
      appBar: AppBar(
        backgroundColor: const Color(0xFF141B27),
        title: Text('History — ${widget.sectionName}'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : history.isEmpty
              ? const Center(
                  child: Text('No commits yet', style: TextStyle(color: Color(0xFF94A3B8))))
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: history.length,
                  itemBuilder: (_, i) {
                    final c = history[i];
                    final type = c['commit_type'] as String? ?? 'save';
                    return Card(
                      color: const Color(0xFF1A1F2E),
                      margin: const EdgeInsets.only(bottom: 10),
                      child: ExpansionTile(
                        title: Text(
                          'v${c['version_number']} · ${c['author_name']}',
                          style: const TextStyle(color: Colors.white, fontSize: 13),
                        ),
                        subtitle: Text(
                          '${c['created_at']} · $type',
                          style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
                        ),
                        children: [
                          Padding(
                            padding: const EdgeInsets.all(12),
                            child: Text(
                              c['content'] as String? ?? '',
                              style: const TextStyle(color: Color(0xFFCBD5E1), fontSize: 12),
                            ),
                          ),
                          Align(
                            alignment: Alignment.centerRight,
                            child: TextButton.icon(
                              onPressed: () => _rollback(c['id'] as int),
                              icon: const Icon(Icons.restore, size: 16),
                              label: const Text('Rollback to this'),
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
    );
  }
}
