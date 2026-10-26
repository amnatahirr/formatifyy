import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../widgets/admin/admin_ui.dart';
import 'group_detail_screen.dart';

import '../../widgets/tr.dart';
class MyGroupsScreen extends StatefulWidget {
  const MyGroupsScreen({super.key});

  @override
  State<MyGroupsScreen> createState() => _MyGroupsScreenState();
}

class _MyGroupsScreenState extends State<MyGroupsScreen> {
  final SupervisorApiService _api = SupervisorApiService();
  List<SupervisorGroupSummary> _groups = const [];
  String _filter = 'All';
  String? _error;
  bool _loading = true;

  String get _apiFilter {
    switch (_filter) {
      case 'On Track':
        return 'on_track';
      case 'Behind':
        return 'behind';
      default:
        return 'all';
    }
  }

  @override
  void initState() {
    super.initState();
    _loadGroups();
  }

  Future<void> _loadGroups() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final groups = await _api.fetchMyGroups(userId, filter: _apiFilter);
      if (mounted) setState(() => _groups = groups);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _setFilter(String label) async {
    if (_filter == label) return;
    setState(() => _filter = label);
    await _loadGroups();
  }

  Future<void> _discardGroup(SupervisorGroupSummary group) async {
    final reasonController = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          backgroundColor: AdminColors.surface,
          shape: adminDialogShape(),
          title: const Tr('Discard group?'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Remove "${group.title}" from My Groups and free one supervision slot so you can accept a new student request.',
                style: TextStyle(color: Colors.white.withOpacity(0.75), height: 1.4),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: reasonController,
                maxLines: 2,
                style: const TextStyle(color: Colors.white),
                decoration: adminFieldDecoration(
                  label: 'Reason (optional)',
                  hint: 'e.g. Group inactive / wrong allotment',
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Tr('Cancel'),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AdminColors.danger,
                foregroundColor: Colors.white,
              ),
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Tr('Discard'),
            ),
          ],
        );
      },
    );
    final reason = reasonController.text.trim();
    reasonController.dispose();
    if (confirmed != true || !mounted) return;

    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    try {
      final result = await _api.discardGroup(
        userId: userId,
        groupId: group.id,
        reason: reason.isEmpty ? null : reason,
      );
      if (!mounted) return;
      final slots = result['slots_used'];
      final max = result['max_groups'];
      showAdminSnackBar(
        context,
        slots != null && max != null
            ? 'Group discarded. Slots used: $slots / $max'
            : 'Group discarded. Slot freed.',
      );
      await _loadGroups();
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading && _groups.isEmpty && _error == null) {
      return const AdminPage(child: AdminLoadingView(label: 'Loading your groups...'));
    }
    if (_error != null && _groups.isEmpty) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _loadGroups));
    }

    return AdminPage(
      onRefresh: _loadGroups,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageMeta(
            text: _groups.isEmpty
                ? 'Accepted groups will appear here'
                : '${_groups.length} group${_groups.length == 1 ? '' : 's'} · filter: $_filter',
          ),
          const SizedBox(height: 18),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final label in const ['All', 'On Track', 'Behind'])
                AdminFilterChip(
                  label: label,
                  selected: _filter == label,
                  onTap: () => _setFilter(label),
                ),
            ],
          ),
          const SizedBox(height: 20),
          if (_loading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 40),
              child: AdminLoadingView(),
            )
          else if (_groups.isEmpty)
            AdminEmptyView(
              icon: Icons.groups_outlined,
              title: 'No groups to show',
              message: _filter == 'All'
                  ? 'No accepted groups yet. Accept an assignment request to add a group here.'
                  : 'No groups match the "$_filter" filter.',
            )
          else
            ..._groups.map(
              (group) => Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: InkWell(
                  onTap: () async {
                    await Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => GroupDetailScreen(
                          groupId: group.id,
                          groupTitle: group.title,
                        ),
                      ),
                    );
                    if (mounted) _loadGroups();
                  },
                  borderRadius: BorderRadius.circular(adminCardRadius),
                  child: _MyGroupCard(
                    group: group,
                    onDiscard: () => _discardGroup(group),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _MyGroupCard extends StatelessWidget {
  final SupervisorGroupSummary group;
  final VoidCallback onDiscard;

  const _MyGroupCard({required this.group, required this.onDiscard});

  @override
  Widget build(BuildContext context) {
    final behind = group.isBehind;
    final accent = behind ? AdminColors.danger : AdminColors.primary;
    final progress = group.progress / 100.0;
    final deadlineLabel = group.deadlineDate.isEmpty ? 'No deadline set' : group.deadlineDate;

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: adminCardDecoration(
        color: behind ? const Color(0xFF23193C) : AdminColors.card,
        borderColor: behind
            ? AdminColors.danger.withOpacity(0.6)
            : AdminColors.borderStrong,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AdminIconBadge(icon: Icons.groups_rounded, color: accent, size: 20),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      group.title,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: behind ? const Color(0xFFFFCDD2) : Colors.white,
                      ),
                    ),
                    if (group.projectTitle.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        group.projectTitle,
                        style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.55)),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  PopupMenuButton<String>(
                    tooltip: 'Group actions',
                    color: AdminColors.card,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(adminTileRadius),
                      side: const BorderSide(color: AdminColors.borderStrong),
                    ),
                    onSelected: (value) {
                      if (value == 'discard') onDiscard();
                    },
                    itemBuilder: (context) => const [
                      PopupMenuItem(
                        value: 'discard',
                        child: Tr('Discard group'),
                      ),
                    ],
                    icon: Icon(Icons.more_vert_rounded, color: Colors.white.withOpacity(0.65)),
                  ),
                  AdminPill(
                    label: '${group.progress.round()}%',
                    color: behind ? AdminColors.danger : AdminColors.accentBright,
                  ),
                  if (behind) ...[
                    const SizedBox(height: 6),
                    const AdminPill(
                      label: 'Behind',
                      color: AdminColors.danger,
                      icon: Icons.warning_amber_rounded,
                    ),
                  ],
                ],
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Icon(Icons.people_outline_rounded, size: 15, color: Colors.white.withOpacity(0.45)),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  group.membersLabel,
                  style: TextStyle(fontSize: 13, color: Colors.white.withOpacity(0.82), height: 1.35),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Icon(
                Icons.event_rounded,
                size: 15,
                color: behind ? AdminColors.danger : Colors.white.withOpacity(0.45),
              ),
              const SizedBox(width: 8),
              Text(
                'Deadline: $deadlineLabel',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: behind ? FontWeight.w600 : FontWeight.w500,
                  color: behind ? AdminColors.danger : Colors.white.withOpacity(0.82),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          AdminProgressBar(
            value: progress,
            color: behind ? AdminColors.danger : null,
          ),
        ],
      ),
    );
  }
}
