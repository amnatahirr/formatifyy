import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/admin_models.dart';
import '../../providers/auth_provider.dart';
import '../../screens/template_configuration_screen.dart';
import '../../services/admin_api_service.dart';
import '../../widgets/admin/admin_ui.dart';

import '../../widgets/tr.dart';
class TemplateListScreen extends StatefulWidget {
  final DepartmentSummary department;

  const TemplateListScreen({super.key, required this.department});

  @override
  State<TemplateListScreen> createState() => _TemplateListScreenState();
}

class _TemplateListScreenState extends State<TemplateListScreen> {
  final AdminApiService _api = AdminApiService();
  bool _loading = true;
  bool _changed = false;
  String? _error;
  List<AdminTemplateModel> _templates = const [];

  @override
  void initState() {
    super.initState();
    _loadTemplates();
  }

  Future<void> _loadTemplates() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final templates = await _api.fetchTemplates(userId, departmentId: widget.department.id);
      if (mounted) setState(() => _templates = templates);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openCreateTemplate() async {
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => TemplateConfigurationScreen(
          departmentId: widget.department.id,
          standalone: true,
        ),
      ),
    );
    if (created == true) {
      _changed = true;
      await _loadTemplates();
    }
  }

  Future<void> _confirmDelete(AdminTemplateModel item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AdminColors.surface,
        title: const Tr('Delete Template'),
        content: Text('Delete "${item.name}"? This cannot be undone.'),
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
      await _api.deleteTemplate(userId, item.id);
      _changed = true;
      await _loadTemplates();
      if (!mounted) return;
      showAdminSnackBar(context, '${item.name} deleted successfully.');
    } catch (e) {
      if (!mounted) return;
      showAdminSnackBar(context, e.toString(), isError: true);
    }
  }

  Future<void> _openTemplateSheet(AdminTemplateModel item) async {
    final nameController = TextEditingController(text: item.name);
    final descriptionController = TextEditingController(text: item.description);
    final rulesController = TextEditingController(
      text: const JsonEncoder.withIndent('  ').convert(item.formattingRules),
    );
    final formKey = GlobalKey<FormState>();

    await showAdminBottomSheet(
      context: context,
      title: 'Edit Template',
      child: Form(
        key: formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextFormField(
              controller: nameController,
              decoration: const InputDecoration(labelText: 'Template Name'),
              validator: (value) => value == null || value.trim().isEmpty ? 'Enter a template name' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: descriptionController,
              decoration: const InputDecoration(labelText: 'Description (optional)'),
              maxLines: 2,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: rulesController,
              minLines: 8,
              maxLines: 12,
              style: const TextStyle(fontFamily: 'monospace'),
              decoration: const InputDecoration(labelText: 'Rules'),
              validator: (value) => value == null || value.trim().isEmpty ? 'Enter template rules JSON' : null,
            ),
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(onPressed: () => Navigator.pop(context), child: const Tr('Cancel')),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: () async {
                    if (!formKey.currentState!.validate()) return;
                    final userId = this.context.read<AuthProvider>().userId;
                    if (userId == null) return;
                    try {
                      final Map<String, dynamic> rules = Map<String, dynamic>.from(
                        jsonDecode(rulesController.text.trim()) as Map<String, dynamic>,
                      );
                      final body = {
                        'name': nameController.text.trim(),
                        'description': descriptionController.text.trim(),
                        'required_sections': item.requiredSections,
                        'formatting_rules': rules,
                      };
                      await _api.updateTemplate(userId, item.id, body, departmentId: widget.department.id);
                      if (!mounted) return;
                      Navigator.pop(context);
                      _changed = true;
                      await _loadTemplates();
                      if (!mounted) return;
                      showAdminSnackBar(this.context, 'Template updated successfully.');
                    } catch (e) {
                      if (!mounted) return;
                      showAdminSnackBar(this.context, 'Could not save template: $e', isError: true);
                    }
                  },
                  child: const Tr('Save'),
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
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (didPop) return;
        Navigator.of(context).pop(_changed);
      },
      child: AdminSubPage(
        title: widget.department.name,
        subtitle: 'Department templates and formatting rules',
        onRefresh: _loadTemplates,
        onBack: () => Navigator.of(context).pop(_changed),
        floatingActionButton: FloatingActionButton.extended(
          onPressed: _openCreateTemplate,
          backgroundColor: AdminColors.primary,
          icon: const Icon(Icons.add),
          label: const Tr('Create Template'),
        ),
        child: _loading
            ? const AdminLoadingView()
            : _error != null
                ? AdminErrorView(message: _error!, onRetry: _loadTemplates)
                : _templates.isEmpty
                    ? const AdminEmptyView(message: 'No templates are configured for this department yet.')
                    : ListView.builder(
                        padding: const EdgeInsets.fromLTRB(20, 12, 20, 100),
                        itemCount: _templates.length,
                        itemBuilder: (context, index) {
                          final item = _templates[index];
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
                                        child: Text(item.name, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white)),
                                      ),
                                      IconButton(onPressed: () => _openTemplateSheet(item), icon: const Icon(Icons.edit_outlined)),
                                      IconButton(onPressed: () => _confirmDelete(item), icon: const Icon(Icons.delete_outline)),
                                    ],
                                  ),
                                  const SizedBox(height: 8),
                                  Text(item.rulesPreview, style: TextStyle(color: Colors.white.withOpacity(0.75))),
                                  const SizedBox(height: 8),
                                  Text('Created: ${item.createdAt}', style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 12)),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
      ),
    );
  }
}
