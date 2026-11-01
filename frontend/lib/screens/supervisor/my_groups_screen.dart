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

  Future<void> _openGroup(SupervisorGroupSummary group) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => GroupDetailScreen(
          groupId: group.id,
          groupTitle: group.title,
        ),
      ),
    );
    if (mounted) _loadGroups();
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
          if (_groups.isNotEmpty && !_loading) ...[
            _StatsStrip(groups: _groups),
            const SizedBox(height: 22),
          ],
          Row(
            children: [
              Expanded(
                child: Wrap(
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
              ),
              const SizedBox(width: 12),
              Text(
                _groups.isEmpty
                    ? 'No groups'
                    : '${_groups.length} group${_groups.length == 1 ? '' : 's'}',
                style: TextStyle(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.3,
                  color: Colors.white.withOpacity(0.5),
                ),
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
            LayoutBuilder(
              builder: (context, constraints) {
                const gap = 16.0;
                final columns = constraints.maxWidth >= 900 ? 2 : 1;
                final itemWidth =
                    (constraints.maxWidth - gap * (columns - 1)) / columns;
                return Wrap(
                  spacing: gap,
                  runSpacing: gap,
                  children: [
                    for (final group in _groups)
                      SizedBox(
                        width: itemWidth,
                        child: _MyGroupCard(
                          group: group,
                          onOpen: () => _openGroup(group),
                          onDiscard: () => _discardGroup(group),
                        ),
                      ),
                  ],
                );
              },
            ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Summary strip
// ---------------------------------------------------------------------------

class _StatsStrip extends StatelessWidget {
  final List<SupervisorGroupSummary> groups;

  const _StatsStrip({required this.groups});

  @override
  Widget build(BuildContext context) {
    final total = groups.length;
    final behind = groups.where((g) => g.isBehind).length;
    final onTrack = total - behind;
    final avg = total == 0
        ? 0
        : (groups.fold<double>(0, (sum, g) => sum + g.progress.toDouble()) / total)
            .round();

    return LayoutBuilder(
      builder: (context, constraints) {
        const gap = 12.0;
        final columns = constraints.maxWidth >= 720 ? 4 : 2;
        final width = (constraints.maxWidth - gap * (columns - 1)) / columns;
        Widget tile(IconData icon, String value, String label, Color color) {
          return SizedBox(
            width: width,
            child: _StatTile(icon: icon, value: value, label: label, color: color),
          );
        }

        return Wrap(
          spacing: gap,
          runSpacing: gap,
          children: [
            tile(Icons.groups_rounded, '$total', 'Total groups', AdminColors.primary),
            tile(Icons.trending_up_rounded, '$onTrack', 'On track', const Color(0xFF34D399)),
            tile(Icons.warning_amber_rounded, '$behind', 'Behind', AdminColors.danger),
            tile(Icons.speed_rounded, '$avg%', 'Avg. progress', AdminColors.accentBright),
          ],
        );
      },
    );
  }
}

class _StatTile extends StatelessWidget {
  final IconData icon;
  final String value;
  final String label;
  final Color color;

  const _StatTile({
    required this.icon,
    required this.value,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.035),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withOpacity(0.07)),
      ),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: color.withOpacity(0.14),
              borderRadius: BorderRadius.circular(11),
            ),
            child: Icon(icon, size: 19, color: color),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  value,
                  style: const TextStyle(
                    fontSize: 19,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                    height: 1.1,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.white.withOpacity(0.55),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Group card
// ---------------------------------------------------------------------------

class _MyGroupCard extends StatefulWidget {
  final SupervisorGroupSummary group;
  final VoidCallback onOpen;
  final VoidCallback onDiscard;

  const _MyGroupCard({
    required this.group,
    required this.onOpen,
    required this.onDiscard,
  });

  @override
  State<_MyGroupCard> createState() => _MyGroupCardState();
}

class _MyGroupCardState extends State<_MyGroupCard> {
  bool _hover = false;

  /// Returns a human friendly deadline hint, or null if the date can't be parsed.
  String? _relativeDeadline(String raw) {
    final parsed = DateTime.tryParse(raw);
    if (parsed == null) return null;
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final due = DateTime(parsed.year, parsed.month, parsed.day);
    final days = due.difference(today).inDays;
    if (days < 0) return 'Overdue by ${-days}d';
    if (days == 0) return 'Due today';
    if (days == 1) return 'Due tomorrow';
    return '$days days left';
  }

  @override
  Widget build(BuildContext context) {
    final group = widget.group;
    final behind = group.isBehind;
    final accent = behind ? AdminColors.danger : AdminColors.primary;
    final progress = (group.progress / 100.0).clamp(0.0, 1.0).toDouble();
    final hasDeadline = group.deadlineDate.isNotEmpty;
    final deadlineLabel = hasDeadline ? group.deadlineDate : 'No deadline set';
    final relative = hasDeadline ? _relativeDeadline(group.deadlineDate) : null;
    final overdue = relative != null && relative.startsWith('Overdue');
    final showSubtitle = group.projectTitle.isNotEmpty &&
        group.projectTitle.trim().toLowerCase() != group.title.trim().toLowerCase();
    final radius = BorderRadius.circular(adminCardRadius);
    final initial = group.title.trim().isEmpty
        ? '?'
        : group.title.trim()[0].toUpperCase();

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        curve: Curves.easeOut,
        transform: Matrix4.translationValues(0, _hover ? -3 : 0, 0),
        decoration: BoxDecoration(
          borderRadius: radius,
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              AdminColors.card,
              Color.alphaBlend(accent.withOpacity(behind ? 0.12 : 0.07), AdminColors.card),
            ],
          ),
          border: Border.all(
            color: behind
                ? AdminColors.danger.withOpacity(_hover ? 0.85 : 0.5)
                : (_hover
                    ? AdminColors.primary.withOpacity(0.7)
                    : Colors.white.withOpacity(0.09)),
          ),
          boxShadow: [
            BoxShadow(
              color: accent.withOpacity(_hover ? 0.22 : 0.08),
              blurRadius: _hover ? 28 : 16,
              offset: const Offset(0, 10),
            ),
          ],
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            borderRadius: radius,
            onTap: widget.onOpen,
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // ---- Header ----
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 46,
                        height: 46,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(14),
                          gradient: LinearGradient(
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                            colors: [accent, accent.withOpacity(0.55)],
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: accent.withOpacity(0.35),
                              blurRadius: 12,
                              offset: const Offset(0, 4),
                            ),
                          ],
                        ),
                        child: Text(
                          initial,
                          style: const TextStyle(
                            fontSize: 19,
                            fontWeight: FontWeight.w800,
                            color: Colors.white,
                          ),
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                group.title,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  fontSize: 16.5,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                  letterSpacing: 0.1,
                                ),
                              ),
                              if (showSubtitle) ...[
                                const SizedBox(height: 4),
                                Text(
                                  group.projectTitle,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(
                                    fontSize: 12.5,
                                    color: Colors.white.withOpacity(0.55),
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      _StatusChip(behind: behind),
                      SizedBox(
                        width: 32,
                        height: 32,
                        child: PopupMenuButton<String>(
                          tooltip: 'Group actions',
                          padding: EdgeInsets.zero,
                          color: AdminColors.card,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(adminTileRadius),
                            side: const BorderSide(color: AdminColors.borderStrong),
                          ),
                          onSelected: (value) {
                            if (value == 'discard') widget.onDiscard();
                          },
                          itemBuilder: (context) => const [
                            PopupMenuItem(
                              value: 'discard',
                              child: Tr('Discard group'),
                            ),
                          ],
                          icon: Icon(
                            Icons.more_vert_rounded,
                            size: 20,
                            color: Colors.white.withOpacity(0.6),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 18),
                  Divider(height: 1, color: Colors.white.withOpacity(0.07)),
                  const SizedBox(height: 16),

                  // ---- Info rows ----
                  _InfoRow(
                    icon: Icons.people_alt_rounded,
                    label: 'Members',
                    value: group.membersLabel,
                  ),
                  const SizedBox(height: 12),
                  _InfoRow(
                    icon: Icons.event_rounded,
                    label: 'Deadline',
                    value: deadlineLabel,
                    iconColor: overdue ? AdminColors.danger : null,
                    trailing: relative == null
                        ? null
                        : _RelativeBadge(label: relative, danger: overdue || behind),
                  ),
                  const SizedBox(height: 20),

                  // ---- Progress ----
                  Row(
                    children: [
                      Text(
                        'Progress',
                        style: TextStyle(
                          fontSize: 12.5,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 0.3,
                          color: Colors.white.withOpacity(0.6),
                        ),
                      ),
                      const Spacer(),
                      Text(
                        '${group.progress.round()}%',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w800,
                          color: behind ? AdminColors.danger : AdminColors.accentBright,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  _GradientProgressBar(
                    value: progress,
                    colors: behind
                        ? [AdminColors.danger, const Color(0xFFFF8A80)]
                        : [AdminColors.primary, AdminColors.accentBright],
                  ),
                  const SizedBox(height: 16),

                  // ---- Footer ----
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      AnimatedDefaultTextStyle(
                        duration: const Duration(milliseconds: 180),
                        style: TextStyle(
                          fontSize: 12.5,
                          fontWeight: FontWeight.w600,
                          color: Colors.white.withOpacity(_hover ? 0.95 : 0.55),
                        ),
                        child: const Text('View details'),
                      ),
                      const SizedBox(width: 4),
                      AnimatedSlide(
                        duration: const Duration(milliseconds: 180),
                        offset: Offset(_hover ? 0.25 : 0, 0),
                        child: Icon(
                          Icons.arrow_forward_rounded,
                          size: 16,
                          color: Colors.white.withOpacity(_hover ? 0.95 : 0.55),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Small building blocks
// ---------------------------------------------------------------------------

class _StatusChip extends StatelessWidget {
  final bool behind;

  const _StatusChip({required this.behind});

  @override
  Widget build(BuildContext context) {
    final color = behind ? AdminColors.danger : const Color(0xFF34D399);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withOpacity(0.14),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(
            behind ? 'Behind' : 'On track',
            style: TextStyle(
              fontSize: 11.5,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color? iconColor;
  final Widget? trailing;

  const _InfoRow({
    required this.icon,
    required this.label,
    required this.value,
    this.iconColor,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 30,
          height: 30,
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.06),
            borderRadius: BorderRadius.circular(9),
          ),
          child: Icon(icon, size: 16, color: iconColor ?? Colors.white.withOpacity(0.6)),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: TextStyle(
                  fontSize: 11,
                  letterSpacing: 0.4,
                  color: Colors.white.withOpacity(0.45),
                ),
              ),
              const SizedBox(height: 2),
              Text(
                value,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 13.5,
                  fontWeight: FontWeight.w600,
                  color: Colors.white.withOpacity(0.9),
                  height: 1.3,
                ),
              ),
            ],
          ),
        ),
        if (trailing != null) ...[
          const SizedBox(width: 8),
          trailing!,
        ],
      ],
    );
  }
}

class _RelativeBadge extends StatelessWidget {
  final String label;
  final bool danger;

  const _RelativeBadge({required this.label, required this.danger});

  @override
  Widget build(BuildContext context) {
    final color = danger ? AdminColors.danger : Colors.white;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(danger ? 0.14 : 0.07),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11.5,
          fontWeight: FontWeight.w600,
          color: danger ? AdminColors.danger : Colors.white.withOpacity(0.7),
        ),
      ),
    );
  }
}

class _GradientProgressBar extends StatelessWidget {
  final double value;
  final List<Color> colors;

  const _GradientProgressBar({required this.value, required this.colors});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(999),
      child: Container(
        height: 8,
        color: Colors.white.withOpacity(0.08),
        alignment: Alignment.centerLeft,
        child: LayoutBuilder(
          builder: (context, constraints) {
            // Keep a small visible nub so 0% still reads as a bar, not an empty hole.
            final fill = value <= 0 ? 0.0 : (constraints.maxWidth * value).clamp(8.0, constraints.maxWidth);
            return TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: fill),
              duration: const Duration(milliseconds: 600),
              curve: Curves.easeOutCubic,
              builder: (context, w, _) => Container(
                width: w,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(999),
                  gradient: LinearGradient(colors: colors),
                  boxShadow: [
                    BoxShadow(
                      color: colors.first.withOpacity(0.5),
                      blurRadius: 8,
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}