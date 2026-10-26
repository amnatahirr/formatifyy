import 'dart:io';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:provider/provider.dart';
import '../utils/analysis_nav.dart';
import '../providers/document_provider.dart';
import '../providers/template_provider.dart';
import '../providers/auth_provider.dart';
import './style_preview_widget.dart';
import './admin/admin_ui.dart';
import './freeform_analyze_dialogs.dart';
import '../screens/analyze_screen.dart';

import 'tr.dart';
class DocumentUploadWidget extends StatefulWidget {
  const DocumentUploadWidget({Key? key}) : super(key: key);

  @override
  State<DocumentUploadWidget> createState() => _DocumentUploadWidgetState();
}

class _DocumentUploadWidgetState extends State<DocumentUploadWidget> {
  int? _selectedTemplateId;
  Map<String, dynamic>? _selectedTemplate;
  File? _selectedFile;
  bool _isUploading = false;
  bool _isUploadMode = true;
  final TextEditingController _pasteController = TextEditingController();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Tr('Upload & Format Your Report',
            style: theme.textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Tr('Apply professional formatting to your documents',
            style: theme.textTheme.bodySmall?.copyWith(color: Colors.white70),
          ),
          const SizedBox(height: 32),

          /// STEP 1 — TEMPLATE
          _buildStepCard(
            context,
            step: 1,
            title: 'Select a Template',
            subtitle: 'Choose the formatting template to apply',
            child: Consumer<TemplateProvider>(
              builder: (_, templateProvider, __) {
                if (templateProvider.templates.isEmpty) {
                  return Tr('No templates available. Please contact admin.',
                    style: theme.textTheme.bodySmall,
                  );
                }

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      decoration: BoxDecoration(
                        color: theme.cardColor,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: theme.dividerColor.withOpacity(0.2),
                        ),
                      ),
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      child: DropdownButton<int>(
                        value: _selectedTemplateId,
                        isExpanded: true,
                        underline: const SizedBox(),
                        dropdownColor: theme.cardColor,
                        iconEnabledColor: Colors.white,
                        hint: const Tr('Choose a template'),
                        style: theme.textTheme.bodyMedium,
                        items: templateProvider.templates.map((template) {
                          return DropdownMenuItem<int>(
                            value: template['id'],
                            child: Text(template['name']),
                          );
                        }).toList(),
                        onChanged: (value) {
                          final template = templateProvider.templates
                              .firstWhere((t) => t['id'] == value);
                          setState(() {
                            _selectedTemplateId = value;
                            _selectedTemplate = template;
                          });
                        },
                      ),
                    ),

                    if (_selectedTemplate != null) ...[
                      const SizedBox(height: 16),
                      Tr('Required Sections',
                        style: theme.textTheme.titleSmall,
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children:
                            (_selectedTemplate!['required_sections'] as List)
                                .map(
                                  (s) => Chip(
                                    label: Text(s.toString()),
                                    backgroundColor: theme.primaryColor
                                        .withOpacity(0.15),
                                    labelStyle: const TextStyle(
                                      color: Colors.white,
                                    ),
                                  ),
                                )
                                .toList(),
                      ),
                      const SizedBox(height: 12),
                      ExpansionTile(
                        title: const Tr('View Formatting Rules'),
                        children: [
                          StylePreviewWidget(
                            formattingRules:
                                _selectedTemplate!['formatting_rules'],
                          ),
                        ],
                      ),
                    ],
                  ],
                );
              },
            ),
          ),

          if (!context.watch<AuthProvider>().isStudent) ...[
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _isUploading ? null : _analyzeWithoutTemplate,
                icon: const Icon(Icons.auto_awesome, size: 18),
                label: const Tr('Analyze without template'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AdminColors.primary,
                  side: BorderSide(color: AdminColors.primary.withOpacity(0.7)),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
          ],

          const SizedBox(height: 24),

          /// STEP 2 — FILE UPLOAD OR PASTE CONTENT
          _buildStepCard(
            context,
            step: 2,
            title: 'Upload Your Document or Paste Content',
            subtitle: 'DOC, DOCX, PDF, or paste text directly',
            child: Column(
              children: [
                // Tab-style selector
                Container(
                  decoration: BoxDecoration(
                    color: theme.cardColor,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: theme.dividerColor.withOpacity(0.2),
                    ),
                  ),
                  padding: const EdgeInsets.all(4),
                  child: Row(
                    children: [
                      Expanded(
                        child: GestureDetector(
                          onTap: () => setState(() => _isUploadMode = true),
                          child: Container(
                            decoration: BoxDecoration(
                              color: _isUploadMode
                                  ? theme.primaryColor
                                  : Colors.transparent,
                              borderRadius: BorderRadius.circular(6),
                            ),
                            padding: const EdgeInsets.symmetric(vertical: 10),
                            child: Tr('Upload File',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                color: _isUploadMode
                                    ? Colors.white
                                    : Colors.white70,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ),
                      ),
                      Expanded(
                        child: GestureDetector(
                          onTap: () => setState(() => _isUploadMode = false),
                          child: Container(
                            decoration: BoxDecoration(
                              color: !_isUploadMode
                                  ? theme.primaryColor
                                  : Colors.transparent,
                              borderRadius: BorderRadius.circular(6),
                            ),
                            padding: const EdgeInsets.symmetric(vertical: 10),
                            child: Tr('Paste Content',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                color: !_isUploadMode
                                    ? Colors.white
                                    : Colors.white70,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                // Upload file mode
                if (_isUploadMode)
                  Container(
                    decoration: BoxDecoration(
                      color: theme.cardColor,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: theme.dividerColor.withOpacity(0.25),
                      ),
                    ),
                    padding: const EdgeInsets.all(32),
                    child: Column(
                      children: [
                        Icon(
                          Icons.cloud_upload,
                          size: 48,
                          color: _selectedFile != null
                              ? Colors.greenAccent
                              : Colors.white54,
                        ),
                        const SizedBox(height: 16),
                        Text(
                          _selectedFile?.path.split('/').last ??
                              'No file selected',
                          style: theme.textTheme.bodyLarge,
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 16),
                        ElevatedButton.icon(
                          onPressed: _isUploading ? null : _selectFile,
                          icon: const Icon(Icons.folder_open),
                          label: const Tr('Choose File'),
                        ),
                      ],
                    ),
                  ),
                // Paste content mode
                if (!_isUploadMode)
                  Container(
                    decoration: BoxDecoration(
                      color: theme.cardColor,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: theme.dividerColor.withOpacity(0.25),
                      ),
                    ),
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Tr('Paste your content here:',
                          style: theme.textTheme.labelLarge,
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: _pasteController,
                          maxLines: 8,
                          minLines: 6,
                          decoration: InputDecoration(
                            hintText:
                                'Enter or paste your document content here...',
                            hintStyle: TextStyle(
                              color: Colors.white.withOpacity(0.5),
                            ),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(8),
                              borderSide: BorderSide(
                                color: theme.dividerColor.withOpacity(0.2),
                              ),
                            ),
                            enabledBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(8),
                              borderSide: BorderSide(
                                color: theme.dividerColor.withOpacity(0.2),
                              ),
                            ),
                            focusedBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(8),
                              borderSide: BorderSide(color: theme.primaryColor),
                            ),
                            contentPadding: const EdgeInsets.all(12),
                            filled: true,
                            fillColor: Colors.transparent,
                          ),
                          style: theme.textTheme.bodyMedium,
                        ),
                        const SizedBox(height: 12),
                        Text(
                          '${_pasteController.text.length} characters',
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: Colors.white.withOpacity(0.5),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),

          const SizedBox(height: 32),

          /// SUBMIT BUTTON
          SizedBox(
            width: double.infinity,
            height: 50,
            child: ElevatedButton.icon(
              onPressed: _isUploading
                  ? null
                  : (_isUploadMode
                        ? (_selectedFile == null || _selectedTemplateId == null)
                              ? null
                              : _uploadFile
                        : (_pasteController.text.isEmpty ||
                              _selectedTemplateId == null)
                        ? null
                        : _uploadPastedContent),
              icon: _isUploading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.upload_file),
              label: Text(
                _isUploading
                    ? 'Processing...'
                    : (_isUploadMode
                          ? 'Upload & Format Document'
                          : 'Format Pasted Content'),
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// STEP CARD UI
  Widget _buildStepCard(
    BuildContext context, {
    required int step,
    required String title,
    required String subtitle,
    required Widget child,
  }) {
    final theme = Theme.of(context);

    return Container(
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: theme.dividerColor.withOpacity(0.2)),
      ),
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 16,
                backgroundColor: theme.primaryColor,
                child: Text(
                  step.toString(),
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: theme.textTheme.titleMedium),
                  Text(
                    subtitle,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: Colors.white70,
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 16),
          child,
        ],
      ),
    );
  }

  /// FILE PICKER
  Future<void> _selectFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['doc', 'docx', 'pdf'],
    );

    if (result != null && result.files.single.path != null) {
      setState(() {
        _selectedFile = File(result.files.single.path!);
      });
    }
  }

  /// UPLOAD LOGIC
  Future<void> _uploadFile() async {
    setState(() => _isUploading = true);

    final auth = context.read<AuthProvider>();
    final docs = context.read<DocumentProvider>();

    final success = await docs.uploadDocument(
      _selectedFile!,
      _selectedTemplateId!,
      auth.userId!,
    );

    setState(() => _isUploading = false);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          success
              ? 'Document uploaded & formatted successfully'
              : 'Upload failed',
        ),
        backgroundColor: success ? Colors.green : Colors.red,
      ),
    );

    if (success) {
      setState(() {
        _selectedFile = null;
        _selectedTemplateId = null;
        _selectedTemplate = null;
      });
    }
  }

  /// PASTE CONTENT LOGIC
  Future<void> _uploadPastedContent() async {
    setState(() => _isUploading = true);

    final auth = context.read<AuthProvider>();
    final docs = context.read<DocumentProvider>();

    final success = await docs.uploadPastedContent(
      _pasteController.text,
      _selectedTemplateId!,
      auth.userId!,
    );

    setState(() => _isUploading = false);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          success ? 'Content formatted successfully' : 'Formatting failed',
        ),
        backgroundColor: success ? Colors.green : Colors.red,
      ),
    );

    if (success) {
      setState(() {
        _pasteController.clear();
        _selectedTemplateId = null;
        _selectedTemplate = null;
      });
    }
  }

  Future<void> _analyzeWithoutTemplate() async {
    final auth = context.read<AuthProvider>();
    if (auth.isStudent) return;
    final confirmed = await confirmAnalyzeWithoutTemplate(context);
    if (!confirmed || !mounted) return;

    if (_isUploadMode && _selectedFile == null) {
      await _selectFile();
      if (_selectedFile == null) return;
    }
    if (!_isUploadMode && _pasteController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Tr('Paste content first'), backgroundColor: Colors.red),
      );
      return;
    }

    setState(() => _isUploading = true);
    final docs = context.read<DocumentProvider>();
    Map<String, dynamic>? response;
    try {
      if (_isUploadMode) {
        response = await docs.uploadDocumentFreeform(_selectedFile!, auth.userId!);
      } else {
        response = await docs.uploadPastedContentFreeform(
          _pasteController.text,
          auth.userId!,
        );
      }
    } finally {
      if (mounted) setState(() => _isUploading = false);
    }

    if (!mounted) return;
    if (response == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(docs.errorMessage ?? 'Freeform upload failed'),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

  AnalysisNav.open(AnalysisRequest(
  documentId: response!['document_id'] as int,
  documentName: (response['filename'] ?? 'Document').toString(),
  templateId: 0,
  templateName: 'AI general analysis — no template applied',
  freeform: true,
));
  }
}
