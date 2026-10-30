import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../utils/responsive.dart';
import '../../widgets/admin/admin_ui.dart';

import '../../widgets/tr.dart';

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
      return const AdminPage(
          child: AdminLoadingView(label: 'Loading your dashboard...'));
    }
    if (_error != null) {
      return AdminPage(
          child: AdminErrorView(message: _error!, onRetry: _loadHome));
    }

    final home = _home;
    if (home == null) {
      return AdminPage(
        onRefresh: _loadHome,
        child: const AdminEmptyView(
          icon: Icons.dashboard_outlined,
          title: 'Dashboard not available',
          message:
              'Dashboard data is not available yet. Pull to refresh once the backend is running.',
        ),
      );
    }

    final auth = context.watch<AuthProvider>();
    final displayName = home.supervisorName.isNotEmpty
        ? home.supervisorName
        : (auth.currentUser ?? 'Supervisor');
    final compact = isCompact(context);

    return AdminPage(
      onRefresh: _loadHome,
      child: _buildHome(home, displayName, compact),
    );
  }

  // ───────────────────────────── Layout ───────────────────────────────────

  Widget _buildHome(
      SupervisorHomeModel home, String displayName, bool compact) {
    final pending = home.pendingAssignmentRequests;
    final toReview = home.documentsToReview;
    final unread = home.unreadReplies;
    // Only real pending work (notifications are informational, not tasks).
    final needsAttention = pending + toReview;

    final stats = <_StatData>[
      _StatData(
        title: 'Pending requests',
        caption: pending == 0 ? 'All caught up' : 'Awaiting your response',
        value: '$pending',
        icon: Icons.assignment_ind_rounded,
        color: AdminColors.primary,
        onTap: widget.onOpenAssignmentRequests,
      ),
      _StatData(
        title: 'Documents to review',
        caption: toReview == 0 ? 'Nothing to review' : 'Waiting for feedback',
        value: '$toReview',
        icon: Icons.description_outlined,
        color: AdminColors.warning,
        onTap: widget.onOpenSubmissions,
      ),
      _StatData(
        title: 'Notifications',
        caption: unread == 0 ? 'No new replies' : 'Unread replies',
        value: '$unread',
        icon: Icons.mark_email_unread_outlined,
        color: AdminColors.accent,
        onTap: widget.onOpenNotifications,
      ),
      _StatData(
        title: 'Active groups',
        caption: 'Accepted by you',
        value: '${home.groups.length}',
        icon: Icons.groups_rounded,
        color: AdminColors.success,
        onTap: widget.onOpenMyGroups,
      ),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _header(displayName, needsAttention, compact),
        SizedBox(height: compact ? 18 : 24),
        _statGrid(stats, compact),
        if (widget.onOpenPlagiarism != null) ...[
          const SizedBox(height: 14),
          _plagiarismBanner(),
        ],
        SizedBox(height: compact ? 26 : 32),
        AdminSectionLabel(
          label: compact ? 'Groups' : 'Accepted Groups',
          trailing: widget.onOpenMyGroups == null || home.groups.isEmpty
              ? null
              : TextButton.icon(
                  onPressed: widget.onOpenMyGroups,
                  icon: const Icon(Icons.arrow_forward_rounded, size: 15),
                  label: const Tr('View all'),
                  style: TextButton.styleFrom(
                    foregroundColor: AdminColors.accentBright,
                    textStyle: const TextStyle(
                        fontSize: 12.5, fontWeight: FontWeight.w600),
                  ),
                ),
        ),
        const SizedBox(height: 14),
        _groups(home, compact),
      ],
    );
  }

  // ───────────────────────────── Header ───────────────────────────────────

  Widget _header(String name, int needsAttention, bool compact) {
    final ok = needsAttention == 0;
    final color = ok ? AdminColors.success : AdminColors.warning;

    final summary = Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(ok ? Icons.check_circle_outline : Icons.bolt_rounded,
              size: 15, color: color),
          const SizedBox(width: 6),
          Text(
            ok
                ? 'Everything is up to date'
                : '$needsAttention item${needsAttention == 1 ? '' : 's'} need attention',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
        ],
      ),
    );

    final text = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          compact ? 'Hi, $name' : 'Welcome back, $name',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            color: Colors.white,
            fontSize: compact ? 20 : 24,
            fontWeight: FontWeight.w700,
            letterSpacing: -0.3,
          ),
        ),
        const SizedBox(height: 6),
        Tr('Pending work and progress across your accepted groups',
          style: TextStyle(
            fontSize: 13,
            color: Colors.white.withOpacity(0.55),
          ),
        ),
      ],
    );

    if (compact) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [text, const SizedBox(height: 12), summary],
      );
    }
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [Expanded(child: text), const SizedBox(width: 16), summary],
    );
  }

  // ───────────────────────────── Stats ────────────────────────────────────

  Widget _statGrid(List<_StatData> stats, bool compact) {
    return LayoutBuilder(builder: (context, c) {
      const gap = 14.0;
      final cols = compact ? 2 : (c.maxWidth >= 900 ? 4 : 2);
      final w = (c.maxWidth - gap * (cols - 1)) / cols;
      return Wrap(
        spacing: gap,
        runSpacing: gap,
        children: stats
            .map((s) => SizedBox(
                  width: w,
                  child: _StatTile(data: s, compact: compact),
                ))
            .toList(),
      );
    });
  }

  Widget _plagiarismBanner() {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: widget.onOpenPlagiarism,
        borderRadius: BorderRadius.circular(adminCardRadius),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(
            color: AdminColors.card,
            borderRadius: BorderRadius.circular(adminCardRadius),
            border: Border.all(color: AdminColors.danger.withOpacity(0.3)),
          ),
          child: Row(
            children: [
              AdminIconBadge(
                  icon: Icons.policy_rounded,
                  color: AdminColors.danger,
                  size: 18,
                  padding: 9),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Tr('Plagiarism monitor',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Tr('Check similarity scores and matched sources',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.55),
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_rounded,
                  color: Colors.white.withOpacity(0.4)),
            ],
          ),
        ),
      ),
    );
  }

  // ───────────────────────────── Groups ───────────────────────────────────

  Widget _groups(SupervisorHomeModel home, bool compact) {
    if (home.groups.isEmpty) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 34),
        decoration: adminCardDecoration(),
        child: Column(
          children: [
            AdminIconBadge(
                icon: Icons.groups_outlined,
                color: AdminColors.accent,
                size: 24,
                padding: 14),
            const SizedBox(height: 14),
            const Tr('No groups yet',
              style: TextStyle(
                color: Colors.white,
                fontSize: 15,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 6),
            Tr('Accepted groups will appear here with their progress. New requests appear under Requests.',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.white.withOpacity(0.55),
                fontSize: 12.5,
                height: 1.45,
              ),
            ),
          ],
        ),
      );
    }

    final groups = compact ? home.groups.take(6).toList() : home.groups;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LayoutBuilder(builder: (context, c) {
          const gap = 14.0;
          final cols = (!compact && c.maxWidth >= 860) ? 2 : 1;
          final w = (c.maxWidth - gap * (cols - 1)) / cols;
          return Wrap(
            spacing: gap,
            runSpacing: gap,
            children: groups
                .map((g) => SizedBox(
                      width: w,
                      child: _GroupCard(
                        group: g,
                        compact: compact,
                        onTap: widget.onOpenMyGroups,
                      ),
                    ))
                .toList(),
          );
        }),
        if (compact && home.groups.length > 6) ...[
          const SizedBox(height: 8),
          Center(
            child: TextButton(
              onPressed: widget.onOpenMyGroups,
              child: const Tr('View all groups'),
            ),
          ),
        ],
      ],
    );
  }
}

