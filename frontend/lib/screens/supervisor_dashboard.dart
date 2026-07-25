import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';
import '../utils/responsive.dart';
import '../widgets/admin/admin_ui.dart';
import 'supervisor/assignment_requests_screen.dart';
import 'supervisor/my_groups_screen.dart';
import 'supervisor/plagiarism_monitor_screen.dart';
import 'supervisor/submission_review_screen.dart';
import 'supervisor/supervisor_home_screen.dart';
import 'supervisor/supervisor_more_screen.dart';
import 'supervisor/supervisor_notifications_screen.dart';

class _MobileNavItem {
  final int tabIndex;
  final IconData icon;
  final String label;

  const _MobileNavItem(this.tabIndex, this.icon, this.label);
}

/// Compact bottom nav — core supervisor work on phone.
const List<_MobileNavItem> _kMobileNavItems = [
  _MobileNavItem(0, Icons.dashboard_outlined, 'Home'),
  _MobileNavItem(1, Icons.assignment_ind_outlined, 'Requests'),
  _MobileNavItem(2, Icons.groups_outlined, 'Groups'),
  _MobileNavItem(3, Icons.fact_check_outlined, 'Review'),
  _MobileNavItem(6, Icons.more_horiz_rounded, 'More'),
];

class SupervisorDashboard extends StatefulWidget {
  const SupervisorDashboard({super.key});

  @override
  State<SupervisorDashboard> createState() => _SupervisorDashboardState();
}

class _SupervisorDashboardState extends State<SupervisorDashboard> {
  int _selectedTab = 0;
  int _unreadCount = 0;

  final List<String> _tabs = const [
    'Dashboard',
    'Assignment Requests',
    'My Groups',
    'Submissions',
    'Plagiarism',
    'Profile',
    'More',
    'Notifications',
  ];
  final List<IconData> _tabIcons = const [
    Icons.dashboard_rounded,
    Icons.assignment_ind_rounded,
    Icons.groups_rounded,
    Icons.fact_check_rounded,
    Icons.policy_rounded,
    Icons.person_rounded,
  ];

  static const int _requestsTabIndex = 1;
  static const int _groupsTabIndex = 2;
  static const int _submissionsTabIndex = 3;
  static const int _plagiarismTabIndex = 4;
  static const int _profileTabIndex = 5;
  static const int _moreTabIndex = 6;
  static const int _notificationsTabIndex = 7;

  String get _title {
    if (_selectedTab >= 0 && _selectedTab < _tabs.length) {
      return _tabs[_selectedTab];
    }
    return 'Supervisor';
  }

