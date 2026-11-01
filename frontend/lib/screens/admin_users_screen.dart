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

  bool _roleMatches(String filter, String role) {
    return filter == 'All' ||
        (filter == 'Supervisors' && role == 'supervisor') ||
        (filter == 'Students' && role == 'student') ||
        (filter == 'Members' && role == 'student') ||
        (filter == 'Admins' && role == 'admin');
  }

  int _countFor(String filter) {
    if (filter == 'All') return _allUsers.length;
    return _allUsers
        .where((u) =>
            _roleMatches(filter, (u['role'] ?? '').toString().toLowerCase()))
        .length;
  }

  List<Map<String, dynamic>> get _roleFiltered {
    final query = _searchQuery.trim().toLowerCase();
    return _allUsers.where((u) {
      final role = (u['role'] ?? '').toString().toLowerCase();
      final matchesRole = _roleMatches(_roleFilter, role);
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
          // ---- Search + refresh ----
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchController,
                  style: const TextStyle(color: Colors.white, fontSize: 14.5),
                  cursorColor: AdminColors.primary,
                  decoration: InputDecoration(
                    hintText: 'Search by username or email',
                    hintStyle: TextStyle(
                      color: Colors.white.withOpacity(0.4),
                      fontSize: 14,
                    ),
                    filled: true,
                    fillColor: Colors.white.withOpacity(0.045),
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 16,
                    ),
                    prefixIcon: Icon(
                      Icons.search_rounded,
                      color: Colors.white.withOpacity(0.5),
                    ),
                    suffixIcon: _searchController.text.isEmpty
                        ? null
                        : IconButton(
                            icon: Icon(
                              Icons.close_rounded,
                              size: 18,
                              color: Colors.white.withOpacity(0.55),
                            ),
                            tooltip: 'Clear',
                            onPressed: () {
                              _searchController.clear();
                              _searchQuery = '';
                              _currentPage = 1;
                              _applyFiltersAndPagination();
                            },
                          ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(14),
                      borderSide:
                          BorderSide(color: Colors.white.withOpacity(0.09)),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(14),
                      borderSide: BorderSide(
                        color: AdminColors.primary.withOpacity(0.8),
                        width: 1.4,
                      ),
                    ),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(14),
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
              SizedBox(
                height: 50,
                child: ElevatedButton.icon(
                  onPressed: _loadUsers,
                  icon: const Icon(Icons.refresh_rounded, size: 20),
                  label: const Tr('Refresh'),
                  style: ElevatedButton.styleFrom(
                    elevation: 0,
                    backgroundColor: AdminColors.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 18),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                    textStyle: const TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 13.5,
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // ---- Role filters with live counts + result summary ----
          Row(
            children: [
              Expanded(
                child: Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _roleFilters.map((label) {
                    return _RoleFilterChip(
                      label: label,
                      count: _countFor(label),
                      selected: _roleFilter == label,
                      onTap: () {
                        setState(() {
                          _roleFilter = label;
                          _currentPage = 1;
                        });
                        _applyFiltersAndPagination();
                      },
                    );
                  }).toList(),
                ),
              ),
              const SizedBox(width: 12),
              Text(
                '${filtered.length} user${filtered.length == 1 ? '' : 's'}',
                style: TextStyle(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0.3,
                  color: Colors.white.withOpacity(0.5),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // ---- List ----
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
                              return _UserCard(
                                username: (u['username'] ?? '').toString(),
                                email: (u['email'] ?? '').toString(),
                                roleLabel: _roleLabel(role),
                                color: _roleColor(role),
                                icon: _roleIcon(role),
                                university: hasFyp
                                    ? (u['organization_name'] ?? u['university_name'] ?? 'N/A')
                                        .toString()
                                    : null,
                              );
                            },
                          ),
          ),

          // ---- Pagination ----
          if (totalPages > 1 && !_isLoading && _error == null)
            Padding(
              padding: const EdgeInsets.only(top: 14),
              child: Row(
                children: [
                  Text(
                    'Showing ${(_currentPage - 1) * _itemsPerPage + 1}'
                    '–${(_currentPage - 1) * _itemsPerPage + _pagedUsers.length}'
                    ' of ${filtered.length}',
                    style: TextStyle(
                      fontSize: 12.5,
                      color: Colors.white.withOpacity(0.5),
                    ),
                  ),
                  const Spacer(),
                  _PagerButton(
                    icon: Icons.chevron_left_rounded,
                    tooltip: 'Prev',
                    onTap: _currentPage > 1
                        ? () {
                            _currentPage--;
                            _applyFiltersAndPagination();
                          }
                        : null,
                  ),
                  Container(
                    margin: const EdgeInsets.symmetric(horizontal: 8),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      color: AdminColors.primary.withOpacity(0.14),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: AdminColors.primary.withOpacity(0.35),
                      ),
                    ),
                    child: Text(
                      '$_currentPage / $totalPages',
                      style: const TextStyle(
                        fontSize: 12.5,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
                    ),
                  ),
                  _PagerButton(
                    icon: Icons.chevron_right_rounded,
                    tooltip: 'Next',
                    onTap: _currentPage < totalPages
                        ? () {
                            _currentPage++;
                            _applyFiltersAndPagination();
                          }
                        : null,
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

// ---------------------------------------------------------------------------
// Widgets
// ---------------------------------------------------------------------------

class _RoleFilterChip extends StatelessWidget {
  final String label;
  final int count;
  final bool selected;
  final VoidCallback onTap;

  const _RoleFilterChip({
    required this.label,
    required this.count,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(999),
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
        decoration: BoxDecoration(
          gradient: selected
              ? LinearGradient(
                  colors: [
                    AdminColors.primary.withOpacity(0.35),
                    AdminColors.primary.withOpacity(0.15),
                  ],
                )
              : null,
          color: selected ? null : Colors.white.withOpacity(0.04),
          borderRadius: BorderRadius.circular(999),
          border: Border.all(
            color: selected
                ? AdminColors.primary.withOpacity(0.7)
                : Colors.white.withOpacity(0.1),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: selected ? FontWeight.w700 : FontWeight.w600,
                color: selected ? Colors.white : Colors.white.withOpacity(0.7),
              ),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 1.5),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(selected ? 0.18 : 0.08),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                '$count',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: Colors.white.withOpacity(selected ? 0.95 : 0.6),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _UserCard extends StatefulWidget {
  final String username;
  final String email;
  final String roleLabel;
  final Color color;
  final IconData icon;
  final String? university;

  const _UserCard({
    required this.username,
    required this.email,
    required this.roleLabel,
    required this.color,
    required this.icon,
    this.university,
  });

  @override
  State<_UserCard> createState() => _UserCardState();
}

class _UserCardState extends State<_UserCard> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final color = widget.color;

    final rolePill = Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 5),
      decoration: BoxDecoration(
        color: color.withOpacity(0.14),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.35)),
      ),
      child: Text(
        widget.roleLabel,
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.w700,
          fontSize: 11.5,
          letterSpacing: 0.3,
        ),
      ),
    );

    Widget? universityChip;
    if (widget.university != null) {
      universityChip = Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.account_balance_rounded,
            size: 14,
            color: Colors.white.withOpacity(0.4),
          ),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              widget.university!,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 12.5,
                color: Colors.white.withOpacity(0.65),
              ),
            ),
          ),
        ],
      );
    }

    final avatar = Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(13),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [color.withOpacity(0.28), color.withOpacity(0.10)],
        ),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Icon(widget.icon, color: color, size: 22),
    );

    final info = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          widget.username,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w700,
            fontSize: 14.5,
          ),
        ),
        const SizedBox(height: 3),
        Text(
          widget.email,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            color: Colors.white.withOpacity(0.55),
            fontSize: 12.5,
          ),
        ),
      ],
    );

    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        curve: Curves.easeOut,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.centerLeft,
            end: Alignment.centerRight,
            colors: [
              AdminColors.card,
              Color.alphaBlend(
                color.withOpacity(_hover ? 0.10 : 0.04),
                AdminColors.card,
              ),
            ],
          ),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: _hover
                ? color.withOpacity(0.55)
                : Colors.white.withOpacity(0.08),
          ),
          boxShadow: [
            BoxShadow(
              color: color.withOpacity(_hover ? 0.14 : 0.0),
              blurRadius: 18,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final narrow = constraints.maxWidth < 640;
            if (narrow) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      avatar,
                      const SizedBox(width: 12),
                      Expanded(child: info),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 12,
                    runSpacing: 8,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      rolePill,
                      if (universityChip != null) universityChip,
                    ],
                  ),
                ],
              );
            }
            return Row(
              children: [
                avatar,
                const SizedBox(width: 14),
                Expanded(child: info),
                const SizedBox(width: 12),
                rolePill,
                if (universityChip != null) ...[
                  const SizedBox(width: 16),
                  ConstrainedBox(
                    constraints: BoxConstraints(
                      maxWidth: constraints.maxWidth * 0.32,
                    ),
                    child: universityChip,
                  ),
                ],
              ],
            );
          },
        ),
      ),
    );
  }
}

class _PagerButton extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final VoidCallback? onTap;

  const _PagerButton({
    required this.icon,
    required this.tooltip,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final enabled = onTap != null;
    return Tooltip(
      message: tooltip,
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: onTap,
        child: Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(enabled ? 0.06 : 0.02),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: Colors.white.withOpacity(enabled ? 0.12 : 0.05),
            ),
          ),
          child: Icon(
            icon,
            size: 22,
            color: Colors.white.withOpacity(enabled ? 0.85 : 0.25),
          ),
        ),
      ),
    );
  }
}