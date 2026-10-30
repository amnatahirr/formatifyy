import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/dev_user_config.dart';
import '../providers/auth_provider.dart';
import '../screens/admin/analytics_screen.dart';
import '../screens/admin/deadlines_screen.dart';
import '../screens/admin/semester_deadlines_screen.dart';
import '../screens/admin/department_manager_screen.dart';
import '../screens/admin/supervisor_management_screen.dart';
import '../screens/admin/template_manager_screen.dart';
import '../screens/admin_overview_screen.dart';
import '../screens/admin_settings_screen.dart';
import '../screens/admin_universities_screen.dart';
import '../screens/admin_users_screen.dart';
import '../screens/admin_verify_screen.dart';
import '../services/super_admin_api_service.dart';
import '../utils/logout_confirm.dart';
import '../utils/responsive.dart';
import '../theme/app_theme.dart';
import '../widgets/admin/admin_ui.dart';

import '../widgets/tr.dart';

class _AdminNavItem {
  final int id;
  final String label;
  final String shortLabel;
  final IconData icon;
  final bool requiresFyp;

  const _AdminNavItem({
    required this.id,
    required this.label,
    required this.shortLabel,
    required this.icon,
    this.requiresFyp = false,
  });
}

/// Visual grouping of sidebar items (presentation only, ids are unchanged).
class _NavGroup {
  final String title;
  final List<int> ids;

  const _NavGroup(this.title, this.ids);
}

class AdminDashboard extends StatefulWidget {
  const AdminDashboard({super.key});

  @override
  State<AdminDashboard> createState() => _AdminDashboardState();
}

