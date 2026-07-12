import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:open_file_plus/open_file_plus.dart';
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';
import '../../../config/dev_user_config.dart';
import '../../../providers/auth_provider.dart';
import '../../../providers/collaboration_provider.dart';
import '../../../providers/document_provider.dart';
import '../section_editor_screen.dart';

/// Document tab — preview by default, download / edit / upload new version.
class ProjectEditorTab extends StatefulWidget {
  final int projectId;
  final bool isLive;
  final Set<int> onlineUserIds;
  final VoidCallback onReload;

  const ProjectEditorTab({
    super.key,
    required this.projectId,
    required this.isLive,
    required this.onlineUserIds,
    required this.onReload,
  });

  @override
  State<ProjectEditorTab> createState() => _ProjectEditorTabState();
}

class _ProjectEditorTabState extends State<ProjectEditorTab> {
  bool _editMode = false;
  bool _downloading = false;
  bool _uploading = false;

  Future<void> _download() async {
    setState(() => _downloading = true);
    final vc = context.read<CollaborationProvider>();
    final url = vc.downloadUrl(widget.projectId);
    try {
      final resp = await http.get(Uri.parse(url));
      if (resp.statusCode != 200) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Download failed (${resp.statusCode})')),
        );
        return;
      }
      final dir = await getTemporaryDirectory();
      final project = vc.currentProject ?? {};
      final name = (project['base_document_filename'] as String?)?.trim();
      final safe = (name != null && name.isNotEmpty)
          ? name
          : 'project_${widget.projectId}.docx';
      final path = '${dir.path}${Platform.pathSeparator}$safe';
      final file = File(path);
      await file.writeAsBytes(resp.bodyBytes);
      await OpenFile.open(path);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Document downloaded'),
          backgroundColor: Color(0xFF10B981),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Download error: $e')),
      );
    } finally {
      if (mounted) setState(() => _downloading = false);
    }
  }

  Future<void> _uploadNewVersion() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['docx'],
      withData: false,
    );
    if (result == null || result.files.single.path == null) return;

    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF1A1F2E),
        title: const Text(
          'Upload new version?',
          style: TextStyle(color: Colors.white),
        ),
        content: const Text(
          'This will import the file as new version history entries for each '
          'section. It does not silently overwrite — previous versions stay '
          'in Version History and can be restored.',
          style: TextStyle(color: Color(0xFF94A3B8)),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF6366F1),
            ),
            child: const Text('Upload'),
          ),
        ],
      ),
    );
    if (confirm != true || !mounted) return;

    setState(() => _uploading = true);
    final vc = context.read<CollaborationProvider>();
    final ok = await vc.uploadProjectDocument(
      widget.projectId,
      File(result.files.single.path!),
    );
    if (!mounted) return;
    setState(() => _uploading = false);

    final auth = context.read<AuthProvider>();
    final userId = auth.userId ?? DevUserConfig.backendUserId;
    await context.read<DocumentProvider>().fetchDocuments(userId);

    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          ok
              ? 'New version uploaded — check Version History'
              : (vc.error ?? 'Upload failed'),
        ),
        backgroundColor: ok ? const Color(0xFF10B981) : const Color(0xFFEF4444),
      ),
    );
    if (ok) {
      setState(() => _editMode = false);
      widget.onReload();
    }
  }

  @override
  Widget build(BuildContext context) {
    final vc = context.watch<CollaborationProvider>();
    final project = vc.currentProject ?? {};
    final sections = vc.sections;
    final members = (project['members'] as List? ?? [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
    final filename = (project['base_document_filename'] as String?)?.trim();
    final hasFilename = filename != null && filename.isNotEmpty;

    if (vc.loading && sections.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: const Color(0xFF1A1F2E),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: const Color(0xFF2D3748)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          hasFilename ? filename : 'No document yet',
                          style: TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w700,
                            fontSize: 14,
                            fontStyle:
                                hasFilename ? FontStyle.normal : FontStyle.italic,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Template: ${project['template_name'] ?? ''} · '
                          '${widget.isLive ? 'Live' : 'Offline'}',
                          style: const TextStyle(
                            color: Color(0xFF94A3B8),
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  ElevatedButton.icon(
                    onPressed: _downloading ? null : _download,
                    icon: _downloading
                        ? const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.download, size: 16),
                    label: const Text('Download'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF6366F1),
                    ),
                  ),
                  OutlinedButton.icon(
                    onPressed: () => setState(() => _editMode = !_editMode),
                    icon: Icon(
                      _editMode ? Icons.visibility : Icons.edit,
                      size: 16,
                    ),
                    label: Text(_editMode ? 'Preview' : 'Edit here'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFFA5B4FC),
                      side: const BorderSide(color: Color(0xFF6366F1)),
                    ),
                  ),
                  OutlinedButton.icon(
                    onPressed: _uploading ? null : _uploadNewVersion,
                    icon: _uploading
                        ? const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.upload_file, size: 16),
                    label: const Text('Upload new version'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFF10B981),
                      side: const BorderSide(color: Color(0xFF10B981)),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              const Text(
                'Active now',
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                ),
              ),
              const SizedBox(height: 8),
              _PresenceRow(
                members: members,
                onlineUserIds: widget.onlineUserIds,
              ),
              if (vc.lastLiveUpdate != null) ...[
                const SizedBox(height: 10),
                Text(
                  vc.lastLiveUpdate!,
                  style: const TextStyle(color: Color(0xFF10B981), fontSize: 11),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: 20),
        if (_editMode) ...[
          const Text(
            'Edit sections',
            style: TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 12),
          ...sections.map(
            (s) => _SectionTile(
              projectId: widget.projectId,
              section: s,
              onChanged: widget.onReload,
            ),
          ),
        ] else ...[
          const Text(
            'Document preview',
            style: TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Read-only view from section text. Use Download for full .docx fidelity.',
            style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
          ),
          const SizedBox(height: 12),
          if (sections.every(
            (s) => ((s['latest_content'] as String?) ?? '').trim().isEmpty,
          ))
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFF1A1F2E),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFF2D3748)),
              ),
              child: const Text(
                'Nothing to preview yet. Upload a document or use Edit here to add content.',
                style: TextStyle(color: Color(0xFF94A3B8), fontSize: 13),
              ),
            )
          else
            ...sections.map((s) => _PreviewSection(section: s)),
        ],
      ],
    );
  }
}

