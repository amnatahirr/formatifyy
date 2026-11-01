import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../providers/collaboration_provider.dart';

import '../../../widgets/tr.dart';
/// Activity tab — who uploaded / changed what and when, most recent first.
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
    await context
        .read<CollaborationProvider>()
        .loadProjectActivity(widget.projectId);
  }

  /// Returns a const-style Icon widget — do not return IconData dynamically
  /// (breaks Material icon tree-shaking and can empty all icons app-wide).
  Widget _typeIcon(String type, Color color) {
    switch (type) {
      case 'upload':
        return Icon(Icons.upload_file, color: color, size: 16);
      case 'new_version':
        return Icon(Icons.file_upload_outlined, color: color, size: 16);
      case 'rollback':
        return Icon(Icons.restore, color: color, size: 16);
      default:
        return Icon(Icons.edit_outlined, color: color, size: 16);
    }
  }

  Color _color(String type) {
    switch (type) {
      case 'upload':
        return const Color(0xFF8B5CF6);
      case 'new_version':
        return const Color(0xFF10B981);
      case 'rollback':
        return const Color(0xFFF59E0B);
      default:
        return const Color(0xFF3B82F6);
    }
  }

  /// Backend timestamps are UTC ("YYYY-MM-DD HH:MM:SS"); show them in local time.
  String _formatWhen(String raw) {
    if (raw.isEmpty) return '';
    final parsed = DateTime.tryParse(raw.replaceFirst(' ', 'T'));
    if (parsed == null) return raw;
    final utc = parsed.isUtc
        ? parsed
        : DateTime.utc(
            parsed.year,
            parsed.month,
            parsed.day,
            parsed.hour,
            parsed.minute,
            parsed.second,
          );
    final l = utc.toLocal();
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    final hour12 = l.hour % 12 == 0 ? 12 : l.hour % 12;
    final minute = l.minute.toString().padLeft(2, '0');
    final ampm = l.hour >= 12 ? 'PM' : 'AM';
    return '${l.day} ${months[l.month - 1]} ${l.year}, $hour12:$minute $ampm';
  }

  List<InlineSpan> _description(Map<String, dynamic> e, String type) {
    final author = e['author_name'] as String? ?? 'Someone';
    final filename = (e['filename'] as String?)?.trim();
    final section =
        e['section_name'] as String? ?? e['section_id'] as String? ?? 'section';
    final version = e['version_number'];

    const bold = TextStyle(fontWeight: FontWeight.w700);
    const semi = TextStyle(fontWeight: FontWeight.w600);
    const dim = TextStyle(color: Color(0xFF94A3B8));

    switch (type) {
      case 'upload':
        return [
          TextSpan(text: author, style: bold),
          const TextSpan(text: ' uploaded '),
          TextSpan(
            text: (filename != null && filename.isNotEmpty)
                ? filename
                : 'a document',
            style: semi,
          ),
        ];
      case 'new_version':
        return [
          TextSpan(text: author, style: bold),
          const TextSpan(text: ' uploaded a new version '),
          TextSpan(
            text: (filename != null && filename.isNotEmpty) ? filename : '',
            style: semi,
          ),
        ];
      case 'rollback':
        return [
          TextSpan(text: author, style: bold),
          const TextSpan(text: ' restored '),
          TextSpan(text: section, style: semi),
          TextSpan(text: ' to v$version', style: dim),
        ];
      default:
        return [
          TextSpan(text: author, style: bold),
          const TextSpan(text: ' updated '),
          TextSpan(text: section, style: semi),
          TextSpan(text: ' to v$version', style: dim),
        ];
    }
  }

  @override
  Widget build(BuildContext context) {
    final vc = context.watch<CollaborationProvider>();
    final events = vc.projectActivity;

    if (vc.loading && events.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (events.isEmpty) {
      return RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          children: const [
            SizedBox(height: 160),
            Center(
              child: Tr('No activity yet',
                style: TextStyle(color: Color(0xFF94A3B8)),
              ),
            ),
          ],
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
          final type = e['event_type'] as String? ?? 'save';
          final color = _color(type);
          final when = _formatWhen(e['created_at'] as String? ?? '');
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
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 13,
                          ),
                          children: _description(e, type),
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