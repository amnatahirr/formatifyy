import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../config/api_config.dart';
import '../../models/admin_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/admin_api_service.dart';
import 'common_widgets.dart';

import '../tr.dart';
/// Logo + cover / project-info DOCX template uploads for frontmatter generation.
class FrontmatterAssetsCard extends StatefulWidget {
  const FrontmatterAssetsCard({super.key});

  @override
  State<FrontmatterAssetsCard> createState() => _FrontmatterAssetsCardState();
}

class _FrontmatterAssetsCardState extends State<FrontmatterAssetsCard> {
  final AdminApiService _api = AdminApiService();

  bool _loading = true;
  bool _uploadingLogo = false;
  bool _uploadingCover = false;
  bool _uploadingInfo = false;
  String? _error;
  FrontmatterConfigModel? _config;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final config = await _api.fetchFrontmatterConfig(userId);
      if (!mounted) return;
      setState(() {
        _config = config;
        _loading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _loading = false;
        });
      }
    }
  }

  void _snack(String message, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: error ? const Color(0xFFEF4444) : const Color(0xFF10B981),
      ),
    );
  }

  Future<void> _uploadLogo() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['png', 'jpg', 'jpeg', 'webp', 'gif'],
    );
    if (result == null || result.files.single.path == null) return;

    setState(() => _uploadingLogo = true);
    try {
      final updated = await _api.uploadFrontmatterLogo(userId, result.files.single.path!);
      if (!mounted) return;
      setState(() => _config = updated);
      _snack('Organization logo uploaded');
    } catch (e) {
      _snack(e.toString(), error: true);
    } finally {
      if (mounted) setState(() => _uploadingLogo = false);
    }
  }

  Future<void> _uploadTemplate(String kind) async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['docx'],
    );
    if (result == null || result.files.single.path == null) return;

    setState(() {
      if (kind == 'cover') {
        _uploadingCover = true;
      } else {
        _uploadingInfo = true;
      }
    });
    try {
      final updated = await _api.uploadFrontmatterTemplate(
        userId,
        kind,
        result.files.single.path!,
      );
      if (!mounted) return;
      setState(() => _config = updated);
      _snack(kind == 'cover' ? 'Cover page template replaced' : 'Project info template replaced');
    } catch (e) {
      _snack(e.toString(), error: true);
    } finally {
      if (mounted) {
        setState(() {
          _uploadingCover = false;
          _uploadingInfo = false;
        });
      }
    }
  }

  String? _logoPreviewUrl() {
    final config = _config;
    if (config == null || config.logoUrl == null || config.logoUrl!.isEmpty) return null;
    final root = ApiConfig.imageBaseUrl.replaceAll(RegExp(r'/$'), '');
    final path = config.logoUrl!.startsWith('/') ? config.logoUrl! : '/${config.logoUrl!}';
    return '$root$path?t=${DateTime.now().millisecondsSinceEpoch}';
  }

  String _formatBytes(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  @override
  Widget build(BuildContext context) {
    final config = _config;
    final logoUrl = _logoPreviewUrl();

    return CommonWidgets.buildCardContainer(
      icon: Icons.image_outlined,
      title: 'Cover Page Assets',
      subtitle: 'Organization logo and DOCX templates for cover / project-info pages',
      child: _loading
          ? const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Center(
                child: SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF6366F1)),
                ),
              ),
            )
          : _error != null
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(_error!, style: const TextStyle(color: Color(0xFFEF4444), fontSize: 12)),
                    TextButton(onPressed: _load, child: const Tr('Retry')),
                  ],
                )
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Tr('Organization logo',
                      style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.7)),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Container(
                          width: 64,
                          height: 64,
                          decoration: BoxDecoration(
                            color: const Color(0xFF0F1419),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: const Color(0xFF2D3748)),
                          ),
                          clipBehavior: Clip.antiAlias,
                          child: logoUrl != null && (config?.logoExists ?? false)
                              ? Image.network(
                                  logoUrl,
                                  fit: BoxFit.contain,
                                  errorBuilder: (_, __, ___) => Icon(
                                    Icons.broken_image_outlined,
                                    color: Colors.white.withOpacity(0.35),
                                  ),
                                )
                              : Icon(Icons.image_outlined, color: Colors.white.withOpacity(0.35)),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: _uploadingLogo ? null : _uploadLogo,
                            icon: _uploadingLogo
                                ? const SizedBox(
                                    width: 14,
                                    height: 14,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  )
                                : const Icon(Icons.upload_rounded, size: 16, color: Color(0xFF6366F1)),
                            label: Text(
                              _uploadingLogo ? 'Uploading…' : 'Upload logo',
                              style: const TextStyle(color: Color(0xFF6366F1), fontWeight: FontWeight.w600),
                            ),
                            style: OutlinedButton.styleFrom(
                              side: const BorderSide(color: Color(0xFF6366F1)),
                              padding: const EdgeInsets.symmetric(vertical: 14),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    _templateTile(
                      title: 'Cover page template (.docx)',
                      info: config?.coverTemplate,
                      uploading: _uploadingCover,
                      onUpload: () => _uploadTemplate('cover'),
                    ),
                    const SizedBox(height: 12),
                    _templateTile(
                      title: 'Project info page template (.docx)',
                      info: config?.infoTemplate,
                      uploading: _uploadingInfo,
                      onUpload: () => _uploadTemplate('info'),
                    ),
                    const SizedBox(height: 8),
                    Tr('Use Jinja placeholders like {{ project_title }}, {{ university_name }}, {%p for member in members %}.',
                      style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.45)),
                    ),
                  ],
                ),
    );
  }

  Widget _templateTile({
    required String title,
    required FrontmatterTemplateInfo? info,
    required bool uploading,
    required VoidCallback onUpload,
  }) {
    final exists = info?.exists == true;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1419),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFF2D3748)),
      ),
      child: Row(
        children: [
          Icon(
            exists ? Icons.description_rounded : Icons.note_add_outlined,
            color: exists ? const Color(0xFF10B981) : const Color(0xFFF59E0B),
            size: 20,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Text(
                  exists
                      ? '${info!.filename} · ${_formatBytes(info.sizeBytes)}'
                      : 'No template on file yet',
                  style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.45)),
                ),
              ],
            ),
          ),
          OutlinedButton(
            onPressed: uploading ? null : onUpload,
            style: OutlinedButton.styleFrom(
              foregroundColor: const Color(0xFF6366F1),
              side: const BorderSide(color: Color(0xFF6366F1)),
            ),
            child: uploading
                ? const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Tr('Replace'),
          ),
        ],
      ),
    );
  }
}
