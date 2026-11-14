import 'dart:async';
import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/collaboration_provider.dart';
import '../../widgets/document_preview_panel.dart';
import '../../widgets/tr.dart';

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
  late final CollaborationProvider _vc;
  final _message = TextEditingController();
  bool _saving = false;
  bool _loadingImages = true;
  List<Map<String, dynamic>> _images = [];

  // ── auto-save state ────────────────────────────────────────────────────────
  _SaveStatus _saveStatus = _SaveStatus.idle;
  DateTime? _lastSavedAt;
  Timer? _debounce;
  Timer? _retryTimer;
  String? _pendingContent;

  // ── live preview state ─────────────────────────────────────────────────────
  Timer? _previewDebounce;
  List<Map<String, dynamic>> _previewBlocks = [];
  bool _showPreviewOnNarrow = false;

  static const int _charsPerPage = 3200;

  @override
  void initState() {
    super.initState();
    _vc = context.read<CollaborationProvider>();
    _content = TextEditingController(text: widget.initialContent);
    _content.addListener(_onContentChanged);
    _previewBlocks = _buildBlocks(_content.text);
    _loadImages();
    _loadDraft();
  }

  void _onContentChanged() {
    _pendingContent = _content.text;
    _retryTimer?.cancel();
    _debounce?.cancel();
    _debounce = Timer(const Duration(seconds: 2), _autoSave);
    _schedulePreview();
  }

  void _schedulePreview() {
    _previewDebounce?.cancel();
    _previewDebounce = Timer(const Duration(milliseconds: 350), () {
      if (!mounted) return;
      setState(() => _previewBlocks = _buildBlocks(_content.text));
    });
  }

  // ── plain text -> blocks that DocumentPreviewPanel understands ─────────────
  static final _listRe = RegExp(r'^\s*(?:[-*•]|\d+[.)])\s+(.*)$');
  static final _numListRe = RegExp(r'^\s*\d+[.)]\s+');

  bool _looksLikeHeading(String t) {
    if (t.contains('\n')) return false;
    if (t.length > 60) return false;
    if (RegExp(r'[.:;,!?]$').hasMatch(t)) return false;
    return t.split(RegExp(r'\s+')).length <= 8;
  }

  List<Map<String, dynamic>> _buildBlocks(String text) {
    final out = <Map<String, dynamic>>[];
    var page = 1;
    var used = 0;

    void add(Map<String, dynamic> b, int weight) {
      if (used + weight > _charsPerPage && used > 0) {
        page++;
        used = 0;
      }
      used += weight;
      b['page'] = page;
      out.add(b);
    }

    final usedImages = <int>{};
    // Put each "[image:ID]" marker line in its own chunk.
    final prepared = text.replaceAllMapped(
      RegExp(r'^[ \t]*\[image:(\d+)\][ \t]*$', multiLine: true),
      (m) => '\n\n[[IMG${m[1]}]]\n\n',
    );
    final chunks = prepared.split(RegExp(r'\n\s*\n'));
    for (final raw in chunks) {
      final chunk = raw.trim();
      if (chunk.isEmpty) continue;

      final im = RegExp(r'^\[\[IMG(\d+)\]\]$').firstMatch(chunk);
      if (im != null) {
        final id = int.parse(im.group(1)!);
        if (_images.any((x) => x['id'] == id) && usedImages.add(id)) {
          final url =
              _vc.sectionImageUrl(widget.projectId, widget.sectionId, id);
          add({'type': 'image', 'image_path': url}, 900);
        }
        continue;
      }

      // Markdown-style heading: "# Title", "## Title"
      final md = RegExp(r'^(#{1,3})\s+(.+)$').firstMatch(chunk);
      if (md != null && !chunk.contains('\n')) {
        add({
          'type': 'heading',
          'level': md.group(1)!.length,
          'text': md.group(2)!.trim(),
        }, 200);
        continue;
      }

      final lines = chunk.split('\n');
      final allList = lines.every((l) => _listRe.hasMatch(l));
      if (allList) {
        for (final l in lines) {
          add({
            'type': 'list_item',
            'list_style': _numListRe.hasMatch(l) ? 'number' : 'bullet',
            'text': _listRe.firstMatch(l)!.group(1)!.trim(),
          }, l.length + 80);
        }
        continue;
      }

      if (_looksLikeHeading(chunk)) {
        add({'type': 'heading', 'level': 2, 'text': chunk}, 200);
        continue;
      }

      add({'type': 'paragraph', 'text': chunk}, chunk.length + 80);
    }

    // Images without a marker in the text fall back to the end of the section.
    for (final img in _images) {
      final id = img['id'];
      if (id is! int || usedImages.contains(id)) continue;
      final url = _vc.sectionImageUrl(widget.projectId, widget.sectionId, id);
      add({'type': 'image', 'image_path': url}, 900);
    }
    return out;
  }

  Future<void> _loadDraft() async {
    final draft = await _vc.loadSectionDraft(widget.projectId, widget.sectionId);
    if (!mounted || draft == null || draft.isEmpty) return;
    if (draft == widget.initialContent) return;
    if (_content.text != widget.initialContent) return;
    _content.removeListener(_onContentChanged);
    _content.text = draft;
    _content.addListener(_onContentChanged);
    setState(() => _previewBlocks = _buildBlocks(draft));
  }

  Future<void> _autoSave() async {
    final content = _pendingContent;
    if (content == null || !mounted) return;
    setState(() => _saveStatus = _SaveStatus.saving);
    final ok = await _vc.saveSectionDraft(
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
        _retryTimer = Timer(const Duration(seconds: 10), _autoSave);
      }
    });
  }

  Future<void> _loadImages() async {
    final images = await _vc.loadSectionImages(
      widget.projectId,
      widget.sectionId,
    );
    if (mounted) {
      setState(() {
        _images = images;
        _loadingImages = false;
        _previewBlocks = _buildBlocks(_content.text);
      });
    }
  }

  @override
  void dispose() {
    _content.removeListener(_onContentChanged);
    if (_pendingContent != null) {
      _vc.saveSectionDraft(
        projectId: widget.projectId,
        sectionId: widget.sectionId,
        content: _pendingContent!,
      );
    }
    _debounce?.cancel();
    _retryTimer?.cancel();
    _previewDebounce?.cancel();
    _content.dispose();
    _message.dispose();
    super.dispose();
  }

  /// Inserts "[image:ID]" on its own line at the cursor (or at the end if the
  /// text field has no cursor yet).
  void _insertImageMarker(int id) {
    final text = _content.text;
    final sel = _content.selection;
    final at = sel.isValid ? sel.start.clamp(0, text.length) : text.length;
    final marker = '\n\n[image:$id]\n\n';
    _content.value = TextEditingValue(
      text: text.replaceRange(at, at, marker),
      selection: TextSelection.collapsed(offset: at + marker.length),
    );
  }

  Future<void> _pickAndUploadImage() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.image,
      withData: false,
    );
    if (result == null || result.files.single.path == null) return;

    final uploaded = await _vc.uploadSectionImage(
      widget.projectId,
      widget.sectionId,
      File(result.files.single.path!),
    );

    if (!mounted) return;
    if (uploaded != null) {
      setState(() => _images.add(uploaded));
      final newId = uploaded['id'];
      if (newId is int) _insertImageMarker(newId); // lands at the cursor
      setState(() => _previewBlocks = _buildBlocks(_content.text));
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Tr('Image uploaded'),
          backgroundColor: Color(0xFF10B981),
        ),
      );
    } else {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(_vc.error ?? 'Upload failed')));
    }
  }

  Future<void> _removeImage(int imageId) async {
    final ok = await _vc.deleteSectionImage(
      widget.projectId,
      widget.sectionId,
      imageId,
    );
    if (!mounted) return;
    if (ok) {
      // Remove its marker from the text as well.
      _content.text = _content.text
          .replaceAll(RegExp('\\n*[ \\t]*\\[image:$imageId\\][ \\t]*\\n*'), '\n\n')
          .trimRight();
      setState(() {
        _images.removeWhere((img) => img['id'] == imageId);
        _previewBlocks = _buildBlocks(_content.text);
      });
    }
  }

  Future<void> _save() async {
    _debounce?.cancel();
    _retryTimer?.cancel();
    setState(() => _saving = true);

    final ok = await _vc.saveSection(
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
          ok ? 'Commit saved — broadcast to team' : (_vc.error ?? 'Save failed'),
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

  // ── UI pieces ──────────────────────────────────────────────────────────────

  Widget _buildEditorPane() {
    return Padding(
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
              const Tr('Attached Images',
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
                label: const Tr('Upload Image'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFF6366F1),
                  side: const BorderSide(color: Color(0xFF6366F1)),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          _buildImagesStrip(),
          const SizedBox(height: 12),
          const Align(
            alignment: Alignment.centerLeft,
            child: Tr('Auto-saved as a draft. Save Commit creates a permanent version. Place the cursor in the text and tap "Insert here" on an image to position it; a marker like [image:12] shows where it will appear.',
              style: TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildImagesStrip() {
    if (_loadingImages) {
      return const SizedBox(
        height: 80,
        child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    if (_images.isEmpty) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFF1A1F2E),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: const Color(0xFF2D3748)),
        ),
        child: const Tr('No images attached. Upload images to include them in the merged document.',
          style: TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
          textAlign: TextAlign.center,
        ),
      );
    }
    return SizedBox(
      height: 90,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: _images.length,
        separatorBuilder: (_, __) => const SizedBox(width: 10),
        itemBuilder: (_, i) {
          final img = _images[i];
          final imageId = img['id'] as int;
          final url = _vc.sectionImageUrl(
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
                    child: const Icon(Icons.broken_image,
                        color: Color(0xFF94A3B8)),
                  ),
                ),
              ),
              Positioned(
                left: 4,
                bottom: 4,
                child: GestureDetector(
                  onTap: () => _insertImageMarker(imageId),
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                    decoration: BoxDecoration(
                      color: const Color(0xFF6366F1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Text('Insert here',
                        style: TextStyle(color: Colors.white, fontSize: 10)),
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
                    child: const Icon(Icons.close,
                        size: 14, color: Colors.white),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildPreviewPane() {
    return DocumentPreviewPanel(
      blocks: _previewBlocks,
      issues: const [],
      imageBaseUrl: '', // panel falls back to ApiConfig.getBaseUrl()
      documentId: widget.projectId,
      appliedFixes: const {},
      ignoredIssueIds: const {},
      onApplyFix: (_, __) {},
      onIgnoreIssue: (_) {},
      readOnly: true,
      showOriginalInitially: false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final label = _statusLabel();

    return Scaffold(
      backgroundColor: const Color(0xFF0F1419),
      appBar: AppBar(
        backgroundColor: const Color(0xFF141B27),
        title: Text(widget.sectionName),
        actions: [
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
                : const Tr('Save Commit'),
          ),
        ],
      ),
      body: LayoutBuilder(
        builder: (context, c) {
          // Wide screens: edit + live preview side by side.
          if (c.maxWidth >= 900) {
            return Row(
              children: [
                Expanded(flex: 5, child: _buildEditorPane()),
                const VerticalDivider(width: 1, color: Color(0xFF2D3748)),
                Expanded(flex: 5, child: _buildPreviewPane()),
              ],
            );
          }
          // Narrow screens: Edit / Preview toggle.
          return Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
                child: SegmentedButton<bool>(
                  segments: const [
                    ButtonSegment(
                        value: false,
                        icon: Icon(Icons.edit, size: 16),
                        label: Text('Edit')),
                    ButtonSegment(
                        value: true,
                        icon: Icon(Icons.visibility, size: 16),
                        label: Text('Preview')),
                  ],
                  selected: {_showPreviewOnNarrow},
                  onSelectionChanged: (s) =>
                      setState(() => _showPreviewOnNarrow = s.first),
                ),
              ),
              Expanded(
                child: IndexedStack(
                  index: _showPreviewOnNarrow ? 1 : 0,
                  children: [_buildEditorPane(), _buildPreviewPane()],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}