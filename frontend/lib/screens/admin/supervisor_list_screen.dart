import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/admin_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/admin_api_service.dart';
import '../../widgets/admin/admin_ui.dart';

class SupervisorListScreen extends StatefulWidget {
  final DepartmentSummary department;

  const SupervisorListScreen({super.key, required this.department});

  @override
  State<SupervisorListScreen> createState() => _SupervisorListScreenState();
}

class _SupervisorListScreenState extends State<SupervisorListScreen> {
  final AdminApiService _api = AdminApiService();
  final TextEditingController _searchController = TextEditingController();

  bool _loading = true;
  bool _changed = false;
  String? _error;
  String _filter = 'All';
  List<SupervisorModel> _supervisors = const [];

  @override
  void initState() {
    super.initState();
    _searchController.addListener(() => setState(() {}));
    _loadSupervisors();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _markChanged() {
    _changed = true;
  }

  Future<void> _loadSupervisors() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await _api.fetchSupervisors(
        userId,
        departmentId: widget.department.id,
        search: _searchController.text.trim().isEmpty ? null : _searchController.text.trim(),
      );
      if (mounted) setState(() => _supervisors = data);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  List<SupervisorModel> get _filtered {
    final query = _searchController.text.trim().toLowerCase();
    return _supervisors.where((item) {
      final matchesQuery = query.isEmpty ||
          item.name.toLowerCase().contains(query) ||
          item.email.toLowerCase().contains(query);
      final matchesFilter = _filter == 'All' ||
          (_filter == 'Active' && item.isActive) ||
          (_filter == 'Inactive' && !item.isActive);
      return matchesQuery && matchesFilter;
    }).toList();
  }

  Future<void> _toggleSupervisor(SupervisorModel item) async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    try {
      await _api.toggleSupervisor(userId, item.id);
      await _loadSupervisors();
      _markChanged();
      if (!mounted) return;
      showAdminSnackBar(context, '${item.name} status updated successfully.');
    } catch (e) {
      if (!mounted) return;
      showAdminSnackBar(context, e.toString(), isError: true);
    }
  }

