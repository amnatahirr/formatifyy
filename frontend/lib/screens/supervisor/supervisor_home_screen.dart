import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../utils/responsive.dart';
import '../../widgets/admin/admin_ui.dart';

class SupervisorHomeScreen extends StatefulWidget {
  final VoidCallback? onOpenAssignmentRequests;
  final VoidCallback? onOpenMyGroups;
  final VoidCallback? onOpenSubmissions;
  final VoidCallback? onOpenPlagiarism;
  final VoidCallback? onOpenNotifications;
  final ValueChanged<int>? onUnreadCount;

  const SupervisorHomeScreen({
    super.key,
    this.onOpenAssignmentRequests,
    this.onOpenMyGroups,
    this.onOpenSubmissions,
    this.onOpenPlagiarism,
    this.onOpenNotifications,
    this.onUnreadCount,
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
      if (mounted) {
        setState(() => _home = home);
        widget.onUnreadCount?.call(home.unreadReplies);
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const AdminPage(child: AdminLoadingView(label: 'Loading your dashboard...'));
    }
    if (_error != null) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _loadHome));
    }

    final home = _home;
    if (home == null) {
      return AdminPage(
        onRefresh: _loadHome,
        child: const AdminEmptyView(
          icon: Icons.dashboard_outlined,
          title: 'Dashboard not available',
          message: 'Dashboard data is not available yet. Pull to refresh once the backend is running.',
        ),
      );
    }

    final auth = context.watch<AuthProvider>();
    final displayName = home.supervisorName.isNotEmpty
        ? home.supervisorName
        : (auth.currentUser ?? 'Supervisor');

    if (isCompact(context)) {
      return AdminPage(
        onRefresh: _loadHome,
        child: _buildMobileHome(home, displayName),
      );
    }

    return AdminPage(
      onRefresh: _loadHome,
      child: _buildDesktopHome(home, displayName),
    );
  }

  Widget _buildMobileHome(SupervisorHomeModel home, String displayName) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Hi, $displayName',
          style: const TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: Colors.white,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 4),
        Text(
          'Your pending work',
          style: TextStyle(fontSize: 13, color: Colors.white.withOpacity(0.55)),
        ),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: _CompactStatTile(
                label: 'Requests',
                value: '${home.pendingAssignmentRequests}',
                icon: Icons.assignment_ind_rounded,
                color: AdminColors.primary,
                onTap: widget.onOpenAssignmentRequests,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _CompactStatTile(
                label: 'To review',
                value: '${home.documentsToReview}',
                icon: Icons.description_outlined,
                color: AdminColors.warning,
                onTap: widget.onOpenSubmissions,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: _CompactStatTile(
                label: 'Alerts',
                value: '${home.unreadReplies}',
                icon: Icons.notifications_outlined,
                color: AdminColors.accent,
                onTap: widget.onOpenNotifications,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _CompactStatTile(
                label: 'Groups',
                value: '${home.groups.length}',
                icon: Icons.groups_rounded,
                color: AdminColors.success,
                onTap: widget.onOpenMyGroups,
              ),
            ),
          ],
        ),
        const SizedBox(height: 24),
        const AdminSectionLabel(label: 'Groups'),
        const SizedBox(height: 12),
        if (home.groups.isEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: adminCardDecoration(),
            child: Text(
              'No accepted groups yet. New requests appear under Requests.',
              style: TextStyle(color: Colors.white.withOpacity(0.6), height: 1.4, fontSize: 13),
            ),
          )
        else
          ...home.groups.take(6).map(
                (group) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: InkWell(
                    onTap: widget.onOpenMyGroups,
                    borderRadius: BorderRadius.circular(adminCardRadius),
                    child: _MobileGroupCard(group: group),
                  ),
                ),
              ),
        if (home.groups.length > 6) ...[
          const SizedBox(height: 4),
          TextButton(
            onPressed: widget.onOpenMyGroups,
            child: const Text('View all groups'),
          ),
        ],
      ],
    );
  }

  Widget _buildDesktopHome(SupervisorHomeModel home, String displayName) {
    return Column(
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
              _TappableStatCard(
                onTap: widget.onOpenNotifications,
                child: AdminStatCard(
                  title: 'Notifications',
                  value: '${home.unreadReplies}',
                  icon: Icons.mark_email_unread_outlined,
                  accent: AdminColors.accent,
                ),
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
        const SizedBox(height: 30),
        AdminSectionLabel(
          label: 'Accepted Groups',
          trailing: widget.onOpenMyGroups == null
              ? null
              : TextButton.icon(
                  onPressed: widget.onOpenMyGroups,
                  icon: const Icon(Icons.arrow_forward_rounded, size: 15),
                  label: const Text('View My Groups'),
                  style: TextButton.styleFrom(
                    foregroundColor: AdminColors.accentBright,
                    textStyle: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600),
                  ),
                ),
        ),
        const SizedBox(height: 14),
        if (home.groups.isEmpty)
          AdminSectionCard(
            title: 'No groups yet',
            icon: Icons.groups_outlined,
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
                borderRadius: BorderRadius.circular(adminCardRadius),
                child: _SupervisorGroupProgressCard(group: group),
              ),
            ),
          ),
      ],
    );
  }
}

class _CompactStatTile extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;
  final VoidCallback? onTap;

  const _CompactStatTile({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(adminTileRadius + 2),
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AdminColors.card,
            borderRadius: BorderRadius.circular(adminTileRadius + 2),
            border: Border.all(color: color.withOpacity(0.3)),
          ),
          child: Row(
            children: [
              AdminIconBadge(icon: icon, color: color, size: 17, padding: 8),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      value,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      label,
                      style: TextStyle(
                        fontSize: 11,
                        color: Colors.white.withOpacity(0.55),
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MobileGroupCard extends StatelessWidget {
  final SupervisorGroupSummary group;

  const _MobileGroupCard({required this.group});

  @override
  Widget build(BuildContext context) {
    final progress = (group.progress / 100.0).clamp(0.0, 1.0);

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: adminCardDecoration(radius: adminCardRadius, glow: false),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  group.title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(width: 8),
              AdminPill(
                label: '${group.progress.round()}%',
                color: AdminColors.accentBright,
              ),
            ],
          ),
          if (group.projectTitle.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              group.projectTitle,
              style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.5)),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ],
          const SizedBox(height: 12),
          AdminProgressBar(value: progress, height: 6),
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
        borderRadius: BorderRadius.circular(adminCardRadius),
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
              const AdminIconBadge(icon: Icons.groups_rounded, size: 20),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      group.title,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
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
              AdminPill(label: percentLabel, color: AdminColors.accentBright),
            ],
          ),
          const SizedBox(height: 16),
          AdminProgressBar(value: progress),
        ],
      ),
    );
  }
}
