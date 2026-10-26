import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/dev_user_config.dart';
import '../../providers/auth_provider.dart';
import '../../providers/collaboration_provider.dart';
import '../../providers/template_provider.dart';
import '../../widgets/collaboration/project_card.dart';
import 'project_detail_screen.dart';
import 'widgets/create_project_dialog.dart';
import 'widgets/hub_version_summary.dart';
import 'widgets/join_project_dialog.dart';
import '../../theme/app_theme.dart';

import '../../widgets/tr.dart';
/// Collaboration hub — Create / Join actions + full project list.
class ProjectDashboardScreen extends StatefulWidget {
  final bool embedded;
  final void Function(int projectId, {int tab})? onOpenProject;

  const ProjectDashboardScreen({
    super.key,
    this.embedded = false,
    this.onOpenProject,
  });

  @override
  State<ProjectDashboardScreen> createState() => _ProjectDashboardScreenState();
}

class _ProjectDashboardScreenState extends State<ProjectDashboardScreen> {
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
    await vc.loadHubActivitySummary();
    if (templates.templates.isEmpty) {
      await templates.fetchTemplates(userId);
    }
  }

  void _openProjectById(int projectId, {int tab = 0}) {
    if (widget.onOpenProject != null) {
      widget.onOpenProject!(projectId, tab: tab);
      return;
    }
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ProjectDetailScreen(
          projectId: projectId,
          initialTab: tab,
        ),
      ),
    );
  }

  Future<void> _showCreateDialog() async {
    await showDialog<void>(
      context: context,
      builder: (_) => CreateProjectDialog(
        onCreated: (id) => _openProjectById(id),
      ),
    );
    await _refresh();
  }

  Future<void> _showJoinDialog() async {
    await showDialog<void>(
      context: context,
      builder: (_) => JoinProjectDialog(
        onJoined: (id) => _openProjectById(id),
      ),
    );
    await _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final p = context.watch<ThemeProvider>().palette;
    final body = _buildBody(context, p);
    if (widget.embedded) {
      return ColoredBox(color: p.scaffold, child: body);
    }

    final auth = context.watch<AuthProvider>();
    return Scaffold(
      backgroundColor: p.scaffold,
      appBar: AppBar(
        title: Text(
          'Collaboration — ${auth.currentUser ?? DevUserConfig.memberKey}',
        ),
        backgroundColor: p.surface,
        foregroundColor: p.textPrimary,
      ),
      body: body,
    );
  }

  Widget _buildBody(BuildContext context, AppPalette p) {
    final vc = context.watch<CollaborationProvider>();

    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Row(
            children: [
              ElevatedButton.icon(
                onPressed: _showCreateDialog,
                icon: const Icon(Icons.add, size: 18, color: Colors.white),
                label: const Tr('Create Project', style: TextStyle(color: Colors.white)),
                style: ElevatedButton.styleFrom(
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                ),
              ),
              const SizedBox(width: 12),
              OutlinedButton.icon(
                onPressed: _showJoinDialog,
                icon: const Icon(Icons.group_add, size: 18),
                label: const Tr('Join Project'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFF10B981),
                  side: const BorderSide(color: Color(0xFF10B981)),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                ),
              ),
            ],
          ),
          const SizedBox(height: 28),
          Text(
            'Your Projects (${vc.projects.length})',
            style: TextStyle(
              color: p.textPrimary,
              fontSize: 18,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 12),
          if (vc.loading && vc.projects.isEmpty)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (vc.projects.isEmpty)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: p.surface,
                borderRadius: BorderRadius.circular(p.isDark ? p.cardRadius : 12),
                border: Border.all(color: p.isDark ? p.borderStrong : p.border),
                boxShadow: p.cardShadow,
              ),
              child: Tr('No projects yet — create or join one to get started.',
                style: TextStyle(color: p.textSecondary, fontSize: 13),
              ),
            )
          else
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: vc.projects
                  .map(
                    (proj) => ProjectCard(
                      project: proj,
                      onTap: () => _openProjectById(proj['id'] as int),
                    ),
                  )
                  .toList(),
            ),
          const SizedBox(height: 28),
          HubVersionSummary(onOpenProject: _openProjectById),
        ],
      ),
    );
  }
}
