import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/dev_user_config.dart';
import '../../providers/auth_provider.dart';
import '../../providers/collaboration_provider.dart';
import '../../providers/document_provider.dart';
import '../../providers/template_provider.dart';
import 'project_workspace_screen.dart';

class ProjectDashboardScreen extends StatefulWidget {
  const ProjectDashboardScreen({super.key});

  @override
  State<ProjectDashboardScreen> createState() => _ProjectDashboardScreenState();
}

class _ProjectDashboardScreenState extends State<ProjectDashboardScreen> {
  final _createName = TextEditingController();
  final _createDesc = TextEditingController();
  final _inviteCode = TextEditingController();
  int? _selectedTemplateId;
  File? _selectedDocument;
  String? _selectedDocumentName;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
  }

  Future<void> _refresh() async {
    final auth = context.read<AuthProvider>();
    final userId = auth.userId ?? DevUserConfig.backendUserId;
    final vc = context.read<CollaborationProvider>();
    vc.setActiveUserId(userId);
    final templates = context.read<TemplateProvider>();
    await vc.fetchProjects();
    if (templates.templates.isEmpty) {
      await templates.fetchTemplates(userId);
    }
    if (mounted && templates.templates.isNotEmpty) {
      setState(() => _selectedTemplateId = templates.templates.first['id'] as int?);
    }
  }

  @override
  void dispose() {
    _createName.dispose();
    _createDesc.dispose();
    _inviteCode.dispose();
    super.dispose();
  }

  Future<void> _pickDocument() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['docx'],
      withData: false,
    );
    if (result != null && result.files.single.path != null) {
      setState(() {
        _selectedDocument = File(result.files.single.path!);
        _selectedDocumentName = result.files.single.name;
      });
    }
  }

  void _clearDocument() {
    setState(() {
      _selectedDocument = null;
      _selectedDocumentName = null;
    });
  }

  Future<void> _createProject() async {
    final auth = context.read<AuthProvider>();
    final userId = auth.userId ?? DevUserConfig.backendUserId;
    final vc = context.read<CollaborationProvider>();
    vc.setActiveUserId(userId);
    if (_selectedTemplateId == null || _createName.text.trim().isEmpty) return;

    final project = await vc.createProject(
      name: _createName.text.trim(),
      description: _createDesc.text.trim(),
      templateId: _selectedTemplateId!,
      documentFile: _selectedDocument,
    );
    if (!mounted) return;
    if (project != null) {
      await context.read<DocumentProvider>().fetchDocuments(userId);
      if (!mounted) return;
      if (project['base_document_id'] != null || project['reports_sync'] != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Project created — document saved to My Reports for all members',
            ),
            backgroundColor: Color(0xFF10B981),
          ),
        );
      }
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ProjectWorkspaceScreen(projectId: project['id'] as int),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(vc.error ?? 'Create failed')),
      );
    }
  }

  Future<void> _joinProject() async {
    final auth = context.read<AuthProvider>();
    final userId = auth.userId ?? DevUserConfig.backendUserId;
    final vc = context.read<CollaborationProvider>();
    vc.setActiveUserId(userId);
    final ok = await vc.joinProject(_inviteCode.text.trim());
    if (!mounted) return;
    if (ok && vc.currentProject != null) {
      await context.read<DocumentProvider>().fetchDocuments(userId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Joined project — document available in My Reports'),
          backgroundColor: Color(0xFF10B981),
        ),
      );
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ProjectWorkspaceScreen(
            projectId: vc.currentProject!['id'] as int,
          ),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(vc.error ?? 'Join failed')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final vc = context.watch<CollaborationProvider>();
    final templates = context.watch<TemplateProvider>();

    return Scaffold(
      backgroundColor: const Color(0xFF0F1419),
      appBar: AppBar(
        title: Text('Collaboration — ${auth.currentUser ?? DevUserConfig.memberKey}'),
        backgroundColor: const Color(0xFF141B27),
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            _panel(
              title: 'Create Project',
              child: Column(
                children: [
                  TextField(
                    controller: _createName,
                    decoration: const InputDecoration(labelText: 'Project name'),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _createDesc,
                    decoration: const InputDecoration(labelText: 'Description'),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<int>(
                    value: _selectedTemplateId,
                    decoration: const InputDecoration(labelText: 'Template'),
                    items: templates.templates
                        .map(
                          (t) => DropdownMenuItem<int>(
                            value: t['id'] as int,
                            child: Text(t['name'] as String? ?? 'Template'),
                          ),
                        )
                        .toList(),
                    onChanged: (v) => setState(() => _selectedTemplateId = v),
                  ),
                  const SizedBox(height: 16),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0F1419),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: const Color(0xFF2D3748)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Base Document (optional)',
                          style: TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w600,
                            fontSize: 13,
                          ),
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          'Upload a .docx to pre-populate sections with existing content.',
                          style: TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
                        ),
                        const SizedBox(height: 12),
                        if (_selectedDocumentName != null)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                            margin: const EdgeInsets.only(bottom: 10),
                            decoration: BoxDecoration(
                              color: const Color(0xFF10B981).withOpacity(0.1),
                              borderRadius: BorderRadius.circular(6),
                              border: Border.all(color: const Color(0xFF10B981).withOpacity(0.3)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.description, color: Color(0xFF10B981), size: 18),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    _selectedDocumentName!,
                                    style: const TextStyle(color: Color(0xFF10B981), fontSize: 12),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                IconButton(
                                  icon: const Icon(Icons.close, size: 16, color: Color(0xFF94A3B8)),
                                  onPressed: _clearDocument,
                                  padding: EdgeInsets.zero,
                                  constraints: const BoxConstraints(),
                                ),
                              ],
                            ),
                          ),
                        OutlinedButton.icon(
                          onPressed: _pickDocument,
                          icon: const Icon(Icons.upload_file, size: 18),
                          label: Text(_selectedDocumentName == null ? 'Upload .docx' : 'Change file'),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: const Color(0xFF6366F1),
                            side: const BorderSide(color: Color(0xFF6366F1)),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: vc.loading ? null : _createProject,
                      child: vc.loading
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          : const Text('Create Project'),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            _panel(
              title: 'Join with Invite Code',
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _inviteCode,
                      decoration: const InputDecoration(
                        labelText: 'Invite code',
                        hintText: 'ABC123XYZ',
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  ElevatedButton(onPressed: _joinProject, child: const Text('Join')),
                ],
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Your Projects (${vc.projects.length})',
              style: const TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 12),
            if (vc.loading && vc.projects.isEmpty)
              const Center(child: CircularProgressIndicator())
            else if (vc.projects.isEmpty)
              const Text('No projects yet. Create one or join with an invite code.',
                  style: TextStyle(color: Color(0xFF94A3B8)))
            else
              ...vc.projects.map((p) => _projectCard(p)),
          ],
        ),
      ),
    );
  }

  Widget _panel({required String title, required Widget child}) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F2E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF2D3748)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: const TextStyle(
                  color: Colors.white, fontWeight: FontWeight.w600, fontSize: 16)),
          const SizedBox(height: 16),
          child,
        ],
      ),
    );
  }

  Widget _projectCard(Map<String, dynamic> p) {
    return Card(
      color: const Color(0xFF1A1F2E),
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        title: Text(p['name'] as String? ?? 'Project',
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
        subtitle: Text(
          '${p['template_name'] ?? 'Template'} · ${p['member_count'] ?? 1} members · ${p['status'] ?? 'active'}',
          style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
        ),
        trailing: const Icon(Icons.chevron_right, color: Color(0xFF6366F1)),
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => ProjectWorkspaceScreen(projectId: p['id'] as int),
          ),
        ),
      ),
    );
  }
}
