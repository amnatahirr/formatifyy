import 'dart:async';
import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/collaboration_provider.dart';

class SectionEditorScreen extends StatefulWidget {
  final int projectId;
  final String sectionId;
  final String sectionName;
  final String initialContent;

  const SectionEditorScreen({
    super.key,
    required this.projectId,
    required this.sectionId,
    required this.sectionName,
    required this.initialContent,
  });

  @override
  State<SectionEditorScreen> createState() => _SectionEditorScreenState();
}

enum _SaveStatus { idle, saving, saved, error }

class _SectionEditorScreenState extends State<SectionEditorScreen> {
  late final TextEditingController _content;
  final _message = TextEditingController();
  bool _saving = false;
  bool _loadingImages = true;
  List<Map<String, dynamic>> _images = [];

  // ── auto-save state ────────────────────────────────────────────────────────
  _SaveStatus _saveStatus = _SaveStatus.idle;
  DateTime? _lastSavedAt;
  Timer? _debounce;
  Timer? _retryTimer;
  String? _pendingContent; // latest content waiting to be flushed

  @override
  void initState() {
    super.initState();
    _content = TextEditingController(text: widget.initialContent);
    _content.addListener(_onContentChanged);
    _loadImages();
    _loadDraft();
  }

  void _onContentChanged() {
    _pendingContent = _content.text;
    _retryTimer?.cancel();
    _debounce?.cancel();
    _debounce = Timer(const Duration(seconds: 2), _autoSave);
  }

  /// If an auto-saved draft exists on the server, show it instead of the
  /// committed text. The listener is detached while setting the text so that
  /// loading the draft does not immediately trigger another save.
  Future<void> _loadDraft() async {
    final vc = context.read<CollaborationProvider>();
    final draft = await vc.loadSectionDraft(widget.projectId, widget.sectionId);
    if (!mounted || draft == null || draft.isEmpty) return;
    if (draft == widget.initialContent) return;
    // Don't overwrite anything the user has already started typing.
    if (_content.text != widget.initialContent) return;
    _content.removeListener(_onContentChanged);
    _content.text = draft;
    _content.addListener(_onContentChanged);
    setState(() {});
  }

  Future<void> _autoSave() async {
    final content = _pendingContent;
    if (content == null || !mounted) return;
    setState(() => _saveStatus = _SaveStatus.saving);
    final vc = context.read<CollaborationProvider>();
    final ok = await vc.saveSectionDraft(
      projectId: widget.projectId,
      sectionId: widget.sectionId,
      content: content,
    );
    if (!mounted) return;
    setState(() {
      if (ok) {
        _saveStatus = _SaveStatus.saved;
        _lastSavedAt = DateTime.now();
        _pendingContent = null;
      } else {
        _saveStatus = _SaveStatus.error;
        // retry after 10 s if still on this screen
        _retryTimer = Timer(const Duration(seconds: 10), _autoSave);
      }
    });
  }

  Future<void> _loadImages() async {
    final vc = context.read<CollaborationProvider>();
    final images = await vc.loadSectionImages(
      widget.projectId,
      widget.sectionId,
    );
    if (mounted) {
      setState(() {
        _images = images;
        _loadingImages = false;
      });
    }
  }

  @override
  void dispose() {
    _content.removeListener(_onContentChanged);
    // Flush pending draft before leaving.
    if (_pendingContent != null) {
      final vc = context.read<CollaborationProvider>();
      vc.saveSectionDraft(
        projectId: widget.projectId,
        sectionId: widget.sectionId,
        content: _pendingContent!,
      );
    }
    _debounce?.cancel();
    _retryTimer?.cancel();
    _content.dispose();
    _message.dispose();
    super.dispose();
  }

