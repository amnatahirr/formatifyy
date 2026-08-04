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
import '../widgets/admin/admin_ui.dart';

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
      backgroundColor: AdminColors.background,
      drawer: compact ? _buildDrawer(items) : null,
      body: compact
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
      bottomNavigationBar: compact ? _buildMobileBottomNav() : null,
    );
  }

  Widget _buildDrawer(List<_AdminNavItem> items) {
    return Drawer(
      backgroundColor: AdminColors.surface,
      child: SafeArea(
        child: Column(
          children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
              decoration: BoxDecoration(
                border: Border(
                  bottom: BorderSide(color: AdminColors.border.withOpacity(0.5)),
                ),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AdminColors.primary.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.shield_rounded,
                      color: AdminColors.primary,
                      size: 20,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Admin Panel',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                        ),
                        Text(
                          DevUserConfig.orgCode,
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
            Expanded(
              child: ListView.builder(
                padding: const EdgeInsets.symmetric(vertical: 12),
                itemCount: items.length,
                itemBuilder: (context, index) {
                  return _buildNavItem(items[index], closeDrawer: true);
                },
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
              child: OutlinedButton.icon(
                onPressed: () {
                  Navigator.of(context).maybePop();
                  confirmAndLogout(context);
                },
                icon: const Icon(Icons.logout_rounded, size: 18),
                label: const Text('Logout'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white70,
                  side: BorderSide(color: AdminColors.border.withOpacity(0.8)),
                  minimumSize: const Size(double.infinity, 44),
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
      width: 250,
      decoration: BoxDecoration(
        color: AdminColors.surface,
        border: Border(
          right: BorderSide(color: AdminColors.border.withOpacity(0.5)),
        ),
      ),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              border: Border(
                bottom: BorderSide(color: AdminColors.border.withOpacity(0.5)),
              ),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AdminColors.primary.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.shield_rounded,
                    color: AdminColors.primary,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Admin Panel',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                      ),
                      Text(
                        DevUserConfig.orgCode,
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
          Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: ListView.builder(
                itemCount: items.length,
                itemBuilder: (context, index) {
                  return _buildNavItem(items[index]);
                },
              ),
            ),
          ),
          if (!_orgLoaded)
            const Padding(
              padding: EdgeInsets.all(8),
              child: SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: AdminColors.primary,
                ),
              ),
            ),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              border: Border(
                top: BorderSide(color: AdminColors.border.withOpacity(0.5)),
              ),
            ),
            child: Consumer<AuthProvider>(
              builder: (context, auth, _) {
                final displayName =
                    auth.currentUser?.trim().isNotEmpty == true
                        ? auth.currentUser!
                        : 'Admin';
                final subtitle = auth.userEmail?.trim().isNotEmpty == true
                    ? auth.userEmail!
                    : (auth.userRole ?? 'Administrator');
                return GestureDetector(
                  onLongPress: () => confirmAndLogout(context),
                  child: Row(
                    children: [
                      Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [AdminColors.primary, AdminColors.accent],
                          ),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(
                          Icons.person_rounded,
                          color: Colors.white,
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
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: Colors.white,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            Text(
                              subtitle,
                              style: TextStyle(
                                fontSize: 10,
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
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNavItem(_AdminNavItem item, {bool closeDrawer = false}) {
    final isSelected = _selectedId == item.id;
    return GestureDetector(
      onTap: () => _selectNav(item, closeDrawer: closeDrawer),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        decoration: BoxDecoration(
          color: isSelected
              ? AdminColors.primary.withOpacity(0.15)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
          border: isSelected
              ? Border.all(color: AdminColors.primary.withOpacity(0.35))
              : null,
        ),
        child: Row(
          children: [
            Icon(
              item.icon,
              size: 20,
              color: isSelected
                  ? AdminColors.primary
                  : Colors.white.withOpacity(0.6),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                item.label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                  color: isSelected
                      ? AdminColors.primary
                      : Colors.white.withOpacity(0.7),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMobileBottomNav() {
    final items = _mobilePrimaryItems;
    final selectedNav = items.indexWhere((item) => item.id == _selectedId);
    final showMoreSelected = selectedNav < 0;

    return Container(
      decoration: BoxDecoration(
        color: AdminColors.surface,
        border: Border(
          top: BorderSide(color: AdminColors.border.withOpacity(0.5)),
        ),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 64,
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
          Icon(icon, size: 22, color: color),
          const SizedBox(height: 4),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: 10,
              fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTopBar({required bool compact}) {
    return Container(
      height: compact ? 56 : 72,
      decoration: BoxDecoration(
        color: AdminColors.surface,
        border: Border(
          bottom: BorderSide(color: AdminColors.border.withOpacity(0.5)),
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
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                if (!compact)
                  Text(
                    _selectedSubtitle,
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.white.withOpacity(0.55),
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
              ],
            ),
          ),
          IconButton(
            icon: const Icon(Icons.logout_rounded),
            color: AdminColors.primary,
            tooltip: 'Logout',
            onPressed: () => confirmAndLogout(context),
          ),
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