  @override
  Widget build(BuildContext context) {
    final compact = isCompact(context);

    return Scaffold(
      backgroundColor: AdminColors.background,
      body: compact
          ? SafeArea(
              bottom: false,
              child: Column(
                children: [
                  _buildTopBar(compact: true),
                  Expanded(child: _buildContent()),
                ],
              ),
            )
          : Row(
              children: [
                _buildSidebar(),
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

  Widget _buildMobileBottomNav() {
    final selectedNav = _kMobileNavItems.indexWhere(
      (item) => item.tabIndex == _selectedTab ||
          (_selectedTab == _notificationsTabIndex && item.tabIndex == _moreTabIndex) ||
          (_selectedTab == _plagiarismTabIndex && item.tabIndex == _moreTabIndex) ||
          (_selectedTab == _profileTabIndex && item.tabIndex == _moreTabIndex),
    );

    return Container(
      decoration: BoxDecoration(
        color: AdminColors.surface,
        border: Border(top: BorderSide(color: AdminColors.border.withOpacity(0.6))),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 64,
          child: Row(
            children: [
              for (var i = 0; i < _kMobileNavItems.length; i++)
                Expanded(
                  child: _buildMobileNavButton(
                    item: _kMobileNavItems[i],
                    selected: selectedNav == i,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMobileNavButton({
    required _MobileNavItem item,
    required bool selected,
  }) {
    final color = selected ? AdminColors.primary : Colors.white.withOpacity(0.55);

    return InkWell(
      onTap: () => setState(() => _selectedTab = item.tabIndex),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(item.icon, size: 22, color: color),
          const SizedBox(height: 4),
          Text(
            item.label,
            style: TextStyle(
              fontSize: 11,
              fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
              color: color,
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
        border: Border(right: BorderSide(color: AdminColors.border.withOpacity(0.5))),
      ),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              border: Border(bottom: BorderSide(color: AdminColors.border.withOpacity(0.5))),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AdminColors.primary.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.supervisor_account_rounded, color: AdminColors.primary, size: 20),
                ),
                const SizedBox(width: 12),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Supervisor',
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
              child: ListView(
                children: [
                  for (var index = 0; index < 6; index++)
                    _sidebarItem(index),
                  _sidebarItem(
                    _notificationsTabIndex,
                    label: 'Notifications',
                    icon: Icons.notifications_outlined,
                  ),
                ],
              ),
            ),
          ),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              border: Border(top: BorderSide(color: AdminColors.border.withOpacity(0.5))),
            ),
            child: Consumer<AuthProvider>(
              builder: (context, auth, _) {
                return Row(
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
                            auth.currentUser ?? 'Supervisor',
                            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Colors.white),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          Text(
                            auth.userEmail ?? 'supervisor',
                            style: TextStyle(fontSize: 10, color: Colors.white.withOpacity(0.5)),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _sidebarItem(int index, {String? label, IconData? icon}) {
    final selected = _selectedTab == index;
    final title = label ?? _tabs[index];
    final tabIcon = icon ?? _tabIcons[index];
    return GestureDetector(
      onTap: () => setState(() => _selectedTab = index),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        decoration: BoxDecoration(
          color: selected ? AdminColors.primary.withOpacity(0.15) : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
          border: selected ? Border.all(color: AdminColors.primary.withOpacity(0.35)) : null,
        ),
        child: Row(
          children: [
            Icon(
              tabIcon,
              size: 20,
              color: selected ? AdminColors.primary : Colors.white.withOpacity(0.6),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                title,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                  color: selected ? AdminColors.primary : Colors.white.withOpacity(0.7),
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (index == _notificationsTabIndex && _unreadCount > 0)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: AdminColors.primary,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '$_unreadCount',
                  style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w700),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildTopBar({required bool compact}) {
    return Container(
      height: compact ? 52 : 72,
      decoration: BoxDecoration(
        color: AdminColors.surface,
        border: Border(bottom: BorderSide(color: AdminColors.border.withOpacity(0.5))),
      ),
      padding: EdgeInsets.symmetric(horizontal: compact ? 8 : 28),
      child: Row(
        children: [
          if (compact) ...[
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: AdminColors.primary.withOpacity(0.18),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.supervisor_account_rounded, color: AdminColors.primary, size: 16),
            ),
            const SizedBox(width: 8),
          ],
          Expanded(
            child: Text(
              compact && _selectedTab == 0 ? 'Supervisor' : _title,
              style: TextStyle(
                fontSize: compact ? 16 : 24,
                fontWeight: FontWeight.w700,
                color: Colors.white,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (compact)
            IconButton(
              tooltip: 'Notifications',
              visualDensity: VisualDensity.compact,
              onPressed: () => setState(() => _selectedTab = _notificationsTabIndex),
              icon: Badge(
                isLabelVisible: _unreadCount > 0,
                label: Text('$_unreadCount'),
                child: const Icon(Icons.notifications_outlined, color: Colors.white, size: 22),
              ),
            ),
          IconButton(
            icon: const Icon(Icons.logout_rounded, size: 22),
            color: AdminColors.primary,
            tooltip: 'Logout',
            visualDensity: VisualDensity.compact,
            onPressed: () => context.read<AuthProvider>().logout(),
          ),
        ],
      ),
    );
  }

  Widget _buildContent() {
    switch (_selectedTab) {
      case 0:
        return SupervisorHomeScreen(
          onOpenAssignmentRequests: () => setState(() => _selectedTab = _requestsTabIndex),
          onOpenMyGroups: () => setState(() => _selectedTab = _groupsTabIndex),
          onOpenSubmissions: () => setState(() => _selectedTab = _submissionsTabIndex),
          onOpenPlagiarism: () => setState(() => _selectedTab = _plagiarismTabIndex),
          onOpenNotifications: () => setState(() => _selectedTab = _notificationsTabIndex),
          onUnreadCount: (count) {
            if (_unreadCount != count && mounted) {
              setState(() => _unreadCount = count);
            }
          },
        );
      case 1:
        return const AssignmentRequestsScreen();
      case 2:
        return const MyGroupsScreen();
      case 3:
        return const SubmissionReviewScreen();
      case 4:
        return const PlagiarismMonitorScreen();
      case 5:
        return const _SupervisorProfileView();
      case 6:
        return SupervisorMoreScreen(
          unreadCount: _unreadCount,
          onOpenNotifications: () => setState(() => _selectedTab = _notificationsTabIndex),
          onOpenPlagiarism: () => setState(() => _selectedTab = _plagiarismTabIndex),
          onOpenProfile: () => setState(() => _selectedTab = _profileTabIndex),
        );
      case 7:
        return const SupervisorNotificationsScreen();
      default:
        return const _SupervisorProfileView();
    }
  }
}

class _SupervisorProfileView extends StatefulWidget {
  const _SupervisorProfileView();

  @override
  State<_SupervisorProfileView> createState() => _SupervisorProfileViewState();
}

class _SupervisorProfileViewState extends State<_SupervisorProfileView> {
  final _formKey = GlobalKey<FormState>();
  final _currentController = TextEditingController();
  final _newController = TextEditingController();
  final _confirmController = TextEditingController();
  bool _obscureCurrent = true;
  bool _obscureNew = true;
  bool _obscureConfirm = true;
  bool _saving = false;

  @override
  void dispose() {
    _currentController.dispose();
    _newController.dispose();
    _confirmController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    final auth = context.read<AuthProvider>();
    final ok = await auth.changePassword(
      currentPassword: _currentController.text,
      newPassword: _newController.text,
    );
    if (!mounted) return;
    setState(() => _saving = false);
    if (ok) {
      _currentController.clear();
      _newController.clear();
      _confirmController.clear();
      showAdminSnackBar(context, 'Password updated successfully.');
    } else {
      showAdminSnackBar(context, auth.errorMessage ?? 'Could not change password.', isError: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    return AdminPage(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const AdminPageHeader(
            title: 'Profile',
            subtitle: 'Account details and password settings',
          ),
          const SizedBox(height: 24),
          AdminSectionCard(
            title: 'Account',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Name: ${auth.currentUser ?? '—'}', style: const TextStyle(color: Colors.white)),
                const SizedBox(height: 8),
                Text('Email: ${auth.userEmail ?? '—'}', style: const TextStyle(color: Colors.white)),
                const SizedBox(height: 8),
                Text('Role: supervisor', style: TextStyle(color: Colors.white.withOpacity(0.75))),
              ],
            ),
          ),
          const SizedBox(height: 18),
          AdminSectionCard(
            title: 'Change Password',
            child: Form(
              key: _formKey,
              child: Column(
                children: [
                  TextFormField(
                    controller: _currentController,
                    obscureText: _obscureCurrent,
                    decoration: InputDecoration(
                      labelText: 'Current password',
                      suffixIcon: IconButton(
                        onPressed: () => setState(() => _obscureCurrent = !_obscureCurrent),
                        icon: Icon(_obscureCurrent ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                      ),
                    ),
                    validator: (v) => v == null || v.isEmpty ? 'Enter your current password' : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _newController,
                    obscureText: _obscureNew,
                    decoration: InputDecoration(
                      labelText: 'New password',
                      suffixIcon: IconButton(
                        onPressed: () => setState(() => _obscureNew = !_obscureNew),
                        icon: Icon(_obscureNew ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                      ),
                    ),
                    validator: (v) {
                      if (v == null || v.trim().length < 6) return 'Use at least 6 characters';
                      return null;
                    },
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _confirmController,
                    obscureText: _obscureConfirm,
                    decoration: InputDecoration(
                      labelText: 'Confirm new password',
                      suffixIcon: IconButton(
                        onPressed: () => setState(() => _obscureConfirm = !_obscureConfirm),
                        icon: Icon(_obscureConfirm ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                      ),
                    ),
                    validator: (v) {
                      if (v != _newController.text) return 'Passwords do not match';
                      return null;
                    },
                  ),
                  const SizedBox(height: 20),
                  Align(
                    alignment: Alignment.centerRight,
                    child: ElevatedButton.icon(
                      onPressed: _saving ? null : _submit,
                      icon: _saving
                          ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.lock_reset_rounded),
                      label: Text(_saving ? 'Updating...' : 'Update Password'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
