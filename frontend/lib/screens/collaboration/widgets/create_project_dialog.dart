import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../config/dev_user_config.dart';
import '../../../providers/auth_provider.dart';
import '../../../providers/collaboration_provider.dart';
import '../../../providers/document_provider.dart';
import '../../../providers/template_provider.dart';

import '../../../widgets/tr.dart';
/// Modal form to create a collaboration project (document optional).
class CreateProjectDialog extends StatefulWidget {
  final void Function(int projectId)? onCreated;

  const CreateProjectDialog({super.key, this.onCreated});

  @override
  State<CreateProjectDialog> createState() => _CreateProjectDialogState();
}

class _CreateProjectDialogState extends State<CreateProjectDialog> {
  final _name = TextEditingController();
  final _desc = TextEditingController();
  int? _templateId;
  File? _document;
  String? _documentName;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final auth = context.read<AuthProvider>();
      final userId = auth.userId ?? DevUserConfig.backendUserId;
      final templates = context.read<TemplateProvider>();
      if (templates.templates.isEmpty) {
        await templates.fetchTemplates(userId);
      }
      if (mounted && templates.templates.isNotEmpty) {
        setState(() => _templateId = templates.templates.first['id'] as int?);
      }
    });
  }

  @override
  void dispose() {
    _name.dispose();
    _desc.dispose();
    super.dispose();
  }

  Future<void> _pickDocument() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['docx'],
      withData: false,
    );
    if (result != null && result.files.single.path != null) {
      setState(() {
        _document = File(result.files.single.path!);
        _documentName = result.files.single.name;
      });
    }
  }

  Future<void> _submit() async {
    if (_name.text.trim().isEmpty || _templateId == null) return;
    setState(() => _submitting = true);

    final auth = context.read<AuthProvider>();
    final userId = auth.userId ?? DevUserConfig.backendUserId;
    final vc = context.read<CollaborationProvider>();
    vc.setActiveUserId(userId);

    final project = await vc.createProject(
      name: _name.text.trim(),
      description: _desc.text.trim(),
      templateId: _templateId!,
      documentFile: _document,
    );

    if (!mounted) return;
    setState(() => _submitting = false);

    if (project == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(vc.error ?? 'Create failed')),
      );
      return;
    }

    await context.read<DocumentProvider>().fetchDocuments(userId);
    if (!mounted) return;
    Navigator.pop(context);
    widget.onCreated?.call(project['id'] as int);
  }

  @override
  Widget build(BuildContext context) {
    final templates = context.watch<TemplateProvider>();

    return Dialog(
      backgroundColor: const Color(0xFF1A1F2E),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 480),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Tr('Create Project',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 4),
              const Tr('Document upload is optional — you can add one later.',
                style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
              ),
              const SizedBox(height: 20),
              TextField(
                controller: _name,
                decoration: const InputDecoration(labelText: 'Project name'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _desc,
                decoration: const InputDecoration(labelText: 'Description'),
                maxLines: 2,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<int>(
                value: _templateId,
                decoration: const InputDecoration(labelText: 'Template'),
                items: templates.templates
                    .map(
                      (t) => DropdownMenuItem<int>(
                        value: t['id'] as int,
                        child: Text(t['name'] as String? ?? 'Template'),
                      ),
                    )
                    .toList(),
                onChanged: (v) => setState(() => _templateId = v),
              ),
              const SizedBox(height: 16),
              OutlinedButton.icon(
                onPressed: _pickDocument,
                icon: const Icon(Icons.upload_file, size: 18),
                label: Text(
                  _documentName == null
                      ? 'Upload document (optional)'
                      : _documentName!,
                ),
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFF6366F1),
                  side: const BorderSide(color: Color(0xFF6366F1)),
                ),
              ),
              if (_documentName != null) ...[
                const SizedBox(height: 8),
                TextButton(
                  onPressed: () => setState(() {
                    _document = null;
                    _documentName = null;
                  }),
                  child: const Tr('Remove file'),
                ),
              ],
              const SizedBox(height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _submitting ? null : () => Navigator.pop(context),
                    child: const Tr('Cancel'),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton(
                    onPressed: _submitting ? null : _submit,
                    child: _submitting
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Tr('Create'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
