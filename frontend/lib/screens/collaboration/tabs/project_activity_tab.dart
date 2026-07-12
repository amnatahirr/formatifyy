import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../providers/collaboration_provider.dart';

/// Activity tab — who changed what, most recent first.
class ProjectActivityTab extends StatefulWidget {
  final int projectId;

  const ProjectActivityTab({super.key, required this.projectId});

  @override
  State<ProjectActivityTab> createState() => _ProjectActivityTabState();
}

class _ProjectActivityTabState extends State<ProjectActivityTab> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    await context.read<CollaborationProvider>().loadProjectHistory(widget.projectId);
  }

  String _verb(String type) {
    switch (type) {
      case 'import':
        return 'imported';
      case 'rollback':
        return 'restored';
      default:
        return 'updated';
    }
  }

  /// Returns a const Icon widget — do not return IconData dynamically
  /// (breaks Material icon tree-shaking and can empty all icons app-wide).
  Widget _typeIcon(String type, Color color) {
    switch (type) {
      case 'import':
        return Icon(Icons.upload_file, color: color, size: 16);
      case 'rollback':
        return Icon(Icons.restore, color: color, size: 16);
      default:
        return Icon(Icons.edit_outlined, color: color, size: 16);
    }
  }

  Color _color(String type) {
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
    final events = vc.projectHistory.reversed.toList();

    if (vc.loading && events.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (events.isEmpty) {
      return const Center(
        child: Text(
          'No activity yet',
          style: TextStyle(color: Color(0xFF94A3B8)),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: events.length,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (_, i) {
          final e = events[i];
          final type = e['commit_type'] as String? ?? 'save';
          final color = _color(type);
          final author = e['author_name'] as String? ?? 'Someone';
          final section = e['section_name'] as String? ?? e['section_id'] ?? 'section';
          final version = e['version_number'];
          final when = e['created_at'] as String? ?? '';
          final message = (e['message'] as String?)?.trim();

          return Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: const Color(0xFF1A1F2E),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFF2D3748)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: _typeIcon(type, color),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text.rich(
                        TextSpan(
                          style: const TextStyle(color: Colors.white, fontSize: 13),
                          children: [
                            TextSpan(
                              text: author,
                              style: const TextStyle(fontWeight: FontWeight.w700),
                            ),
                            TextSpan(text: ' ${_verb(type)} '),
                            TextSpan(
                              text: '$section',
                              style: const TextStyle(fontWeight: FontWeight.w600),
                            ),
                            TextSpan(
                              text: ' to v$version',
                              style: const TextStyle(color: Color(0xFF94A3B8)),
                            ),
                          ],
                        ),
                      ),
                      if (message != null && message.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Text(
                          message,
                          style: const TextStyle(
                            color: Color(0xFFCBD5E1),
                            fontSize: 12,
                          ),
                        ),
                      ],
                      const SizedBox(height: 4),
                      Text(
                        when,
                        style: const TextStyle(
                          color: Color(0xFF64748B),
                          fontSize: 11,
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
    );
  }
}