  Future<void> _pickAndUploadImage() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.image,
      withData: false,
    );
    if (result == null || result.files.single.path == null) return;

    final vc = context.read<CollaborationProvider>();
    final uploaded = await vc.uploadSectionImage(
      widget.projectId,
      widget.sectionId,
      File(result.files.single.path!),
    );

    if (!mounted) return;
    if (uploaded != null) {
      setState(() => _images.add(uploaded));
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Image uploaded'),
          backgroundColor: Color(0xFF10B981),
        ),
      );
    } else {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(vc.error ?? 'Upload failed')));
    }
  }

  Future<void> _removeImage(int imageId) async {
    final vc = context.read<CollaborationProvider>();
    final ok = await vc.deleteSectionImage(
      widget.projectId,
      widget.sectionId,
      imageId,
    );
    if (!mounted) return;
    if (ok) {
      setState(() => _images.removeWhere((img) => img['id'] == imageId));
    }
  }

  Future<void> _save() async {
    // Cancel pending auto-save; the manual commit supersedes it.
    _debounce?.cancel();
    _retryTimer?.cancel();
    setState(() => _saving = true);
    final vc = context.read<CollaborationProvider>();

    final ok = await vc.saveSection(
      projectId: widget.projectId,
      sectionId: widget.sectionId,
      content: _content.text,
      message: _message.text.trim(),
    );

    if (!mounted) return;
    setState(() {
      _saving = false;
      if (ok) {
        _saveStatus = _SaveStatus.saved;
        _lastSavedAt = DateTime.now();
        _pendingContent = null;
      }
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          ok ? 'Commit saved — broadcast to team' : (vc.error ?? 'Save failed'),
        ),
        backgroundColor: ok ? const Color(0xFF10B981) : const Color(0xFFEF4444),
      ),
    );
    if (ok) Navigator.pop(context);
  }

  String _statusLabel() {
    switch (_saveStatus) {
      case _SaveStatus.saving:
        return 'Saving…';
      case _SaveStatus.saved:
        final t = _lastSavedAt;
        if (t != null) {
          final hh = t.hour.toString().padLeft(2, '0');
          final mm = t.minute.toString().padLeft(2, '0');
          return 'Saved ✓ $hh:$mm';
        }
        return 'Saved ✓';
      case _SaveStatus.error:
        return 'Save failed, retrying';
      case _SaveStatus.idle:
        return '';
    }
  }

  Color _statusColor() {
    switch (_saveStatus) {
      case _SaveStatus.saving:
        return const Color(0xFF94A3B8);
      case _SaveStatus.saved:
        return const Color(0xFF10B981);
      case _SaveStatus.error:
        return const Color(0xFFEF4444);
      case _SaveStatus.idle:
        return Colors.transparent;
    }
  }

  @override
  Widget build(BuildContext context) {
    final vc = context.watch<CollaborationProvider>();
    final label = _statusLabel();

    return Scaffold(
      backgroundColor: const Color(0xFF0F1419),
      appBar: AppBar(
        backgroundColor: const Color(0xFF141B27),
        title: Text(widget.sectionName),
        actions: [
          // Auto-save status indicator
          if (label.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 12),
              child: Center(
                child: Text(
                  label,
                  style: TextStyle(fontSize: 12, color: _statusColor()),
                ),
              ),
            ),
          TextButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Save Commit'),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            TextField(
              controller: _message,
              decoration: const InputDecoration(
                labelText: 'Commit message (optional)',
                hintText: 'e.g. Added methodology details',
              ),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: TextField(
                controller: _content,
                maxLines: null,
                expands: true,
                textAlignVertical: TextAlignVertical.top,
                decoration: InputDecoration(
                  alignLabelWithHint: true,
                  labelText: 'Section content',
                  hintText: 'Write content for "${widget.sectionName}"...',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                const Text(
                  'Attached Images',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                  ),
                ),
                const Spacer(),
                OutlinedButton.icon(
                  onPressed: _pickAndUploadImage,
                  icon: const Icon(Icons.image, size: 16),
                  label: const Text('Upload Image'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: const Color(0xFF6366F1),
                    side: const BorderSide(color: Color(0xFF6366F1)),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 8,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            if (_loadingImages)
              const SizedBox(
                height: 80,
                child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
              )
            else if (_images.isEmpty)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: const Color(0xFF1A1F2E),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFF2D3748)),
                ),
                child: const Text(
                  'No images attached. Upload images to include them in the merged document.',
                  style: TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
                  textAlign: TextAlign.center,
                ),
              )
            else
              SizedBox(
                height: 90,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: _images.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 10),
                  itemBuilder: (_, i) {
                    final img = _images[i];
                    final imageId = img['id'] as int;
                    final url = vc.sectionImageUrl(
                      widget.projectId,
                      widget.sectionId,
                      imageId,
                    );
                    return Stack(
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: Image.network(
                            url,
                            width: 90,
                            height: 90,
                            fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) => Container(
                              width: 90,
                              height: 90,
                              color: const Color(0xFF2D3748),
                              child: const Icon(
                                Icons.broken_image,
                                color: Color(0xFF94A3B8),
                              ),
                            ),
                          ),
                        ),
                        Positioned(
                          top: 2,
                          right: 2,
                          child: GestureDetector(
                            onTap: () => _removeImage(imageId),
                            child: Container(
                              padding: const EdgeInsets.all(2),
                              decoration: const BoxDecoration(
                                color: Color(0xFFEF4444),
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(
                                Icons.close,
                                size: 14,
                                color: Colors.white,
                              ),
                            ),
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),
            const SizedBox(height: 12),
            const Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Auto-saved as a draft. Save Commit creates a permanent version. Images are included when the section is merged.',
                style: TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
