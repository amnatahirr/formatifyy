import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/dev_user_config.dart';
import '../../providers/auth_provider.dart';
import '../../providers/collaboration_provider.dart';
import '../../providers/collaboration_socket.dart';
import '../../providers/document_provider.dart';
import 'merge_conflict_screen.dart';
import 'project_download_screen.dart';
import 'section_editor_screen.dart';
import 'version_history_screen.dart';

/// Hub screen: section list, live updates, merge entry point.
class ProjectWorkspaceScreen extends StatefulWidget {
  final int projectId;

  const ProjectWorkspaceScreen({super.key, required this.projectId});

  @override
  State<ProjectWorkspaceScreen> createState() => _ProjectWorkspaceScreenState();
}

class _ProjectWorkspaceScreenState extends State<ProjectWorkspaceScreen> {
  final CollaborationSocket _socket = CollaborationSocket();
  final _inviteEmail = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _init());
  }

  Future<void> _refreshMemberReports() async {
    final auth = context.read<AuthProvider>();
    final userId = auth.userId ?? DevUserConfig.backendUserId;
    await context.read<DocumentProvider>().fetchDocuments(userId);
  }

  Future<void> _init() async {
    final auth = context.read<AuthProvider>();
    final userId = auth.userId ?? DevUserConfig.backendUserId;
    final vc = context.read<CollaborationProvider>();
    vc.setActiveUserId(userId);
    await vc.loadProject(widget.projectId);
    await _refreshMemberReports();
    // WebSocket uses DevUserConfig.backendUserId from --dart-define=USER_ID
    _socket.connect(
      projectId: widget.projectId,
      onEvent: (event) async {
        if (event['type'] == 'section_updated') {
          vc.applyLiveUpdate(event);
          await _refreshMemberReports();
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                  '${event['author_name']} saved ${event['section_id']} — My Reports updated',
                ),
                duration: const Duration(seconds: 2),
              ),
            );
          }
        }
      },
    );
  }

  @override
  void dispose() {
    _socket.disconnect();
    _inviteEmail.dispose();
    super.dispose();
  }

  Future<void> _invite() async {
    final vc = context.read<CollaborationProvider>();
    if (_inviteEmail.text.trim().isEmpty) return;
    final ok = await vc.inviteMember(
      widget.projectId,
      _inviteEmail.text.trim(),
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(ok ? 'Member invited — My Reports synced' : 'Invite failed')),
    );
    if (ok) await _refreshMemberReports();
  }

  Future<void> _startMerge() async {
    final vc = context.read<CollaborationProvider>();
    final result = await vc.startMerge(widget.projectId);
    if (!mounted || result == null) return;
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => MergeConflictScreen(
          projectId: widget.projectId,
          mergeId: result['merge_id'] as int,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final vc = context.watch<CollaborationProvider>();
    final project = vc.currentProject ?? {};
    final sections = vc.sections;

    return Scaffold(
      backgroundColor: const Color(0xFF0F1419),
      appBar: AppBar(
        backgroundColor: const Color(0xFF141B27),
        title: Text('${project['name'] as String? ?? 'Project'} — ${auth.currentUser ?? DevUserConfig.memberKey}'),
        actions: [
          if (project['status'] == 'merged')
            IconButton(
              icon: const Icon(Icons.download),
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => ProjectDownloadScreen(projectId: widget.projectId),
                ),
              ),
            ),
          IconButton(
            icon: const Icon(Icons.merge_type),
            tooltip: 'Merge',
            onPressed: vc.loading ? null : _startMerge,
          ),
        ],
      ),
      body: vc.loading && sections.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : ListView(
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
                      Text('Invite code: ${project['invite_code'] ?? ''}',
                          style: const TextStyle(
                              color: Color(0xFF6366F1), fontWeight: FontWeight.w600)),
                      const SizedBox(height: 8),
                      Text(
                        'Template: ${project['template_name'] ?? ''} · ${_socket.isConnected ? 'Live' : 'Offline'}',
                        style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                      ),
                      if (vc.lastLiveUpdate != null) ...[
                        const SizedBox(height: 6),
                        Text(vc.lastLiveUpdate!,
                            style: const TextStyle(color: Color(0xFF10B981), fontSize: 11)),
                      ],
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _inviteEmail,
                              decoration: const InputDecoration(
                                labelText: 'Invite by email',
                                isDense: true,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          ElevatedButton(onPressed: _invite, child: const Text('Invite')),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
                const Text('Sections (template order)',
                    style: TextStyle(
                        color: Colors.white, fontSize: 16, fontWeight: FontWeight.w700)),
                const SizedBox(height: 12),
                ...sections.map((s) => _sectionTile(s)),
              ],
            ),
    );
  }

  Future<void> _openSectionEditor(Map<String, dynamic> s) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => SectionEditorScreen(
          projectId: widget.projectId,
          sectionId: s['section_id'] as String,
          sectionName: s['section_name'] as String,
          initialContent: s['latest_content'] as String? ?? '',
        ),
      ),
    );
    if (!mounted) return;
    await context.read<CollaborationProvider>().loadProject(widget.projectId);
    await _refreshMemberReports();
  }

  Widget _sectionTile(Map<String, dynamic> s) {
    final hasContent = (s['latest_content'] as String? ?? '').isNotEmpty;
    return Card(
      color: const Color(0xFF1A1F2E),
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        title: Text(s['section_name'] as String? ?? '',
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
        subtitle: Text(
          hasContent
              ? 'v${s['latest_version'] ?? 0} · ${s['latest_author'] ?? 'unknown'} · ${s['commit_count'] ?? 0} commits'
              : 'No content yet — tap to edit',
          style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
        ),
        trailing: PopupMenuButton<String>(
          onSelected: (value) {
            if (value == 'edit') {
              _openSectionEditor(s);
            } else if (value == 'history') {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => VersionHistoryScreen(
                    projectId: widget.projectId,
                    sectionId: s['section_id'] as String,
                    sectionName: s['section_name'] as String,
                  ),
                ),
              );
            }
          },
          itemBuilder: (_) => const [
            PopupMenuItem(value: 'edit', child: Text('Edit section')),
            PopupMenuItem(value: 'history', child: Text('Version history')),
          ],
        ),
        onTap: () => _openSectionEditor(s),
      ),
    );
  }
}
