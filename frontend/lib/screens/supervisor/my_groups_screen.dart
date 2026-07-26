import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../widgets/admin/admin_ui.dart';
import 'group_detail_screen.dart';

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
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Text('Discard group?'),
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
                decoration: InputDecoration(
                  labelText: 'Reason (optional)',
                  hintText: 'e.g. Group inactive / wrong allotment',
                  filled: true,
                  fillColor: AdminColors.card,
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AdminColors.danger,
                foregroundColor: Colors.white,
              ),
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Discard'),
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
      return const AdminPage(child: AdminLoadingView());
    }
    if (_error != null && _groups.isEmpty) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _loadGroups));
    }

    return AdminPage(
      onRefresh: _loadGroups,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageHeader(
            title: 'My Groups',
            subtitle: _groups.isEmpty
                ? 'Accepted groups will appear here'
                : '${_groups.length} group${_groups.length == 1 ? '' : 's'} · filter: $_filter',
          ),
          const SizedBox(height: 18),
          Row(
            children: ['All', 'On Track', 'Behind']
                .map(
                  (label) => Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(label),
                      selected: _filter == label,
                      onSelected: (_) => _setFilter(label),
                    ),
                  ),
                )
                .toList(),
          ),
          const SizedBox(height: 20),
          if (_loading)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 40),
              child: Center(child: CircularProgressIndicator(color: AdminColors.primary)),
            )
          else if (_groups.isEmpty)
            AdminEmptyView(
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
                  borderRadius: BorderRadius.circular(14),
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
      decoration: adminCardDecoration().copyWith(
        border: Border.all(
          color: behind ? AdminColors.danger.withOpacity(0.75) : AdminColors.border,
          width: behind ? 1.4 : 1,
        ),
        color: behind ? AdminColors.danger.withOpacity(0.08) : AdminColors.card,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: accent.withOpacity(0.14),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.groups_rounded, color: accent, size: 20),
              ),
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
                    color: AdminColors.surface,
                    onSelected: (value) {
                      if (value == 'discard') onDiscard();
                    },
                    itemBuilder: (context) => const [
                      PopupMenuItem(
                        value: 'discard',
                        child: Text('Discard group'),
                      ),
                    ],
                    icon: Icon(Icons.more_vert_rounded, color: Colors.white.withOpacity(0.65)),
                  ),
                  Text(
                    '${group.progress.round()}%',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: accent,
                    ),
                  ),
                  if (behind) ...[
                    const SizedBox(height: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: AdminColors.danger.withOpacity(0.18),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: const Text(
                        'Behind',
                        style: TextStyle(
                          color: AdminColors.danger,
                          fontWeight: FontWeight.w700,
                          fontSize: 11,
                        ),
                      ),
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
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 8,
              backgroundColor: AdminColors.border.withOpacity(0.65),
              valueColor: AlwaysStoppedAnimation<Color>(accent),
            ),
          ),
        ],
      ),
    );
  }
}
