import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../providers/upload_provider.dart';

import 'tr.dart';
class GoogleDriveFileSelector extends StatefulWidget {
  final int templateId;
  final Function(String) onFileSelected;

  const GoogleDriveFileSelector({
    Key? key,
    required this.templateId,
    required this.onFileSelected,
  }) : super(key: key);

  @override
  State<GoogleDriveFileSelector> createState() => _GoogleDrivFileSelectorState();
}

class _GoogleDrivFileSelectorState extends State<GoogleDriveFileSelector> {
  bool _showManualInput = false;
  final TextEditingController _fileIdController = TextEditingController();
  final TextEditingController _filenameController = TextEditingController();

  @override
  void dispose() {
    _fileIdController.dispose();
    _filenameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Consumer2<AuthProvider, UploadProvider>(
      builder: (context, authProvider, uploadProvider, child) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Main button to open Google Drive
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                border: Border.all(color: Colors.blue.shade300),
                borderRadius: BorderRadius.circular(8),
                color: Colors.blue.shade50,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Tr('Select from Google Drive',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Logged in as: ${authProvider.userEmail}',
                    style: const TextStyle(fontSize: 14, color: Colors.grey),
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: uploadProvider.isUploading
                          ? null
                          : () => _openGoogleDrive(context, authProvider, uploadProvider),
                      icon: const Icon(Icons.cloud),
                      label: uploadProvider.isUploading
                          ? const Tr('Opening Google Drive...')
                          : const Tr('Open Google Drive'),
                      style: ElevatedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        backgroundColor: Colors.blue,
                        foregroundColor: Colors.white,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    '1. Click to open your Google Drive\n'
                    '2. Select a .docx or .pdf file\n'
                    '3. Copy the file ID from the URL\n'
                    '4. Paste it below and click Download',
                    style: TextStyle(fontSize: 12, color: Colors.grey),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            // Manual input section
            if (_showManualInput)
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.orange.shade300),
                  borderRadius: BorderRadius.circular(8),
                  color: Colors.orange.shade50,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Tr('Paste File Details',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _fileIdController,
                      decoration: InputDecoration(
                        labelText: 'File ID (from Google Drive URL)',
                        hintText: '1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _filenameController,
                      decoration: InputDecoration(
                        labelText: 'Filename',
                        hintText: 'document.docx or report.pdf',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: uploadProvider.isUploading
                            ? null
                            : () => _downloadFile(
                                  context,
                                  authProvider,
                                  uploadProvider,
                                ),
                        icon: uploadProvider.isUploading
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  valueColor: AlwaysStoppedAnimation(Colors.white),
                                  strokeWidth: 2,
                                ),
                              )
                            : const Icon(Icons.download),
                        label: uploadProvider.isUploading
                            ? const Tr('Downloading...')
                            : const Tr('Download & Load'),
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          backgroundColor: Colors.green,
                          foregroundColor: Colors.white,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            const SizedBox(height: 16),
            // Toggle button
            TextButton.icon(
              onPressed: () {
                setState(() {
                  _showManualInput = !_showManualInput;
                });
              },
              icon: Icon(
                _showManualInput ? Icons.expand_less : Icons.expand_more,
              ),
              label: Text(
                _showManualInput ? 'Hide Manual Input' : 'Manual File ID Input',
              ),
            ),
            // Error message
            if (uploadProvider.uploadErrorMessage != null)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                margin: const EdgeInsets.only(top: 16),
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.red.shade300),
                  borderRadius: BorderRadius.circular(4),
                  color: Colors.red.shade50,
                ),
                child: Text(
                  uploadProvider.uploadErrorMessage!,
                  style: TextStyle(color: Colors.red.shade700),
                ),
              ),
            // Progress indicator
            if (uploadProvider.isUploading && uploadProvider.uploadProgress > 0)
              Container(
                margin: const EdgeInsets.only(top: 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    LinearProgressIndicator(
                      value: uploadProvider.uploadProgress / 100,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Progress: ${uploadProvider.uploadProgress}%',
                      style: const TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                  ],
                ),
              ),
          ],
        );
      },
    );
  }

  Future<void> _openGoogleDrive(
    BuildContext context,
    AuthProvider authProvider,
    UploadProvider uploadProvider,
  ) async {
    if (authProvider.userId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Tr('Please login first')),
      );
      return;
    }

    final success = await uploadProvider.openGoogleDrivePicker(
      userId: authProvider.userId!,
    );

    if (success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Google Drive opened. Select a file and copy its ID from the URL, '
            'then paste it below.',
          ),
          duration: Duration(seconds: 5),
        ),
      );
      setState(() {
        _showManualInput = true;
      });
    }
  }

  Future<void> _downloadFile(
    BuildContext context,
    AuthProvider authProvider,
    UploadProvider uploadProvider,
  ) async {
    if (_fileIdController.text.isEmpty || _filenameController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Tr('Please enter file ID and filename')),
      );
      return;
    }

    if (authProvider.userId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Tr('Please login first')),
      );
      return;
    }

    final success = await uploadProvider.downloadFromGoogleDrive(
      userId: authProvider.userId!,
      fileId: _fileIdController.text.trim(),
      filename: _filenameController.text.trim(),
      templateId: widget.templateId,
    );

    if (success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Tr('File downloaded successfully')),
      );
      widget.onFileSelected(_filenameController.text.trim());
      Navigator.of(context).pop();
    }
  }
}
