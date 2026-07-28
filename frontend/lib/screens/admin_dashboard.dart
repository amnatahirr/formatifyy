import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

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
import '../utils/logout_confirm.dart';
import '../widgets/admin/admin_ui.dart';

class AdminDashboard extends StatefulWidget {
  const AdminDashboard({super.key});

  @override
  State<AdminDashboard> createState() => _AdminDashboardState();
}

class _AdminDashboardState extends State<AdminDashboard> {
  int _selectedTab = 0;

  final List<String> _tabs = const [
    'Overview',
    'Department Manager',
    'Supervisors',
    'Template Manager',
    'Deadlines',
    'Semester Deadlines',
    'Users',
    'Universities',
    'Analytics',
    'Verify Files',
    'Settings',
  ];

  final List<IconData> _tabIcons = const [
    Icons.dashboard_rounded,
    Icons.apartment_rounded,
    Icons.supervisor_account_rounded,
    Icons.layers_rounded,
    Icons.event_note_rounded,
    Icons.event_available_rounded,
    Icons.people_rounded,
    Icons.school_rounded,
    Icons.bar_chart_rounded,
    Icons.fact_check_rounded,
    Icons.settings_rounded,
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AdminColors.background,
      body: Row(
        children: [
          _buildSidebar(),
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

  Widget _buildSidebar() {
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
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Admin Panel',
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Colors.white),
                    ),
                    Text(
                      'FORMATIFY',
                      style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.5)),
                    ),
                  ],
                ),
              ],
            ),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: ListView.builder(
                itemCount: _tabs.length,
                itemBuilder: (context, index) {
                  return _buildNavItem(
                    icon: _tabIcons[index],
                    label: _tabs[index],
                    index: index,
                  );
                },
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
                final displayName = auth.currentUser?.trim().isNotEmpty == true ? auth.currentUser! : 'Admin';
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
                          gradient: const LinearGradient(colors: [AdminColors.primary, AdminColors.accent]),
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
                              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Colors.white),
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

  Widget _buildNavItem({
    required IconData icon,
    required String label,
    required int index,
  }) {
    final isSelected = _selectedTab == index;
    return GestureDetector(
      onTap: () => setState(() => _selectedTab = index),
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
              icon,
              size: 20,
              color: isSelected ? AdminColors.primary : Colors.white.withOpacity(0.6),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                label,
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
                _tabs[_selectedTab],
                style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: Colors.white),
              ),
              Text(
                'Live data from backend services',
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
    switch (_selectedTab) {
      case 0:
        return const AdminOverviewScreen();
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
