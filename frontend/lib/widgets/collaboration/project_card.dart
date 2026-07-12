import 'package:flutter/material.dart';

/// Shared project card used by the Dashboard recent list and Collaboration hub.
class ProjectCard extends StatelessWidget {
  final Map<String, dynamic> project;
  final VoidCallback onTap;
  final double? width;

  const ProjectCard({
    super.key,
    required this.project,
    required this.onTap,
    this.width = 300,
  });

  String _formatDate(dynamic raw) {
    if (raw == null) return '—';
    final s = raw.toString();
    if (s.length >= 10) return s.substring(0, 10);
    return s;
  }

  @override
  Widget build(BuildContext context) {
    final name = project['name'] as String? ?? 'Project';
    final creator = project['owner_name'] as String? ?? 'Unknown';
    final created = _formatDate(project['created_at']);
    final filename = (project['base_document_filename'] as String?)?.trim();
    final hasDoc = filename != null && filename.isNotEmpty;

    return GestureDetector(
      onTap: onTap,
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        child: Container(
          width: width,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: const Color(0xFF161B22),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.white.withOpacity(0.1)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: const Color(0xFF10B981).withOpacity(0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.folder_shared,
                      color: Color(0xFF10B981),
                      size: 18,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      name,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                        fontSize: 14,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Icon(
                    Icons.chevron_right,
                    size: 16,
                    color: Colors.white.withOpacity(0.4),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              _metaRow(Icons.person_outline, 'Created by $creator'),
              const SizedBox(height: 6),
              _metaRow(Icons.calendar_today_outlined, created),
              const SizedBox(height: 6),
              _metaRow(
                Icons.description_outlined,
                hasDoc ? filename : 'No document yet',
                muted: !hasDoc,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _metaRow(IconData icon, String text, {bool muted = false}) {
    return Row(
      children: [
        Icon(icon, size: 12, color: Colors.white.withOpacity(0.35)),
        const SizedBox(width: 6),
        Expanded(
          child: Text(
            text,
            style: TextStyle(
              color: muted
                  ? Colors.white.withOpacity(0.35)
                  : Colors.white.withOpacity(0.55),
              fontSize: 11,
              fontStyle: muted ? FontStyle.italic : FontStyle.normal,
            ),
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }
}
