import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/admin_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/admin_api_service.dart';
import '../../widgets/admin/admin_ui.dart';
import 'supervisor_list_screen.dart';

class SupervisorManagementScreen extends StatefulWidget {
  final bool embedded;

  const SupervisorManagementScreen({super.key, this.embedded = false});

  @override
  State<SupervisorManagementScreen> createState() => _SupervisorManagementScreenState();
}

class _SupervisorManagementScreenState extends State<SupervisorManagementScreen> {
  final AdminApiService _api = AdminApiService();
  bool _loading = true;
  String? _error;
  List<DepartmentSummary> _departments = const [];

  @override
  void initState() {
    super.initState();
    _loadDepartments();
  }

  Future<void> _loadDepartments() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final departments = await _api.fetchDepartments(userId);
      if (mounted) setState(() => _departments = departments);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openDepartment(DepartmentSummary department) async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => SupervisorListScreen(department: department)),
    );
    if (changed == true && mounted) {
      await _loadDepartments();
    }
  }

  Widget _buildList() {
    if (_loading) return const AdminLoadingView();
    if (_error != null) return AdminErrorView(message: _error!, onRetry: _loadDepartments);
    if (_departments.isEmpty) {
      return const AdminEmptyView(
        message: 'No departments are available yet. Add departments from Department Manager first.',
      );
    }
    return ListView.builder(
      padding: widget.embedded ? EdgeInsets.zero : const EdgeInsets.fromLTRB(20, 12, 20, 24),
      itemCount: _departments.length,
      itemBuilder: (context, index) {
        final department = _departments[index];
        return AdminDepartmentTile(
          title: department.name,
          subtitle: department.code,
          badge: '${department.supervisorCount} supervisors',
          onTap: () => _openDepartment(department),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    if (widget.embedded) {
      return AdminPage(
        scrollable: false,
        onRefresh: _loadDepartments,
        child: _buildList(),
      );
    }

    return AdminSubPage(
      title: 'Supervisor Management',
      subtitle: 'Choose a department to manage supervisors',
      onRefresh: _loadDepartments,
      child: _buildList(),
    );
  }
}