// ───────────────────────────── Widgets ──────────────────────────────────────

class _StatData {
  final String title;
  final String caption;
  final String value;
  final IconData icon;
  final Color color;
  final VoidCallback? onTap;

  const _StatData({
    required this.title,
    required this.caption,
    required this.value,
    required this.icon,
    required this.color,
    this.onTap,
  });
}

class _StatTile extends StatelessWidget {
  final _StatData data;
  final bool compact;

  const _StatTile({required this.data, required this.compact});

  @override
  Widget build(BuildContext context) {
    final radius = BorderRadius.circular(adminCardRadius);
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: data.onTap,
        borderRadius: radius,
        child: Container(
          padding: EdgeInsets.all(compact ? 14 : 18),
          decoration: BoxDecoration(
            color: AdminColors.card,
            borderRadius: radius,
            border: Border.all(color: data.color.withOpacity(0.28)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                children: [
                  AdminIconBadge(
                    icon: data.icon,
                    color: data.color,
                    size: compact ? 17 : 19,
                    padding: compact ? 8 : 10,
                  ),
                  const Spacer(),
                  if (data.onTap != null)
                    Icon(Icons.arrow_outward_rounded,
                        size: 15, color: Colors.white.withOpacity(0.3)),
                ],
              ),
              SizedBox(height: compact ? 12 : 16),
              Text(
                data.value,
                style: TextStyle(
                  color: Colors.white,
                  fontSize: compact ? 24 : 30,
                  fontWeight: FontWeight.w800,
                  height: 1.0,
                ),
              ),
              const SizedBox(height: 6),
              Tr(
                data.title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: Colors.white.withOpacity(0.9),
                  fontSize: compact ? 12 : 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
              if (!compact) ...[
                const SizedBox(height: 2),
                Tr(
                  data.caption,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.45),
                    fontSize: 11.5,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _GroupCard extends StatelessWidget {
  final SupervisorGroupSummary group;
  final bool compact;
  final VoidCallback? onTap;

  const _GroupCard({
    required this.group,
    required this.compact,
    this.onTap,
  });

  Color _progressColor(double pct) {
    if (pct <= 0) return AdminColors.accent; // not started: neutral
    if (pct >= 75) return AdminColors.success;
    if (pct >= 40) return AdminColors.accentBright;
    return AdminColors.warning;
  }

  @override
  Widget build(BuildContext context) {
    final pct = group.progress.toDouble();
    final value = (pct / 100.0).clamp(0.0, 1.0);
    final color = _progressColor(pct);
    final radius = BorderRadius.circular(adminCardRadius);

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: radius,
        child: Container(
          padding: EdgeInsets.all(compact ? 14 : 18),
          decoration: adminCardDecoration(
            radius: adminCardRadius,
            glow: false,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  AdminIconBadge(
                    icon: Icons.groups_rounded,
                    size: compact ? 18 : 20,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          group.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 14.5,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                        ),
                        if (group.projectTitle.isNotEmpty) ...[
                          const SizedBox(height: 3),
                          Text(
                            group.projectTitle,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.white.withOpacity(0.5),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  AdminPill(
                    label: pct <= 0 ? 'Not started' : '${group.progress.round()}%',
                    color: color,
                  ),
                ],
              ),
              if (pct > 0) ...[
                const SizedBox(height: 16),
                Row(
                  children: [
                    Tr('Progress',
                        style: TextStyle(
                            fontSize: 11.5,
                            color: Colors.white.withOpacity(0.5))),
                    const Spacer(),
                    Text('${group.progress.round()}%',
                        style: TextStyle(
                            fontSize: 11.5,
                            color: Colors.white.withOpacity(0.5))),
                  ],
                ),
                const SizedBox(height: 8),
                AdminProgressBar(value: value, height: 6),
              ],
            ],
          ),
        ),
      ),
    );
  }
}