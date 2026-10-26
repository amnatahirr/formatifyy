import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import 'dart:io';
import 'package:file_picker/file_picker.dart';
import '../models/json_parse.dart';
import '../services/image_replacement_service.dart';

AppPalette _ap = AppPalette.dark;

Color get _bg => _ap.scaffold;
Color get _surface => _ap.surface;
Color get _surface2 => _ap.surfaceElevated;
Color get _border => _ap.border;
Color get _textPri => _ap.textPrimary;
Color get _textSec => _ap.textSecondary;
const _green = Color(0xFF10B981);
const _yellow = Color(0xFFFACC15);
const _red = Color(0xFFEF4444);
const _blue = Color(0xFF4A9EFF);

class ImageReplacementDialog extends StatefulWidget {
  final int documentId;
  final int imageIndex;
  final String currentImagePath;
  final ImageReplacementService service;
  final void Function(Map<String, dynamic> result) onSuccess;
  final Function(String) onError;

  final int? userId;

  const ImageReplacementDialog({
    super.key,
    required this.documentId,
    required this.imageIndex,
    required this.currentImagePath,
    required this.service,
    required this.onSuccess,
    required this.onError,
    this.userId,
  });

  @override
  State<ImageReplacementDialog> createState() => _ImageReplacementDialogState();
}

class _ImageReplacementDialogState extends State<ImageReplacementDialog> {
  bool _isLoading = false;
  File? _selectedImage;
  String? _selectedImagePath;
  String _uploadStatus = '';
  bool _showPreview = false;

  Future<void> _pickImage() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.image,
        allowMultiple: false,
      );

      if (result != null && result.files.single.path != null) {
        final file = File(result.files.single.path!);
        setState(() {
          _selectedImage = file;
          _selectedImagePath = result.files.single.name;
          _showPreview = true;
          _uploadStatus = '';
        });
      }
    } catch (e) {
      widget.onError('Error picking image: $e');
    }
  }

  bool _isSuccessResponse(Map<String, dynamic> result) {
    return result['success'] == true || result['status'] == 'success';
  }

  Future<void> _uploadImage() async {
    if (_selectedImage == null) {
      setState(() => _uploadStatus = 'Please select an image first');
      return;
    }

    setState(() {
      _isLoading = true;
      _uploadStatus = 'Uploading and validating...';
    });

    try {
      final result = await widget.service.replaceImage(
        documentId: widget.documentId,
        imageIndex: widget.imageIndex,
        imageFile: _selectedImage!,
        userId: widget.userId,
      );

      if (_isSuccessResponse(result)) {
        final cleared = result['cleared'] == true;
        final isRelevant = result['is_relevant'] ?? true;
        final isEthical = result['is_ethical'] ?? true;

        // Server ne image document mein replace kar di hai -> preview hamesha refresh ho
        if (mounted) widget.onSuccess(result);

        if (cleared || (isRelevant == true && isEthical == true)) {
          if (mounted) {
            Navigator.of(context).pop();
          }
          return;
        }

        setState(() {
          _uploadStatus =
              'Image replaced but still flagged — try a more relevant academic image.';
        });
        widget.onError('Replacement image still appears irrelevant or inappropriate.');
      }
    } catch (e) {
      setState(() => _uploadStatus = 'Error: $e');
      widget.onError(e.toString());
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    _ap = context.watch<ThemeProvider>().palette;
    return Dialog(
      backgroundColor: _surface,
      child: Container(
        width: 500,
        decoration: BoxDecoration(
          color: _surface,
          border: Border.all(color: _border, width: 1),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: _surface2,
                border: Border(bottom: BorderSide(color: _border, width: 1)),
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(12),
                  topRight: Radius.circular(12),
                ),
              ),
              child: Row(
                children: [
                  const Icon(Icons.image_search, color: _yellow, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Replace Image',
                      style: TextStyle(
                        color: _textPri,
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  if (!_isLoading)
                    IconButton(
                      icon: Icon(Icons.close, color: _textSec),
                      onPressed: () => Navigator.pop(context),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: _surface2,
                      border: Border.all(color: _border, width: 1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      'Select a new image. It will be embedded in your document and checked for relevance.',
                      style: TextStyle(color: _textSec, fontSize: 12),
                    ),
                  ),
                  const SizedBox(height: 16),
                  if (_showPreview && _selectedImage != null) ...[
                    Text(
                      'New Image',
                      style: TextStyle(
                        color: _textPri,
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      height: 200,
                      width: double.infinity,
                      decoration: BoxDecoration(
                        border: Border.all(color: _border, width: 1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Image.file(_selectedImage!, fit: BoxFit.contain),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _selectedImagePath ?? 'Unknown file',
                      style: TextStyle(
                        color: _textSec,
                        fontSize: 10,
                        fontFamily: 'monospace',
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                  if (_uploadStatus.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Text(
                      _uploadStatus,
                      style: TextStyle(
                        color: _uploadStatus.contains('Error') || _uploadStatus.contains('irrelevant')
                            ? _red
                            : _textSec,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                border: Border(top: BorderSide(color: _border, width: 1)),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  if (!_isLoading)
                    TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: Text('Cancel', style: TextStyle(color: _textSec)),
                    ),
                  const SizedBox(width: 8),
                  if (_selectedImage == null)
                    ElevatedButton.icon(
                      icon: const Icon(Icons.upload_file, size: 16),
                      label: const Text('Select Image'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _blue,
                        foregroundColor: _textPri,
                      ),
                      onPressed: _isLoading ? null : _pickImage,
                    )
                  else
                    ElevatedButton.icon(
                      icon: _isLoading
                          ? SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor: AlwaysStoppedAnimation(_textPri),
                              ),
                            )
                          : const Icon(Icons.check, size: 16),
                      label: Text(_isLoading ? 'Uploading...' : 'Upload & Validate'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _green,
                        foregroundColor: _textPri,
                      ),
                      onPressed: _isLoading ? null : _uploadImage,
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
