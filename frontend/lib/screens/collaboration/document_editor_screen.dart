import 'dart:convert';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import '../../config/api_config.dart';
import '../../config/dev_user_config.dart';
import '../../providers/auth_provider.dart';
import '../../providers/document_provider.dart';
import '../../widgets/document_preview_panel.dart';
import '../../widgets/tr.dart';

class _PendingImage {
  final String path;
  final String name;
  final Map<String, dynamic>? anchor; // null = end of document
  final String anchorLabel;
  _PendingImage(this.path, this.name, this.anchor, this.anchorLabel);
}

/// Full-screen editor for the project document.
///
/// Word-style page where you click a paragraph and type. Tables and images
/// stay untouched. Pops with `true` after a successful "Save commit".
class DocumentEditorScreen extends StatefulWidget {
  final int projectId;
  final int documentId;

  const DocumentEditorScreen({
    super.key,
    required this.projectId,
    required this.documentId,
  });

  @override
  State<DocumentEditorScreen> createState() => _DocumentEditorScreenState();
}

class _DocumentEditorScreenState extends State<DocumentEditorScreen> {
  int _epoch = 0;
  late Future<List<Map<String, dynamic>>> _future;

  List<Map<String, dynamic>> _source = const [];
  List<Map<String, dynamic>> _original = [];
  List<Map<String, dynamic>> _edited = [];
  Map<String, dynamic>? _selected;

Map<String, dynamic>? _lastSelected;

  final _message = TextEditingController();
  final List<_PendingImage> _images = [];

  bool _dirty = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  @override
  void dispose() {
    _message.dispose();
    super.dispose();
  }

  int get _userId =>
      context.read<AuthProvider>().userId ?? DevUserConfig.backendUserId;

  Future<List<Map<String, dynamic>>> _load() async {
    final docs = context.read<DocumentProvider>();
    final data = await docs.getPreview(widget.documentId, _userId);
    final raw = data?['formatted_lines'];
    final blocks = raw is List
        ? raw
            .whereType<Map>()
            .map((e) => Map<String, dynamic>.from(e))
            .toList()
        : <Map<String, dynamic>>[];
    _source = blocks;
    return blocks;
  }

  // ── helpers ────────────────────────────────────────────────────────────────

  bool _isText(Map<String, dynamic> b) {
    final t = (b['type'] ?? 'paragraph').toString().toLowerCase();
    if (t == 'image' || t == 'table' || t == 'toc_item' || t == 'ghost_heading') {
      return false;
    }
    return b['is_placeholder'] != true;
  }

  String _orig(Map<String, dynamic> b) =>
      (b['text'] ?? b['title'] ?? '').toString().trim();

  List<Map<String, dynamic>> _originalTexts() => _original
      .where((b) => _isText(b) && _orig(b).isNotEmpty)
      .toList();

  List<int> _occurrences(List<Map<String, dynamic>> o) {
    final seen = <String, int>{};
    final occ = <int>[];
    for (final b in o) {
      final k = _orig(b);
      occ.add(seen[k] ?? 0);
      seen[k] = (seen[k] ?? 0) + 1;
    }
    return occ;
  }

  void _msg(String text, {bool ok = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(text),
        backgroundColor:
            ok ? const Color(0xFF10B981) : const Color(0xFFEF4444),
      ),
    );
  }

  // ── diff: original blocks vs edited blocks -> backend ops ──────────────────

  List<Map<String, dynamic>> _buildTextOps() {
    final o = _originalTexts();
    final occ = _occurrences(o);

    Map<String, dynamic> ref(int i) =>
        {'match': _orig(o[i]), 'occurrence': occ[i]};

    final ops = <Map<String, dynamic>>[];
    var j = 0;
    int? anchor;

    for (final e in _edited) {
      if (!_isText(e)) continue;
      final cur = e['corrected_text'] is String
          ? (e['corrected_text'] as String)
          : _orig(e);

      if (e['is_new'] == true) {
        if (cur.trim().isEmpty) continue;
        ops.add({
          'op': 'insert_after',
          'anchor': anchor == null ? null : ref(anchor),
          'text': cur,
          'type': (e['type'] ?? 'paragraph').toString(),
        });
        continue;
      }

      final t = _orig(e);
      if (t.isEmpty) continue;

      var k = -1;
      for (var x = j; x < o.length; x++) {
        if (_orig(o[x]) == t) {
          k = x;
          break;
        }
      }
      if (k < 0) continue;

      for (var x = j; x < k; x++) {
        ops.add({'op': 'delete', ...ref(x)});
      }
      if (cur.trim() != t) {
        ops.add({'op': 'replace', ...ref(k), 'text': cur});
      }
      j = k + 1;
      anchor = k;
    }

    for (var x = j; x < o.length; x++) {
      ops.add({'op': 'delete', ...ref(x)});
    }
    return ops;
  }

  // ── images ─────────────────────────────────────────────────────────────────

Future<int?> _chooseAnchorDialog(List<Map<String, dynamic>> o) {
  return showDialog<int>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('Insert image after…'),
      content: SizedBox(
        width: 520,
        height: 420,
        child: ListView(
          children: [
            ListTile(
              leading: const Icon(Icons.vertical_align_bottom),
              title: const Text('End of document'),
              onTap: () => Navigator.pop(ctx, -1),
            ),
            const Divider(),
            for (var i = 0; i < o.length; i++)
              ListTile(
                dense: true,
                title: Text(
                  _orig(o[i]),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                onTap: () => Navigator.pop(ctx, i),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx),
          child: const Text('Cancel'),
        ),
      ],
    ),
  );
}

