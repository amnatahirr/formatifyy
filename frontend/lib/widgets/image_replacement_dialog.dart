import 'package:flutter/material.dart';
import 'dart:io';
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
import '../services/image_replacement_service.dart';

const _bg = Color(0xFF0D1117);
const _surface = Color(0xFF161B22);
const _surface2 = Color(0xFF1C2333);
const _border = Color(0xFF30363D);
const _textPri = Colors.white;
const _textSec = Color(0xFF8B949E);
const _green = Color(0xFF10B981);
const _yellow = Color(0xFFFACC15);
const _red = Color(0xFFEF4444);
const _blue = Color(0xFF4A9EFF);

class ImageReplacementDialog extends StatefulWidget {
  final int documentId;
  final int imageIndex;
  final String currentImagePath;
  final ImageReplacementService service;
  final VoidCallback onSuccess;
  final Function(String) onError;

  const ImageReplacementDialog({
    Key? key,
    required this.documentId,
    required this.imageIndex,
    required this.currentImagePath,
    required this.service,
    required this.onSuccess,
    required this.onError,
  }) : super(key: key);

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
      );

      if (result['success'] == true) {
        final isRelevant = result['is_relevant'] ?? false;
        final confidence = (result['confidence'] ?? 0.0) as num;

        setState(() {
          _uploadStatus = isRelevant
              ? '✓ Image replaced and validated successfully!'
              : '⚠ Image replaced but shows relevance concerns';
        });

        // Show validation result
        if (mounted) {
          _showValidationResult(result);
        }

        // Notify parent after brief delay
        await Future.delayed(const Duration(milliseconds: 1500));
        if (mounted) {
          widget.onSuccess();
          Navigator.pop(context);
        }
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

  void _showValidationResult(Map<String, dynamic> result) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _surface,
        title: Row(
          children: [
            Icon(
              result['is_relevant'] ? Icons.check_circle : Icons.warning,
              color: result['is_relevant'] ? _green : _yellow,
              size: 24,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                result['is_relevant']
                    ? 'Validation Passed'
                    : 'Validation Complete',
                style: TextStyle(
                  color: result['is_relevant'] ? _green : _yellow,
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildResultRow(
              'Status',
              result['is_relevant'] ? 'Relevant' : 'Needs Review',
              result['is_relevant'] ? _green : _yellow,
            ),
            const SizedBox(height: 8),
            _buildResultRow(
              'Confidence',
              '${((result['confidence'] ?? 0.0) * 100).toStringAsFixed(1)}%',
              _textSec,
            ),
            const SizedBox(height: 12),
            if (result['analysis_details'] != null) ...[
              Text(
                'Details:',
                style: TextStyle(
                  color: _textSec,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                result['analysis_details']['recommendation'] ?? '',
                style: const TextStyle(
                  color: _textSec,
                  fontSize: 11,
                ),
              ),
            ],
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text(
              'Close',
              style: TextStyle(color: _blue),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResultRow(String label, String value, Color color) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: const TextStyle(color: _textSec, fontSize: 12),
        ),
        Text(
          value,
          style: TextStyle(
            color: color,
            fontSize: 12,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
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
            // Header
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: _surface2,
                border: Border(
                  bottom: BorderSide(color: _border, width: 1),
                ),
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(12),
                  topRight: Radius.circular(12),
                ),
              ),
              child: Row(
                children: [
                  const Icon(Icons.image_search, color: _yellow, size: 20),
                  const SizedBox(width: 8),
                  const Expanded(
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
                      icon: const Icon(Icons.close, color: _textSec),
                      onPressed: () => Navigator.pop(context),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                    ),
                ],
              ),
            ),

            // Body
            Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Info text
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: _surface2,
                      border: Border.all(color: _border, width: 1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: const Text(
                      'Select a new image. It will be automatically checked for relevance to the document section.',
                      style: TextStyle(
                        color: _textSec,
                        fontSize: 12,
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Current image info
                  if (_selectedImagePath == null)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 16,
                      ),
                      decoration: BoxDecoration(
                        color: _surface2,
                        border: Border.all(color: _border, width: 1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            'Current Image',
                            style: const TextStyle(
                              color: _textSec,
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            widget.currentImagePath,
                            style: const TextStyle(
                              color: _textSec,
                              fontSize: 10,
                              fontFamily: 'monospace',
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),

                  // Selected image preview
                  if (_showPreview && _selectedImage != null)
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'New Image',
                          style: const TextStyle(
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
                          child: Image.file(
                            _selectedImage!,
                            fit: BoxFit.contain,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          _selectedImagePath ?? 'Unknown file',
                          style: const TextStyle(
                            color: _textSec,
                            fontSize: 10,
                            fontFamily: 'monospace',
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),

                  const SizedBox(height: 16),

                  // Status message
                  if (_uploadStatus.isNotEmpty)
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: _uploadStatus.contains('✓')
                            ? _green.withOpacity(0.1)
                            : _uploadStatus.contains('⚠')
                                ? _yellow.withOpacity(0.1)
                                : _red.withOpacity(0.1),
                        border: Border.all(
                          color: _uploadStatus.contains('✓')
                              ? _green.withOpacity(0.3)
                              : _uploadStatus.contains('⚠')
                                  ? _yellow.withOpacity(0.3)
                                  : _red.withOpacity(0.3),
                          width: 1,
                        ),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Row(
                        children: [
                          if (_isLoading)
                            SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor: AlwaysStoppedAnimation(
                                  _uploadStatus.contains('✓') ? _green : _yellow,
                                ),
                              ),
                            )
                          else
                            Icon(
                              _uploadStatus.contains('✓')
                                  ? Icons.check_circle
                                  : _uploadStatus.contains('⚠')
                                      ? Icons.warning
                                      : Icons.error,
                              size: 16,
                              color: _uploadStatus.contains('✓')
                                  ? _green
                                  : _uploadStatus.contains('⚠')
                                      ? _yellow
                                      : _red,
                            ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              _uploadStatus,
                              style: TextStyle(
                                color: _uploadStatus.contains('✓')
                                    ? _green
                                    : _uploadStatus.contains('⚠')
                                        ? _yellow
                                        : _red,
                                fontSize: 12,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),

            // Footer buttons
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                border: Border(
                  top: BorderSide(color: _border, width: 1),
                ),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  if (!_isLoading)
                    TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text(
                        'Cancel',
                        style: TextStyle(color: _textSec),
                      ),
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
