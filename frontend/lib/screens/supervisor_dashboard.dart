import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';
import '../utils/logout_confirm.dart';
import '../utils/responsive.dart';
import '../theme/app_theme.dart';
import '../widgets/admin/admin_ui.dart';
import '../widgets/notification_bell.dart';
import '../providers/notification_provider.dart';
import 'supervisor/assignment_requests_screen.dart';
import 'supervisor/my_groups_screen.dart';
import 'supervisor/plagiarism_monitor_screen.dart';
import 'supervisor/submission_review_screen.dart';
import 'supervisor/supervisor_home_screen.dart';
import 'supervisor/supervisor_more_screen.dart';
import '../screens/notifications_screen.dart';

import '../widgets/tr.dart';
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
  /// Optional initial sidebar tab (e.g. from a notification deep link).
  final int? initialTab;

  const SupervisorDashboard({super.key, this.initialTab});

  @override
  State<SupervisorDashboard> createState() => _SupervisorDashboardState();
}

class _SupervisorDashboardState extends State<SupervisorDashboard> {
  int _selectedTab = 0;

  /// Per-tab nested navigators so detail screens (Group Detail, Document Review,
  /// etc.) push beside the sidebar instead of covering the whole dashboard.
  final Map<int, GlobalKey<NavigatorState>> _contentNavKeys = {};
  final Map<int, _ShellNavObserver> _navObservers = {};

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
  final List<String> _tabSubtitles = const [
    'Overview of your supervision workload',
    'Approve or decline student group requests',
    'Groups you supervise and their progress',
    'Documents waiting for your review',
    'Similarity monitoring across submissions',
    'Account details and password settings',
    'Additional supervisor tools',
    'Recent activity and alerts',
  ];

  static const int _requestsTabIndex = 1;
  static const int _groupsTabIndex = 2;
  static const int _submissionsTabIndex = 3;
  static const int _plagiarismTabIndex = 4;
  static const int _profileTabIndex = 5;
  static const int _moreTabIndex = 6;
  static const int _notificationsTabIndex = 7;

  GlobalKey<NavigatorState> _navKeyFor(int tab) {
    return _contentNavKeys.putIfAbsent(tab, GlobalKey<NavigatorState>.new);
  }

  _ShellNavObserver _observerFor(int tab) {
    return _navObservers.putIfAbsent(
      tab,
      () => _ShellNavObserver(onChanged: () {
        if (mounted) setState(() {});
      }),
    );
  }

  bool get _contentCanPop {
    final nav = _navKeyFor(_selectedTab).currentState;
    return nav != null && nav.canPop();
  }

  void _selectTab(int index) {
    if (_selectedTab == index) {
      _navKeyFor(index).currentState?.popUntil((route) => route.isFirst);
      return;
    }
    setState(() => _selectedTab = index);
  }

  @override
  void initState() {
    super.initState();
    final t = widget.initialTab;
    if (t != null && t >= 0 && t < _tabs.length) {
      _selectedTab = t;
    }
  }

  String get _title {
    if (_selectedTab >= 0 && _selectedTab < _tabs.length) {
      return _tabs[_selectedTab];
    }
    return 'Supervisor';
  }