class _PreviewSection extends StatelessWidget {
  final Map<String, dynamic> section;

  const _PreviewSection({required this.section});

  @override
  Widget build(BuildContext context) {
    final title = section['section_name'] as String? ?? '';
    final content = (section['latest_content'] as String? ?? '').trim();
    if (content.isEmpty) return const SizedBox.shrink();

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F2E),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF2D3748)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w700,
              fontSize: 15,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'v${section['latest_version'] ?? 0} · ${section['latest_author'] ?? ''}',
            style: const TextStyle(color: Color(0xFF64748B), fontSize: 11),
          ),
          const SizedBox(height: 10),
          Text(
            content,
            style: const TextStyle(
              color: Color(0xFFCBD5E1),
              fontSize: 13,
              height: 1.45,
            ),
          ),
        ],
      ),
    );
  }
}

class _PresenceRow extends StatelessWidget {
  final List<Map<String, dynamic>> members;
  final Set<int> onlineUserIds;

  const _PresenceRow({
    required this.members,
    required this.onlineUserIds,
  });

  @override
  Widget build(BuildContext context) {
    if (onlineUserIds.isEmpty) {
      return Text(
        'No one else is connected',
        style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 12),
      );
    }

    final onlineMembers = members
        .where((m) => onlineUserIds.contains(m['user_id'] as int?))
        .toList();
    final knownIds = onlineMembers.map((m) => m['user_id'] as int).toSet();
    final unknownIds = onlineUserIds.difference(knownIds);

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        ...onlineMembers.map((m) {
          final name = (m['username'] as String?)?.trim().isNotEmpty == true
              ? m['username'] as String
              : (m['email'] as String? ?? 'User');
          return _AvatarChip(label: name);
        }),
        ...unknownIds.map((id) => _AvatarChip(label: 'User $id')),
      ],
    );
  }
}

class _AvatarChip extends StatelessWidget {
  final String label;

  const _AvatarChip({required this.label});

  String get _initials {
    final parts = label.trim().split(RegExp(r'\s+|@'));
    if (parts.isEmpty || parts.first.isEmpty) return '?';
    if (parts.length == 1) return parts.first.substring(0, 1).toUpperCase();
    return (parts[0].substring(0, 1) + parts[1].substring(0, 1)).toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: label,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Stack(
            children: [
              CircleAvatar(
                radius: 14,
                backgroundColor: const Color(0xFF6366F1).withOpacity(0.25),
                child: Text(
                  _initials,
                  style: const TextStyle(
                    color: Color(0xFFA5B4FC),
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              Positioned(
                right: 0,
                bottom: 0,
                child: Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: const Color(0xFF10B981),
                    shape: BoxShape.circle,
                    border: Border.all(color: const Color(0xFF1A1F2E), width: 1.5),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(width: 6),
          Text(
            label,
            style: const TextStyle(color: Color(0xFFCBD5E1), fontSize: 12),
          ),
        ],
      ),
    );
  }
}

class _SectionTile extends StatelessWidget {
  final int projectId;
  final Map<String, dynamic> section;
  final VoidCallback onChanged;

  const _SectionTile({
    required this.projectId,
    required this.section,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final hasContent = (section['latest_content'] as String? ?? '').isNotEmpty;
    return Card(
      color: const Color(0xFF1A1F2E),
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        title: Text(
          section['section_name'] as String? ?? '',
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
        subtitle: Text(
          hasContent
              ? 'v${section['latest_version'] ?? 0} · ${section['latest_author'] ?? 'unknown'} · ${section['commit_count'] ?? 0} commits'
              : 'No content yet — tap to edit',
          style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
        ),
        trailing: const Icon(Icons.chevron_right, color: Color(0xFF6366F1)),
        onTap: () => _openEditor(context),
      ),
    );
  }

  Future<void> _openEditor(BuildContext context) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => SectionEditorScreen(
          projectId: projectId,
          sectionId: section['section_id'] as String,
          sectionName: section['section_name'] as String,
          initialContent: section['latest_content'] as String? ?? '',
        ),
      ),
    );
    if (!context.mounted) return;
    final auth = context.read<AuthProvider>();
    final userId = auth.userId ?? DevUserConfig.backendUserId;
    await context.read<CollaborationProvider>().loadProject(projectId);
    await context.read<DocumentProvider>().fetchDocuments(userId);
    onChanged();
  }
}
