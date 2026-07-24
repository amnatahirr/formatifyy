import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/admin_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/admin_api_service.dart';
import 'common_widgets.dart';

/// University / department / session branding for generated cover pages.
/// Persists to admin_settings (same keys frontmatter_data already reads).
class FrontmatterBrandingCard extends StatefulWidget {
  const FrontmatterBrandingCard({super.key});

  @override
  State<FrontmatterBrandingCard> createState() => _FrontmatterBrandingCardState();
}

class _FrontmatterBrandingCardState extends State<FrontmatterBrandingCard> {
  final AdminApiService _api = AdminApiService();
  final _universityController = TextEditingController();
  final _sessionController = TextEditingController();

  bool _loading = true;
  bool _saving = false;
  String? _error;
  List<DepartmentSummary> _departments = const [];
  String? _selectedDepartmentName;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _universityController.dispose();
    _sessionController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        _api.fetchFrontmatterConfig(userId),
        _api.fetchDepartments(userId),
      ]);
      if (!mounted) return;
      final config = results[0] as FrontmatterConfigModel;
      final departments = results[1] as List<DepartmentSummary>;
      _universityController.text = config.universityName;
      _sessionController.text = config.session;
      setState(() {
        _departments = departments;
        _selectedDepartmentName = config.departmentName.isNotEmpty
            ? config.departmentName
            : (departments.isNotEmpty ? departments.first.name : null);
        _loading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _loading = false;
        });
      }
    }
  }

  Future<void> _save() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _saving = true);
    try {
      await _api.updateFrontmatterConfig(userId, {
        'university_name': _universityController.text.trim(),
        'department_name': (_selectedDepartmentName ?? '').trim(),
        'session': _sessionController.text.trim(),
      });
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Cover page branding saved'),
          backgroundColor: Color(0xFF10B981),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString()), backgroundColor: const Color(0xFFEF4444)),
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  InputDecoration _fieldDecoration(String hint) {
    return InputDecoration(
      hintText: hint,
      hintStyle: TextStyle(color: Colors.white.withOpacity(0.35), fontSize: 13),
      filled: true,
      fillColor: const Color(0xFF0F1419),
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(6),
        borderSide: const BorderSide(color: Color(0xFF2D3748)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(6),
        borderSide: const BorderSide(color: Color(0xFF2D3748)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(6),
        borderSide: const BorderSide(color: Color(0xFF6366F1)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final deptNames = _departments.map((d) => d.name).toList();
    if (_selectedDepartmentName != null &&
        _selectedDepartmentName!.isNotEmpty &&
        !deptNames.contains(_selectedDepartmentName)) {
      deptNames.insert(0, _selectedDepartmentName!);
    }

    return CommonWidgets.buildCardContainer(
      icon: Icons.menu_book_rounded,
      title: 'Cover Page Branding',
      subtitle: 'University name, department and session for auto-generated cover pages',
      child: _loading
          ? const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Center(
                child: SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF6366F1)),
                ),
              ),
            )
          : _error != null
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(_error!, style: const TextStyle(color: Color(0xFFEF4444), fontSize: 12)),
                    const SizedBox(height: 8),
                    TextButton(onPressed: _load, child: const Text('Retry')),
                  ],
                )
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'University name',
                      style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.7)),
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _universityController,
                      style: const TextStyle(color: Colors.white, fontSize: 13),
                      decoration: _fieldDecoration('e.g. COMSATS University Islamabad'),
                    ),
                    const SizedBox(height: 16),
                    CommonWidgets.buildSettingGroup(
                      'Department (from Department Manager)',
                      DropdownButton<String>(
                        value: deptNames.contains(_selectedDepartmentName)
                            ? _selectedDepartmentName
                            : null,
                        isExpanded: true,
                        underline: const SizedBox(),
                        dropdownColor: const Color(0xFF1A1F2E),
                        hint: Text(
                          _departments.isEmpty
                              ? 'No departments — add them in Department Manager'
                              : 'Select department',
                          style: TextStyle(color: Colors.white.withOpacity(0.45), fontSize: 13),
                        ),
                        items: deptNames
                            .map(
                              (name) => DropdownMenuItem(
                                value: name,
                                child: Text(name, style: const TextStyle(color: Colors.white)),
                              ),
                            )
                            .toList(),
                        onChanged: deptNames.isEmpty
                            ? null
                            : (v) => setState(() => _selectedDepartmentName = v),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'Session / batch',
                      style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.7)),
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _sessionController,
                      style: const TextStyle(color: Colors.white, fontSize: 13),
                      decoration: _fieldDecoration('e.g. Fall 2025'),
                    ),
                    const SizedBox(height: 16),
                    Align(
                      alignment: Alignment.centerRight,
                      child: ElevatedButton.icon(
                        onPressed: _saving ? null : _save,
                        icon: _saving
                            ? const SizedBox(
                                width: 14,
                                height: 14,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                              )
                            : const Icon(Icons.save_rounded, size: 16),
                        label: Text(_saving ? 'Saving…' : 'Save branding'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF6366F1),
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        ),
                      ),
                    ),
                  ],
                ),
    );
  }
}
