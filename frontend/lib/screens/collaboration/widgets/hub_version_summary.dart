import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../providers/collaboration_provider.dart';
import '../../../theme/app_theme.dart';

import '../../../widgets/tr.dart';
/// Compact cross-project version activity for the Collaboration hub.
class HubVersionSummary extends StatelessWidget {
  final void Function(int projectId, {int tab})? onOpenProject;

  const HubVersionSummary({super.key, this.onOpenProject});

  @override
  Widget build(BuildContext context) {
    final vc = context.watch<CollaborationProvider>();
    final p = context.watch<ThemeProvider>().palette;
    final items = vc.hubActivity;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Tr('Recent version activity',
          style: TextStyle(
            color: p.textPrimary,
            fontSize: 18,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 4),
        Tr('Latest changes across your projects',
          style: TextStyle(color: p.textSecondary, fontSize: 12),
        ),
        const SizedBox(height: 12),
        if (items.isEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: p.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: p.border),
              boxShadow: p.cardShadow,
            ),
            child: Tr('No version history yet. Edits in shared projects will show up here.',
              style: TextStyle(color: p.textSecondary, fontSize: 13),
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
    final p = context.watch<ThemeProvider>().palette;
    final type = entry['commit_type'] as String? ?? 'save';
    final projectName = entry['project_name'] as String? ?? 'Project';
    final section = entry['section_name'] as String? ?? entry['section_id'] ?? 'section';
    final author = entry['author_name'] as String? ?? 'Someone';
    final when = entry['created_at'] as String? ?? '';
    final version = entry['version_number'];
    final projectId = entry['project_id'] as int?;

    return Card(
      color: p.surface,
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(color: p.border),
      ),
      child: ListTile(
        dense: true,
        leading: _leadingIcon(type),
        title: Text(
          '$author · $section v$version',
          style: TextStyle(color: p.textPrimary, fontSize: 13),
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(
          '$projectName · $when',
          style: TextStyle(color: p.textSecondary, fontSize: 11),
          overflow: TextOverflow.ellipsis,
        ),
        trailing: Icon(Icons.chevron_right, color: p.textMuted, size: 18),
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