  String? get _subtitle {
    if (_selectedTab >= 0 && _selectedTab < _tabSubtitles.length) {
      return _tabSubtitles[_selectedTab];
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final compact = isCompact(context);

    return PopScope(
      canPop: !_contentCanPop,
      onPopInvokedWithResult: (didPop, result) {
        if (didPop) return;
        final nav = _navKeyFor(_selectedTab).currentState;
        if (nav != null && nav.canPop()) {
          nav.pop(result);
        }
      },
      child: Scaffold(
        backgroundColor: Colors.transparent,
        body: AppPalette.dark.innerGlowBackdrop(
          child: compact
              ? SafeArea(
                  bottom: false,
                  child: Column(
                    children: [
                      _buildTopBar(compact: true),
                      Expanded(child: _buildShellNavigator()),
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
                          Expanded(child: _buildShellNavigator()),
                        ],
                      ),
                    ),
                  ],
                ),
        ),
        bottomNavigationBar: compact ? _buildMobileBottomNav() : null,
      ),
    );
  }

  /// Nested navigator: keeps sidebar/bottom-nav visible on pushed detail routes.
  Widget _buildShellNavigator() {
    return Navigator(
      key: _navKeyFor(_selectedTab),
      observers: [_observerFor(_selectedTab)],
      onGenerateRoute: (settings) {
        return MaterialPageRoute<void>(
          settings: settings,
          builder: (_) => _buildContent(),
        );
      },
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
      decoration: const BoxDecoration(
        color: AdminColors.surface,
        border: Border(top: BorderSide(color: AdminColors.borderStrong)),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 66,
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
    final color = selected ? AdminColors.accentBright : Colors.white.withOpacity(0.55);

    return InkWell(
      onTap: () => _selectTab(item.tabIndex),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
            decoration: BoxDecoration(
              color: selected ? AdminColors.primary.withOpacity(0.2) : Colors.transparent,
              borderRadius: BorderRadius.circular(999),
            ),
            child: Icon(item.icon, size: 21, color: color),
          ),
          const SizedBox(height: 3),
          Text(
            item.label,
            style: TextStyle(
              fontSize: 10.5,
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
      width: 252,
      decoration: const BoxDecoration(
        color: AdminColors.surface,
        border: Border(right: BorderSide(color: AdminColors.borderStrong)),
      ),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: AdminColors.border)),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(9),
                  decoration: BoxDecoration(
                    gradient: AdminColors.primaryGradient,
                    borderRadius: BorderRadius.circular(10),
                    boxShadow: [
                      BoxShadow(
                        color: AdminColors.primary.withOpacity(0.42),
                        blurRadius: 16,
                        offset: const Offset(0, 6),
                      ),
                    ],
                  ),
                  child: const Icon(Icons.supervisor_account_rounded, color: Colors.white, size: 20),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Tr('FORMATIFY',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                          letterSpacing: 0.4,
                        ),
                      ),
                      Tr('Supervisor Console',
                        style: TextStyle(fontSize: 10.5, color: Color(0x8CFFFFFF)),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(vertical: 14),
              children: [
                _sidebarSectionLabel('Workspace'),
                for (var index = 0; index < 5; index++) _sidebarItem(index),
                const SizedBox(height: 6),
                _sidebarSectionLabel('Account'),
                _sidebarItem(_profileTabIndex),
                _sidebarItem(
                  _notificationsTabIndex,
                  label: 'Notifications',
                  icon: Icons.notifications_outlined,
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Container(
              decoration: BoxDecoration(
                color: AdminColors.surfaceAlt,
                borderRadius: BorderRadius.circular(adminCardRadius),
                border: Border.all(color: AdminColors.borderStrong),
              ),
              padding: const EdgeInsets.all(14),
              child: Consumer<AuthProvider>(
                builder: (context, auth, _) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            width: 36,
                            height: 36,
                            decoration: BoxDecoration(
                              gradient: AdminColors.primaryGradient,
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Center(
                              child: Text(
                                (auth.currentUser?.isNotEmpty ?? false)
                                    ? auth.currentUser![0].toUpperCase()
                                    : 'S',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w700,
                                  fontSize: 15,
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 11),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  auth.currentUser ?? 'Supervisor',
                                  style: const TextStyle(
                                    fontSize: 12.5,
                                    fontWeight: FontWeight.w700,
                                    color: Colors.white,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                const SizedBox(height: 2),
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
                      ),
                      const SizedBox(height: 12),
                      SizedBox(
                        width: double.infinity,
                        child: OutlinedButton.icon(
                          onPressed: () => confirmAndLogout(context),
                          icon: const Icon(Icons.logout_rounded, size: 14),
                          label: const Tr('Logout', style: TextStyle(fontSize: 11.5)),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: Colors.white.withOpacity(0.85),
                            side: const BorderSide(color: AdminColors.borderStrong),
                            padding: const EdgeInsets.symmetric(vertical: 9),
                            minimumSize: const Size(0, 34),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(adminTileRadius),
                            ),
                          ),
                        ),
                      ),
                    ],
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _sidebarSectionLabel(String label) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 6, 16, 8),
      child: Text(
        label.toUpperCase(),
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          letterSpacing: 1.1,
          color: Colors.white.withOpacity(0.38),
        ),
      ),
    );
  }

  Widget _sidebarItem(int index, {String? label, IconData? icon}) {
    final selected = _selectedTab == index;
    final title = label ?? _tabs[index];
    final tabIcon = icon ?? _tabIcons[index];
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
      child: InkWell(
        onTap: () => _selectTab(index),
        borderRadius: BorderRadius.circular(adminTileRadius),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 11),
          decoration: BoxDecoration(
            color: selected ? AdminColors.primary.withOpacity(0.18) : Colors.transparent,
            borderRadius: BorderRadius.circular(adminTileRadius),
            border: Border.all(
              color: selected ? AdminColors.accent.withOpacity(0.6) : Colors.transparent,
              width: 1.4,
            ),
          ),
          child: Row(
            children: [
              Icon(
                tabIcon,
                size: 19,
                color: selected ? AdminColors.accentBright : Colors.white.withOpacity(0.58),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                    color: selected ? Colors.white : Colors.white.withOpacity(0.68),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (index == _notificationsTabIndex)
                Consumer<NotificationProvider>(
                  builder: (context, provider, _) {
                    if (provider.unreadCount > 0) {
                      return Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                        decoration: BoxDecoration(
                          gradient: AdminColors.primaryGradient,
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          '${provider.unreadCount}',
                          style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w700),
                        ),
                      );
                    }
                    return const SizedBox.shrink();
                  },
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTopBar({required bool compact}) {
    final subtitle = _subtitle;
    return Container(
      height: compact ? 54 : 84,
      decoration: const BoxDecoration(
        color: AdminColors.surface,
        border: Border(bottom: BorderSide(color: AdminColors.borderStrong)),
      ),
      padding: EdgeInsets.symmetric(horizontal: compact ? 10 : 32),
      child: Row(
        children: [
          if (compact) ...[
            Container(
              padding: const EdgeInsets.all(7),
              decoration: BoxDecoration(
                gradient: AdminColors.primaryGradient,
                borderRadius: BorderRadius.circular(9),
              ),
              child: const Icon(Icons.supervisor_account_rounded, color: Colors.white, size: 16),
            ),
            const SizedBox(width: 10),
          ],
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  compact && _selectedTab == 0 ? 'Supervisor' : _title,
                  style: TextStyle(
                    fontSize: compact ? 16 : 23,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                    letterSpacing: -0.3,
                    height: 1.15,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                if (!compact && subtitle != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    subtitle,
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
          const NotificationBell(),
          IconButton(
            icon: const Icon(Icons.logout_rounded, size: 21),
            color: AdminColors.accentBright,
            tooltip: 'Logout',
            visualDensity: VisualDensity.compact,
            onPressed: () => confirmAndLogout(context),
          ),
        ],
      ),
    );
  }

  Widget _buildContent() {
    switch (_selectedTab) {
      case 0:
        return SupervisorHomeScreen(
          onOpenAssignmentRequests: () => _selectTab(_requestsTabIndex),
          onOpenMyGroups: () => _selectTab(_groupsTabIndex),
          onOpenSubmissions: () => _selectTab(_submissionsTabIndex),
          onOpenPlagiarism: () => _selectTab(_plagiarismTabIndex),
          onOpenNotifications: () => _selectTab(_notificationsTabIndex),
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
          onOpenNotifications: () => _selectTab(_notificationsTabIndex),
          onOpenPlagiarism: () => _selectTab(_plagiarismTabIndex),
          onOpenProfile: () => _selectTab(_profileTabIndex),
        );
      case 7:
        return const NotificationsScreen(embedded: true);
      default:
        return const _SupervisorProfileView();
    }
  }
}

/// Rebuilds the dashboard shell when nested routes push/pop (keeps PopScope in sync).
class _ShellNavObserver extends NavigatorObserver {
  final VoidCallback onChanged;

  _ShellNavObserver({required this.onChanged});

  void _notify() {
    // Defer so NavigatorState.canPop() is up to date.
    WidgetsBinding.instance.addPostFrameCallback((_) => onChanged());
  }

  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) => _notify();

  @override
  void didPop(Route<dynamic> route, Route<dynamic>? previousRoute) => _notify();

  @override
  void didRemove(Route<dynamic> route, Route<dynamic>? previousRoute) => _notify();

  @override
  void didReplace({Route<dynamic>? newRoute, Route<dynamic>? oldRoute}) => _notify();
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

  Widget _profileRow(IconData icon, String label, String value) {
    return Row(
      children: [
        Icon(icon, size: 17, color: AdminColors.accent.withOpacity(0.85)),
        const SizedBox(width: 10),
        SizedBox(
          width: 64,
          child: Text(
            label,
            style: TextStyle(fontSize: 12.5, color: Colors.white.withOpacity(0.55)),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(
              fontSize: 13.5,
              fontWeight: FontWeight.w600,
              color: Colors.white,
            ),
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    return AdminPage(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminSectionCard(
            title: 'Account',
            subtitle: 'Your supervisor identity on Formatify',
            icon: Icons.badge_rounded,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _profileRow(Icons.person_outline_rounded, 'Name', auth.currentUser ?? '—'),
                const SizedBox(height: 12),
                _profileRow(Icons.mail_outline_rounded, 'Email', auth.userEmail ?? '—'),
                const SizedBox(height: 12),
                _profileRow(Icons.verified_user_outlined, 'Role', 'Supervisor'),
              ],
            ),
          ),
          const SizedBox(height: 18),
          AdminSectionCard(
            title: 'Change Password',
            subtitle: 'Use at least 6 characters',
            icon: Icons.lock_outline_rounded,
            accent: AdminColors.accent,
            child: Form(
              key: _formKey,
              child: Column(
                children: [
                  TextFormField(
                    controller: _currentController,
                    obscureText: _obscureCurrent,
                    style: const TextStyle(color: Colors.white),
                    decoration: adminFieldDecoration(
                      label: 'Current password',
                      prefixIcon: Icons.lock_outline_rounded,
                      suffixIcon: IconButton(
                        onPressed: () => setState(() => _obscureCurrent = !_obscureCurrent),
                        icon: Icon(
                          _obscureCurrent ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                          size: 19,
                        ),
                      ),
                    ),
                    validator: (v) => v == null || v.isEmpty ? 'Enter your current password' : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _newController,
                    obscureText: _obscureNew,
                    style: const TextStyle(color: Colors.white),
                    decoration: adminFieldDecoration(
                      label: 'New password',
                      prefixIcon: Icons.lock_reset_rounded,
                      suffixIcon: IconButton(
                        onPressed: () => setState(() => _obscureNew = !_obscureNew),
                        icon: Icon(
                          _obscureNew ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                          size: 19,
                        ),
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
                    style: const TextStyle(color: Colors.white),
                    decoration: adminFieldDecoration(
                      label: 'Confirm new password',
                      prefixIcon: Icons.check_circle_outline_rounded,
                      suffixIcon: IconButton(
                        onPressed: () => setState(() => _obscureConfirm = !_obscureConfirm),
                        icon: Icon(
                          _obscureConfirm ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                          size: 19,
                        ),
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
