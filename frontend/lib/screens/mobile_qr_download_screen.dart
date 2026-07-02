import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:open_file_plus/open_file_plus.dart';

class MobileQrDownloadScreen extends StatefulWidget {
  final String qrId;
  final String host; 

  const MobileQrDownloadScreen({
    Key? key,
    required this.qrId,
    required this.host,
  }) : super(key: key);

  @override
  State<MobileQrDownloadScreen> createState() => _MobileQrDownloadScreenState();
}

enum _DownloadState { downloading, success, error, expired }

class _MobileQrDownloadScreenState extends State<MobileQrDownloadScreen>
    with SingleTickerProviderStateMixin {
  _DownloadState _state = _DownloadState.downloading;
  String _errorMessage = '';
  String _savedFileName = '';
  String _savedFilePath = '';
  double _downloadProgress = 0;
  late AnimationController _pulseController;
  late Animation<double> _pulseAnim;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
    _pulseAnim = Tween<double>(begin: 0.85, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
    _downloadFile();
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  String get _baseUrl => 'http://${widget.host}';

  Future<void> _downloadFile() async {
    setState(() {
      _state = _DownloadState.downloading;
      _downloadProgress = 0;
    });

    try {
      final uri = Uri.parse('$_baseUrl/qr/download/${widget.qrId}');
      final request = http.Request('GET', uri);
      final streamedResponse = await request.send().timeout(const Duration(seconds: 30));

      if (streamedResponse.statusCode == 410) {
        setState(() {
          _state = _DownloadState.expired;
          _errorMessage = 'This QR code has already been used or has expired.\n\nGenerate a new QR from your Formatify desktop app.';
        });
        return;
      }

      if (streamedResponse.statusCode != 200) {
        setState(() {
          _state = _DownloadState.error;
          _errorMessage = 'Server returned an error (${streamedResponse.statusCode}).\n\nPlease try again.';
        });
        return;
      }

      // Extract filename from Content-Disposition header
      String filename = 'formatify_download';
      final contentDisposition = streamedResponse.headers['content-disposition'];
      if (contentDisposition != null) {
        final match = RegExp(r'filename="?([^";]+)"?').firstMatch(contentDisposition);
        if (match != null) filename = match.group(1)!;
      }

      // Determine save directory
      Directory saveDir;
      if (Platform.isAndroid) {
        saveDir = Directory('/storage/emulated/0/Download');
        if (!await saveDir.exists()) {
          saveDir = await getApplicationDocumentsDirectory();
        }
      } else if (Platform.isIOS) {
        saveDir = await getApplicationDocumentsDirectory();
      } else {
        saveDir = await getApplicationDocumentsDirectory();
      }

      final filePath = '${saveDir.path}/$filename';

      // Stream download with progress
      final contentLength = streamedResponse.contentLength ?? 0;
      final List<int> bytes = [];
      int received = 0;

      await streamedResponse.stream.listen((chunk) {
        bytes.addAll(chunk);
        received += chunk.length;
        if (contentLength > 0) {
          setState(() {
            _downloadProgress = received / contentLength;
          });
        } else {
          // Unknown size — pulse progress
          setState(() {
            _downloadProgress = (_downloadProgress + 0.01).clamp(0, 0.95);
          });
        }
      }).asFuture();

      // Write file
      final outputFile = File(filePath);
      await outputFile.writeAsBytes(Uint8List.fromList(bytes));

      setState(() {
        _state = _DownloadState.success;
        _savedFileName = filename;
        _savedFilePath = filePath;
        _downloadProgress = 1.0;
      });
    } catch (e) {
      setState(() {
        _state = _DownloadState.error;
        _errorMessage = 'Download failed: ${e.toString()}\n\nMake sure your phone and computer are on the same Wi-Fi.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            Expanded(child: _buildBody()),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        border: Border(
          bottom: BorderSide(color: Colors.white.withOpacity(0.08)),
        ),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF10B981), Color(0xFF3B82F6)],
              ),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.download_rounded, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 14),
          const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Formatify',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              Text(
                'Download Report',
                style: TextStyle(color: Color(0xFF64748B), fontSize: 12),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildBody() {
    switch (_state) {
      case _DownloadState.downloading:
        return _buildDownloading();
      case _DownloadState.success:
        return _buildSuccess();
      case _DownloadState.error:
        return _buildError();
      case _DownloadState.expired:
        return _buildExpired();
    }
  }

  Widget _buildDownloading() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ScaleTransition(
              scale: _pulseAnim,
              child: Container(
                width: 96,
                height: 96,
                decoration: BoxDecoration(
                  color: const Color(0xFF10B981).withOpacity(0.12),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.cloud_download_rounded, color: Color(0xFF10B981), size: 44),
              ),
            ),
            const SizedBox(height: 28),
            const Text(
              'Downloading your report',
              style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Text(
              'Please wait...',
              style: TextStyle(color: Colors.white.withOpacity(0.45), fontSize: 14),
            ),
            const SizedBox(height: 36),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: _downloadProgress > 0 ? _downloadProgress : null,
                minHeight: 8,
                backgroundColor: const Color(0xFF1A1F2E),
                color: const Color(0xFF10B981),
              ),
            ),
            if (_downloadProgress > 0) ...[
              const SizedBox(height: 10),
              Text(
                '${(_downloadProgress * 100).toInt()}%',
                style: const TextStyle(color: Color(0xFF10B981), fontSize: 13, fontWeight: FontWeight.w600),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSuccess() {
    final ext = _savedFileName.split('.').last.toLowerCase();
    final icon = ext == 'pdf'
        ? Icons.picture_as_pdf_rounded
        : ext == 'docx' || ext == 'doc'
            ? Icons.description_rounded
            : Icons.insert_drive_file_rounded;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(32),
      child: Column(
        children: [
          const SizedBox(height: 24),
          Container(
            width: 96,
            height: 96,
            decoration: BoxDecoration(
              color: const Color(0xFF10B981).withOpacity(0.12),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.check_circle_rounded, color: Color(0xFF10B981), size: 50),
          ),
          const SizedBox(height: 24),
          const Text(
            'Download Complete!',
            style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF161B22),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: Colors.white.withOpacity(0.08)),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFF10B981).withOpacity(0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, color: const Color(0xFF10B981), size: 26),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _savedFileName,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        Platform.isAndroid ? 'Saved to Downloads' : 'Saved to Formatify',
                        style: const TextStyle(color: Color(0xFF10B981), fontSize: 12),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 28),
          Text(
            'Your formatted report has been saved to your device successfully.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 14, height: 1.5),
          ),
          const SizedBox(height: 36),
          Row(
            children: [
              Expanded(
                child: SizedBox(
                  height: 50,
                  child: OutlinedButton.icon(
                    onPressed: () async {
                      final result = await OpenFile.open(_savedFilePath);
                      if (result.type != ResultType.done && mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('Could not open file: ${result.message}')),
                        );
                      }
                    },
                    icon: const Icon(Icons.description_outlined, size: 18),
                    label: const Text('Open file', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFF10B981),
                      side: const BorderSide(color: Color(0xFF10B981)),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: SizedBox(
                  height: 50,
                  child: ElevatedButton.icon(
                    onPressed: () async {
                      await SharePlus.instance.share(
                        ShareParams(
                          files: [XFile(_savedFilePath)],
                          subject: _savedFileName,
                        ),
                      );
                    },
                    icon: const Icon(Icons.share_rounded, size: 18),
                    label: const Text('Share / Save', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF10B981),
                      foregroundColor: Colors.white,
                      elevation: 0,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            height: 44,
            child: TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(
                'Back to home',
                style: TextStyle(color: Colors.white.withOpacity(0.5), fontWeight: FontWeight.w600),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 90,
              height: 90,
              decoration: BoxDecoration(
                color: const Color(0xFFEF4444).withOpacity(0.12),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.error_outline_rounded, color: Color(0xFFEF4444), size: 44),
            ),
            const SizedBox(height: 24),
            const Text(
              'Download Failed',
              style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFFEF4444).withOpacity(0.08),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFEF4444).withOpacity(0.2)),
              ),
              child: Text(
                _errorMessage,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Color(0xFFEF4444), fontSize: 13, height: 1.5),
              ),
            ),
            const SizedBox(height: 32),
            SizedBox(
              width: double.infinity,
              height: 50,
              child: ElevatedButton.icon(
                onPressed: _downloadFile,
                icon: const Icon(Icons.refresh_rounded, size: 18),
                label: const Text('Retry Download', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF3B82F6),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildExpired() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 90,
              height: 90,
              decoration: BoxDecoration(
                color: const Color(0xFFD97706).withOpacity(0.12),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.timer_off_outlined, color: Color(0xFFD97706), size: 44),
            ),
            const SizedBox(height: 24),
            const Text(
              'QR Code Expired',
              style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            Text(
              _errorMessage,
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 14, height: 1.5),
            ),
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: const Color(0xFFD97706).withOpacity(0.08),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFFD97706).withOpacity(0.2)),
              ),
              child: const Text(
                'Go to your Formatify desktop app → open your report → Export → Generate a new QR code',
                textAlign: TextAlign.center,
                style: TextStyle(color: Color(0xFFD97706), fontSize: 13, height: 1.5),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
