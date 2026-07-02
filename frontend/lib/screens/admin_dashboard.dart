import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../screens/template_configuration_screen.dart';
import '../screens/admin_users_screen.dart';
import '../screens/admin_overview_screen.dart';
import '../screens/admin_universities_screen.dart';
import '../screens/admin_analytics_screen.dart';
import '../screens/admin_settings_screen.dart';
import '../screens/admin_verify_screen.dart';
import '../screens/admin_templates_list_screen.dart';

class AdminDashboard extends StatefulWidget {
  const AdminDashboard({super.key});

  @override
  State<AdminDashboard> createState() => _AdminDashboardState();
}

class _AdminDashboardState extends State<AdminDashboard> {
  int _selectedTab = 0;
  final List<String> _tabs = [
    'Overview',
    'Templates List',
    'Create Template',
    'Verify Files',
    'Users',
    'Universities',
    'Analytics',
    'Settings',
  ];

  final List<IconData> _tabIcons = [
    Icons.dashboard,
    Icons.library_books,
    Icons.layers,
    Icons.fact_check,
    Icons.people,
    Icons.school,
    Icons.bar_chart,
    Icons.settings,
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F1419),
      body: Row(
        children: [
          // Sidebar
          _buildSidebar(),
          // Main content
          Expanded(
            child: Column(
              children: [
                // Top bar
                _buildTopBar(),
                // Content
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
      width: 240,
      decoration: BoxDecoration(
        color: const Color(0xFF141B27),
        border: Border(
          right: BorderSide(color: const Color(0xFF2D3748).withOpacity(0.5)),
        ),
      ),
      child: Column(
        children: [
          // Logo/Branding
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              border: Border(
                bottom: BorderSide(
                  color: const Color(0xFF2D3748).withOpacity(0.5),
                ),
              ),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF6366F1).withOpacity(0.2),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: const Icon(
                    Icons.shield,
                    color: Color(0xFF6366F1),
                    size: 20,
                  ),
                ),
                const SizedBox(width: 12),
                Column(
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
                      'FORMATIFY',
                      style: TextStyle(
                        fontSize: 11,
                        color: Colors.white.withOpacity(0.5),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          // Navigation items
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
          // User info at bottom
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              border: Border(
                top: BorderSide(
                  color: const Color(0xFF2D3748).withOpacity(0.5),
                ),
              ),
            ),
            child: Consumer<AuthProvider>(
              builder: (context, auth, _) {
                return GestureDetector(
                  onLongPress: () {
                    _showLogoutDialog();
                  },
                  child: Row(
                    children: [
                      Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)],
                          ),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(Icons.person, color: Colors.white),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Admin User',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: Colors.white,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            Text(
                              'System Administrator',
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

  Widget _buildNavItem({
    required IconData icon,
    required String label,
    required int index,
  }) {
    final isSelected = _selectedTab == index;
    return GestureDetector(
      onTap: () {
        setState(() => _selectedTab = index);
      },
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        decoration: BoxDecoration(
          color: isSelected
              ? const Color(0xFF6366F1).withOpacity(0.15)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
          border: isSelected
              ? Border.all(color: const Color(0xFF6366F1).withOpacity(0.3))
              : null,
        ),
        child: Row(
          children: [
            Icon(
              icon,
              size: 20,
              color: isSelected
                  ? const Color(0xFF6366F1)
                  : Colors.white.withOpacity(0.6),
            ),
            const SizedBox(width: 12),
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                color: isSelected
                    ? const Color(0xFF6366F1)
                    : Colors.white.withOpacity(0.7),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTopBar() {
    return Container(
      height: 70,
      decoration: BoxDecoration(
        color: const Color(0xFF141B27),
        border: Border(
          bottom: BorderSide(color: const Color(0xFF2D3748).withOpacity(0.5)),
        ),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            _tabs[_selectedTab],
            style: const TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w700,
              color: Colors.white,
            ),
          ),
          Row(
            children: [
              IconButton(
                icon: const Icon(Icons.notifications_outlined),
                color: Colors.white.withOpacity(0.6),
                onPressed: () {},
              ),
              const SizedBox(width: 8),
              Container(width: 1, height: 24, color: const Color(0xFF2D3748)),
              const SizedBox(width: 16),
              IconButton(
                icon: const Icon(Icons.logout),
                color: const Color(0xFF6366F1),
                tooltip: 'Logout',
                onPressed: _logout,
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
        return const AdminTemplatesListScreen();
      case 2:
        return const TemplateConfigurationScreen();
      case 3:
        return const AdminVerifyScreen();
      case 4:
        return const AdminUsersScreen();
      case 5:
        return const AdminUniversitiesScreen();
      case 6:
        return const AdminAnalyticsScreen();
      case 7:
        return const AdminSettingsScreen();
      default:
        return const SizedBox();
    }
  }

  void _logout() {
    context.read<AuthProvider>().logout();
  }

  void _showLogoutDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Logout'),
        content: const Text('Are you sure you want to logout?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              _logout();
            },
            child: const Text('Logout'),
          ),
        ],
      ),
    );
  }
}
