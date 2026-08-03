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
import '../widgets/admin/admin_ui.dart';

class _AdminNavItem {
  final int id;
  final String label;
  final IconData icon;
  final bool requiresFyp;

  const _AdminNavItem({
    required this.id,
    required this.label,
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
  int _selectedId = 0;
  bool _orgLoaded = false;

  static const _allItems = <_AdminNavItem>[
    _AdminNavItem(id: 0, label: 'Overview', icon: Icons.dashboard_rounded),
    _AdminNavItem(
      id: 1,
      label: 'Department Manager',
      icon: Icons.apartment_rounded,
    ),
    _AdminNavItem(
      id: 2,
      label: 'Supervisors',
      icon: Icons.supervisor_account_rounded,
      requiresFyp: true,
    ),
    _AdminNavItem(id: 3, label: 'Template Manager', icon: Icons.layers_rounded),
    _AdminNavItem(
      id: 4,
      label: 'Deadlines',
      icon: Icons.event_note_rounded,
      requiresFyp: true,
    ),
    _AdminNavItem(
      id: 5,
      label: 'Semester Deadlines',
      icon: Icons.event_available_rounded,
      requiresFyp: true,
    ),
    _AdminNavItem(id: 6, label: 'Users', icon: Icons.people_rounded),
    _AdminNavItem(
      id: 7,
      label: 'Universities',
      icon: Icons.school_rounded,
      requiresFyp: true,
    ),
    _AdminNavItem(id: 8, label: 'Analytics', icon: Icons.bar_chart_rounded),
    _AdminNavItem(id: 9, label: 'Verify Files', icon: Icons.fact_check_rounded),
    _AdminNavItem(id: 10, label: 'Settings', icon: Icons.settings_rounded),
  ];

  List<_AdminNavItem> get _visibleItems => _allItems
      .where((item) => !item.requiresFyp || DevUserConfig.hasFypModule)
      .toList();

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

  @override
  Widget build(BuildContext context) {
    final items = _visibleItems;
    return Scaffold(
      backgroundColor: AdminColors.background,
      body: Row(
        children: [
          _buildSidebar(items),
          Expanded(
            child: Column(
              children: [
                _buildTopBar(),
                Expanded(child: _buildContent()),
              ],
            ),
          ),
        ],
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
                  child: const Icon(Icons.shield_rounded, color: AdminColors.primary, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Admin Panel',
                        style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Colors.white),
                      ),
                      Text(
                        DevUserConfig.orgCode,
                        style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.5)),
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
                  final item = items[index];
                  return _buildNavItem(item);
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
                child: CircularProgressIndicator(strokeWidth: 2, color: AdminColors.primary),
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
                    auth.currentUser?.trim().isNotEmpty == true ? auth.currentUser! : 'Admin';
                final subtitle = auth.userEmail?.trim().isNotEmpty == true
                    ? auth.userEmail!
                    : (auth.userRole ?? 'Administrator');
                return GestureDetector(
                  onLongPress: _showLogoutDialog,
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
                        child: const Icon(Icons.person_rounded, color: Colors.white),
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
                              style: TextStyle(fontSize: 10, color: Colors.white.withOpacity(0.5)),
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

  Widget _buildNavItem(_AdminNavItem item) {
    final isSelected = _selectedId == item.id;
    return GestureDetector(
      onTap: () => setState(() => _selectedId = item.id),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        decoration: BoxDecoration(
          color: isSelected ? AdminColors.primary.withOpacity(0.15) : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
          border: isSelected ? Border.all(color: AdminColors.primary.withOpacity(0.35)) : null,
        ),
        child: Row(
          children: [
            Icon(
              item.icon,
              size: 20,
              color: isSelected ? AdminColors.primary : Colors.white.withOpacity(0.6),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                item.label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                  color: isSelected ? AdminColors.primary : Colors.white.withOpacity(0.7),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTopBar() {
    return Container(
      height: 72,
      decoration: BoxDecoration(
        color: AdminColors.surface,
        border: Border(
          bottom: BorderSide(color: AdminColors.border.withOpacity(0.5)),
        ),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 28),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _selectedLabel,
                style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: Colors.white),
              ),
              Text(
                _selectedSubtitle,
                style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.55)),
              ),
            ],
          ),
          Row(
            children: [
              Container(width: 1, height: 24, color: AdminColors.border),
              const SizedBox(width: 12),
              IconButton(
                icon: const Icon(Icons.logout_rounded),
                color: AdminColors.primary,
                tooltip: 'Logout',
                onPressed: () => confirmAndLogout(context),
              ),
            ],
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

  void _showLogoutDialog() {
    confirmAndLogout(context);
  }
}
