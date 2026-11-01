import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/dev_user_config.dart';
import '../../providers/auth_provider.dart';
import '../../providers/collaboration_provider.dart';
import '../../providers/collaboration_socket.dart';
import '../../providers/document_provider.dart';
import 'tabs/project_activity_tab.dart';
import 'tabs/project_editor_tab.dart';
import 'tabs/project_members_tab.dart';
import 'tabs/project_version_history_tab.dart';
import 'widgets/invite_menu_dialog.dart';

import '../../widgets/tr.dart';
/// Project Detail — Document / Members / Version History / Activity.
class ProjectDetailScreen extends StatefulWidget {
  final int projectId;
  final int initialTab;
  /// When true, renders inside StudentDashboard (no outer Scaffold).
  final bool embedded;
  final VoidCallback? onBack;

  const ProjectDetailScreen({
    super.key,
    required this.projectId,
    this.initialTab = 0,
    this.embedded = false,
    this.onBack,
  });

  @override
  State<ProjectDetailScreen> createState() => _ProjectDetailScreenState();
}

class _ProjectDetailScreenState extends State<ProjectDetailScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  final CollaborationSocket _socket = CollaborationSocket();
  final Set<int> _onlineUserIds = {};

  @override
  void initState() {
    super.initState();
    _tabs = TabController(
      length: 4,
      vsync: this,
      initialIndex: widget.initialTab.clamp(0, 3),
    );
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
    await vc.loadProjectHistory(widget.projectId);
    await _refreshMemberReports();

    if (!mounted) return;
    setState(() {
      _onlineUserIds.add(userId);
    });

    _socket.connect(
      projectId: widget.projectId,
      userId: userId,
      onEvent: (event) async {
        final type = event['type'] as String?;
        if (type == 'section_updated') {
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
        } else if (type == 'member_joined' || type == 'member_left') {
          final list = event['online_user_ids'];
          if (list is List) {
            if (mounted) {
              setState(() {
                _onlineUserIds
                  ..clear()
                  ..addAll(list.whereType<int>());
              });
            }
          } else {
            final uid = event['user_id'] as int?;
            if (uid != null && mounted) {
              setState(() {
                if (type == 'member_joined') {
                  _onlineUserIds.add(uid);
                } else {
                  _onlineUserIds.remove(uid);
                }
              });
            }
          }
        }
      },
    );
  }

  @override
  void dispose() {
    _socket.disconnect();
    _tabs.dispose();
    super.dispose();
  }

  void _openInvite(Map<String, dynamic> project) {
    showDialog<void>(
      context: context,
      builder: (_) => InviteMenuDialog(
        projectId: widget.projectId,
        inviteCode: project['invite_code'] as String? ?? '',
      ),
    );
  }

  Widget _inviteButton(Map<String, dynamic> project) {
    return TextButton.icon(
      onPressed: () => _openInvite(project),
      icon: const Icon(Icons.person_add_alt_1, size: 18, color: Color(0xFFA5B4FC)),
      label: const Tr('Invite', style: TextStyle(color: Color(0xFFA5B4FC))),
    );
  }

  Widget _tabBar() {
    return TabBar(
      controller: _tabs,
      indicatorColor: const Color(0xFF6366F1),
      labelColor: Colors.white,
      unselectedLabelColor: const Color(0xFF94A3B8),
      tabs: const [
        Tab(text: 'Document'),
        Tab(text: 'Members'),
        Tab(text: 'Version History'),
        Tab(text: 'Activity'),
      ],
    );
  }

  Widget _tabViews() {
    return TabBarView(
      controller: _tabs,
      children: [
        ProjectEditorTab(
          projectId: widget.projectId,
          isLive: _socket.isConnected,
          onlineUserIds: _onlineUserIds,
          onReload: () {},
        ),
        ProjectMembersTab(projectId: widget.projectId),
        ProjectVersionHistoryTab(projectId: widget.projectId),
        ProjectActivityTab(projectId: widget.projectId),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final vc = context.watch<CollaborationProvider>();
    final project = vc.currentProject ?? {};
    final name = project['name'] as String? ?? 'Project';
    final subtitle = '${auth.currentUser ?? DevUserConfig.memberKey}';

    if (widget.embedded) {
      return ColoredBox(
        color: const Color(0xFF0F1419),
        child: Column(
          children: [
            Container(
              color: const Color(0xFF141B27),
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              child: Row(
                children: [
                  IconButton(
                    icon: const Icon(Icons.arrow_back, color: Colors.white),
                    tooltip: 'Back to Collaboration',
                    onPressed: widget.onBack,
                  ),
                  Expanded(
                    child: Text(
                      '$name — $subtitle',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  _inviteButton(project),
                ],
              ),
            ),
            Material(
              color: const Color(0xFF141B27),
              child: _tabBar(),
            ),
            Expanded(child: _tabViews()),
          ],
        ),
      );
    }

    return Scaffold(
      backgroundColor: const Color(0xFF0F1419),
      appBar: AppBar(
        backgroundColor: const Color(0xFF141B27),
        title: Text('$name — $subtitle'),
        actions: [_inviteButton(project)],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(48),
          child: _tabBar(),
        ),
      ),
      body: _tabViews(),
    );
  }
}
