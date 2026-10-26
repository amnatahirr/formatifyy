import 'dart:io';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:open_file_plus/open_file_plus.dart';
import 'package:path_provider/path_provider.dart';
import 'package:provider/provider.dart';
import '../../providers/collaboration_provider.dart';

import '../../widgets/tr.dart';
class ProjectDownloadScreen extends StatefulWidget {
  final int projectId;
  final int? mergeId;
  final Map<String, dynamic>? analysisReport;

  const ProjectDownloadScreen({
    super.key,
    required this.projectId,
    this.mergeId,
    this.analysisReport,
  });

  @override
  State<ProjectDownloadScreen> createState() => _ProjectDownloadScreenState();
}

class _ProjectDownloadScreenState extends State<ProjectDownloadScreen> {
  bool _downloading = false;

  Future<void> _download() async {
    setState(() => _downloading = true);
    final vc = context.read<CollaborationProvider>();

    final url = vc.downloadUrl(
      widget.projectId,
      mergeId: widget.mergeId,
    );

    try {
      final resp = await http.get(Uri.parse(url));
      if (resp.statusCode != 200) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Download failed: ${resp.statusCode}')),
        );
        return;
      }

      if (kIsWeb) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Tr('Document ready on server — use export from reports tab')),
        );
        return;
      }

      final dir = await getDownloadsDirectory() ?? await getApplicationDocumentsDirectory();
      final file = File('${dir.path}/formatify_merged_${widget.projectId}.docx');
      await file.writeAsBytes(resp.bodyBytes);
      await OpenFile.open(file.path);

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Saved to ${file.path}')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    } finally {
      if (mounted) setState(() => _downloading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final report = widget.analysisReport;
    final stats = report?['stats'] as Map<String, dynamic>?;
    final totalIssues = stats?['total_issues'] ?? report?['issues']?.length ?? 0;

    return Scaffold(
      backgroundColor: const Color(0xFF0F1419),
      appBar: AppBar(
        backgroundColor: const Color(0xFF141B27),
        title: const Tr('Merged Document'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: const Color(0xFF10B981).withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFF10B981).withOpacity(0.3)),
              ),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.check_circle, color: Color(0xFF10B981), size: 40),
                  SizedBox(height: 12),
                  Tr('Merge completed successfully',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  SizedBox(height: 6),
                  Tr('The final document was assembled in template section order and analyzed with the Formatify 6-function pipeline.',
                    style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12, height: 1.4),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            if (report != null && report['error'] == null) ...[
              const Tr('Analysis Summary',
                  style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Text('Total issues found: $totalIssues',
                  style: const TextStyle(color: Color(0xFF94A3B8))),
              if (stats != null) ...[
                Text('Grammar: ${stats['grammar_issues'] ?? 0}',
                    style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12)),
                Text('Formatting: ${stats['formatting_issues'] ?? 0}',
                    style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12)),
                Text('Plagiarism: ${stats['plagiarism_issues'] ?? 0}',
                    style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12)),
              ],
            ] else if (report?['error'] != null)
              Text('Analysis note: ${report!['error']}',
                  style: const TextStyle(color: Color(0xFFF59E0B), fontSize: 12)),
            const Spacer(),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _downloading ? null : _download,
                icon: _downloading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.download),
                label: const Tr('Download Merged DOCX'),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
