import 'dart:io';
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'mobile_qr_upload_screen.dart';
import 'mobile_qr_download_screen.dart';

import '../widgets/tr.dart';
class MobileCompanionScreen extends StatefulWidget {
  const MobileCompanionScreen({Key? key}) : super(key: key);

  @override
  State<MobileCompanionScreen> createState() => _MobileCompanionScreenState();
}

class _MobileCompanionScreenState extends State<MobileCompanionScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _breatheController;
  late Animation<double> _breatheAnim;

  @override
  void initState() {
    super.initState();
    _breatheController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2500),
    )..repeat(reverse: true);
    _breatheAnim = Tween<double>(begin: 0.92, end: 1.0).animate(
      CurvedAnimation(parent: _breatheController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _breatheController.dispose();
    super.dispose();
  }

  void _openQrScanner() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const _QrScannerPage()),
    );
  }

  Future<void> _uploadFromCamera() async {
    final picker = ImagePicker();
    final XFile? image = await picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 90,
    );
    if (image != null && mounted) {
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => _StandaloneUploadPage(
            file: File(image.path),
            filename: image.name,
          ),
        ),
      );
    }
  }

  Future<void> _uploadFromGallery() async {
    final picker = ImagePicker();
    final XFile? image = await picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 90,
    );
    if (image != null && mounted) {
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => _StandaloneUploadPage(
            file: File(image.path),
            filename: image.name,
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final canPop = Navigator.of(context).canPop();

    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      // When pushed from the student dashboard, provide a normal back affordance.
      // (As app home it had no AppBar — system back alone was enough only as root.)
      appBar: canPop
          ? AppBar(
              backgroundColor: const Color(0xFF161B22),
              foregroundColor: Colors.white,
              elevation: 0,
              title: const Tr('Quick Access',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
              ),
            )
          : null,
      body: SafeArea(
        child: Column(
          children: [
            if (!canPop) _buildHeader(),
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
        gradient: const LinearGradient(
          colors: [Color(0xFF161B22), Color(0xFF0D1117)],
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
        ),
        border: Border(
          bottom: BorderSide(color: Colors.white.withOpacity(0.06)),
        ),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(11),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)],
              ),
              borderRadius: BorderRadius.circular(14),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF6366F1).withOpacity(0.3),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: const Icon(Icons.phone_android_rounded, color: Colors.white, size: 22),
          ),
          const SizedBox(width: 14),
          const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Tr('Formatify',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.3,
                ),
              ),
              Tr('Mobile Companion',
                style: TextStyle(
                  color: Color(0xFF8B5CF6),
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildBody() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          const SizedBox(height: 20),
          // Breathing QR icon
          ScaleTransition(
            scale: _breatheAnim,
            child: Container(
              width: 100,
              height: 100,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(28),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF6366F1).withOpacity(0.35),
                    blurRadius: 30,
                    offset: const Offset(0, 10),
                  ),
                ],
              ),
              child: const Icon(Icons.qr_code_scanner_rounded, color: Colors.white, size: 48),
            ),
          ),
          const SizedBox(height: 28),
          const Tr('Quick Access',
            style: TextStyle(
              color: Colors.white,
              fontSize: 28,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 8),
          Tr('Scan a QR code from your desktop or upload files directly from your phone',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Colors.white.withOpacity(0.5),
              fontSize: 14,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 40),
          // Primary action — Scan QR
          _buildPrimaryAction(
            icon: Icons.qr_code_scanner_rounded,
            title: 'Scan QR Code',
            subtitle: 'Scan from your desktop Formatify app',
            gradient: const [Color(0xFF6366F1), Color(0xFF8B5CF6)],
            onTap: _openQrScanner,
          ),
          const SizedBox(height: 20),
          // Divider with label
          Row(
            children: [
              Expanded(child: Container(height: 1, color: Colors.white.withOpacity(0.06))),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Tr('OR UPLOAD DIRECTLY',
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.3),
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.2,
                  ),
                ),
              ),
              Expanded(child: Container(height: 1, color: Colors.white.withOpacity(0.06))),
            ],
          ),
          const SizedBox(height: 20),
          // Secondary actions
          Row(
            children: [
              Expanded(
                child: _buildSecondaryAction(
                  icon: Icons.camera_alt_rounded,
                  title: 'Camera',
                  subtitle: 'Take a photo',
                  color: const Color(0xFF3B82F6),
                  onTap: _uploadFromCamera,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: _buildSecondaryAction(
                  icon: Icons.photo_library_rounded,
                  title: 'Gallery',
                  subtitle: 'Pick an image',
                  color: const Color(0xFF10B981),
                  onTap: _uploadFromGallery,
                ),
              ),
            ],
          ),
          const SizedBox(height: 40),
          // Info card
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF161B22),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: Colors.white.withOpacity(0.06)),
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: const Color(0xFF3B82F6).withOpacity(0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.info_outline_rounded, color: Color(0xFF3B82F6), size: 20),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Tr('Make sure your phone and computer are on the same Wi-Fi network for uploads to work.',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.45),
                      fontSize: 12,
                      height: 1.5,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPrimaryAction({
    required IconData icon,
    required String title,
    required String subtitle,
    required List<Color> gradient,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(22),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: gradient.map((c) => c.withOpacity(0.12)).toList(),
          ),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: gradient.first.withOpacity(0.25)),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: gradient),
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: gradient.first.withOpacity(0.3),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Icon(icon, color: Colors.white, size: 28),
            ),
            const SizedBox(width: 18),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    subtitle,
                    style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 13),
                  ),
                ],
              ),
            ),
            Icon(Icons.arrow_forward_ios_rounded, color: Colors.white.withOpacity(0.3), size: 16),
          ],
        ),
      ),
    );
  }

  Widget _buildSecondaryAction({
    required IconData icon,
    required String title,
    required String subtitle,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: const Color(0xFF161B22),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: Colors.white.withOpacity(0.06)),
        ),
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: color.withOpacity(0.12),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(icon, color: color, size: 28),
            ),
            const SizedBox(height: 14),
            Text(
              title,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 15,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 3),
            Text(
              subtitle,
              style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }
}

