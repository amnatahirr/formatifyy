import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/document_provider.dart';
import '../providers/auth_provider.dart';

class DocumentListWidget extends StatefulWidget {
  const DocumentListWidget({Key? key}) : super(key: key);

  @override
  State<DocumentListWidget> createState() => _DocumentListWidgetState();
}

class _DocumentListWidgetState extends State<DocumentListWidget> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      final auth = context.read<AuthProvider>();
      if (auth.userId != null) {
        context.read<DocumentProvider>().fetchDocuments(auth.userId!);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'My Documents',
            style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 24),
          Expanded(
            child: Consumer<DocumentProvider>(
              builder: (context, provider, _) {
                if (provider.isLoading)
                  return const Center(child: CircularProgressIndicator());
                if (provider.documents.isEmpty) return _emptyState();
                return ListView.builder(
                  itemCount: provider.documents.length,
                  itemBuilder: (context, index) {
                    return DocumentCard(document: provider.documents[index]);
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _emptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.folder_open, size: 64, color: Colors.grey.shade400),
          const SizedBox(height: 16),
          const Text(
            'No documents uploaded yet',
            style: TextStyle(color: Colors.grey),
          ),
        ],
      ),
    );
  }
}

class DocumentCard extends StatelessWidget {
  final Map<String, dynamic> document;
  const DocumentCard({Key? key, required this.document}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final provider = Provider.of<DocumentProvider>(context);
    final auth = Provider.of<AuthProvider>(context, listen: false);
    final docId = document['id'] as int?;
    final isReAnalyzing = docId != null && provider.isReAnalyzing(docId);

    final statusColor = _getStatusColor(document['status']);
    final statusIcon = _getStatusIcon(document['status']);

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: statusColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(Icons.description, color: statusColor, size: 32),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        document['filename'] ?? 'Unknown file',
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 8),
                      if (document['template_name'] != null)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8.0),
                          child: Row(
                            children: [
                              Icon(
                                Icons.style,
                                size: 14,
                                color: Colors.deepPurple,
                              ),
                              const SizedBox(width: 4),
                              Text(
                                'Template: ${document['template_name']}',
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: Colors.deepPurple,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ],
                          ),
                        ),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: statusColor.withOpacity(0.15),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(statusIcon, size: 14, color: statusColor),
                                const SizedBox(width: 4),
                                Text(
                                  document['status'] ?? 'Unknown',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: statusColor,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 12),
                          Text(
                            'Created: ${document['created_at'] ?? 'N/A'}',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey[600],
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.deepPurple,
                  ),
                  icon: isReAnalyzing
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.refresh),
                  label: Text(isReAnalyzing ? 'Re-analyzing…' : 'Re-analyze'),
                  onPressed: (auth.userId == null || docId == null || isReAnalyzing)
                      ? null
                      : () async {
                          final ok = await provider.reAnalyzeDocument(
                            docId,
                            auth.userId!,
                          );
                          if (!context.mounted) return;
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(
                                ok ? 'Re-analysis completed!' : 'Re-analysis failed',
                              ),
                              backgroundColor: ok ? Colors.green : Colors.red,
                            ),
                          );
                        },
                ),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blue,
                    foregroundColor: Colors.white,
                  ),
                  icon: const Icon(Icons.preview),
                  label: const Text('Preview'),
                  onPressed: () =>
                      _showPreviewDialog(context, provider, auth.userId),
                ),
                const SizedBox(width: 8),
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green,
                    foregroundColor: Colors.white,
                  ),
                  icon: const Icon(Icons.download),
                  label: const Text('Export'),
                  onPressed: () => _showExportDialog(
                    context,
                    provider,
                    auth.userId,
                    document['id'],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Color _getStatusColor(String? status) {
    switch (status?.toLowerCase()) {
      case 'completed':
      case 'formatted':
        return Colors.green;
      case 'processing':
      case 'formatting':
        return Colors.orange;
      case 'failed':
      case 'error':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  IconData _getStatusIcon(String? status) {
    switch (status?.toLowerCase()) {
      case 'completed':
      case 'formatted':
        return Icons.check_circle;
      case 'processing':
      case 'formatting':
        return Icons.hourglass_bottom;
      case 'failed':
      case 'error':
        return Icons.error;
      default:
        return Icons.info;
    }
  }

  void _showPreviewDialog(
    BuildContext context,
    DocumentProvider provider,
    int? userId,
  ) {
    if (userId == null) return;

    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: Row(
          children: [
            const Icon(Icons.preview, color: Colors.blue),
            const SizedBox(width: 8),
            const Text('Formatted Document Preview'),
          ],
        ),
        content: FutureBuilder<Map<String, dynamic>?>(
          future: provider.getPreview(document['id'], userId),
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const SizedBox(
                height: 300,
                child: Center(child: CircularProgressIndicator()),
              );
            }

            if (snapshot.hasError || snapshot.data == null) {
              return SizedBox(
                height: 300,
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.error_outline,
                        size: 48,
                        color: Colors.red.withOpacity(0.5),
                      ),
                      const SizedBox(height: 12),
                      const Text('Could not load preview'),
                    ],
                  ),
                ),
              );
            }

            final previewData = snapshot.data!;
             final authProvider = Provider.of<AuthProvider>(context, listen: false);
             final userId = authProvider.userId;
            final formattedContent = previewData['formatted_preview'] as List?;
            final formattingRules =
                previewData['formatting_rules'] as Map<String, dynamic>?;

            if (formattedContent == null || formattedContent.isEmpty) {
              return const SizedBox(
                height: 300,
                child: Center(child: Text('No content available')),
              );
            }

            return SizedBox(
              width: 500,
              height: 400,
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: formattedContent.map<Widget>((item) {
                    final text = item['text'] as String? ?? '';
                    final type = item['type'] as String? ?? 'paragraph';
                    final styleInfo =
                        item['style_info'] as Map<String, dynamic>? ?? {};

                    // Apply styling based on type
                    TextStyle style = const TextStyle(
                      fontSize: 12,
                      color: Colors.black,
                    );
                    double bottomPadding = 8;

                    switch (type) {
                      case 'heading1':
                        style = const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          color: Colors.black87,
                        );
                        bottomPadding = 16;
                        break;
                      case 'heading2':
                        style = const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: Colors.black87,
                        );
                        bottomPadding = 12;
                        break;
                      case 'heading3':
                        style = const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: Colors.black87,
                        );
                        bottomPadding = 10;
                        break;
                      case 'bullet':
                        return Padding(
                          padding: EdgeInsets.only(
                            left: 16,
                            bottom: bottomPadding,
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('• ', style: TextStyle(fontSize: 12)),
                              Expanded(child: Text(text, style: style)),
                            ],
                          ),
                        );
                      case 'numbered':
                        final index = formattedContent.indexOf(item);
                        return Padding(
                          padding: EdgeInsets.only(
                            left: 16,
                            bottom: bottomPadding,
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '$index. ',
                                style: const TextStyle(fontSize: 12),
                              ),
                              Expanded(child: Text(text, style: style)),
                            ],
                          ),
                        );
                      default:
                        style = const TextStyle(
                          fontSize: 12,
                          color: Colors.black,
                        );
                        bottomPadding = 8;
                    }

                    return Padding(
                      padding: EdgeInsets.only(bottom: bottomPadding),
                      child: Text(text, style: style),
                    );
                  }).toList(),
                ),
              ),
            );
          },
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  void _showExportDialog(
    BuildContext context,
    DocumentProvider provider,
    int? userId,
    int documentId,
  ) {
    if (userId == null) return;
    

    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Export Document'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.description),
              title: const Text('Export as DOCX'),
              onTap: () async {
                Navigator.pop(context);
                final success = await provider.downloadFormattedDocument(
                  documentId,
                  userId!,
                  format: 'docx',
                );
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      success
                          ? 'Formatted DOCX downloaded!'
                          : 'Download failed: ${provider.errorMessage}',
                    ),
                    backgroundColor: success ? Colors.green : Colors.red,
                  ),
                );
              },
            ),
            ListTile(
              leading: const Icon(Icons.picture_as_pdf),
              title: const Text('Export as PDF'),
              onTap: () async {
                Navigator.pop(context);
                final success = await provider.downloadFormattedDocument(
                  documentId,
                  userId!,
                  format: 'pdf',
                );
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      success
                          ? 'Formatted PDF downloaded!'
                          : 'Download failed: ${provider.errorMessage}',
                    ),
                    backgroundColor: success ? Colors.green : Colors.red,
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
