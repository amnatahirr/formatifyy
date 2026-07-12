import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../providers/collaboration_provider.dart';

/// Compact cross-project version activity for the Collaboration hub.
class HubVersionSummary extends StatelessWidget {
  final void Function(int projectId, {int tab})? onOpenProject;

  const HubVersionSummary({super.key, this.onOpenProject});

  @override
  Widget build(BuildContext context) {
    final vc = context.watch<CollaborationProvider>();
    final items = vc.hubActivity;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Recent version activity',
          style: TextStyle(
            color: Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 4),
        const Text(
          'Latest changes across your projects',
          style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
        ),
        const SizedBox(height: 12),
        if (items.isEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF1A1F2E),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFF2D3748)),
            ),
            child: const Text(
              'No version history yet. Edits in shared projects will show up here.',
              style: TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
            ),
          )
        else
          ...items.map(
            (e) => _ActivityRow(
              entry: e,
              onOpenProject: onOpenProject,
            ),
          ),
      ],
    );
  }
}

class _ActivityRow extends StatelessWidget {
  final Map<String, dynamic> entry;
  final void Function(int projectId, {int tab})? onOpenProject;

  const _ActivityRow({
    required this.entry,
    this.onOpenProject,
  });

  @override
  Widget build(BuildContext context) {
    final type = entry['commit_type'] as String? ?? 'save';
    final projectName = entry['project_name'] as String? ?? 'Project';
    final section = entry['section_name'] as String? ?? entry['section_id'] ?? 'section';
    final author = entry['author_name'] as String? ?? 'Someone';
    final when = entry['created_at'] as String? ?? '';
    final version = entry['version_number'];
    final projectId = entry['project_id'] as int?;

    return Card(
      color: const Color(0xFF1A1F2E),
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        dense: true,
        leading: _leadingIcon(type),
        title: Text(
          '$author · $section v$version',
          style: const TextStyle(color: Colors.white, fontSize: 13),
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(
          '$projectName · $when',
          style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
          overflow: TextOverflow.ellipsis,
        ),
        trailing: const Icon(Icons.chevron_right, color: Color(0xFF64748B), size: 18),
        onTap: projectId == null
            ? null
            : () {
                if (onOpenProject != null) {
                  onOpenProject!(projectId, tab: 2);
                }
              },
      ),
    );
  }

  Widget _leadingIcon(String type) {
    switch (type) {
      case 'rollback':
        return const Icon(Icons.restore, color: Color(0xFF6366F1), size: 18);
      case 'import':
        return const Icon(Icons.upload_file, color: Color(0xFF6366F1), size: 18);
      default:
        return const Icon(Icons.edit_outlined, color: Color(0xFF6366F1), size: 18);
    }
  }
}
