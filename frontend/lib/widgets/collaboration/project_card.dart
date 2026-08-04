import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../theme/app_theme.dart';

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
    final p = context.watch<ThemeProvider>().palette;
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
            color: p.surface,
            borderRadius: BorderRadius.circular(p.isDark ? p.cardRadius : 12),
            border: Border.all(color: p.isDark ? p.borderStrong : p.border),
            boxShadow: p.cardShadow,
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
                      style: TextStyle(
                        color: p.textPrimary,
                        fontWeight: FontWeight.w700,
                        fontSize: 14,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Icon(
                    Icons.chevron_right,
                    size: 16,
                    color: p.textMuted,
                  ),
                ],
              ),
              const SizedBox(height: 12),
              _metaRow(p, Icons.person_outline, 'Created by $creator'),
              const SizedBox(height: 6),
              _metaRow(p, Icons.calendar_today_outlined, created),
              const SizedBox(height: 6),
              _metaRow(
                p,
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

  Widget _metaRow(AppPalette p, IconData icon, String text, {bool muted = false}) {
    return Row(
      children: [
        Icon(icon, size: 12, color: p.textMuted),
        const SizedBox(width: 6),
        Expanded(
          child: Text(
            text,
            style: TextStyle(
              color: muted ? p.textMuted : p.textSecondary,
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