  Future<void> _deleteSupervisor(SupervisorModel item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AdminColors.surface,
        title: const Text('Delete Supervisor'),
        content: Text('Are you sure you want to delete ${item.name}?'),
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
      await _api.deleteSupervisor(userId, item.id);
      await _loadSupervisors();
      _markChanged();
      if (!mounted) return;
      showAdminSnackBar(context, '${item.name} deleted successfully.');
    } catch (e) {
      if (!mounted) return;
      showAdminSnackBar(context, e.toString(), isError: true);
    }
  }

  Future<void> _openSupervisorSheet({SupervisorModel? item}) async {
    final nameController = TextEditingController(text: item?.name ?? '');
    final emailController = TextEditingController(text: item?.email ?? '');
    final maxGroupsController = TextEditingController(text: '${item?.maxGroups ?? widget.department.maxGroupsPerSupervisor}');
    final currentGroupsController = TextEditingController(text: '${item?.currentGroups ?? 0}');
    final formKey = GlobalKey<FormState>();
    var saving = false;

    await showAdminBottomSheet(
      context: context,
      title: item == null ? 'Add Supervisor' : 'Edit Supervisor',
      subtitle: item == null
          ? 'Create a login account and assign them to ${widget.department.name}'
          : 'Update supervisor details for ${widget.department.name}',
      child: StatefulBuilder(
        builder: (sheetContext, setSheetState) {
          return Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextFormField(
                  controller: nameController,
                  style: const TextStyle(color: Colors.white),
                  decoration: adminFieldDecoration(
                    label: 'Full name',
                    hint: 'e.g. Dr. Ahmed Ali',
                    prefixIcon: Icons.person_outline_rounded,
                  ),
                  validator: (value) => value == null || value.trim().isEmpty ? 'Enter a supervisor name' : null,
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: emailController,
                  style: const TextStyle(color: Colors.white),
                  keyboardType: TextInputType.emailAddress,
                  decoration: adminFieldDecoration(
                    label: 'Email address',
                    hint: 'name@university.edu',
                    prefixIcon: Icons.email_outlined,
                  ),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) return 'Enter an email address';
                    if (!value.contains('@')) return 'Enter a valid email';
                    return null;
                  },
                ),
                const SizedBox(height: 14),
                TextFormField(
                  initialValue: widget.department.name,
                  enabled: false,
                  style: TextStyle(color: Colors.white.withOpacity(0.75)),
                  decoration: adminFieldDecoration(
                    label: 'Department',
                    prefixIcon: Icons.apartment_rounded,
                  ),
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: maxGroupsController,
                  style: const TextStyle(color: Colors.white),
                  keyboardType: TextInputType.number,
                  decoration: adminFieldDecoration(
                    label: 'Max groups',
                    hint: 'Maximum groups this supervisor can handle',
                    prefixIcon: Icons.groups_outlined,
                  ),
                  validator: (value) => value == null || int.tryParse(value) == null ? 'Enter a valid group limit' : null,
                ),
                if (item != null) ...[
                  const SizedBox(height: 14),
                  TextFormField(
                    controller: currentGroupsController,
                    style: const TextStyle(color: Colors.white),
                    keyboardType: TextInputType.number,
                    decoration: adminFieldDecoration(
                      label: 'Current groups',
                      prefixIcon: Icons.tag_rounded,
                    ),
                    validator: (value) => value == null || int.tryParse(value) == null ? 'Enter a valid current group count' : null,
                  ),
                ],
                if (item == null) ...[
                  const SizedBox(height: 16),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: AdminColors.primary.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AdminColors.primary.withOpacity(0.25)),
                    ),
                    child: Text(
                      'A temporary password will be generated. You can copy it or email it to the supervisor after saving.',
                      style: TextStyle(color: Colors.white.withOpacity(0.78), height: 1.4, fontSize: 13),
                    ),
                  ),
                ],
                const SizedBox(height: 22),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: saving ? null : () => Navigator.pop(sheetContext),
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          side: const BorderSide(color: AdminColors.border),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        child: const Text('Cancel'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      flex: 2,
                      child: ElevatedButton(
                        onPressed: saving
                            ? null
                            : () async {
                                if (!formKey.currentState!.validate()) return;
                                final userId = this.context.read<AuthProvider>().userId;
                                if (userId == null) return;
                                setSheetState(() => saving = true);
                                final body = {
                                  'name': nameController.text.trim(),
                                  'email': emailController.text.trim(),
                                  'department_id': widget.department.id,
                                  'max_groups': int.parse(maxGroupsController.text.trim()),
                                  'current_groups': int.tryParse(currentGroupsController.text.trim()) ?? item?.currentGroups ?? 0,
                                  'is_active': item?.isActive ?? true,
                                };
                                try {
                                  if (item == null) {
                                    final result = await _api.createSupervisor(userId, body);
                                    if (!mounted) return;
                                    Navigator.pop(sheetContext);
                                    await _loadSupervisors();
                                    _markChanged();
                                    if (!mounted) return;
                                    final supervisor = Map<String, dynamic>.from(result['supervisor'] as Map? ?? {});
                                    final tempPassword = (result['temporary_password'] ?? '').toString();
                                    final createdName = (supervisor['name'] ?? body['name']).toString();
                                    final createdEmail = (supervisor['email'] ?? body['email']).toString();
                                    final supervisorId = supervisor['id'] is int
                                        ? supervisor['id'] as int
                                        : int.tryParse('${supervisor['id']}') ?? 0;

                                    await showSupervisorCredentialsDialog(
                                      context: this.context,
                                      name: createdName,
                                      email: createdEmail,
                                      temporaryPassword: tempPassword,
                                      onSendEmail: () async {
                                        if (supervisorId == 0) throw Exception('Missing supervisor id');
                                        await _api.sendSupervisorCredentials(
                                          userId,
                                          supervisorId,
                                          temporaryPassword: tempPassword,
                                        );
                                      },
                                    );
                                  } else {
                                    await _api.updateSupervisor(userId, item.id, body);
                                    if (!mounted) return;
                                    Navigator.pop(sheetContext);
                                    await _loadSupervisors();
                                    _markChanged();
                                    if (!mounted) return;
                                    showAdminSnackBar(this.context, 'Supervisor updated successfully.');
                                  }
                                } catch (e) {
                                  if (!mounted) return;
                                  setSheetState(() => saving = false);
                                  showAdminSnackBar(this.context, e.toString(), isError: true);
                                }
                              },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AdminColors.primary,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        child: saving
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                              )
                            : Text(item == null ? 'Create Supervisor' : 'Save Changes'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final supervisors = _filtered;
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (didPop) return;
        Navigator.of(context).pop(_changed);
      },
      child: AdminSubPage(
        title: widget.department.name,
        subtitle: 'Manage supervisors for this department',
        onRefresh: _loadSupervisors,
        onBack: () => Navigator.of(context).pop(_changed),
        floatingActionButton: FloatingActionButton.extended(
          onPressed: () => _openSupervisorSheet(),
          backgroundColor: AdminColors.primary,
          label: const Text('Add Supervisor'),
          icon: const Icon(Icons.add),
        ),
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  TextField(
                    controller: _searchController,
                    decoration: InputDecoration(
                      hintText: 'Search by name or email',
                      prefixIcon: const Icon(Icons.search),
                      suffixIcon: IconButton(
                        onPressed: _loadSupervisors,
                        icon: const Icon(Icons.refresh),
                      ),
                    ),
                    onChanged: (_) => _loadSupervisors(),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: ['All', 'Active', 'Inactive']
                        .map(
                          (label) => Padding(
                            padding: const EdgeInsets.only(right: 8),
                            child: ChoiceChip(
                              label: Text(label),
                              selected: _filter == label,
                              onSelected: (_) => setState(() => _filter = label),
                            ),
                          ),
                        )
                        .toList(),
                  ),
                ],
              ),
            ),
            Expanded(
              child: _loading
                  ? const AdminLoadingView()
                  : _error != null
                      ? AdminErrorView(message: _error!, onRetry: _loadSupervisors)
                      : supervisors.isEmpty
                          ? const AdminEmptyView(message: 'No supervisors match this department yet. Add one or adjust your filters.')
                          : ListView.builder(
                              padding: const EdgeInsets.fromLTRB(20, 0, 20, 100),
                              itemCount: supervisors.length,
                              itemBuilder: (context, index) {
                                final item = supervisors[index];
                                return Padding(
                                  padding: const EdgeInsets.only(bottom: 12),
                                  child: Container(
                                    decoration: adminCardDecoration(),
                                    child: InkWell(
                                      borderRadius: BorderRadius.circular(14),
                                      onTap: () => _openSupervisorSheet(item: item),
                                      child: Padding(
                                        padding: const EdgeInsets.all(16),
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            Row(
                                              children: [
                                                Expanded(
                                                  child: Column(
                                                    crossAxisAlignment: CrossAxisAlignment.start,
                                                    children: [
                                                      Text(item.name, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white)),
                                                      const SizedBox(height: 4),
                                                      Text(item.email, style: TextStyle(color: Colors.white.withOpacity(0.7))),
                                                    ],
                                                  ),
                                                ),
                                              Container(
                                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                                decoration: BoxDecoration(
                                                  color: AdminColors.primary.withOpacity(0.15),
                                                  borderRadius: BorderRadius.circular(20),
                                                ),
                                                child: Text('${item.currentGroups}/${item.maxGroups}', style: const TextStyle(color: AdminColors.primary, fontWeight: FontWeight.w600)),
                                              ),
                                              IconButton(
                                                tooltip: 'Delete supervisor',
                                                onPressed: () => _deleteSupervisor(item),
                                                icon: const Icon(Icons.delete_outline, color: AdminColors.danger),
                                              ),
                                              ],
                                            ),
                                          const SizedBox(height: 12),
                                          Row(
                                            children: [
                                              Text(item.isActive ? 'Active' : 'Inactive'),
                                              const SizedBox(width: 8),
                                              Switch(value: item.isActive, activeColor: AdminColors.primary, onChanged: (_) => _toggleSupervisor(item)),
                                            ],
                                          ),
                                          ],
                                        ),
                                      ),
                                    ),
                                  ),
                                );
                              },
                            ),
            ),
          ],
        ),
      ),
    );
  }
}
