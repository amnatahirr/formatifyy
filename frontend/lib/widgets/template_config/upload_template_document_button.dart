import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../../services/template_extract_api.dart';

/// Outlined "Upload Document" control for Create Template.
/// Calls [onDraftReady] with the extracted draft; never saves a template.
class UploadTemplateDocumentButton extends StatefulWidget {
  final ValueChanged<Map<String, dynamic>> onDraftReady;
  final bool enabled;

  const UploadTemplateDocumentButton({
    super.key,
    required this.onDraftReady,
    this.enabled = true,
  });

  @override
  State<UploadTemplateDocumentButton> createState() =>
      _UploadTemplateDocumentButtonState();
}

class _UploadTemplateDocumentButtonState
    extends State<UploadTemplateDocumentButton> {
  bool _busy = false;

  Future<void> _pickAndExtract() async {
    if (_busy || !widget.enabled) return;

    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['docx'],
      withData: false,
    );
    if (result == null || result.files.isEmpty) return;

    final path = result.files.single.path;
    if (path == null || path.isEmpty) {
      _snack('Could not read the selected file path', isError: true);
      return;
    }

    setState(() => _busy = true);
    try {
      final draft = await TemplateExtractApi().extractFromDocument(path);
      if (!mounted) return;
      widget.onDraftReady(draft);
      _snack('Draft loaded from document — review fields, then Create Template');
    } on TemplateExtractException catch (e) {
      if (mounted) _snack(e.message, isError: true);
    } catch (e) {
      if (mounted) _snack('Upload failed: $e', isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _snack(String message, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? const Color(0xFFEF4444) : const Color(0xFF10B981),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: (!_busy && widget.enabled) ? _pickAndExtract : null,
      icon: _busy
          ? const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : const Icon(Icons.upload_file, size: 18),
      label: Text(_busy ? 'Extracting…' : 'Upload Document'),
      style: OutlinedButton.styleFrom(
        foregroundColor: const Color(0xFFA5B4FC),
        side: const BorderSide(color: Color(0xFF6366F1)),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      ),
    );
  }
}
