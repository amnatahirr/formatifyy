import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/admin_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/admin_api_service.dart';
import '../../widgets/admin/admin_ui.dart';
import 'template_list_screen.dart';

class TemplateManagerScreen extends StatefulWidget {
  final bool embedded;

  const TemplateManagerScreen({super.key, this.embedded = false});

  @override
  State<TemplateManagerScreen> createState() => _TemplateManagerScreenState();
}

class _TemplateManagerScreenState extends State<TemplateManagerScreen> {
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
      MaterialPageRoute(builder: (_) => TemplateListScreen(department: department)),
    );
    if (changed == true && mounted) {
      await _loadDepartments();
    }
  }

  Widget _buildList() {
    if (_loading) return const AdminLoadingView();
    if (_error != null) return AdminErrorView(message: _error!, onRetry: _loadDepartments);
    if (_departments.isEmpty) {
      return const AdminEmptyView(message: 'No departments are available yet for template management.');
    }
    return ListView.builder(
      padding: widget.embedded ? EdgeInsets.zero : const EdgeInsets.fromLTRB(20, 12, 20, 24),
      itemCount: _departments.length,
      itemBuilder: (context, index) {
        final department = _departments[index];
        return AdminDepartmentTile(
          title: department.name,
          subtitle: 'Max members: ${department.maxMembers}',
          badge: '${department.templateCount} templates',
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
      title: 'Template Manager',
      subtitle: 'Manage department-specific formatting templates',
      onRefresh: _loadDepartments,
      child: _buildList(),
    );
  }
}