class _AdminDashboardState extends State<AdminDashboard> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  int _selectedId = 0;
  bool _orgLoaded = false;

  static const _allItems = <_AdminNavItem>[
    _AdminNavItem(
      id: 0,
      label: 'Overview',
      shortLabel: 'Home',
      icon: Icons.dashboard_rounded,
    ),
    _AdminNavItem(
      id: 1,
      label: 'Department Manager',
      shortLabel: 'Depts',
      icon: Icons.apartment_rounded,
    ),
    _AdminNavItem(
      id: 2,
      label: 'Supervisors',
      shortLabel: 'Supers',
      icon: Icons.supervisor_account_rounded,
      requiresFyp: true,
    ),
    _AdminNavItem(
      id: 3,
      label: 'Template Manager',
      shortLabel: 'Templates',
      icon: Icons.layers_rounded,
    ),
    _AdminNavItem(
      id: 4,
      label: 'Deadlines',
      shortLabel: 'Dates',
      icon: Icons.event_note_rounded,
      requiresFyp: true,
    ),
    _AdminNavItem(
      id: 5,
      label: 'Semester Deadlines',
      shortLabel: 'Sem',
      icon: Icons.event_available_rounded,
      requiresFyp: true,
    ),
    _AdminNavItem(
      id: 6,
      label: 'Users',
      shortLabel: 'Users',
      icon: Icons.people_rounded,
    ),
    _AdminNavItem(
      id: 7,
      label: 'Universities',
      shortLabel: 'Unis',
      icon: Icons.school_rounded,
      requiresFyp: true,
    ),
    _AdminNavItem(
      id: 8,
      label: 'Analytics',
      shortLabel: 'Stats',
      icon: Icons.bar_chart_rounded,
    ),
    _AdminNavItem(
      id: 9,
      label: 'Verify Files',
      shortLabel: 'Verify',
      icon: Icons.fact_check_rounded,
    ),
    _AdminNavItem(
      id: 10,
      label: 'Settings',
      shortLabel: 'More',
      icon: Icons.settings_rounded,
    ),
  ];

  /// Sidebar sections (visual only).
  static const _navGroups = <_NavGroup>[
    _NavGroup('WORKSPACE', [0, 8]),
    _NavGroup('ORGANIZATION', [1, 2, 6, 7]),
    _NavGroup('DOCUMENTS', [3, 4, 5, 9]),
    _NavGroup('SYSTEM', [10]),
  ];

  /// Primary destinations shown in the mobile bottom bar.
  static const _mobilePrimaryIds = <int>[0, 1, 3, 6, 10];

  List<_AdminNavItem> get _visibleItems => _allItems
      .where((item) => !item.requiresFyp || DevUserConfig.hasFypModule)
      .toList();

  List<_AdminNavItem> get _mobilePrimaryItems {
    final visible = _visibleItems;
    return _mobilePrimaryIds
        .map((id) {
          for (final item in visible) {
            if (item.id == id) return item;
          }
          return null;
        })
        .whereType<_AdminNavItem>()
        .toList();
  }

  @override
  void initState() {
    super.initState();
    _refreshOrgFlags();
  }

  Future<void> _refreshOrgFlags() async {
    try {
      final info = await SuperAdminApiService().fetchOrgInfo();
      final expected = DevUserConfig.orgCode.trim().toUpperCase();
      final got = (info['org_code'] ?? '').toString().trim().toUpperCase();
      if (expected.isEmpty || got.isEmpty || got == expected) {
        DevUserConfig.applyOrgInfo(info);
      }
    } catch (_) {
      // Keep local DevUserConfig.modulesCsv
    }
    if (!mounted) return;
    setState(() {
      _orgLoaded = true;
      final visible = _visibleItems;
      if (!visible.any((i) => i.id == _selectedId)) {
        _selectedId = visible.isEmpty ? 0 : visible.first.id;
      }
    });
  }

  String get _selectedLabel {
    for (final item in _allItems) {
      if (item.id == _selectedId) return item.label;
    }
    return 'Admin';
  }

  String get _selectedSubtitle {
    switch (_selectedId) {
      case 0:
        return DevUserConfig.hasFypModule
            ? 'Live metrics and organization overview'
            : 'Live metrics for your organization';
      case 1:
        return 'Create and manage departments';
      case 2:
        return 'Manage supervisors by department';
      case 3:
        return 'Department templates and formatting rules';
      case 4:
        return 'Department submission deadlines';
      case 5:
        return 'Semester 6 and 7 submission cutoffs';
      case 6:
        return DevUserConfig.hasFypModule
            ? 'Accounts, supervisors, and students'
            : 'Organization members and admins';
      case 7:
        return 'Registered institutions';
      case 8:
        return 'Usage and compliance trends';
      case 9:
        return 'Upload a file and verify against a template';
      case 10:
        return 'System configuration';
      default:
        return DevUserConfig.hasFypModule
            ? 'Modules: ${DevUserConfig.modulesLabel}'
            : 'Core module · document formatting';
    }
  }

  String _todayLabel() {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    final n = DateTime.now();
    return '${days[n.weekday - 1]}, ${n.day} ${months[n.month - 1]} ${n.year}';
  }

  void _selectNav(_AdminNavItem item, {bool closeDrawer = false}) {
    setState(() => _selectedId = item.id);
    if (closeDrawer) {
      Navigator.of(context).maybePop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = _visibleItems;
    final compact = isCompact(context);

    return Scaffold(
      key: _scaffoldKey,
      backgroundColor: Colors.transparent,
      drawer: compact ? _buildDrawer(items) : null,
      body: AppPalette.dark.ambientGlowBackdrop(
        child: compact
            ? SafeArea(
                child: Column(
                  children: [
                    _buildTopBar(compact: true),
                    Expanded(child: _buildContent()),
                  ],
                ),
              )
            : Row(
                children: [
                  _buildSidebar(items),
                  Expanded(
                    child: Column(
                      children: [
                        _buildTopBar(compact: false),
                        Expanded(child: _buildContent()),
                      ],
                    ),
                  ),
                ],
              ),
      ),
      bottomNavigationBar: compact ? _buildMobileBottomNav() : null,
    );
  }

  // -------------------------------------------------------------------------
  // Shared pieces
  // -------------------------------------------------------------------------

  Color get _sidebarColor =>
      Color.alphaBlend(Colors.black.withOpacity(0.16), AdminColors.surface);

  Widget _buildBrandHeader() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(20, 22, 20, 18),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(color: Colors.white.withOpacity(0.06)),
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(13),
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [AdminColors.primary, AdminColors.accent],
              ),
              boxShadow: [
                BoxShadow(
                  color: AdminColors.primary.withOpacity(0.4),
                  blurRadius: 14,
                  offset: const Offset(0, 5),
                ),
              ],
            ),
            child: const Icon(
              Icons.shield_rounded,
              color: Colors.white,
              size: 22,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Tr(
                  'Admin Panel',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                    letterSpacing: 0.2,
                  ),
                ),
                const SizedBox(height: 5),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.07),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    DevUserConfig.orgCode,
                    style: TextStyle(
                      fontSize: 10.5,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.6,
                      color: Colors.white.withOpacity(0.65),
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// Grouped navigation list used by both the sidebar and the mobile drawer.
  Widget _buildNavList(List<_AdminNavItem> items, {bool closeDrawer = false}) {
    final children = <Widget>[];
    for (final group in _navGroups) {
      final groupItems = <_AdminNavItem>[];
      for (final id in group.ids) {
        for (final item in items) {
          if (item.id == id) groupItems.add(item);
        }
      }
      if (groupItems.isEmpty) continue;
      children.add(
        Padding(
          padding: const EdgeInsets.fromLTRB(22, 16, 20, 6),
          child: Text(
            group.title,
            style: TextStyle(
              fontSize: 10.5,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.3,
              color: Colors.white.withOpacity(0.35),
            ),
          ),
        ),
      );
      for (final item in groupItems) {
        children.add(
          _NavTile(
            item: item,
            selected: _selectedId == item.id,
            onTap: () => _selectNav(item, closeDrawer: closeDrawer),
          ),
        );
      }
    }
    return ListView(
      padding: const EdgeInsets.only(bottom: 12),
      children: children,
    );
  }

  Widget _buildUserCard() {
    return Consumer<AuthProvider>(
      builder: (context, auth, _) {
        final displayName = auth.currentUser?.trim().isNotEmpty == true
            ? auth.currentUser!
            : 'Admin';
        final subtitle = auth.userEmail?.trim().isNotEmpty == true
            ? auth.userEmail!
            : (auth.userRole ?? 'Administrator');
        final initial = displayName.trim().isEmpty
            ? 'A'
            : displayName.trim()[0].toUpperCase();
        return GestureDetector(
          onLongPress: () => confirmAndLogout(context),
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.04),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: Colors.white.withOpacity(0.07)),
            ),
            child: Row(
              children: [
                Container(
                  width: 38,
                  height: 38,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [AdminColors.primary, AdminColors.accent],
                    ),
                    borderRadius: BorderRadius.circular(11),
                  ),
                  child: Text(
                    initial,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        displayName,
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Text(
                        subtitle,
                        style: TextStyle(
                          fontSize: 11,
                          color: Colors.white.withOpacity(0.5),
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
        );
      },
    );
  }

  // -------------------------------------------------------------------------
  // Drawer / sidebar
  // -------------------------------------------------------------------------

  Widget _buildDrawer(List<_AdminNavItem> items) {
    return Drawer(
      backgroundColor: _sidebarColor,
      child: SafeArea(
        child: Column(
          children: [
            _buildBrandHeader(),
            Expanded(child: _buildNavList(items, closeDrawer: true)),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
              child: OutlinedButton.icon(
                onPressed: () {
                  Navigator.of(context).maybePop();
                  confirmAndLogout(context);
                },
                icon: const Icon(Icons.logout_rounded, size: 18),
                label: const Tr('Logout'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white70,
                  side: BorderSide(color: Colors.white.withOpacity(0.14)),
                  minimumSize: const Size(double.infinity, 46),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSidebar(List<_AdminNavItem> items) {
    return Container(
      width: 262,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            _sidebarColor,
            Color.alphaBlend(Colors.black.withOpacity(0.12), _sidebarColor),
          ],
        ),
        border: Border(
          right: BorderSide(color: Colors.white.withOpacity(0.07)),
        ),
      ),
      child: Column(
        children: [
          _buildBrandHeader(),
          Expanded(child: _buildNavList(items)),
          if (!_orgLoaded)
            Padding(
              padding: const EdgeInsets.fromLTRB(22, 4, 22, 12),
              child: Row(
                children: [
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: AdminColors.primary,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    'Syncing organization...',
                    style: TextStyle(
                      fontSize: 11.5,
                      color: Colors.white.withOpacity(0.45),
                    ),
                  ),
                ],
              ),
            ),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              border: Border(
                top: BorderSide(color: Colors.white.withOpacity(0.06)),
              ),
            ),
            child: _buildUserCard(),
          ),
        ],
      ),
    );
  }

  // -------------------------------------------------------------------------
  // Mobile bottom nav
  // -------------------------------------------------------------------------

  Widget _buildMobileBottomNav() {
    final items = _mobilePrimaryItems;
    final selectedNav = items.indexWhere((item) => item.id == _selectedId);
    final showMoreSelected = selectedNav < 0;

    return Container(
      decoration: BoxDecoration(
        color: _sidebarColor,
        border: Border(
          top: BorderSide(color: Colors.white.withOpacity(0.08)),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.35),
            blurRadius: 20,
            offset: const Offset(0, -6),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 66,
          child: Row(
            children: [
              for (final item in items)
                Expanded(
                  child: _buildMobileNavButton(
                    icon: item.icon,
                    label: item.shortLabel,
                    selected: item.id == _selectedId,
                    onTap: () => _selectNav(item),
                  ),
                ),
              Expanded(
                child: _buildMobileNavButton(
                  icon: Icons.menu_rounded,
                  label: 'Menu',
                  selected: showMoreSelected,
                  onTap: () => _scaffoldKey.currentState?.openDrawer(),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMobileNavButton({
    required IconData icon,
    required String label,
    required bool selected,
    required VoidCallback onTap,
  }) {
    final color =
        selected ? AdminColors.primary : Colors.white.withOpacity(0.45);

    return InkWell(
      onTap: onTap,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            curve: Curves.easeOut,
            width: 46,
            height: 28,
            decoration: BoxDecoration(
              color: selected
                  ? AdminColors.primary.withOpacity(0.18)
                  : Colors.transparent,
              borderRadius: BorderRadius.circular(999),
            ),
            child: Icon(icon, size: 21, color: color),
          ),
          const SizedBox(height: 3),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: 10,
              fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  // -------------------------------------------------------------------------
  // Top bar
  // -------------------------------------------------------------------------

  Widget _buildTopBar({required bool compact}) {
    return Container(
      height: compact ? 58 : 76,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Color.alphaBlend(Colors.white.withOpacity(0.02), AdminColors.surface),
            AdminColors.surface,
          ],
        ),
        border: Border(
          bottom: BorderSide(color: Colors.white.withOpacity(0.07)),
        ),
      ),
      padding: EdgeInsets.symmetric(horizontal: compact ? 8 : 28),
      child: Row(
        children: [
          if (compact)
            IconButton(
              icon: const Icon(Icons.menu_rounded),
              color: Colors.white,
              tooltip: 'Menu',
              onPressed: () => _scaffoldKey.currentState?.openDrawer(),
            ),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _selectedLabel,
                  style: TextStyle(
                    fontSize: compact ? 17 : 24,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                    letterSpacing: 0.1,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                if (!compact) ...[
                  const SizedBox(height: 2),
                  Text(
                    _selectedSubtitle,
                    style: TextStyle(
                      fontSize: 12.5,
                      color: Colors.white.withOpacity(0.55),
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ],
            ),
          ),
          if (!compact) ...[
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.05),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: Colors.white.withOpacity(0.08)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.calendar_today_rounded,
                    size: 14,
                    color: Colors.white.withOpacity(0.55),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    _todayLabel(),
                    style: TextStyle(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                      color: Colors.white.withOpacity(0.75),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
          ],
          Tooltip(
            message: 'Logout',
            child: InkWell(
              borderRadius: BorderRadius.circular(12),
              onTap: () => confirmAndLogout(context),
              child: Container(
                padding: EdgeInsets.symmetric(
                  horizontal: compact ? 10 : 14,
                  vertical: 10,
                ),
                decoration: BoxDecoration(
                  color: AdminColors.primary.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: AdminColors.primary.withOpacity(0.35),
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.logout_rounded,
                      size: 18,
                      color: AdminColors.primary,
                    ),
                    if (!compact) ...[
                      const SizedBox(width: 8),
                      const Text(
                        'Logout',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          color: AdminColors.primary,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
          if (compact) const SizedBox(width: 4),
        ],
      ),
    );
  }

  Widget _buildContent() {
    switch (_selectedId) {
      case 0:
        return AdminOverviewScreen(onOrgUpdated: () {
          if (mounted) setState(() {});
        });
      case 1:
        return const DepartmentManagerScreen(embedded: true);
      case 2:
        return const SupervisorManagementScreen(embedded: true);
      case 3:
        return const TemplateManagerScreen(embedded: true);
      case 4:
        return const DeadlinesScreen(embedded: true);
      case 5:
        return const SemesterDeadlinesScreen(embedded: true);
      case 6:
        return const AdminUsersScreen();
      case 7:
        return const AdminUniversitiesScreen();
      case 8:
        return const AnalyticsScreen(embedded: true);
      case 9:
        return const AdminVerifyScreen();
      case 10:
        return const AdminSettingsScreen();
      default:
        return const SizedBox();
    }
  }
}

// ---------------------------------------------------------------------------
// Sidebar / drawer tile with hover + active indicator
// ---------------------------------------------------------------------------

class _NavTile extends StatefulWidget {
  final _AdminNavItem item;
  final bool selected;
  final VoidCallback onTap;

  const _NavTile({
    required this.item,
    required this.selected,
    required this.onTap,
  });

  @override
  State<_NavTile> createState() => _NavTileState();
}

class _NavTileState extends State<_NavTile> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final selected = widget.selected;
    final iconColor = selected
        ? AdminColors.primary
        : Colors.white.withOpacity(_hover ? 0.9 : 0.6);
    final textColor = selected
        ? Colors.white
        : Colors.white.withOpacity(_hover ? 0.95 : 0.7);

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          curve: Curves.easeOut,
          margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
          decoration: BoxDecoration(
            gradient: selected
                ? LinearGradient(
                    colors: [
                      AdminColors.primary.withOpacity(0.22),
                      AdminColors.primary.withOpacity(0.06),
                    ],
                  )
                : null,
            color: !selected && _hover ? Colors.white.withOpacity(0.045) : null,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: selected
                  ? AdminColors.primary.withOpacity(0.4)
                  : Colors.transparent,
            ),
          ),
          child: Row(
            children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 180),
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: selected
                      ? AdminColors.primary.withOpacity(0.18)
                      : Colors.white.withOpacity(_hover ? 0.07 : 0.04),
                  borderRadius: BorderRadius.circular(9),
                ),
                child: Icon(widget.item.icon, size: 18, color: iconColor),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  widget.item.label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 13.5,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                    color: textColor,
                  ),
                ),
              ),
              AnimatedContainer(
                duration: const Duration(milliseconds: 180),
                width: 4,
                height: selected ? 18 : 0,
                decoration: BoxDecoration(
                  color: AdminColors.primary,
                  borderRadius: BorderRadius.circular(4),
                  boxShadow: selected
                      ? [
                          BoxShadow(
                            color: AdminColors.primary.withOpacity(0.6),
                            blurRadius: 8,
                          ),
                        ]
                      : null,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}