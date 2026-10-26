import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/upload_provider.dart';

class GoogleDriveBrowserWidget extends StatefulWidget {
  final int userId;
  final int templateId;
  final Function(String, String) onFileSelected;

  const GoogleDriveBrowserWidget({
    super.key,
    required this.userId,
    required this.templateId,
    required this.onFileSelected,
  });

  @override
  State<GoogleDriveBrowserWidget> createState() =>
      _GoogleDriveBrowserWidgetState();
}

class _GoogleDriveBrowserWidgetState extends State<GoogleDriveBrowserWidget> {
  late Future<List<dynamic>> _filesFuture;
  String? _searchQuery;

  @override
  void initState() {
    super.initState();
    _loadFiles();
  }

  void _loadFiles() {
    _filesFuture = context
        .read<UploadProvider>()
        .listGoogleDriveFiles(userId: widget.userId, query: _searchQuery)
        .then((files) => files.cast<dynamic>());
  }

  @override
  Widget build(BuildContext context) {
    final uploads = context.watch<UploadProvider>();

    return Column(
      children: [
        // Search bar
        Padding(
          padding: const EdgeInsets.all(16),
          child: TextField(
            decoration: InputDecoration(
              hintText: 'Search in Google Drive...',
              prefixIcon: const Icon(Icons.search),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            onChanged: (value) {
              setState(() {
                _searchQuery = value.isEmpty ? null : value;
              });
              _loadFiles();
            },
          ),
        ),

        // Files list
        Expanded(
          child: FutureBuilder<List<dynamic>>(
            future: _filesFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }

              if (snapshot.hasError) {
                return Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error, color: Colors.red, size: 48),
                      const SizedBox(height: 12),
                      Text('Error: ${snapshot.error}'),
                      const SizedBox(height: 12),
                      ElevatedButton(
                        onPressed: _loadFiles,
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                );
              }

              final files = snapshot.data ?? [];

              if (files.isEmpty) {
                return Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.folder_open,
                        size: 48,
                        color: Colors.grey.shade600,
                      ),
                      const SizedBox(height: 12),
                      const Text('No files found'),
                      const SizedBox(height: 24),
                      ElevatedButton.icon(
                        onPressed: () {
                          setState(() {
                            _searchQuery = null;
                          });
                          _loadFiles();
                        },
                        icon: const Icon(Icons.refresh),
                        label: const Text('Clear Search'),
                      ),
                    ],
                  ),
                );
              }

              return ListView.builder(
                itemCount: files.length,
                itemBuilder: (context, index) {
                  final file = files[index];
                  return _buildFileListItem(file, context, uploads);
                },
              );
            },
          ),
        ),

        // Import info
        if (uploads.uploadErrorMessage != null)
          Container(
            color: Colors.red.shade900.withOpacity(0.2),
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                const Icon(Icons.error_outline, color: Colors.red),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    uploads.uploadErrorMessage!,
                    style: const TextStyle(color: Colors.red),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _buildFileListItem(
    dynamic file,
    BuildContext context,
    UploadProvider uploads,
  ) {
    final isDocument =
        file.mimeType == 'application/pdf' ||
        file.mimeType ==
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
        file.mimeType == 'application/msword';

    final fileSize = file.fileSize != null
        ? _formatFileSize(file.fileSize)
        : 'Unknown size';

    return ListTile(
      leading: Icon(
        _getFileIcon(file.mimeType),
        color: isDocument ? Colors.blue : Colors.grey,
      ),
      title: Text(file.name, maxLines: 1, overflow: TextOverflow.ellipsis),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(fileSize, style: const TextStyle(fontSize: 12)),
          Text(
            _formatDate(file.modifiedTime),
            style: const TextStyle(fontSize: 11, color: Colors.grey),
          ),
        ],
      ),
      trailing: isDocument
          ? ElevatedButton(
              onPressed: uploads.isUploading
                  ? null
                  : () async {
                      await uploads.downloadFromGoogleDrive(
                        userId: widget.userId,
                        fileId: file.id,
                        filename: file.name,
                        templateId: widget.templateId,
                      );

                      if (mounted) {
                        widget.onFileSelected(file.id, file.name);
                        if (uploads.uploadErrorMessage == null) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('File imported successfully!'),
                              backgroundColor: Colors.green,
                            ),
                          );
                        }
                      }
                    },
              child: uploads.isUploading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Import'),
            )
          : Tooltip(
              message: 'Only PDF and Word documents can be imported',
              child: IconButton(onPressed: null, icon: const Icon(Icons.block)),
            ),
    );
  }

  IconData _getFileIcon(String mimeType) {
    if (mimeType == 'application/pdf') {
      return Icons.picture_as_pdf;
    } else if (mimeType ==
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
        mimeType == 'application/msword') {
      return Icons.description;
    } else {
      return Icons.file_present;
    }
  }

  String _formatFileSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  String _formatDate(String isoDate) {
    try {
      final date = DateTime.parse(isoDate);
      final now = DateTime.now();
      final diff = now.difference(date);

      if (diff.inDays == 0) {
        return 'Today at ${date.hour}:${date.minute.toString().padLeft(2, '0')}';
      } else if (diff.inDays == 1) {
        return 'Yesterday';
      } else if (diff.inDays < 7) {
        return '${diff.inDays} days ago';
      } else {
        return '${date.day}/${date.month}/${date.year}';
      }
    } catch (e) {
      return isoDate;
    }
  }
}