// ─── QR Scanner Page ──────────────────────────────────────────
class _QrScannerPage extends StatefulWidget {
  const _QrScannerPage({Key? key}) : super(key: key);

  @override
  State<_QrScannerPage> createState() => _QrScannerPageState();
}

class _QrScannerPageState extends State<_QrScannerPage> {
  final MobileScannerController _controller = MobileScannerController();
  bool _hasNavigated = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_hasNavigated) return;

    for (final barcode in capture.barcodes) {
      final String? rawValue = barcode.rawValue;
      if (rawValue == null) continue;

      // Parse the formatify:// deep link
      final uri = Uri.tryParse(rawValue);
      if (uri == null || uri.scheme != 'formatify') continue;

      _hasNavigated = true;
      _controller.stop();

      final host = uri.queryParameters['host'] ?? '172.20.10.2:8000';

      if (uri.host == 'qr-upload') {
        final session = uri.queryParameters['session'];
        if (session != null) {
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(
              builder: (_) => MobileQrUploadScreen(sessionId: session, host: host),
            ),
          );
        }
      } else if (uri.host == 'qr-download') {
        final id = uri.queryParameters['id'];
        if (id != null) {
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(
              builder: (_) => MobileQrDownloadScreen(qrId: id, host: host),
            ),
          );
        }
      }
      break;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // Scanner
          MobileScanner(
            controller: _controller,
            onDetect: _onDetect,
          ),
          // Overlay
          CustomPaint(
            painter: _ScannerOverlayPainter(),
            child: const SizedBox.expand(),
          ),
          // Top bar
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: SafeArea(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                child: Row(
                  children: [
                    GestureDetector(
                      onTap: () => Navigator.of(context).pop(),
                      child: Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: Colors.black.withOpacity(0.5),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: const Icon(Icons.arrow_back_rounded, color: Colors.white, size: 22),
                      ),
                    ),
                    const SizedBox(width: 16),
                    const Tr('Scan QR Code',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          // Bottom instruction
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
                  decoration: BoxDecoration(
                    color: Colors.black.withOpacity(0.7),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: Colors.white.withOpacity(0.1)),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.qr_code_rounded, color: Color(0xFF8B5CF6), size: 20),
                      const SizedBox(width: 10),
                      Tr('Point at a Formatify QR code',
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.8),
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// Custom overlay painter for the scanner viewfinder
class _ScannerOverlayPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final scanArea = Rect.fromCenter(
      center: Offset(size.width / 2, size.height / 2 - 40),
      width: 260,
      height: 260,
    );

    // Semi-transparent background outside scan area
    final bgPaint = Paint()..color = Colors.black.withOpacity(0.5);
    canvas.drawPath(
      Path.combine(
        PathOperation.difference,
        Path()..addRect(Rect.fromLTWH(0, 0, size.width, size.height)),
        Path()..addRRect(RRect.fromRectAndRadius(scanArea, const Radius.circular(20))),
      ),
      bgPaint,
    );

    // Corner brackets
    final cornerPaint = Paint()
      ..color = const Color(0xFF8B5CF6)
      ..strokeWidth = 4
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    const len = 30.0;
    const r = 20.0;

    // Top-left corner
    canvas.drawArc(Rect.fromLTWH(scanArea.left, scanArea.top, r * 2, r * 2), 3.14, 0.5 * 3.14, false, cornerPaint);
    canvas.drawLine(Offset(scanArea.left, scanArea.top + r), Offset(scanArea.left, scanArea.top + len), cornerPaint);
    canvas.drawLine(Offset(scanArea.left + r, scanArea.top), Offset(scanArea.left + len, scanArea.top), cornerPaint);

    // Top-right corner
    canvas.drawArc(Rect.fromLTWH(scanArea.right - r * 2, scanArea.top, r * 2, r * 2), -0.5 * 3.14, 0.5 * 3.14, false, cornerPaint);
    canvas.drawLine(Offset(scanArea.right, scanArea.top + r), Offset(scanArea.right, scanArea.top + len), cornerPaint);
    canvas.drawLine(Offset(scanArea.right - r, scanArea.top), Offset(scanArea.right - len, scanArea.top), cornerPaint);

    // Bottom-left corner
    canvas.drawArc(Rect.fromLTWH(scanArea.left, scanArea.bottom - r * 2, r * 2, r * 2), 0.5 * 3.14, 0.5 * 3.14, false, cornerPaint);
    canvas.drawLine(Offset(scanArea.left, scanArea.bottom - r), Offset(scanArea.left, scanArea.bottom - len), cornerPaint);
    canvas.drawLine(Offset(scanArea.left + r, scanArea.bottom), Offset(scanArea.left + len, scanArea.bottom), cornerPaint);

    // Bottom-right corner
    canvas.drawArc(Rect.fromLTWH(scanArea.right - r * 2, scanArea.bottom - r * 2, r * 2, r * 2), 0, 0.5 * 3.14, false, cornerPaint);
    canvas.drawLine(Offset(scanArea.right, scanArea.bottom - r), Offset(scanArea.right, scanArea.bottom - len), cornerPaint);
    canvas.drawLine(Offset(scanArea.right - r, scanArea.bottom), Offset(scanArea.right - len, scanArea.bottom), cornerPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

// ─── Standalone Upload Page (Camera/Gallery without QR) ─────────────────
class _StandaloneUploadPage extends StatefulWidget {
  final File file;
  final String filename;
  const _StandaloneUploadPage({Key? key, required this.file, required this.filename}) : super(key: key);

  @override
  State<_StandaloneUploadPage> createState() => _StandaloneUploadPageState();
}

enum _StandaloneState { preview, uploading, success, error }

class _StandaloneUploadPageState extends State<_StandaloneUploadPage> {
  _StandaloneState _state = _StandaloneState.preview;
  String _errorMessage = '';
  final TextEditingController _hostController =
      TextEditingController(text: '172.20.10.2:8000');

  Future<void> _upload() async {
    setState(() => _state = _StandaloneState.uploading);

    try {
      final host = _hostController.text.trim();

      // Create a quick upload session
      final genRes = await http.post(
        Uri.parse('http://$host/qr/upload/generate'),
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: {
          'user_id': '1',
          'template_id': '1',
          'host': host,
        },
      ).timeout(const Duration(seconds: 10));

      if (genRes.statusCode != 200) {
        throw Exception('Could not connect to server');
      }

      final sessionData = jsonDecode(genRes.body);
      final sessionId = sessionData['session_id'];

      // Upload the file
      final uri = Uri.parse('http://$host/qr/upload/$sessionId/file');
      final request = http.MultipartRequest('POST', uri);
      request.files.add(
        await http.MultipartFile.fromPath('file', widget.file.path, filename: widget.filename),
      );

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        setState(() => _state = _StandaloneState.success);
      } else {
        final body = jsonDecode(response.body);
        throw Exception(body['detail'] ?? 'Upload failed');
      }
    } catch (e) {
      setState(() {
        _state = _StandaloneState.error;
        _errorMessage =
            'Upload failed: ${e.toString()}\n\nMake sure your phone and computer are on the same Wi-Fi network.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF161B22),
        title: const Tr('Upload File', style: TextStyle(fontWeight: FontWeight.w700)),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: SafeArea(child: _buildContent()),
    );
  }

  Widget _buildContent() {
    switch (_state) {
      case _StandaloneState.preview:
        return _buildPreview();
      case _StandaloneState.uploading:
        return _buildUploading();
      case _StandaloneState.success:
        return _buildSuccess();
      case _StandaloneState.error:
        return _buildError();
    }
  }

  Widget _buildPreview() {
    final isImage = widget.filename.toLowerCase().endsWith('.jpg') ||
        widget.filename.toLowerCase().endsWith('.jpeg') ||
        widget.filename.toLowerCase().endsWith('.png');

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          const SizedBox(height: 16),
          if (isImage)
            ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: Image.file(
                widget.file,
                height: 280,
                width: double.infinity,
                fit: BoxFit.cover,
              ),
            ),
          if (!isImage)
            Container(
              width: double.infinity,
              height: 180,
              decoration: BoxDecoration(
                color: const Color(0xFF161B22),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: Colors.white.withOpacity(0.08)),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.insert_drive_file_rounded, color: Color(0xFF3B82F6), size: 48),
                  const SizedBox(height: 12),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: Text(
                      widget.filename,
                      style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w500),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                    ),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 24),
          // Server host field
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF161B22),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: Colors.white.withOpacity(0.06)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Tr('Desktop Server',
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.6),
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _hostController,
                  style: const TextStyle(color: Colors.white, fontSize: 14),
                  decoration: InputDecoration(
                    hintText: '172.20.10.2:8000',
                    hintStyle: TextStyle(color: Colors.white.withOpacity(0.25)),
                    filled: true,
                    fillColor: const Color(0xFF0D1117),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: BorderSide(color: Colors.white.withOpacity(0.1)),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: BorderSide(color: Colors.white.withOpacity(0.1)),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide: const BorderSide(color: Color(0xFF6366F1)),
                    ),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    prefixIcon: const Icon(Icons.dns_outlined, color: Color(0xFF64748B), size: 18),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 28),
          SizedBox(
            width: double.infinity,
            height: 54,
            child: ElevatedButton.icon(
              onPressed: _upload,
              icon: const Icon(Icons.cloud_upload_rounded, size: 20),
              label: const Tr('Upload to Desktop',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF6366F1),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                elevation: 0,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildUploading() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: const Color(0xFF6366F1).withOpacity(0.12),
              shape: BoxShape.circle,
            ),
            child: const Center(
              child: CircularProgressIndicator(color: Color(0xFF6366F1), strokeWidth: 3),
            ),
          ),
          const SizedBox(height: 24),
          const Tr('Uploading...', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          Text(widget.filename, style: const TextStyle(color: Color(0xFF64748B), fontSize: 13)),
        ],
      ),
    );
  }

  Widget _buildSuccess() {
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
                color: const Color(0xFF10B981).withOpacity(0.12),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.check_rounded, color: Color(0xFF10B981), size: 48),
            ),
            const SizedBox(height: 24),
            const Tr('Upload Successful!',
              style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            Text(
              '${widget.filename} has been sent to your desktop Formatify app.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 14, height: 1.5),
            ),
            const SizedBox(height: 32),
            SizedBox(
              width: double.infinity,
              height: 50,
              child: ElevatedButton.icon(
                onPressed: () => Navigator.of(context).pop(),
                icon: const Icon(Icons.check_rounded, size: 18),
                label: const Tr('Done', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF10B981),
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
            const Tr('Upload Failed',
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
                onPressed: () => setState(() => _state = _StandaloneState.preview),
                icon: const Icon(Icons.refresh_rounded, size: 18),
                label: const Tr('Try Again', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
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
}
