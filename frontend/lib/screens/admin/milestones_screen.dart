import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/admin_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/admin_api_service.dart';
import '../../widgets/admin/admin_ui.dart';

import '../../widgets/tr.dart';

/// Admin: FYP milestones per department (semester 6 / 7 / 8) with deadlines.
class MilestonesScreen extends StatefulWidget {
  final bool embedded;

  const MilestonesScreen({super.key, this.embedded = false});

  @override
  State<MilestonesScreen> createState() => _MilestonesScreenState();
}

class _MilestonesScreenState extends State<MilestonesScreen> {
  final AdminApiService _api = AdminApiService();
  bool _loading = true;
  String? _error;
  List<MilestoneModel> _items = const [];
  List<DepartmentSummary> _departments = const [];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        _api.fetchMilestones(userId),
        _api.fetchDepartments(userId),
      ]);
      if (mounted) {
        setState(() {
          _items = results[0] as List<MilestoneModel>;
          _departments = results[1] as List<DepartmentSummary>;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _displayDate(String raw) {
    final date = DateTime.tryParse(raw);
    if (date == null) return raw;
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${date.day} ${months[date.month - 1]} ${date.year}';
  }

  int _daysRemaining(String raw) {
    final d = DateTime.tryParse(raw);
    if (d == null) return 0;
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    return DateTime(d.year, d.month, d.day).difference(today).inDays;
  }

  Color _badgeColor(int days) {
    if (days >= 14) return AdminColors.success;
    if (days >= 7) return AdminColors.warning;
    return AdminColors.danger;
  }

  Future<void> _openSheet({MilestoneModel? item}) async {
    final nameController = TextEditingController(text: item?.name ?? '');
    DateTime? selectedDate = item == null ? null : DateTime.tryParse(item.deadlineDate);
    int? selectedDepartmentId = item?.departmentId;
    int? selectedSemester = item?.semester;
    final formKey = GlobalKey<FormState>();
    var saving = false;

    await showAdminBottomSheet(
      context: context,
      title: item == null ? 'Add Milestone' : 'Edit Milestone',
      subtitle: item == null
          ? 'Create a milestone for a department with its semester and deadline'
          : 'Update this milestone’s name, semester or deadline',
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
                    label: 'Milestone name',
                    hint: 'e.g. Proposal Defense',
                    prefixIcon: Icons.flag_rounded,
                  ),
                  validator: (v) => v == null || v.trim().isEmpty ? 'Enter a milestone name' : null,
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<int>(
                  value: selectedDepartmentId,
                  dropdownColor: AdminColors.card,
                  style: const TextStyle(color: Colors.white),
                  decoration: adminFieldDecoration(
                    label: 'Department',
                    prefixIcon: Icons.apartment_rounded,
                  ),
                  items: _departments
                      .map((d) => DropdownMenuItem<int>(value: d.id, child: Text(d.name)))
                      .toList(),
                  onChanged: item == null
                      ? (v) => setSheetState(() => selectedDepartmentId = v)
                      : null,
                  validator: (v) => v == null ? 'Choose a department' : null,
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<int>(
                  value: selectedSemester,
                  dropdownColor: AdminColors.card,
                  style: const TextStyle(color: Colors.white),
                  decoration: adminFieldDecoration(
                    label: 'Semester',
                    prefixIcon: Icons.school_rounded,
                  ),
                  items: const [
                    DropdownMenuItem<int>(value: 6, child: Tr('Proposal (Semester 6)')),
                    DropdownMenuItem<int>(value: 7, child: Tr('FYP-1 (Semester 7)')),
                    DropdownMenuItem<int>(value: 8, child: Tr('FYP-2 (Semester 8)')),
                  ],
                  onChanged: (v) => setSheetState(() => selectedSemester = v),
                  validator: (v) => v == null ? 'Choose a semester' : null,
                ),
                const SizedBox(height: 14),
                InkWell(
                  onTap: () async {
                    final picked = await showDatePicker(
                      context: sheetContext,
                      firstDate: DateTime(2020),
                      lastDate: DateTime(2100),
                      initialDate: selectedDate ?? DateTime.now(),
                      builder: (context, child) {
                        return Theme(
                          data: Theme.of(context).copyWith(
                            colorScheme: const ColorScheme.dark(
                              primary: AdminColors.primary,
                              surface: AdminColors.surface,
                            ),
                          ),
                          child: child!,
                        );
                      },
                    );
                    if (picked != null) setSheetState(() => selectedDate = picked);
                  },
                  borderRadius: BorderRadius.circular(12),
                  child: InputDecorator(
                    decoration: adminFieldDecoration(
                      label: 'Deadline',
                      prefixIcon: Icons.calendar_month_rounded,
                    ),
                    child: Text(
                      selectedDate == null
                          ? 'Choose deadline'
                          : _displayDate(selectedDate!.toIso8601String()),
                      style: TextStyle(
                        color: selectedDate == null ? Colors.white.withOpacity(0.4) : Colors.white,
                        fontSize: 15,
                      ),
                    ),
                  ),
                ),
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
                    'Students and group members get email reminders 3 days before, 1 day before and on the deadline. '
                    'Promoting a group marks that semester’s milestones completed.',
                    style: TextStyle(color: Colors.white.withOpacity(0.78), height: 1.4, fontSize: 13),
                  ),
                ),
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
                        child: const Tr('Cancel'),
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
                                if (selectedDate == null) {
                                  showAdminSnackBar(this.context, 'Please choose a deadline.', isError: true);
                                  return;
                                }
                                final userId = this.context.read<AuthProvider>().userId;
                                if (userId == null) return;
                                setSheetState(() => saving = true);
                                final body = <String, dynamic>{
                                  'name': nameController.text.trim(),
                                  'semester': selectedSemester,
                                  'deadline_date': selectedDate!.toIso8601String().split('T').first,
                                  if (item == null) 'department_id': selectedDepartmentId,
                                };
                                try {
                                  if (item == null) {
                                    await _api.createMilestone(userId, body);
                                  } else {
                                    await _api.updateMilestone(userId, item.id, body);
                                  }
                                  if (!mounted) return;
                                  Navigator.pop(sheetContext);
                                  await _loadData();
                                  if (!mounted) return;
                                  showAdminSnackBar(
                                    this.context,
                                    item == null ? 'Milestone created successfully.' : 'Milestone updated successfully.',
                                  );
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
                            : Text(item == null ? 'Create Milestone' : 'Save Changes'),
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

  Future<void> _deleteMilestone(MilestoneModel item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AdminColors.surface,
        title: const Tr('Delete Milestone'),
        content: Text(
          'Delete "${item.name}" (${item.departmentName})? '
          'It will also disappear from every group of this department.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Tr('Cancel')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Tr('Delete')),
        ],
      ),
    );
    if (confirmed != true) return;
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    try {
      await _api.deleteMilestone(userId, item.id);
      await _loadData();
      if (!mounted) return;
      showAdminSnackBar(context, '${item.name} deleted successfully.');
    } catch (e) {
      if (!mounted) return;
      showAdminSnackBar(context, e.toString(), isError: true);
    }
  }

  Future<void> _copyMilestones() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    int? fromId;
    int? toId;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: AdminColors.surface,
          title: const Tr('Copy Milestones'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<int>(
                value: fromId,
                dropdownColor: AdminColors.card,
                style: const TextStyle(color: Colors.white),
                decoration: adminFieldDecoration(label: 'Copy from'),
                items: _departments
                    .map((d) => DropdownMenuItem<int>(value: d.id, child: Text(d.name)))
                    .toList(),
                onChanged: (v) => setDialogState(() => fromId = v),
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<int>(
                value: toId,
                dropdownColor: AdminColors.card,
                style: const TextStyle(color: Colors.white),
                decoration: adminFieldDecoration(label: 'Copy to'),
                items: _departments
                    .map((d) => DropdownMenuItem<int>(value: d.id, child: Text(d.name)))
                    .toList(),
                onChanged: (v) => setDialogState(() => toId = v),
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Tr('Cancel')),
            TextButton(
              onPressed: (fromId == null || toId == null || fromId == toId)
                  ? null
                  : () => Navigator.pop(ctx, true),
              child: const Tr('Copy'),
            ),
          ],
        ),
      ),
    );
    if (ok != true || fromId == null || toId == null) return;
    try {
      final r = await _api.copyMilestones(
        userId,
        fromDepartmentId: fromId!,
        toDepartmentId: toId!,
      );
      await _loadData();
      if (!mounted) return;
      showAdminSnackBar(context, '${r['copied']} copied, ${r['skipped']} skipped (already existed).');
    } catch (e) {
      if (!mounted) return;
      showAdminSnackBar(context, e.toString(), isError: true);
    }
  }

  Widget _buildList() {
    if (_loading) return const AdminLoadingView();
    if (_error != null) return AdminErrorView(message: _error!, onRetry: _loadData);
    if (_items.isEmpty) {
      return const AdminEmptyView(
        message: 'No milestones yet. Add milestones per department; until then students see the default milestones.',
      );
    }

    final byDept = <String, List<MilestoneModel>>{};
    for (final m in _items) {
      final key = m.departmentName.isEmpty ? 'Department ${m.departmentId}' : m.departmentName;
      byDept.putIfAbsent(key, () => []).add(m);
    }
    final deptNames = byDept.keys.toList()..sort();

    return ListView(
      padding: widget.embedded ? EdgeInsets.zero : const EdgeInsets.fromLTRB(20, 12, 20, 100),
      children: [
        for (final dept in deptNames) ...[
          Padding(
            padding: const EdgeInsets.only(top: 6, bottom: 10),
            child: Text(
              dept,
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: Colors.white),
            ),
          ),
          for (final item in byDept[dept]!) _milestoneCard(item),
          const SizedBox(height: 10),
        ],
      ],
    );
  }

  Widget _milestoneCard(MilestoneModel item) {
    final days = _daysRemaining(item.deadlineDate);
    final color = _badgeColor(days);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: adminCardDecoration(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    item.name,
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white),
                  ),
                ),
                IconButton(
                  tooltip: 'Edit milestone',
                  onPressed: () => _openSheet(item: item),
                  icon: const Icon(Icons.edit_outlined),
                ),
                IconButton(
                  tooltip: 'Delete milestone',
                  onPressed: () => _deleteMilestone(item),
                  icon: const Icon(Icons.delete_outline, color: AdminColors.danger),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                AdminPill(
                  label: 'Semester ${item.semester}${item.phase.isEmpty ? '' : ' · ${item.phase}'}',
                  color: AdminColors.primary,
                ),
                Text(
                  _displayDate(item.deadlineDate),
                  style: TextStyle(color: Colors.white.withOpacity(0.75)),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    days < 0 ? '${days.abs()} day(s) overdue' : '$days day(s) remaining',
                    style: TextStyle(color: color, fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (widget.embedded) {
      return AdminPage(
        scrollable: false,
        onRefresh: _loadData,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                OutlinedButton.icon(
                  onPressed: _copyMilestones,
                  icon: const Icon(Icons.copy_all_rounded),
                  label: const Tr('Copy to Department'),
                ),
                const SizedBox(width: 8),
                ElevatedButton.icon(
                  onPressed: () => _openSheet(),
                  icon: const Icon(Icons.add),
                  label: const Tr('Add Milestone'),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Expanded(child: _buildList()),
          ],
        ),
      );
    }

    return AdminSubPage(
      title: 'Milestones',
      subtitle: 'Department milestones by semester',
      onRefresh: _loadData,
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _openSheet(),
        backgroundColor: AdminColors.primary,
        icon: const Icon(Icons.add),
        label: const Tr('Add Milestone'),
      ),
      child: _buildList(),
    );
  }
}