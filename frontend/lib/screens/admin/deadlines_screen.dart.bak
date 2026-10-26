import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/admin_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/admin_api_service.dart';
import '../../widgets/admin/admin_ui.dart';

class DeadlinesScreen extends StatefulWidget {
  final bool embedded;

  const DeadlinesScreen({super.key, this.embedded = false});

  @override
  State<DeadlinesScreen> createState() => _DeadlinesScreenState();
}

class _DeadlinesScreenState extends State<DeadlinesScreen> {
  final AdminApiService _api = AdminApiService();
  bool _loading = true;
  String? _error;
  List<DeadlineModel> _deadlines = const [];
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
        _api.fetchDeadlines(userId),
        _api.fetchDepartments(userId),
      ]);
      if (mounted) {
        setState(() {
          _deadlines = results[0] as List<DeadlineModel>;
          _departments = results[1] as List<DepartmentSummary>;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Color _badgeColor(int daysRemaining) {
    if (daysRemaining >= 14) return AdminColors.success;
    if (daysRemaining >= 7) return AdminColors.warning;
    return AdminColors.danger;
  }

  int _daysRemaining(String dueDate) {
    final date = DateTime.tryParse(dueDate);
    if (date == null) return 0;
    return date.difference(DateTime.now()).inDays;
  }

  String _displayDate(String raw) {
    final date = DateTime.tryParse(raw);
    if (date == null) return raw;
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${date.day} ${months[date.month - 1]} ${date.year}';
  }

  Future<void> _openDeadlineSheet({DeadlineModel? item}) async {
    final titleController = TextEditingController(text: item?.title ?? '');
    final descriptionController = TextEditingController(text: item?.description ?? '');
    DateTime? selectedDate = item?.dueDate.isNotEmpty == true ? DateTime.tryParse(item!.dueDate) : null;
    int? selectedDepartmentId = item?.appliesToAll == true ? null : item?.departmentId;
    final formKey = GlobalKey<FormState>();
    var saving = false;

    await showAdminBottomSheet(
      context: context,
      title: item == null ? 'Add Deadline' : 'Edit Deadline',
      subtitle: item == null
          ? 'Schedule a submission date for a department or the whole university'
          : 'Update this deadline’s title, date, or department scope',
      child: StatefulBuilder(
        builder: (sheetContext, setSheetState) {
          return Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextFormField(
                  controller: titleController,
                  style: const TextStyle(color: Colors.white),
                  decoration: adminFieldDecoration(
                    label: 'Deadline title',
                    hint: 'e.g. Proposal submission',
                    prefixIcon: Icons.title_rounded,
                  ),
                  validator: (value) => value == null || value.trim().isEmpty ? 'Enter a deadline title' : null,
                ),
                const SizedBox(height: 14),
                TextFormField(
                  controller: descriptionController,
                  style: const TextStyle(color: Colors.white),
                  maxLines: 3,
                  decoration: adminFieldDecoration(
                    label: 'Description (optional)',
                    hint: 'Short note for students and supervisors',
                    prefixIcon: Icons.notes_rounded,
                  ),
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
                    if (picked != null) {
                      setSheetState(() => selectedDate = picked);
                    }
                  },
                  borderRadius: BorderRadius.circular(12),
                  child: InputDecorator(
                    decoration: adminFieldDecoration(
                      label: 'Due date',
                      prefixIcon: Icons.calendar_month_rounded,
                    ),
                    child: Text(
                      selectedDate == null ? 'Choose due date' : _displayDate(selectedDate!.toIso8601String()),
                      style: TextStyle(
                        color: selectedDate == null ? Colors.white.withOpacity(0.4) : Colors.white,
                        fontSize: 15,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<int?>(
                  value: selectedDepartmentId,
                  dropdownColor: AdminColors.card,
                  style: const TextStyle(color: Colors.white),
                  decoration: adminFieldDecoration(
                    label: 'Applies to',
                    prefixIcon: Icons.apartment_rounded,
                  ),
                  items: [
                    const DropdownMenuItem<int?>(value: null, child: Text('All Departments')),
                    ..._departments.map((d) => DropdownMenuItem<int?>(value: d.id, child: Text(d.name))),
                  ],
                  onChanged: (value) => setSheetState(() => selectedDepartmentId = value),
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
                    selectedDepartmentId == null
                        ? 'This deadline will apply to every department.'
                        : 'This deadline will only apply to the selected department.',
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
                                if (selectedDate == null) {
                                  showAdminSnackBar(this.context, 'Please choose a due date.', isError: true);
                                  return;
                                }
                                final userId = this.context.read<AuthProvider>().userId;
                                if (userId == null) return;
                                setSheetState(() => saving = true);
                                final body = {
                                  'title': titleController.text.trim(),
                                  'description': descriptionController.text.trim(),
                                  'due_date': selectedDate!.toIso8601String().split('T').first,
                                  'department_id': selectedDepartmentId,
                                  'applies_to_all': selectedDepartmentId == null,
                                };
                                try {
                                  if (item == null) {
                                    await _api.createDeadline(userId, body);
                                  } else {
                                    await _api.updateDeadline(userId, item.id, body);
                                  }
                                  if (!mounted) return;
                                  Navigator.pop(sheetContext);
                                  await _loadData();
                                  if (!mounted) return;
                                  showAdminSnackBar(
                                    this.context,
                                    item == null ? 'Deadline created successfully.' : 'Deadline updated successfully.',
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
                            : Text(item == null ? 'Create Deadline' : 'Save Changes'),
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

  Future<void> _deleteDeadline(DeadlineModel item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AdminColors.surface,
        title: const Text('Delete Deadline'),
        content: Text('Delete "${item.title}"?'),
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
      await _api.deleteDeadline(userId, item.id);
      await _loadData();
      if (!mounted) return;
      showAdminSnackBar(context, '${item.title} deleted successfully.');
    } catch (e) {
      if (!mounted) return;
      showAdminSnackBar(context, e.toString(), isError: true);
    }
  }

  Widget _buildList() {
    if (_loading) return const AdminLoadingView();
    if (_error != null) return AdminErrorView(message: _error!, onRetry: _loadData);
    if (_deadlines.isEmpty) {
      return const AdminEmptyView(message: 'No deadlines have been scheduled yet. Add one to help departments stay on track.');
    }
    return ListView.builder(
      padding: widget.embedded ? EdgeInsets.zero : const EdgeInsets.fromLTRB(20, 12, 20, 100),
      itemCount: _deadlines.length,
      itemBuilder: (context, index) {
        final item = _deadlines[index];
        final daysRemaining = _daysRemaining(item.dueDate);
        final badgeColor = _badgeColor(daysRemaining);
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
                        item.title,
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white),
                      ),
                    ),
                    IconButton(onPressed: () => _openDeadlineSheet(item: item), icon: const Icon(Icons.edit_outlined)),
                    IconButton(
                      tooltip: 'Delete deadline',
                      onPressed: () => _deleteDeadline(item),
                      icon: const Icon(Icons.delete_outline, color: AdminColors.danger),
                    ),
                  ],
                ),
                if (item.description.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(item.description, style: TextStyle(color: Colors.white.withOpacity(0.72))),
                ],
                const SizedBox(height: 8),
                Text(_displayDate(item.dueDate), style: TextStyle(color: Colors.white.withOpacity(0.75))),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: badgeColor.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    daysRemaining < 0 ? '${daysRemaining.abs()} day(s) overdue' : '$daysRemaining day(s) remaining',
                    style: TextStyle(color: badgeColor, fontWeight: FontWeight.w600),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  item.appliesToAll ? 'All Departments' : (item.departmentName ?? 'Unknown Department'),
                  style: TextStyle(color: Colors.white.withOpacity(0.65)),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    if (widget.embedded) {
      return Stack(
        children: [
          AdminPage(
            scrollable: false,
            onRefresh: _loadData,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Align(
                  alignment: Alignment.centerRight,
                  child: ElevatedButton.icon(
                    onPressed: () => _openDeadlineSheet(),
                    icon: const Icon(Icons.add),
                    label: const Text('Add Deadline'),
                  ),
                ),
                const SizedBox(height: 16),
                Expanded(child: _buildList()),
              ],
            ),
          ),
        ],
      );
    }

    return AdminSubPage(
      title: 'Deadlines',
      subtitle: 'Department submission dates and reminders',
      onRefresh: _loadData,
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _openDeadlineSheet(),
        backgroundColor: AdminColors.primary,
        icon: const Icon(Icons.add),
        label: const Text('Add Deadline'),
      ),
      child: _buildList(),
    );
  }
}
