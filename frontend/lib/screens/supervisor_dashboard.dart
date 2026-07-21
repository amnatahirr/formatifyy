import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';
import 'supervisor/assignment_requests_screen.dart';
import 'supervisor/my_groups_screen.dart';
import 'supervisor/plagiarism_monitor_screen.dart';
import 'supervisor/submission_review_screen.dart';
import 'supervisor/supervisor_home_screen.dart';
import '../widgets/admin/admin_ui.dart';

class SupervisorDashboard extends StatefulWidget {
  const SupervisorDashboard({super.key});

  @override
  State<SupervisorDashboard> createState() => _SupervisorDashboardState();
}

class _SupervisorDashboardState extends State<SupervisorDashboard> {
  int _selectedTab = 0;

  final List<String> _tabs = const [
    'Dashboard',
    'Assignment Requests',
    'My Groups',
    'Submissions',
    'Plagiarism',
    'Profile',
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
              child: ListView.builder(
                itemCount: _tabs.length,
                itemBuilder: (context, index) {
                  final selected = _selectedTab == index;
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
                            _tabIcons[index],
                            size: 20,
                            color: selected ? AdminColors.primary : Colors.white.withOpacity(0.6),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              _tabs[index],
                              style: TextStyle(
                                fontSize: 13,
                                fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                                color: selected ? AdminColors.primary : Colors.white.withOpacity(0.7),
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
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

  Widget _buildTopBar() {
    return Container(
      height: 72,
      decoration: BoxDecoration(
        color: AdminColors.surface,
        border: Border(bottom: BorderSide(color: AdminColors.border.withOpacity(0.5))),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 28),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            _tabs[_selectedTab],
            style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: Colors.white),
          ),
          IconButton(
            icon: const Icon(Icons.logout_rounded),
            color: AdminColors.primary,
            tooltip: 'Logout',
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
        );
      case 1:
        return const AssignmentRequestsScreen();
      case 2:
        return const MyGroupsScreen();
      case 3:
        return const SubmissionReviewScreen();
      case 4:
        return const PlagiarismMonitorScreen();
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
