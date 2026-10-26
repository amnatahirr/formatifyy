import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/dev_user_config.dart';
import '../providers/auth_provider.dart';
import '../services/admin_api_service.dart';
import '../widgets/admin/admin_ui.dart';

import '../widgets/tr.dart';
class AdminUsersScreen extends StatefulWidget {
  const AdminUsersScreen({super.key});

  @override
  State<AdminUsersScreen> createState() => _AdminUsersScreenState();
}

class _AdminUsersScreenState extends State<AdminUsersScreen> {
  final AdminApiService _api = AdminApiService();
  List<Map<String, dynamic>> _allUsers = [];
  List<Map<String, dynamic>> _pagedUsers = [];
  bool _isLoading = false;
  String? _error;
  String _searchQuery = '';
  String _roleFilter = 'All';
  int _currentPage = 1;
  final int _itemsPerPage = 10;

  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadUsers();
  }

  Future<void> _loadUsers() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final auth = context.read<AuthProvider>();
      if (auth.userId == null) return;
      _allUsers = await _api.fetchUsers(auth.userId!);
      _applyFiltersAndPagination();
    } catch (e) {
      if (mounted) {
        setState(() => _error = e.toString());
        showAdminSnackBar(context, 'Error loading users: $e', isError: true);
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  List<String> get _roleFilters {
    if (DevUserConfig.hasFypModule) {
      return const ['All', 'Supervisors', 'Students', 'Admins'];
    }
    return const ['All', 'Members', 'Admins'];
  }

  List<Map<String, dynamic>> get _roleFiltered {
    final query = _searchQuery.trim().toLowerCase();
    return _allUsers.where((u) {
      final role = (u['role'] ?? '').toString().toLowerCase();
      final matchesRole = _roleFilter == 'All' ||
          (_roleFilter == 'Supervisors' && role == 'supervisor') ||
          (_roleFilter == 'Students' && role == 'student') ||
          (_roleFilter == 'Members' && role == 'student') ||
          (_roleFilter == 'Admins' && role == 'admin');
      if (!matchesRole) return false;
      if (query.isEmpty) return true;
      final username = (u['username'] ?? '').toString().toLowerCase();
      final email = (u['email'] ?? '').toString().toLowerCase();
      return username.contains(query) || email.contains(query);
    }).toList();
  }

  void _applyFiltersAndPagination() {
    final filtered = _roleFiltered;
    final totalPages = (filtered.length / _itemsPerPage).ceil();
    if (_currentPage > totalPages && totalPages > 0) _currentPage = totalPages;
    if (_currentPage < 1) _currentPage = 1;

    final start = (_currentPage - 1) * _itemsPerPage;
    final end = (start + _itemsPerPage) > filtered.length
        ? filtered.length
        : (start + _itemsPerPage);
    _pagedUsers = start < filtered.length ? filtered.sublist(start, end) : [];
    setState(() {});
  }

  String _roleLabel(String role) {
    final r = role.toLowerCase();
    if (!DevUserConfig.hasFypModule && r == 'student') return 'member';
    return role;
  }

  Color _roleColor(String role) {
    switch (role.toLowerCase()) {
      case 'admin':
        return AdminColors.accent;
      case 'supervisor':
        return AdminColors.primary;
      case 'student':
        return AdminColors.success;
      default:
        return Colors.white54;
    }
  }

  IconData _roleIcon(String role) {
    switch (role.toLowerCase()) {
      case 'admin':
        return Icons.shield_outlined;
      case 'supervisor':
        return Icons.supervisor_account_outlined;
      case 'student':
        return DevUserConfig.hasFypModule
            ? Icons.school_outlined
            : Icons.person_outline;
      default:
        return Icons.person_outline;
    }
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _roleFiltered;
    final totalPages = (filtered.length / _itemsPerPage).ceil();
    final hasFyp = DevUserConfig.hasFypModule;

    return AdminPage(
      scrollable: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchController,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    hintText: 'Search by username or email',
                    prefixIcon: const Icon(Icons.search),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  onChanged: (value) {
                    _searchQuery = value;
                    _currentPage = 1;
                    _applyFiltersAndPagination();
                  },
                ),
              ),
              const SizedBox(width: 12),
              ElevatedButton.icon(
                onPressed: _loadUsers,
                icon: const Icon(Icons.refresh),
                label: const Tr('Refresh'),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 8,
            children: _roleFilters.map((label) {
              final selected = _roleFilter == label;
              return ChoiceChip(
                label: Text(label),
                selected: selected,
                onSelected: (_) {
                  setState(() {
                    _roleFilter = label;
                    _currentPage = 1;
                  });
                  _applyFiltersAndPagination();
                },
              );
            }).toList(),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: _isLoading
                ? const AdminLoadingView()
                : _error != null
                    ? AdminErrorView(message: _error!, onRetry: _loadUsers)
                    : _pagedUsers.isEmpty
                        ? AdminEmptyView(
                            message: 'No users match this filter.',
                            onAction: _loadUsers,
                            actionLabel: 'Refresh',
                          )
                        : ListView.separated(
                            itemCount: _pagedUsers.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(height: 10),
                            itemBuilder: (context, index) {
                              final u = _pagedUsers[index];
                              final role = (u['role'] ?? 'user').toString();
                              final color = _roleColor(role);
                              return Container(
                                padding: const EdgeInsets.all(14),
                                decoration: adminCardDecoration(),
                                child: Row(
                                  children: [
                                    Container(
                                      padding: const EdgeInsets.all(10),
                                      decoration: BoxDecoration(
                                        color: color.withOpacity(0.14),
                                        borderRadius: BorderRadius.circular(10),
                                      ),
                                      child: Icon(_roleIcon(role), color: color),
                                    ),
                                    const SizedBox(width: 12),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            (u['username'] ?? '').toString(),
                                            style: const TextStyle(
                                              color: Colors.white,
                                              fontWeight: FontWeight.w600,
                                            ),
                                          ),
                                          Text(
                                            (u['email'] ?? '').toString(),
                                            style: TextStyle(
                                              color:
                                                  Colors.white.withOpacity(0.7),
                                              fontSize: 12,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 10,
                                        vertical: 6,
                                      ),
                                      decoration: BoxDecoration(
                                        color: color.withOpacity(0.15),
                                        borderRadius: BorderRadius.circular(20),
                                      ),
                                      child: Text(
                                        _roleLabel(role),
                                        style: TextStyle(
                                          color: color,
                                          fontWeight: FontWeight.w600,
                                          fontSize: 12,
                                        ),
                                      ),
                                    ),
                                    if (hasFyp) ...[
                                      const SizedBox(width: 12),
                                      Text(
                                        (u['university_name'] ?? 'N/A')
                                            .toString(),
                                        style: TextStyle(
                                          color: Colors.white.withOpacity(0.7),
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              );
                            },
                          ),
          ),
          if (totalPages > 1)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _currentPage > 1
                        ? () {
                            _currentPage--;
                            _applyFiltersAndPagination();
                          }
                        : null,
                    child: const Tr('Prev'),
                  ),
                  Text(
                    '$_currentPage / $totalPages',
                    style: TextStyle(color: Colors.white.withOpacity(0.7)),
                  ),
                  TextButton(
                    onPressed: _currentPage < totalPages
                        ? () {
                            _currentPage++;
                            _applyFiltersAndPagination();
                          }
                        : null,
                    child: const Tr('Next'),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }
}