Future<void> _pickImage() async {
  final o = _originalTexts();
  if (o.isEmpty) {
    _msg('Document abhi load ho raha hai, thori der baad try karo.');
    return;
  }
  final choice = await _chooseAnchorDialog(o);
  if (choice == null) return; // cancel

  Map<String, dynamic>? anchor;
  var label = 'end of document';
  if (choice >= 0) {
    final occ = _occurrences(o);
    final t = _orig(o[choice]);
    anchor = {'match': t, 'occurrence': occ[choice]};
    label = 'after "${t.length > 40 ? '${t.substring(0, 40)}…' : t}"';
  }

  final res = await FilePicker.platform.pickFiles(type: FileType.image);
  final path = res?.files.single.path;
  if (path == null) return;
  setState(() {
    _images.add(_PendingImage(path, res!.files.single.name, anchor, label));
  });
}

  // ── actions ────────────────────────────────────────────────────────────────

  Future<void> _save() async {
    final ops = _buildTextOps();
    for (var i = 0; i < _images.length; i++) {
      ops.add({
        'op': 'insert_image',
        'anchor': _images[i].anchor,
        'file_index': i,
      });
    }
    if (ops.isEmpty) {
      _msg('No changes to save');
      return;
    }

    setState(() => _saving = true);
    try {
      final req = http.MultipartRequest(
        'POST',
        Uri.parse(
          '${ApiConfig.getBaseUrl()}/vc/projects/${widget.projectId}'
          '/document/edit?user_id=$_userId',
        ),
      );
      req.headers.addAll(ApiConfig.getHeaders());
      req.fields['ops'] = jsonEncode(ops);
      req.fields['message'] = _message.text.trim();
      for (final img in _images) {
        req.files.add(await http.MultipartFile.fromPath('images', img.path));
      }
      final streamed = await req.send();
      final res = await http.Response.fromStream(streamed);
      if (!mounted) return;

      if (res.statusCode == 200) {
        _msg('Commit saved — shared with the team', ok: true);
        Navigator.pop(context, true);
      } else {
        var detail = 'HTTP ${res.statusCode}';
        try {
          detail = (jsonDecode(res.body)['detail'] ?? detail).toString();
        } catch (_) {}
        _msg('Save failed: $detail');
      }
    } catch (e) {
      _msg('Save error: $e');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _discard() {
    setState(() {
      _epoch++;
      _dirty = false;
      _original = [];
      _edited = [];
      _selected = null;
      _images.clear();
      _message.clear();
      _future = _load();
      _lastSelected = null;
    });
  }

  // ── UI ─────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final hasChanges = _dirty || _images.isNotEmpty;

    return Scaffold(
      backgroundColor: const Color(0xFF0F1419),
      appBar: AppBar(
        backgroundColor: const Color(0xFF141B27),
        title: const Tr('Edit document'),
        actions: [
          if (hasChanges)
            TextButton(
              onPressed: _saving ? null : _discard,
              child: const Tr('Discard'),
            ),
          TextButton(
            onPressed: (hasChanges && !_saving) ? _save : null,
            child: _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Tr('Save Commit'),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _message,
                    decoration: const InputDecoration(
                      labelText: 'Commit message (optional)',
                      hintText: 'e.g. Fixed introduction wording',
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                OutlinedButton.icon(
                  onPressed: _saving ? null : _pickImage,
                  icon: const Icon(Icons.image, size: 16),
                  label: const Tr('Add image'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: const Color(0xFF6366F1),
                    side: const BorderSide(color: Color(0xFF6366F1)),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 14,
                    ),
                  ),
                ),
              ],
            ),
            if (_images.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  for (var i = 0; i < _images.length; i++)
                    Chip(
                      avatar: const Icon(Icons.image, size: 16),
                      label: Text(
                        '${_images[i].name} · ${_images[i].anchorLabel}',
                        style: const TextStyle(fontSize: 11),
                      ),
                      onDeleted: _saving
                          ? null
                          : () => setState(() => _images.removeAt(i)),
                    ),
                ],
              ),
            ],
            const SizedBox(height: 6),
            const Tr('Click a paragraph to edit it. To add an image, click the paragraph it should go after, then "Add image". Tables and existing images stay as they are.',
              style: TextStyle(color: Color(0xFF64748B), fontSize: 11),
            ),
            const SizedBox(height: 10),
            Expanded(
              child: FutureBuilder<List<Map<String, dynamic>>>(
                future: _future,
                builder: (ctx, snap) {
                  if (snap.connectionState != ConnectionState.done) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (_source.isEmpty) {
                    return const Center(
                      child: Tr('Could not load the document for editing.',
                        style: TextStyle(color: Color(0xFF94A3B8)),
                      ),
                    );
                  }
                  return ClipRRect(
                    borderRadius: BorderRadius.circular(10),
                    child: DocumentPreviewPanel(
                      key: ValueKey('panel_$_epoch'),
                      blocks: _source,
                      issues: const [],
                      imageBaseUrl: '',
                      documentId: widget.documentId,
                      appliedFixes: const {},
                      ignoredIssueIds: const {},
                      onApplyFix: (_, __) {},
                      onIgnoreIssue: (_) {},
                      readOnly: false,
                      showOriginalInitially: false,
                      onBlocksReady: (b) => _original = b,
                      onBlockSelected: (b) {
  debugPrint('[editor] onBlockSelected: ${b == null ? "NULL" : (b['text'] ?? b['title'])}');
  _selected = b;
  if (b != null) _lastSelected = b;
},
                      onBlocksChanged: (b) {
                        _edited = b;
                        if (!_dirty && mounted) setState(() => _dirty = true);
                      },
                    ),
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