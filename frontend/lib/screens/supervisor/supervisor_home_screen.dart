import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../widgets/admin/admin_ui.dart';

class SupervisorHomeScreen extends StatefulWidget {
  final VoidCallback? onOpenAssignmentRequests;
  final VoidCallback? onOpenMyGroups;
  final VoidCallback? onOpenSubmissions;
  final VoidCallback? onOpenPlagiarism;

  const SupervisorHomeScreen({
    super.key,
    this.onOpenAssignmentRequests,
    this.onOpenMyGroups,
    this.onOpenSubmissions,
    this.onOpenPlagiarism,
  });

  @override
  State<SupervisorHomeScreen> createState() => _SupervisorHomeScreenState();
}

class _SupervisorHomeScreenState extends State<SupervisorHomeScreen> {
  final SupervisorApiService _api = SupervisorApiService();
  SupervisorHomeModel? _home;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadHome();
  }

  Future<void> _loadHome() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final home = await _api.fetchHome(userId);
      if (mounted) setState(() => _home = home);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const AdminPage(child: AdminLoadingView());
    }
    if (_error != null) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _loadHome));
    }

    final home = _home;
    if (home == null) {
      return AdminPage(
        onRefresh: _loadHome,
        child: const AdminEmptyView(
          message: 'Dashboard data is not available yet. Pull to refresh once the backend is running.',
        ),
      );
    }

    final auth = context.watch<AuthProvider>();
    final displayName = home.supervisorName.isNotEmpty
        ? home.supervisorName
        : (auth.currentUser ?? 'Supervisor');

    return AdminPage(
      onRefresh: _loadHome,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageHeader(
            title: 'Welcome, $displayName',
            subtitle: 'Pending work and progress across your accepted groups',
          ),
          const SizedBox(height: 24),
          adminResponsiveGrid(
            itemCount: 4,
            itemBuilder: (context, index) {
              final cards = [
                _TappableStatCard(
                  onTap: widget.onOpenAssignmentRequests,
                  child: AdminStatCard(
                    title: 'Pending Requests',
                    value: '${home.pendingAssignmentRequests}',
                    icon: Icons.assignment_ind_rounded,
                  ),
                ),
                _TappableStatCard(
                  onTap: widget.onOpenSubmissions,
                  child: AdminStatCard(
                    title: 'Documents to Review',
                    value: '${home.documentsToReview}',
                    icon: Icons.description_outlined,
                    accent: AdminColors.warning,
                  ),
                ),
                AdminStatCard(
                  title: 'Unread Replies',
                  value: '${home.unreadReplies}',
                  icon: Icons.mark_email_unread_outlined,
                  accent: AdminColors.accent,
                ),
                _TappableStatCard(
                  onTap: widget.onOpenPlagiarism,
                  child: AdminStatCard(
                    title: 'Plagiarism Monitor',
                    value: 'Check',
                    icon: Icons.policy_rounded,
                    accent: AdminColors.danger,
                  ),
                ),
              ];
              return cards[index];
            },
          ),
          const SizedBox(height: 28),
          Row(
            children: [
              Expanded(
                child: Text(
                  'Accepted Groups',
                  style: TextStyle(color: Colors.white.withOpacity(0.8), fontWeight: FontWeight.w600),
                ),
              ),
              if (widget.onOpenMyGroups != null)
                TextButton(
                  onPressed: widget.onOpenMyGroups,
                  child: const Text('View My Groups'),
                ),
            ],
          ),
          const SizedBox(height: 14),
          if (home.groups.isEmpty)
            AdminSectionCard(
              title: 'No groups yet',
              child: Text(
                'Accepted groups will appear here with their progress.',
                style: TextStyle(color: Colors.white.withOpacity(0.65), height: 1.45),
              ),
            )
          else
            ...home.groups.map(
              (group) => Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: InkWell(
                  onTap: widget.onOpenMyGroups,
                  borderRadius: BorderRadius.circular(14),
                  child: _SupervisorGroupProgressCard(group: group),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _TappableStatCard extends StatelessWidget {
  final Widget child;
  final VoidCallback? onTap;

  const _TappableStatCard({required this.child, this.onTap});

  @override
  Widget build(BuildContext context) {
    if (onTap == null) return child;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: child,
      ),
    );
  }
}

class _SupervisorGroupProgressCard extends StatelessWidget {
  final SupervisorGroupSummary group;

  const _SupervisorGroupProgressCard({required this.group});

  @override
  Widget build(BuildContext context) {
    final progress = group.progress / 100.0;
    final percentLabel = '${group.progress.round()}%';

    return Container(
      padding: const EdgeInsets.all(18),
      decoration: adminCardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AdminColors.primary.withOpacity(0.14),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.groups_rounded, color: AdminColors.primary, size: 20),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      group.title,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
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
              Text(
                percentLabel,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: AdminColors.primary,
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
              valueColor: const AlwaysStoppedAnimation<Color>(AdminColors.primary),
            ),
          ),
        ],
      ),
    );
  }
}
