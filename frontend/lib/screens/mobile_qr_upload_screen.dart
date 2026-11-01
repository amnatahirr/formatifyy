import 'dart:io';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';

import '../widgets/tr.dart';
class MobileQrUploadScreen extends StatefulWidget {
  final String sessionId;
  final String host; 

  const MobileQrUploadScreen({
    Key? key,
    required this.sessionId,
    required this.host,
  }) : super(key: key);

  @override
  State<MobileQrUploadScreen> createState() => _MobileQrUploadScreenState();
}

enum _UploadState { validating, ready, uploading, success, error, expired }

class _MobileQrUploadScreenState extends State<MobileQrUploadScreen>
    with SingleTickerProviderStateMixin {
  _UploadState _state = _UploadState.validating;
  String _errorMessage = '';
  String _uploadedFileName = '';
  double _uploadProgress = 0;
  late AnimationController _pulseController;
  late Animation<double> _pulseAnim;
  Map<String, dynamic>? _session;

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
    _validateSession();
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  String get _baseUrl => 'http://${widget.host}';

  Future<void> _validateSession() async {
    try {
      final res = await http
          .get(Uri.parse('$_baseUrl/qr/upload/${widget.sessionId}'))
          .timeout(const Duration(seconds: 10));

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        setState(() {
          _session = data;
          _state = _UploadState.ready;
        });
      } else {
        setState(() {
          _state = _UploadState.expired;
          _errorMessage = 'QR session expired or invalid. Please generate a new QR from the desktop app.';
        });
      }
    } catch (e) {
      setState(() {
        _state = _UploadState.error;
        _errorMessage = 'Could not connect to server. Make sure your phone and computer are on the same Wi-Fi network.\n\nServer: ${widget.host}';
      });
    }
  }

  Future<void> _uploadFromCamera() async {
    final picker = ImagePicker();
    final XFile? image = await picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 90,
    );
    if (image != null) {
      await _uploadFile(File(image.path), image.name);
    }
  }

  Future<void> _uploadFromGallery() async {
    final picker = ImagePicker();
    final XFile? image = await picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 90,
    );
    if (image != null) {
      await _uploadFile(File(image.path), image.name);
    }
  }

  Future<void> _uploadFromFiles() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'docx', 'doc', 'txt', 'png', 'jpg', 'jpeg'],
    );
    if (result != null && result.files.single.path != null) {
      final file = File(result.files.single.path!);
      await _uploadFile(file, result.files.single.name);
    }
  }

  Future<void> _uploadFile(File file, String filename) async {
    setState(() {
      _state = _UploadState.uploading;
      _uploadProgress = 0;
      _uploadedFileName = filename;
    });

    try {
      final uri = Uri.parse('$_baseUrl/qr/upload/${widget.sessionId}/file');
      final request = http.MultipartRequest('POST', uri);
      request.files.add(await http.MultipartFile.fromPath('file', file.path, filename: filename));

      // Simulate progress with stream
      final streamedResponse = await request.send();

      // collect response
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        setState(() {
          _state = _UploadState.success;
          _uploadProgress = 1.0;
        });
      } else {
        final body = jsonDecode(response.body);
        setState(() {
          _state = _UploadState.error;
          _errorMessage = body['detail'] ?? 'Upload failed. Please try again.';
        });
      }
    } catch (e) {
      setState(() {
        _state = _UploadState.error;
        _errorMessage = 'Upload failed: ${e.toString()}';
      });
    }
  }

  void _reset() {
    setState(() {
      _state = _UploadState.ready;
      _errorMessage = '';
      _uploadedFileName = '';
      _uploadProgress = 0;
    });
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
                colors: [Color(0xFF3B82F6), Color(0xFF6366F1)],
              ),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.cloud_upload_outlined, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 14),
          const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Tr('Formatify',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              Tr('Upload Document',
                style: TextStyle(
                  color: Color(0xFF64748B),
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildBody() {
    switch (_state) {
      case _UploadState.validating:
        return _buildValidating();
      case _UploadState.ready:
        return _buildReady();
      case _UploadState.uploading:
        return _buildUploading();
      case _UploadState.success:
        return _buildSuccess();
      case _UploadState.error:
        return _buildError();
      case _UploadState.expired:
        return _buildExpired();
    }
  }

  Widget _buildValidating() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ScaleTransition(
            scale: _pulseAnim,
            child: Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: const Color(0xFF3B82F6).withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: const CircularProgressIndicator(
                color: Color(0xFF3B82F6),
                strokeWidth: 3,
              ),
            ),
          ),
          const SizedBox(height: 24),
          const Tr('Validating QR Session...',
            style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          Text(
            'Connecting to ${widget.host}',
            style: const TextStyle(color: Color(0xFF64748B), fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _buildReady() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          const SizedBox(height: 16),
          // Status badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              color: const Color(0xFF10B981).withOpacity(0.12),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: const Color(0xFF10B981).withOpacity(0.3)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 8, height: 8,
                  decoration: const BoxDecoration(
                    color: Color(0xFF10B981), shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 8),
                const Tr('Session Active',
                  style: TextStyle(color: Color(0xFF10B981), fontSize: 13, fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
          const SizedBox(height: 32),
          const Tr('Send a file to your\ndesktop report',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Colors.white,
              fontSize: 26,
              fontWeight: FontWeight.w700,
              height: 1.3,
            ),
          ),
          const SizedBox(height: 12),
          Tr('Choose how you want to add your document or image',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 14, height: 1.5),
          ),
          const SizedBox(height: 40),
          _buildUploadOption(
            icon: Icons.camera_alt_rounded,
            color: const Color(0xFF3B82F6),
            title: 'Take a Photo',
            subtitle: 'Use your camera to scan a document',
            onTap: _uploadFromCamera,
          ),
          const SizedBox(height: 16),
          _buildUploadOption(
            icon: Icons.photo_library_rounded,
            color: const Color(0xFF8B5CF6),
            title: 'Choose from Gallery',
            subtitle: 'Pick an image from your photo library',
            onTap: _uploadFromGallery,
          ),
          const SizedBox(height: 16),
          _buildUploadOption(
            icon: Icons.folder_open_rounded,
            color: const Color(0xFF10B981),
            title: 'Browse Files',
            subtitle: 'Upload PDF, DOCX, or other documents',
            onTap: _uploadFromFiles,
          ),
          const SizedBox(height: 32),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.lock_outline, size: 14, color: Colors.white.withOpacity(0.3)),
              const SizedBox(width: 6),
             
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildUploadOption({
    required IconData icon,
    required Color color,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: const Color(0xFF161B22),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.white.withOpacity(0.08)),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: color.withOpacity(0.12),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 24),
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
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    subtitle,
                    style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 13),
                  ),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: Colors.white.withOpacity(0.25), size: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildUploading() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ScaleTransition(
              scale: _pulseAnim,
              child: Container(
                width: 90,
                height: 90,
                decoration: BoxDecoration(
                  color: const Color(0xFF3B82F6).withOpacity(0.12),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.cloud_upload_rounded, color: Color(0xFF3B82F6), size: 40),
              ),
            ),
            const SizedBox(height: 28),
            const Tr('Uploading...',
              style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            Text(
              _uploadedFileName,
              style: const TextStyle(color: Color(0xFF64748B), fontSize: 13),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 32),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: null,
                minHeight: 6,
                backgroundColor: const Color(0xFF1A1F2E),
                color: const Color(0xFF3B82F6),
              ),
            ),
            const SizedBox(height: 16),
            Tr('Sending to your desktop app...',
              style: TextStyle(color: Colors.white.withOpacity(0.45), fontSize: 13),
            ),
          ],
        ),
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
            const SizedBox(height: 28),
            const Tr('Upload Successful!',
              style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(
                color: const Color(0xFF161B22),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: Colors.white.withOpacity(0.08)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.description_outlined, color: Color(0xFF10B981), size: 16),
                  const SizedBox(width: 8),
                  Text(
                    _uploadedFileName,
                    style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            Tr('Your file has been sent to your desktop Formatify app. You can close this screen.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 14, height: 1.5),
            ),
            const SizedBox(height: 36),
            SizedBox(
              width: double.infinity,
              height: 50,
              child: ElevatedButton.icon(
                onPressed: _reset,
                icon: const Icon(Icons.add_photo_alternate_outlined, size: 18),
                label: const Tr('Upload Another File', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                style: ElevatedButton.styleFrom(
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
            const Tr('Something went wrong',
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
                onPressed: _reset,
                icon: const Icon(Icons.refresh_rounded, size: 18),
                label: const Tr('Try Again', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                style: ElevatedButton.styleFrom(
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
            const Tr('QR Code Expired',
              style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            Text(
              _errorMessage,
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 14, height: 1.5),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: const Color(0xFFD97706).withOpacity(0.08),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFFD97706).withOpacity(0.2)),
              ),
              child: const Tr('Go to your Formatify desktop app → New Report → Generate a new QR code',
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
