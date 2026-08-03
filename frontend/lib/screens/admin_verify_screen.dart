import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';

import '../config/api_config.dart';
import '../providers/auth_provider.dart';
import '../providers/template_provider.dart';
import '../widgets/admin/admin_ui.dart';
import 'analyze_screen.dart';

class AdminVerifyScreen extends StatefulWidget {
  const AdminVerifyScreen({super.key});

  @override
  State<AdminVerifyScreen> createState() => _AdminVerifyScreenState();
}

class _AdminVerifyScreenState extends State<AdminVerifyScreen> {
  File? _selectedFile;
  Map<String, dynamic>? _selectedTemplate;
  bool _isLoadingTemplates = false;
  bool _isVerifying = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadTemplates();
  }

  Future<void> _loadTemplates() async {
    final auth = context.read<AuthProvider>();
    final userId = auth.userId;
    if (userId == null) return;

    setState(() {
      _isLoadingTemplates = true;
      _error = null;
    });

    try {
      await context.read<TemplateProvider>().fetchUserTemplates(userId);
    } catch (e) {
      setState(() => _error = 'Failed to load templates: $e');
    } finally {
      if (mounted) setState(() => _isLoadingTemplates = false);
    }
  }

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['docx', 'pdf', 'txt'],
    );
    if (result == null || result.files.single.path == null) return;

    setState(() {
      _selectedFile = File(result.files.single.path!);
      _error = null;
    });
  }

  Future<void> _verifyNow() async {
    final auth = context.read<AuthProvider>();
    final userId = auth.userId;
    final file = _selectedFile;
    final template = _selectedTemplate;

    if (userId == null) {
      setState(() => _error = 'You must be logged in.');
      return;
    }
    if (file == null) {
      setState(() => _error = 'Please choose a file first.');
      return;
    }
    if (template == null) {
      setState(() => _error = 'Please select a template.');
      return;
    }

    setState(() {
      _isVerifying = true;
      _error = null;
    });

    try {
      final templateId = template['id'] as int;
      final uri = Uri.parse(
        '${ApiConfig.getBaseUrl()}/documents/upload?template_id=$templateId&user_id=$userId',
      );

      final request = http.MultipartRequest('POST', uri)
        ..headers.addAll(ApiConfig.getHeaders())
        ..files.add(await http.MultipartFile.fromPath('file', file.path));

      final streamed = await request.send();
      final body = await streamed.stream.bytesToString();
      if (streamed.statusCode != 200) {
        setState(() => _error = 'Upload failed: $body');
        return;
      }

      final data = jsonDecode(body) as Map<String, dynamic>;
      final documentId = data['document_id'] as int?;
      final filename = (data['filename'] ?? file.path.split('/').last).toString();

      if (!mounted || documentId == null) return;
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => AnalyzeScreen(
            documentId: documentId,
            documentName: filename,
            templateId: templateId,
            templateName: (template['name'] ?? 'Template').toString(),
          ),
        ),
      );
    } catch (e) {
      setState(() => _error = 'Verification failed: $e');
    } finally {
      if (mounted) setState(() => _isVerifying = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final templates = context.watch<TemplateProvider>().templates;

    return AdminPage(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminSectionCard(
            title: 'Verification',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ElevatedButton.icon(
                  onPressed: _isVerifying ? null : _pickFile,
                  icon: const Icon(Icons.upload_file),
                  label: Text(_selectedFile == null ? 'Choose File' : 'Change File'),
                ),
                const SizedBox(height: 12),
                Text(
                  _selectedFile?.path.split('/').last ?? 'No file selected',
                  style: TextStyle(color: Colors.white.withOpacity(0.85)),
                ),
                const SizedBox(height: 18),
                if (_isLoadingTemplates)
                  const AdminLoadingView()
                else
                  DropdownButtonFormField<Map<String, dynamic>>(
                    value: _selectedTemplate,
                    dropdownColor: AdminColors.surface,
                    decoration: const InputDecoration(
                      labelText: 'Select Template',
                      border: OutlineInputBorder(),
                    ),
                    items: templates
                        .map(
                          (t) => DropdownMenuItem<Map<String, dynamic>>(
                            value: t,
                            child: Text((t['name'] ?? 'Template').toString()),
                          ),
                        )
                        .toList(),
                    onChanged: _isVerifying
                        ? null
                        : (value) {
                            setState(() => _selectedTemplate = value);
                          },
                  ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!, style: const TextStyle(color: AdminColors.danger)),
                ],
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _isVerifying ? null : _verifyNow,
                    icon: _isVerifying
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.fact_check),
                    label: Text(_isVerifying ? 'Verifying...' : 'Verify with Template'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
