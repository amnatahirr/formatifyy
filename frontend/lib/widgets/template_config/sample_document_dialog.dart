// lib/widgets/template_config/sample_document_dialog.dart
//
// Requires:  printing: ^5.13.0   (works on Android, iOS, web, desktop)
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:printing/printing.dart';

/// Shows the server-rendered sample document (PDF of the real .docx).
/// [loader] is called on open and again on "Retry".
class SampleDocumentDialog extends StatefulWidget {
  const SampleDocumentDialog({super.key, required this.loader});
  final Future<Uint8List> Function() loader;

  @override
  State<SampleDocumentDialog> createState() => _SampleDocumentDialogState();
}

class _SampleDocumentDialogState extends State<SampleDocumentDialog> {
  late Future<Uint8List> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.loader();
  }

  void _retry() => setState(() => _future = widget.loader());

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    return Dialog(
      backgroundColor: const Color(0xFF161B22),
      insetPadding: const EdgeInsets.all(24),
      child: SizedBox(
        width: size.width.clamp(320.0, 900.0),
        height: size.height * 0.9,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
              child: Row(
                children: [
                  const Icon(Icons.description_outlined,
                      color: Color(0xFF6366F1)),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Text('Sample document',
                        style: TextStyle(
                            color: Colors.white,
                            fontSize: 15,
                            fontWeight: FontWeight.w700)),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close, color: Colors.white70),
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                ],
              ),
            ),
            const Divider(height: 1, color: Color(0xFF30363D)),
            Expanded(
              child: FutureBuilder<Uint8List>(
                future: _future,
                builder: (context, snap) {
                  if (snap.connectionState != ConnectionState.done) {
                    return const Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          CircularProgressIndicator(),
                          SizedBox(height: 16),
                          Text('Generating sample document...',
                              style: TextStyle(color: Colors.white70)),
                        ],
                      ),
                    );
                  }
                  if (snap.hasError) {
                    return Center(
                      child: Padding(
                        padding: const EdgeInsets.all(24),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.error_outline,
                                color: Colors.redAccent, size: 40),
                            const SizedBox(height: 12),
                            Text('${snap.error}',
                                textAlign: TextAlign.center,
                                style: const TextStyle(color: Colors.white70)),
                            const SizedBox(height: 16),
                            OutlinedButton.icon(
                              onPressed: _retry,
                              icon: const Icon(Icons.refresh),
                              label: const Text('Retry'),
                            ),
                          ],
                        ),
                      ),
                    );
                  }
                  final bytes = snap.data!;
                  return PdfPreview(
                    build: (_) async => bytes,
                    canChangeOrientation: false,
                    canChangePageFormat: false,
                    canDebug: false,
                    allowPrinting: true,
                    allowSharing: true,
                    pdfFileName: 'template_sample.pdf',
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}