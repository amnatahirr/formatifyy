import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../config/dev_user_config.dart';
import '../../models/admin_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/admin_api_service.dart';
import '../../services/super_admin_api_service.dart';
import '../../widgets/admin/admin_ui.dart';

class DepartmentManagerScreen extends StatefulWidget {
  final bool embedded;

  const DepartmentManagerScreen({super.key, this.embedded = false});

  @override
  State<DepartmentManagerScreen> createState() => _DepartmentManagerScreenState();
}

class _DepartmentManagerScreenState extends State<DepartmentManagerScreen> {
  final AdminApiService _api = AdminApiService();
  bool _loading = true;
  String? _error;
  List<DepartmentSummary> _departments = const [];

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    await _refreshModuleFlags();
    await _loadDepartments();
  }

  /// Keep FYP gating in sync with `/org/info` (modules can change in Super Admin).
  Future<void> _refreshModuleFlags() async {
    try {
      final info = await SuperAdminApiService().fetchOrgInfo();
      DevUserConfig.applyOrgInfo(info);
      if (mounted) setState(() {});
    } catch (_) {
      // Keep existing DevUserConfig flags.
    }
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

  Future<void> _openDepartmentSheet({DepartmentSummary? item}) async {
    final hasFyp = DevUserConfig.hasFypModule;
    final nameController = TextEditingController(text: item?.name ?? '');
    final codeController = TextEditingController(text: item?.code ?? '');
    final minController = TextEditingController(text: '${item?.minMembers ?? 1}');
    final maxController = TextEditingController(text: '${item?.maxMembers ?? 3}');
    final maxGroupsController =
        TextEditingController(text: '${item?.maxGroupsPerSupervisor ?? 6}');
    final formKey = GlobalKey<FormState>();

    await showAdminBottomSheet(
      context: context,
      title: item == null ? 'Add Department' : 'Edit Department',
      child: Form(
        key: formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextFormField(
              controller: nameController,
              decoration: const InputDecoration(labelText: 'Department Name'),
              validator: (v) =>
                  v == null || v.trim().isEmpty ? 'Enter a name' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: codeController,
              decoration: const InputDecoration(labelText: 'Code (e.g. CS)'),
              validator: (v) =>
                  v == null || v.trim().isEmpty ? 'Enter a code' : null,
            ),
            // FYP-only: group size + supervisor capacity.
            if (hasFyp) ...[
              const SizedBox(height: 12),
              TextFormField(
                controller: minController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Min Members'),
                validator: (v) =>
                    v == null || int.tryParse(v) == null ? 'Enter a number' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: maxController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Max Members'),
                validator: (v) =>
                    v == null || int.tryParse(v) == null ? 'Enter a number' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: maxGroupsController,
                keyboardType: TextInputType.number,
                decoration:
                    const InputDecoration(labelText: 'Max Groups per Supervisor'),
                validator: (v) =>
                    v == null || int.tryParse(v) == null ? 'Enter a number' : null,
              ),
            ],
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancel'),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: () async {
                    if (!formKey.currentState!.validate()) return;
                    final userId = this.context.read<AuthProvider>().userId;
                    if (userId == null) return;
                    final body = <String, dynamic>{
                      'name': nameController.text.trim(),
                      'code': codeController.text.trim().toUpperCase(),
                    };
                    // Omit FYP fields for core-only orgs; backend keeps defaults / existing.
                    if (hasFyp) {
                      body['min_members'] = int.parse(minController.text.trim());
                      body['max_members'] = int.parse(maxController.text.trim());
                      body['max_groups_per_supervisor'] =
                          int.parse(maxGroupsController.text.trim());
                    }
                    try {
                      if (item == null) {
                        await _api.createDepartment(userId, body);
                      } else {
                        await _api.updateDepartment(userId, item.id, body);
                      }
                      if (!mounted) return;
                      Navigator.pop(context);
                      await _loadDepartments();
                      if (!mounted) return;
                      showAdminSnackBar(
                        this.context,
                        item == null
                            ? 'Department created successfully.'
                            : 'Department updated successfully.',
                      );
                    } catch (e) {
                      if (!mounted) return;
                      showAdminSnackBar(
                        this.context,
                        e.toString(),
                        isError: true,
                      );
                    }
                  },
                  child: const Text('Save'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _deleteDepartment(DepartmentSummary item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AdminColors.surface,
        title: const Text('Delete Department'),
        content: Text('Delete "${item.name}"? This cannot be undone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
        ],
      ),
    );
    if (confirmed != true) return;
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    try {
      await _api.deleteDepartment(userId, item.id);
      await _loadDepartments();
      if (!mounted) return;
      showAdminSnackBar(context, '${item.name} deleted successfully.');
    } catch (e) {
      if (!mounted) return;
      showAdminSnackBar(context, e.toString(), isError: true);
    }
  }

  Widget _buildBody() {
    final list = _loading
        ? const AdminLoadingView()
        : _error != null
            ? AdminErrorView(message: _error!, onRetry: _loadDepartments)
            : _departments.isEmpty
                ? const AdminEmptyView(message: 'No departments yet. Add one to get started.')
                : ListView.builder(
                    padding: widget.embedded ? EdgeInsets.zero : const EdgeInsets.fromLTRB(20, 12, 20, 100),
                    itemCount: _departments.length,
                    itemBuilder: (context, index) {
                      final item = _departments[index];
                      final hasFyp = DevUserConfig.hasFypModule;
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Container(
                          padding: const EdgeInsets.all(16),
                          decoration: adminCardDecoration(),
                          child: Row(
                            children: [
                              Container(
                                width: 44,
                                height: 44,
                                decoration: BoxDecoration(
                                  color: AdminColors.primary.withOpacity(0.14),
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: const Icon(
                                  Icons.apartment_rounded,
                                  color: AdminColors.primary,
                                ),
                              ),
                              const SizedBox(width: 14),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      item.name,
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w600,
                                        color: Colors.white,
                                        fontSize: 16,
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      hasFyp
                                          ? '${item.code} · Members ${item.minMembers}-${item.maxMembers} · Max groups ${item.maxGroupsPerSupervisor}'
                                          : item.code,
                                      style: TextStyle(
                                        color: Colors.white.withOpacity(0.65),
                                        fontSize: 13,
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      hasFyp
                                          ? '${item.supervisorCount} supervisors · ${item.templateCount} templates'
                                          : '${item.templateCount} templates',
                                      style: TextStyle(
                                        color: Colors.white.withOpacity(0.55),
                                        fontSize: 12,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              IconButton(
                                tooltip: 'Edit',
                                onPressed: () => _openDepartmentSheet(item: item),
                                icon: const Icon(Icons.edit_outlined),
                              ),
                              IconButton(
                                tooltip: 'Delete department',
                                onPressed: () => _deleteDepartment(item),
                                icon: const Icon(
                                  Icons.delete_outline,
                                  color: AdminColors.danger,
                                ),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  );

    if (!widget.embedded) return list;

    return AdminPage(
      scrollable: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageHeader(
            title: 'Department Manager',
            subtitle: 'Create and manage academic departments',
            trailing: ElevatedButton.icon(
              onPressed: () => _openDepartmentSheet(),
              icon: const Icon(Icons.add),
              label: const Text('Add Department'),
            ),
          ),
          const SizedBox(height: 20),
          Expanded(child: list),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (widget.embedded) return _buildBody();

    return AdminSubPage(
      title: 'Department Manager',
      subtitle: 'Create and manage academic departments',
      onRefresh: _loadDepartments,
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _openDepartmentSheet(),
        backgroundColor: AdminColors.primary,
        icon: const Icon(Icons.add),
        label: const Text('Add Department'),
      ),
      child: _buildBody(),
    );
  }
}
