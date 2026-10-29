import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../models/json_parse.dart';
import '../services/image_replacement_service.dart';
import '../config/api_config.dart';
import 'image_replacement_dialog.dart';

import 'tr.dart';
AppPalette _ap = AppPalette.dark;

Color get _bg => _ap.scaffold;
Color get _surface => _ap.surface;
Color get _border => _ap.border;
Color get _textPri => _ap.textPrimary;
Color get _textSec => _ap.textSecondary;
const _green = Color(0xFF10B981);
const _yellow = Color(0xFFFACC15);
const _red = Color(0xFFEF4444);
const _blue = Color(0xFF4A9EFF);
const _wordBlue = Color(0xFF2B579A);

const _ribbonBg = Color(0xFFF3F2F1);
const _ribbonLine = Color(0xFFD1D1D1);
const _ribbonActive = Color(0xFFC7E0F4);

/// Original (plain list) + Corrected (editable Word-style paper preview).
class DocumentPreviewPanel extends StatefulWidget {
  final List<Map<String, dynamic>> blocks;
  final List<Map<String, dynamic>> issues;
  final String imageBaseUrl;
  final int documentId;
  final Map<String, String> appliedFixes;
  final Set<String> ignoredIssueIds;
  final Set<String> resolvedIssueIds;
  final void Function(String issueId, String correctedText) onApplyFix;
  final void Function(String issueId) onIgnoreIssue;
  final void Function(Map<String, dynamic> result, Map<String, dynamic> issue)? onImageReplaced;
  final void Function(Map<String, dynamic> result, Map<String, dynamic> issue)? onImageRemoved;
  final void Function(List<Map<String, dynamic>> blocks)? onBlocksChanged;

  final String defaultFont;
  final double bodyPt;
  final Map<int, double> headingPt;
  final double lineSpacing;

  const DocumentPreviewPanel({
    super.key,
    required this.blocks,
    required this.issues,
    required this.imageBaseUrl,
    required this.documentId,
    required this.appliedFixes,
    required this.ignoredIssueIds,
    this.resolvedIssueIds = const {},
    required this.onApplyFix,
    required this.onIgnoreIssue,
    this.onImageReplaced,
    this.onImageRemoved,
    this.onBlocksChanged,
    this.defaultFont = 'Times New Roman',
    this.bodyPt = 12,
    this.headingPt = const {1: 16, 2: 14, 3: 12},
    this.lineSpacing = 1.5,
  });

  @override
  State<DocumentPreviewPanel> createState() => _DocumentPreviewPanelState();
}

class _DocumentPreviewPanelState extends State<DocumentPreviewPanel> {
  late ImageReplacementService _replacementService;

  late List<Map<String, dynamic>> _blocks;
  int _uidSeq = 0;
  String? _selectedUid;

  final List<String> _undo = [];
  final List<String> _redo = [];

  final TextEditingController _editCtrl = TextEditingController();
  late final FocusNode _editFocus;
  String? _editingUid;
  bool _textUndoPushed = false;

  bool _showOriginal = true;
  bool _showStyleTags = false;
  double _zoom = 1.0;

  static const double _pageW = 794;
  static const double _pageH = 1123;
  static const double _marginPx = 96;
  static const double _ptToPx = 96 / 72;

  static const _fonts = <String>[
    'Times New Roman',
    'Arial',
    'Calibri',
    'Cambria',
    'Georgia',
    'Verdana',
    'Tahoma',
    'Courier New',
  ];
  static const _sizes = <double>[8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48];
  static const _styles = <String>[
    'Normal',
    'Heading 1',
    'Heading 2',
    'Heading 3',
    'List Bullet',
    'List Number',
  ];
  static const _spacings = <double>[1.0, 1.15, 1.5, 2.0];
  static final _palette = <MapEntry<String, int>>[
    MapEntry('Black', 0xFF000000),
    MapEntry('Dark Red', 0xFFC00000),
    MapEntry('Blue', 0xFF0070C0),
    MapEntry('Green', 0xFF00B050),
    MapEntry('Orange', 0xFFED7D31),
    MapEntry('Purple', 0xFF7030A0),
    MapEntry('Grey', 0xFF595959),
  ];

  @override
  void initState() {
    super.initState();
    _replacementService = ImageReplacementService(imageBaseUrl: widget.imageBaseUrl);
    _editFocus = FocusNode(onKeyEvent: _onEditorKey);
    _initBlocks();
  }

  @override
  void didUpdateWidget(covariant DocumentPreviewPanel old) {
    super.didUpdateWidget(old);
    if (!identical(old.blocks, widget.blocks) &&
        jsonEncode(old.blocks) != jsonEncode(widget.blocks)) {
      _initBlocks();
      _undo.clear();
      _redo.clear();
      _selectedUid = null;
      _editingUid = null;
    }
  }

  @override
  void dispose() {
    _editCtrl.dispose();
    _editFocus.dispose();
    super.dispose();
  }

  /// Correctly maps and normalizes blocks preserving exact input sequence.
  void _initBlocks() {
    _blocks = widget.blocks.map((b) {
      final m = Map<String, dynamic>.from(b);
      m['_uid'] = _newUid();

      final rawType = (m['type'] ?? '').toString().toLowerCase();
      const textTypes = {'paragraph', 'heading', 'list_item', 'toc_item'};

      if (rawType.contains('toc') ||
          rawType.contains('table_of_contents') ||
          rawType.contains('list_of_figures') ||
          rawType.contains('list_of_tables')) {
        // MUST be checked before 'table' (table_of_contents contains "table").
        m['type'] = 'toc_item';
      } else if (rawType.contains('image') ||
          rawType.contains('figure') ||
          rawType.contains('picture') ||
          rawType.contains('drawing')) {
        m['type'] = 'image';
      } else if (rawType.contains('table')) {
        m['type'] = 'table';
      } else if (!textTypes.contains(rawType)) {
        // Unknown / empty type: infer from keys, but never override a real text block.
        if (_rawImagePath(m).isNotEmpty) {
          m['type'] = 'image';
        } else if (_rawTableRows(m).isNotEmpty) {
          m['type'] = 'table';
        }
      }

      if (m['type'] == 'image' || m['type'] == 'table') {
        debugPrint('[preview] ${m['type']} block keys=${m.keys.toList()} '
            'path=${_rawImagePath(m)} rows=${_rawTableRows(m).length}');
      }

      return m;
    }).toList();
    _blocks = _stripToc(_blocks);
    _logSummary();
    _logSummary();
  }

  String _newUid() => 'u${_uidSeq++}';

  void _logSummary() {
    final counts = <String, int>{};
    for (final b in _blocks) {
      final t = (b['type'] ?? 'null').toString();
      counts[t] = (counts[t] ?? 0) + 1;
    }
    debugPrint('[preview] SUMMARY total=${_blocks.length} types=$counts');
    debugPrint('[preview] raw types=${widget.blocks.map((b) => b['type']).toSet()}');
    debugPrint('[preview] all keys=${widget.blocks.expand((b) => b.keys).toSet()}');
    for (final b in widget.blocks) {
      final t = (b['type'] ?? '').toString().toLowerCase();
      if (t != 'paragraph' && t != 'heading' && t != 'list_item') {
        debugPrint('[preview] NON-TEXT sample: ${jsonEncode(b).substring(0, jsonEncode(b).length.clamp(0, 400))}');
        break;
      }
    }
  }

  /// Hides the Table of Contents / List of Figures / List of Tables pages
  /// from the preview. Starts at a TOC-style heading and stops at the next
  /// real heading (or at a page break to a later page).
  List<Map<String, dynamic>> _stripToc(List<Map<String, dynamic>> blocks) {
    const tocTitles = {
      'table of contents',
      'contents',
      'list of figures',
      'list of tables',
    };

    bool isTocTitle(Map<String, dynamic> b) {
      final t = (b['text'] ?? b['title'] ?? '').toString().trim().toLowerCase();
      return tocTitles.contains(t);
    }

    // A line that is just a page number, or "title ..... 3", or "title \t 3".
    bool looksLikeTocLine(Map<String, dynamic> b) {
      if (_type(b) == 'toc_item') return true;
      final t = (b['text'] ?? b['title'] ?? '').toString().trim();
      if (t.isEmpty) return true;
      if (RegExp(r'^\d+$').hasMatch(t)) return true;
      if (RegExp(r'^.+[\s.…\t]{2,}\d+$').hasMatch(t)) return true;
      return false;
    }

    final out = <Map<String, dynamic>>[];
    var skipping = false;
    for (final b in blocks) {
      if (isTocTitle(b)) {
        skipping = true;
        continue;
      }
      if (skipping) {
        if (looksLikeTocLine(b)) continue;
        skipping = false; // first real content after the TOC
      }
      out.add(b);
    }
    return out;
  }
  /// First non-empty image path-like value found in the block.
  String _rawImagePath(Map<String, dynamic> b) {
    for (final k in const [
      'image_path', 'path', 'url', 'image_url', 'src', 'file_path',
      'file', 'filename', 'image', 'media_path', 'relative_path',
    ]) {
      var v = b[k];
      if (v is Map) v = v['path'] ?? v['url'] ?? v['src'];
      final s = v?.toString() ?? '';
      if (s.isNotEmpty && s != 'null') return s;
    }
    return '';
  }

  String _cellText(dynamic c) {
    if (c == null) return '';
    if (c is Map) {
      final t = c['text'] ?? c['value'] ?? c['content'];
      if (t != null) return _cellText(t);
      final p = c['paragraphs'];
      if (p is List) return p.map(_cellText).join('\n');
      return '';
    }
    if (c is List) return c.map(_cellText).join('\n');
    return c.toString();
  }

  List<List<String>> _rawTableRows(Map<String, dynamic> b) {
    dynamic raw = b['rows'] ?? b['preview_rows'] ?? b['cells'] ??
        b['table_data'] ?? b['data'] ?? b['table'];
    if (raw is Map) raw = raw['rows'] ?? raw['cells'] ?? raw['data'];
    if (raw is! List || raw.isEmpty) return const [];
    return raw.map<List<String>>((r) {
      if (r is List) return r.map(_cellText).toList();
      if (r is Map) {
        final cells = r['cells'] ?? r['columns'];
        if (cells is List) return cells.map(_cellText).toList();
        return r.values.map(_cellText).toList();
      }
      return [_cellText(r)];
    }).toList();
  }

  /// Server root without trailing slash or /api. Falls back to ApiConfig when
  /// the parent passes an empty imageBaseUrl.
  String get _serverRoot {
    var b = widget.imageBaseUrl.trim();
    if (b.isEmpty) b = ApiConfig.getBaseUrl();
    b = b.replaceFirst(RegExp(r'/+$'), '');
    return b.replaceFirst(RegExp(r'/api$'), '');
  }

  List<String> _imageUrls(String rawPath) {
    if (rawPath.isEmpty) return const [];
    if (rawPath.startsWith('http://') || rawPath.startsWith('https://')) return [rawPath];
    var p = rawPath.replaceAll('\\', '/');
    final up = p.indexOf('uploads/');
    final rel = (up >= 0 ? p.substring(up + 8) : p).replaceFirst(RegExp(r'^/+'), '');
    final base = _serverRoot;
    return {
      '$base/api/files/$rel',
      '$base/uploads/$rel',
      '$base/$rel',
      '$base/static/$rel',
      '$base/static/uploads/$rel',
      '$base/api/files/$rel',
      '$base/files/$rel',
    }.toList();
  }

  String _imageUrl(String rawPath) {
    if (rawPath.isEmpty) return '';
    if (rawPath.startsWith('http://') || rawPath.startsWith('https://')) {
      return rawPath;
    }
    rawPath = rawPath.replaceAll('\\', '/');
    // Absolute server paths like /app/uploads/142/img.png -> keep part after uploads/
    final up = rawPath.indexOf('uploads/');
    final clean = up >= 0
        ? rawPath.substring(up + 'uploads/'.length)
        : rawPath.startsWith('/')
            ? rawPath.substring(1)
            : rawPath;

    final base = widget.imageBaseUrl.endsWith('/')
        ? widget.imageBaseUrl.substring(0, widget.imageBaseUrl.length - 1)
        : widget.imageBaseUrl;
        
    return '$base/uploads/$clean';
  }

  double? _num(dynamic v) {
    if (v is num) return v.toDouble();
    if (v is String) return double.tryParse(v);
    return null;
  }

  String _fmt(double v) =>
      v == v.roundToDouble() ? v.round().toString() : v.toStringAsFixed(1);

  List<Map<String, dynamic>> _issuesForBlock(Map<String, dynamic> block) {
    final pid = block['paragraph_id'] as String? ?? '';
    final iid = block['image_id'] as String? ?? '';
    return widget.issues.where((issue) {
      if (widget.ignoredIssueIds.contains(issue['issue_id'] as String? ?? '')) {
        return false;
      }
      if (widget.resolvedIssueIds.contains(issue['issue_id'] as String? ?? '')) {
        return false;
      }
      if (pid.isNotEmpty && issue['paragraph_id'] == pid) return true;
      if (iid.isNotEmpty && issue['image_id'] == iid) return true;
      return false;
    }).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  Color _highlightColor(List<Map<String, dynamic>> blockIssues) {
    if (blockIssues.isEmpty) return Colors.transparent;
    final hasMajor = blockIssues.any(
      (i) => (i['severity'] as String? ?? '').toLowerCase() == 'major',
    );
    return hasMajor ? _red.withOpacity(0.22) : _yellow.withOpacity(0.22);
  }

  Color _borderColor(List<Map<String, dynamic>> blockIssues) {
    if (blockIssues.isEmpty) return _border;
    final hasMajor = blockIssues.any(
      (i) => (i['severity'] as String? ?? '').toLowerCase() == 'major',
    );
    return hasMajor ? _red.withOpacity(0.6) : _yellow.withOpacity(0.6);
  }

  String _correctedText(Map<String, dynamic> block, List<Map<String, dynamic>> blockIssues) {
    final pid = block['paragraph_id'] as String? ?? '';
    if (pid.isNotEmpty && widget.appliedFixes.containsKey(pid)) {
      return widget.appliedFixes[pid]!;
    }
    return block['text'] as String? ?? block['title'] as String? ?? '';
  }

  String _displayText(Map<String, dynamic> block, List<Map<String, dynamic>> blockIssues) {
    final o = block['corrected_text'];
    if (o is String) return o;
    return _correctedText(block, blockIssues);
  }

  String _type(Map<String, dynamic> b) =>
      (b['type'] as String? ?? 'paragraph').toLowerCase();
      
  bool _isTextual(Map<String, dynamic> b) {
    final t = _type(b);
    return t != 'image' && t != 'table';
  }

  int _level(Map<String, dynamic> b) => (_num(b['level'])?.toInt() ?? 1).clamp(1, 6);
  String _fontOf(Map<String, dynamic> b) => (b['font_name'] as String?) ?? widget.defaultFont;
  double _sizeOf(Map<String, dynamic> b) =>
      _num(b['font_size']) ??
      (_type(b) == 'heading' ? (widget.headingPt[_level(b)] ?? 12) : widget.bodyPt);
  bool _boldOf(Map<String, dynamic> b) => b['bold'] as bool? ?? _type(b) == 'heading';
  bool _italicOf(Map<String, dynamic> b) => b['italic'] as bool? ?? false;
  bool _underlineOf(Map<String, dynamic> b) => b['underline'] as bool? ?? false;
  bool _strikeOf(Map<String, dynamic> b) => b['strike'] as bool? ?? false;
  double _spacingOf(Map<String, dynamic> b) =>
      _num(b['line_spacing']) ?? (_type(b) == 'heading' ? 1.2 : widget.lineSpacing);
  TextAlign _alignOf(Map<String, dynamic> b) =>
      _align(b['alignment'], _type(b) == 'paragraph' ? TextAlign.justify : TextAlign.left);
  Color _colorOf(Map<String, dynamic> b) =>
      Color(_num(b['text_color'])?.toInt() ?? 0xFF000000);

  String _styleName(Map<String, dynamic> b) {
    switch (_type(b)) {
      case 'heading':
        return 'Heading ${_level(b)}';
      case 'list_item':
        return b['list_style'] == 'number' ? 'List Number' : 'List Bullet';
      case 'toc_item':
        return 'Table of Contents';
      case 'table':
        return 'Table';
      case 'image':
        return 'Figure / Image';
      default:
        return 'Normal';
    }
  }

  TextAlign _align(dynamic v, TextAlign fallback) {
    switch ((v as String?)?.toLowerCase()) {
      case 'center':
        return TextAlign.center;
      case 'right':
        return TextAlign.right;
      case 'justify':
      case 'both':
        return TextAlign.justify;
      case 'left':
        return TextAlign.left;
      default:
        return fallback;
    }
  }

  TextStyle _wordStyle(
    String font,
    double pt,
    double s, {
    bool bold = false,
    bool italic = false,
    double height = 1.3,
  }) =>
      TextStyle(
        fontFamily: font,
        fontFamilyFallback: const ['Times New Roman', 'Times', 'serif'],
        fontSize: pt * _ptToPx * s,
        fontWeight: bold ? FontWeight.bold : FontWeight.normal,
        fontStyle: italic ? FontStyle.italic : FontStyle.normal,
        color: Colors.black,
        height: height,
      );

  TextStyle _blockStyle(Map<String, dynamic> b, double s) {
    final deco = <TextDecoration>[
      if (_underlineOf(b)) TextDecoration.underline,
      if (_strikeOf(b)) TextDecoration.lineThrough,
    ];
    return TextStyle(
      fontFamily: _fontOf(b),
      fontFamilyFallback: const ['Times New Roman', 'Times', 'serif'],
      fontSize: _sizeOf(b) * _ptToPx * s,
      fontWeight: _boldOf(b) ? FontWeight.bold : FontWeight.normal,
      fontStyle: _italicOf(b) ? FontStyle.italic : FontStyle.normal,
      color: _colorOf(b),
      height: _spacingOf(b),
      decoration: deco.isEmpty ? TextDecoration.none : TextDecoration.combine(deco),
    );
  }

  Map<String, dynamic>? get _sel {
    final uid = _selectedUid;
    if (uid == null) return null;
    for (final b in _blocks) {
      if (b['_uid'] == uid) return b;
    }
    return null;
  }

  void _select(String? uid, {int? cursor}) {
    if (uid == _selectedUid && (uid == null || _editingUid == uid)) return;
    setState(() => _selectedUid = uid);
    _syncEditor(cursor: cursor);
  }

  void _syncEditor({int? cursor}) {
    final b = _sel;
    if (b == null || !_isTextual(b)) {
      _editingUid = null;
      _editFocus.unfocus();
      return;
    }
    if (_editingUid == b['_uid']) return;
    final t = _displayText(b, _issuesForBlock(b));
    final c = (cursor ?? t.length).clamp(0, t.length);
    _editCtrl.value = TextEditingValue(
      text: t,
      selection: TextSelection.collapsed(offset: c),
    );
    _editingUid = b['_uid'] as String;
    _textUndoPushed = false;
    _refocus();
  }

  void _refocus() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _editingUid != null) _editFocus.requestFocus();
    });
  }

  void _pushUndo() {
    _undo.add(jsonEncode(_blocks));
    if (_undo.length > 100) _undo.removeAt(0);
    _redo.clear();
  }

  void _notify() {
    final cb = widget.onBlocksChanged;
    if (cb == null) return;
    cb(_blocks.map((b) {
      final m = Map<String, dynamic>.from(b);
      m.remove('_uid');
      return m;
    }).toList());
  }

  void _restore(String snap) {
    setState(() {
      _blocks = (jsonDecode(snap) as List)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      if (_sel == null) _selectedUid = null;
      _editingUid = null;
    });
    _syncEditor();
    _notify();
  }

  void _undoAction() {
    if (_undo.isEmpty) return;
    _redo.add(jsonEncode(_blocks));
    _restore(_undo.removeLast());
  }

  void _redoAction() {
    if (_redo.isEmpty) return;
    _undo.add(jsonEncode(_blocks));
    _restore(_redo.removeLast());
  }

  void _apply(void Function(Map<String, dynamic> b) change) {
    final b = _sel;
    if (b == null || !_isTextual(b)) return;
    _pushUndo();
    setState(() => change(b));
    _notify();
    _refocus();
  }

  void _toggleBold() => _apply((b) => b['bold'] = !_boldOf(b));
  void _toggleItalic() => _apply((b) => b['italic'] = !_italicOf(b));
  void _toggleUnderline() => _apply((b) => b['underline'] = !_underlineOf(b));
  void _toggleStrike() => _apply((b) => b['strike'] = !_strikeOf(b));
  void _setSize(double v) => _apply((b) => b['font_size'] = v.clamp(6, 96));

  void _setStyle(String name) {
    _apply((b) {
      final wasHeading = _type(b) == 'heading';
      if (name.startsWith('Heading')) {
        b['type'] = 'heading';
        b['level'] = int.parse(name.split(' ').last);
        b.remove('font_size');
        b.remove('bold');
        b.remove('list_style');
      } else if (name == 'Normal') {
        b['type'] = 'paragraph';
        b.remove('level');
        b.remove('list_style');
        if (wasHeading) {
          b.remove('font_size');
          b.remove('bold');
        }
      } else {
        b['type'] = 'list_item';
        b['list_style'] = name == 'List Number' ? 'number' : 'bullet';
        b.remove('level');
        if (wasHeading) {
          b.remove('font_size');
          b.remove('bold');
        }
      }
    });
  }

  void _toggleList(String style) {
    _apply((b) {
      if (_type(b) == 'list_item' && (b['list_style'] ?? 'bullet') == style) {
        b['type'] = 'paragraph';
        b.remove('list_style');
      } else {
        if (_type(b) == 'heading') {
          b.remove('font_size');
          b.remove('bold');
          b.remove('level');
        }
        b['type'] = 'list_item';
        b['list_style'] = style;
      }
    });
  }

  void _insertParagraph() {
    _pushUndo();
    final sel = _sel;
    int idx;
    int page;
    if (sel != null) {
      idx = _blocks.indexOf(sel) + 1;
      page = _num(sel['page'])?.toInt() ?? 1;
    } else {
      idx = _blocks.length;
      page = _blocks.isEmpty ? 1 : (_num(_blocks.last['page'])?.toInt() ?? 1);
    }
    final nb = <String, dynamic>{
      '_uid': _newUid(),
      'type': 'paragraph',
      'text': '',
      'corrected_text': '',
      'page': page,
      'font_name': widget.defaultFont,
      'is_new': true,
    };
    setState(() {
      _blocks.insert(idx, nb);
      _selectedUid = nb['_uid'] as String;
      _editingUid = null;
    });
    _syncEditor(cursor: 0);
    _notify();
  }

  void _deleteSelected() {
    final b = _sel;
    if (b == null || _type(b) == 'image') return;
    _pushUndo();
    setState(() {
      _blocks.remove(b);
      _selectedUid = null;
      _editingUid = null;
    });
    _editFocus.unfocus();
    _notify();
  }

  Map<String, dynamic> _newBlockLike(Map<String, dynamic> b, String text) {
    final heading = _type(b) == 'heading';
    final m = <String, dynamic>{
      '_uid': _newUid(),
      'type': _type(b) == 'list_item' ? 'list_item' : 'paragraph',
      'text': '',
      'corrected_text': text,
      'page': b['page'] ?? 1,
      'font_name': _fontOf(b),
      'is_new': true,
    };
    if (!heading) {
      for (final k in const [
        'font_size',
        'bold',
        'italic',
        'underline',
        'strike',
        'text_color',
        'alignment',
        'line_spacing',
        'list_style',
      ]) {
        if (b[k] != null) m[k] = b[k];
      }
    }
    return m;
  }

  void _onTextChanged(String v) {
    final b = _sel;
    if (b == null) return;
    if (v.contains('\n')) {
      _handleEnter(b, v);
      return;
    }
    if (!_textUndoPushed) {
      _pushUndo();
      _textUndoPushed = true;
    }
    b['corrected_text'] = v;
    _notify();
    setState(() {});
  }

  void _handleEnter(Map<String, dynamic> b, String v) {
    _pushUndo();
    final lines = v.split(RegExp(r'\r?\n'));

    if (_type(b) == 'list_item' && lines.length == 2 && lines[0].isEmpty) {
      setState(() {
        b['type'] = 'paragraph';
        b.remove('list_style');
        b['corrected_text'] = lines[1];
        _editingUid = null;
      });
      _syncEditor(cursor: 0);
      _notify();
      return;
    }

    final idx = _blocks.indexOf(b);
    final added = <Map<String, dynamic>>[
      for (var i = 1; i < lines.length; i++) _newBlockLike(b, lines[i]),
    ];
    setState(() {
      b['corrected_text'] = lines.first;
      _blocks.insertAll(idx + 1, added);
      _selectedUid = added.last['_uid'] as String;
      _editingUid = null;
    });
    final last = lines.last;
    _syncEditor(cursor: lines.length == 2 ? 0 : last.length);
    _notify();
  }

  KeyEventResult _onEditorKey(FocusNode node, KeyEvent event) {
    if (event is KeyDownEvent && event.logicalKey == LogicalKeyboardKey.backspace) {
      final sel = _editCtrl.selection;
      if (sel.isCollapsed && sel.baseOffset == 0) {
        return _backspaceAtStart() ? KeyEventResult.handled : KeyEventResult.ignored;
      }
    }
    return KeyEventResult.ignored;
  }

  bool _backspaceAtStart() {
    final b = _sel;
    if (b == null) return false;

    if (_type(b) == 'list_item') {
      _pushUndo();
      setState(() {
        b['type'] = 'paragraph';
        b.remove('list_style');
      });
      _notify();
      return true;
    }

    final i = _blocks.indexOf(b);
    if (i <= 0) return false;
    final prev = _blocks[i - 1];
    final curText = _displayText(b, _issuesForBlock(b));

    if (!_isTextual(prev)) {
      if (curText.isEmpty) {
        _pushUndo();
        setState(() {
          _blocks.removeAt(i);
          _selectedUid = null;
          _editingUid = null;
        });
        _editFocus.unfocus();
        _notify();
        return true;
      }
      return false;
    }

    _pushUndo();
    final prevText = _displayText(prev, _issuesForBlock(prev));
    setState(() {
      prev['corrected_text'] = prevText + curText;
      _blocks.removeAt(i);
      _selectedUid = prev['_uid'] as String;
      _editingUid = null;
    });
    _syncEditor(cursor: prevText.length);
    _notify();
    return true;
  }

  void _openFixPanel(Map<String, dynamic> block, List<Map<String, dynamic>> blockIssues) {
    if (blockIssues.isEmpty) return;
    final issue = blockIssues.first;
    final issueId = issue['issue_id'] as String? ?? '';
    final pid = block['paragraph_id'] as String? ?? '';

    showModalBottomSheet(
      context: context,
      backgroundColor: _surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _chip(issue['category'] as String? ?? 'Issue', _blue),
                const SizedBox(width: 8),
                _chip(
                  (issue['severity'] as String? ?? 'minor').toUpperCase(),
                  (issue['severity'] as String? ?? '') == 'major' ? _red : _yellow,
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              issue['description'] as String? ?? issue['reason'] as String? ?? '',
              style: TextStyle(color: _textPri, fontSize: 14),
            ),
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      widget.onIgnoreIssue(issueId);
                      Navigator.pop(ctx);
                    },
                    child: const Tr('Ignore'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(backgroundColor: _green),
                    onPressed: () {
                      final corrected = _correctedText(block, blockIssues);
                      if (pid.isNotEmpty) {
                        _pushUndo();
                        setState(() => block.remove('corrected_text'));
                        widget.onApplyFix(issueId, corrected);
                        WidgetsBinding.instance.addPostFrameCallback((_) {
                          if (!mounted) return;
                          _editingUid = null;
                          _syncEditor();
                          _notify();
                        });
                      }
                      Navigator.pop(ctx);
                    },
                    child: const Tr('Apply Fix'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _showReplaceDialog(Map<String, dynamic> block, Map<String, dynamic> issue) {
    showDialog(
      context: context,
      builder: (ctx) => ImageReplacementDialog(
        documentId: widget.documentId,
        imageIndex: jsonIntOr(issue['image_index'], jsonIntOr(block['image_index'], 0)),
        currentImagePath: block['image_path'] as String? ?? block['path'] as String? ?? '',
        service: _replacementService,
        onSuccess: (result) {
          widget.onImageReplaced?.call(result, issue);
        },
        onError: (e) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error: $e'), backgroundColor: _red),
          );
        },
      ),
    );
  }

  Future<void> _confirmAndRemove(Map<String, dynamic> block, Map<String, dynamic> issue) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _surface,
        title: Tr('Remove Image?', style: TextStyle(color: _textPri)),
        content: Tr('This permanently deletes the image from the document.',
          style: TextStyle(color: _textSec, fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Tr('Cancel', style: TextStyle(color: _textSec)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: _red,
              foregroundColor: Colors.white,
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Tr('Remove'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    try {
      final result = await _replacementService.removeImage(
        documentId: widget.documentId,
        imageIndex: jsonIntOr(issue['image_index'], jsonIntOr(block['image_index'], 0)),
      );
      if (!mounted) return;
      widget.onImageRemoved?.call(result, issue);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Remove failed: $e'), backgroundColor: _red),
      );
    }
  }

  Widget _chip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Text(label, style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w600)),
    );
  }

  Widget _buildOriginalColumn() {
    return Expanded(
      flex: 4,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            height: 44,
            padding: const EdgeInsets.symmetric(horizontal: 14),
            alignment: Alignment.centerLeft,
            color: _textSec.withOpacity(0.12),
            child: Tr('Original',
              style: TextStyle(color: _textSec, fontWeight: FontWeight.w700, fontSize: 13),
            ),
          ),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: _blocks.length,
              itemBuilder: (ctx, i) {
                final block = Map<String, dynamic>.from(_blocks[i]);
                final type = _type(block);
                if (type == 'image') {
                  return _buildSimpleImage(block);
                }
                if (type == 'table') {
                  return Container(
                    margin: const EdgeInsets.only(bottom: 6),
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(color: _surface, borderRadius: BorderRadius.circular(6), border: Border.all(color: _border)),
                    child: Text('[Table: ${_rawTableRows(block).length} rows]', style: TextStyle(color: _textSec, fontSize: 11, fontStyle: FontStyle.italic)),
                  );
                }
                final text = block['text'] as String? ?? block['title'] as String? ?? '';
                return Container(
                  margin: const EdgeInsets.only(bottom: 6),
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: _surface,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: _border),
                  ),
                  child: Text(
                    text,
                    style: TextStyle(
                      color: type == 'heading' ? _textPri : _textSec,
                      fontSize: type == 'heading' ? 14 : 12,
                      fontWeight: type == 'heading' ? FontWeight.w700 : FontWeight.w400,
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSimpleImage(Map<String, dynamic> block) {
    final rawPath = _rawImagePath(block);
    final url = _imageUrl(rawPath);
    return Container(
      height: 120,
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _border),
      ),
      clipBehavior: Clip.antiAlias,
      child: url.isEmpty
          ? Center(child: Icon(Icons.broken_image, color: _textSec))
          : _FallbackImage(urls: _imageUrls(rawPath.toString()), height: 120),
    );
  }

  Map<int, List<Map<String, dynamic>>> _groupByPage() {
    final map = <int, List<Map<String, dynamic>>>{};
    for (final b in _blocks) {
      final p = (_num(b['page'])?.toInt() ?? 1).clamp(1, 9999);
      map.putIfAbsent(p, () => []).add(b);
    }
    return Map.fromEntries(
      map.entries.toList()..sort((a, b) => a.key.compareTo(b.key)),
    );
  }

  Widget _buildWordColumn() {
    final pages = _groupByPage();
    return Expanded(
      flex: 6,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _wordTitleBar(pages.length),
          _ribbon(),
          Expanded(
            child: LayoutBuilder(
              builder: (ctx, c) {
                final fit = ((c.maxWidth - 40) / _pageW).clamp(0.3, 1.0);
                final scale = fit * _zoom;
                return GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () => _select(null),
                  child: Container(
                    color: const Color(0xFFE5E7EB),
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 20),
                      child: SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: ConstrainedBox(
                          constraints: BoxConstraints(minWidth: c.maxWidth - 40),
                          child: Column(
                            children: [
                              for (final e in pages.entries)
                                _buildPaper(e.key, pages.length, e.value, scale),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          _statusBar(pages.length),
        ],
      ),
    );
  }

  Widget _wordTitleBar(int pageCount) {
    const white = TextStyle(color: Colors.white, fontSize: 12);
    return Container(
      height: 44,
      padding: const EdgeInsets.symmetric(horizontal: 10),
      color: _wordBlue,
      child: Row(
        children: [
          const Icon(Icons.description, color: Colors.white, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Tr('Corrected — Word preview',
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
                fontSize: 13,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          Tooltip(
            message: 'Show / hide the Original column',
            child: TextButton.icon(
              onPressed: () => setState(() => _showOriginal = !_showOriginal),
              icon: Icon(
                _showOriginal ? Icons.vertical_split : Icons.crop_portrait,
                color: Colors.white,
                size: 16,
              ),
              label: Text(_showOriginal ? 'Hide original' : 'Show original', style: white),
            ),
          ),
          const SizedBox(width: 4),
          const Tr('Styles', style: white),
          Transform.scale(
            scale: 0.8,
            child: Switch(
              value: _showStyleTags,
              activeColor: Colors.white,
              onChanged: (v) => setState(() => _showStyleTags = v),
            ),
          ),
          IconButton(
            visualDensity: VisualDensity.compact,
            icon: const Icon(Icons.zoom_out, color: Colors.white, size: 18),
            onPressed: () => setState(() => _zoom = (_zoom - 0.1).clamp(0.5, 1.5)),
          ),
          Text('${(_zoom * 100).round()}%', style: white),
          IconButton(
            visualDensity: VisualDensity.compact,
            icon: const Icon(Icons.zoom_in, color: Colors.white, size: 18),
            onPressed: () => setState(() => _zoom = (_zoom + 0.1).clamp(0.5, 1.5)),
          ),
        ],
      ),
    );
  }

  Widget _rb(
    IconData icon,
    String tip,
    VoidCallback? onTap, {
    bool active = false,
    Color? color,
  }) {
    return Tooltip(
      message: tip,
      child: Opacity(
        opacity: onTap == null ? 0.4 : 1,
        child: Material(
          color: active ? _ribbonActive : Colors.transparent,
          borderRadius: BorderRadius.circular(4),
          child: InkWell(
            borderRadius: BorderRadius.circular(4),
            onTap: onTap,
            child: Container(
              width: 30,
              height: 30,
              alignment: Alignment.center,
              child: Icon(icon, size: 18, color: color ?? Colors.black87),
            ),
          ),
        ),
      ),
    );
  }

  Widget _menuBox<T>({
    required String label,
    required double width,
    required List<T> values,
    required String Function(T) text,
    required void Function(T) onSelected,
    required bool enabled,
    String tooltip = '',
    TextStyle Function(T)? itemStyle,
  }) {
    return Opacity(
      opacity: enabled ? 1 : 0.5,
      child: PopupMenuButton<T>(
        enabled: enabled,
        tooltip: tooltip,
        onSelected: onSelected,
        itemBuilder: (_) => [
          for (final v in values)
            PopupMenuItem<T>(
              value: v,
              height: 34,
              child: Text(
                text(v),
                style: itemStyle?.call(v) ?? const TextStyle(fontSize: 13),
              ),
            ),
        ],
        child: Container(
          width: width,
          height: 28,
          padding: const EdgeInsets.only(left: 8, right: 2),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(3),
            border: Border.all(color: _ribbonLine),
          ),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: Colors.black87, fontSize: 12),
                ),
              ),
              const Icon(Icons.arrow_drop_down, size: 18, color: Colors.black54),
            ],
          ),
        ),
      ),
    );
  }

  Widget _ribbon() {
    final Map<String, dynamic>? b = _sel;
    final ok = b != null && _isTextual(b);
    final Map<String, dynamic> t = b ?? <String, dynamic>{};
    final align = _alignOf(t);
    final isList = ok && _type(t) == 'list_item';
    final listStyle = (t['list_style'] ?? 'bullet') as String;

    final sep = Container(
      width: 1,
      height: 22,
      margin: const EdgeInsets.symmetric(horizontal: 6),
      color: _ribbonLine,
    );

    return Container(
      height: 44,
      decoration: const BoxDecoration(
        color: _ribbonBg,
        border: Border(bottom: BorderSide(color: _ribbonLine)),
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 8),
        child: Row(
          children: [
            _rb(Icons.undo, 'Undo', _undo.isEmpty ? null : _undoAction),
            _rb(Icons.redo, 'Redo', _redo.isEmpty ? null : _redoAction),
            sep,
            _menuBox<String>(
              label: ok ? _styleName(t) : 'Normal',
              width: 104,
              values: _styles,
              text: (v) => v,
              onSelected: _setStyle,
              enabled: ok,
              tooltip: 'Style',
            ),
            const SizedBox(width: 6),
            _menuBox<String>(
              label: ok ? _fontOf(t) : widget.defaultFont,
              width: 132,
              values: _fonts,
              text: (v) => v,
              onSelected: (v) => _apply((x) => x['font_name'] = v),
              enabled: ok,
              tooltip: 'Font',
              itemStyle: (v) => TextStyle(fontFamily: v, fontSize: 14),
            ),
            const SizedBox(width: 6),
            _rb(Icons.remove, 'Decrease font size',
                ok ? () => _setSize(_sizeOf(t) - 1) : null),
            _menuBox<double>(
              label: _fmt(ok ? _sizeOf(t) : widget.bodyPt),
              width: 52,
              values: _sizes,
              text: _fmt,
              onSelected: _setSize,
              enabled: ok,
              tooltip: 'Font size',
            ),
            _rb(Icons.add, 'Increase font size',
                ok ? () => _setSize(_sizeOf(t) + 1) : null),
            sep,
            _rb(Icons.format_bold, 'Bold (Ctrl+B)', ok ? _toggleBold : null,
                active: ok && _boldOf(t)),
            _rb(Icons.format_italic, 'Italic (Ctrl+I)', ok ? _toggleItalic : null,
                active: ok && _italicOf(t)),
            _rb(Icons.format_underlined, 'Underline (Ctrl+U)', ok ? _toggleUnderline : null,
                active: ok && _underlineOf(t)),
            _rb(Icons.strikethrough_s, 'Strikethrough', ok ? _toggleStrike : null,
                active: ok && _strikeOf(t)),
            sep,
            _rb(Icons.format_align_left, 'Align left',
                ok ? () => _apply((x) => x['alignment'] = 'left') : null,
                active: ok && align == TextAlign.left),
            _rb(Icons.format_align_center, 'Center',
                ok ? () => _apply((x) => x['alignment'] = 'center') : null,
                active: ok && align == TextAlign.center),
            _rb(Icons.format_align_right, 'Align right',
                ok ? () => _apply((x) => x['alignment'] = 'right') : null,
                active: ok && align == TextAlign.right),
            _rb(Icons.format_align_justify, 'Justify',
                ok ? () => _apply((x) => x['alignment'] = 'justify') : null,
                active: ok && align == TextAlign.justify),
            sep,
            _rb(Icons.format_list_bulleted, 'Bullets',
                ok ? () => _toggleList('bullet') : null,
                active: isList && listStyle == 'bullet'),
            _rb(Icons.format_list_numbered, 'Numbering',
                ok ? () => _toggleList('number') : null,
                active: isList && listStyle == 'number'),
            sep,
            _rb(Icons.playlist_add, 'Add paragraph below', _insertParagraph),
            _rb(
              Icons.delete_outline,
              'Delete paragraph',
              (b != null && _type(b) != 'image') ? _deleteSelected : null,
              color: _red,
            ),
          ],
        ),
      ),
    );
  }

  Widget _statusBar(int pageCount) {
    var words = 0;
    var chars = 0;
    for (final b in _blocks) {
      if (!_isTextual(b)) continue;
      final txt = _displayText(b, _issuesForBlock(b));
      chars += txt.length;
      words += txt.trim().isEmpty ? 0 : txt.trim().split(RegExp(r'\s+')).length;
    }
    final b = _sel;
    final info = (b != null && _isTextual(b))
        ? '${_styleName(b)} · ${_fontOf(b)} · ${_fmt(_sizeOf(b))}pt'
        : 'No paragraph selected — click text to edit';
    const st = TextStyle(color: Colors.white, fontSize: 11);
    return Container(
      height: 26,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      color: _wordBlue,
      child: Row(
        children: [
          Text('$pageCount page${pageCount == 1 ? '' : 's'}', style: st),
          const SizedBox(width: 14),
          Text('$words words', style: st),
          const SizedBox(width: 14),
          Text('$chars characters', style: st),
          const Spacer(),
          Flexible(
            child: Text(info, style: st, overflow: TextOverflow.ellipsis),
          ),
        ],
      ),
    );
  }

  Widget _buildPaper(
    int number,
    int total,
    List<Map<String, dynamic>> blocks,
    double s,
  ) {
    final children = <Widget>[];
    var n = 0;
    for (final b in blocks) {
      if (_type(b) == 'list_item' && b['list_style'] == 'number') {
        n++;
      } else {
        n = 0;
      }
      children.add(_buildWordBlock(b, s, number: n));
    }
    return Container(
      margin: const EdgeInsets.only(bottom: 24),
      width: _pageW * s,
      constraints: BoxConstraints(minHeight: _pageH * s),
      padding: EdgeInsets.all(_marginPx * s),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.25),
            blurRadius: 10,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ...children,
          SizedBox(height: 24 * s),
          Center(
            child: Text(
              '$number / $total',
              style: TextStyle(
                color: Colors.black45,
                fontSize: 10 * s,
                fontFamily: widget.defaultFont,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _editor(TextStyle style, TextAlign align) {
    return TextField(
      controller: _editCtrl,
      focusNode: _editFocus,
      maxLines: null,
      keyboardType: TextInputType.multiline,
      textInputAction: TextInputAction.newline,
      style: style,
      textAlign: align,
      cursorColor: Colors.black,
      decoration: const InputDecoration(
        isCollapsed: true,
        filled: false,
        fillColor: Colors.transparent,
        border: InputBorder.none,
        enabledBorder: InputBorder.none,
        focusedBorder: InputBorder.none,
        contentPadding: EdgeInsets.zero,
      ),
      onChanged: _onTextChanged,
    );
  }

  Widget _buildWordBlock(Map<String, dynamic> block, double s, {int number = 0}) {
    final type = _type(block);
    final blockIssues = _issuesForBlock(block);

    if (type == 'image') {
      return _buildWordImage(block, blockIssues, s);
    }
    if (type == 'table') {
      return _buildWordTable(block, _fontOf(block), s);
    }
    if (type == 'toc_item') {
      final title = block['text'] ?? block['title'] ?? block['heading'] ?? '';
      final pageNum = block['page'] ?? block['page_number'] ?? '';
      if (title.toString().toLowerCase().contains('table of contents') ||
          title.toString().toLowerCase().contains('list of figures') ||
          title.toString().toLowerCase().contains('list of tables')) {
        return Padding(
          padding: EdgeInsets.only(top: 14 * s, bottom: 6 * s),
          child: Text(
            title.toString(),
            style: _wordStyle(_fontOf(block), 14, s, bold: true),
          ),
        );
      }
      return Padding(
        padding: EdgeInsets.symmetric(vertical: 4 * s),
        child: Row(
          children: [
            Expanded(
              child: Text(
                title.toString(),
                style: _wordStyle(widget.defaultFont, widget.bodyPt, s),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (pageNum.toString().isNotEmpty) ...[
              Padding(
                padding: EdgeInsets.symmetric(horizontal: 8 * s),
                child: Tr('. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .',
                  style: TextStyle(color: Colors.black38, fontSize: 10 * s),
                ),
              ),
              Text(
                pageNum.toString(),
                style: _wordStyle(widget.defaultFont, widget.bodyPt, s, bold: true),
              ),
            ],
          ],
        ),
      );
    }

    final uid = block['_uid'] as String;
    final pid = block['paragraph_id'] as String? ?? '';
    final text = _displayText(block, blockIssues);
    final isFixed = pid.isNotEmpty && widget.appliedFixes.containsKey(pid);
    final hasIssue = blockIssues.isNotEmpty;
    final isSelected = _selectedUid == uid;
    final editable = _isTextual(block);

    final font = _fontOf(block);
    final pt = _sizeOf(block);
    final style = _blockStyle(block, s);
    final align = _alignOf(block);

    final Widget body = (isSelected && editable)
        ? _editor(style, align)
        : Text(
            text.isEmpty ? ' ' : text,
            textAlign: align,
            style: style,
          );

    Widget content;
    String styleLabel;
    final flags = [
      if (_boldOf(block)) 'B',
      if (_italicOf(block)) 'I',
      if (_underlineOf(block)) 'U',
    ].join();
    final flagText = flags.isEmpty ? '' : ' · $flags';

    switch (type) {
      case 'heading':
        content = Padding(
          padding: EdgeInsets.only(top: 12 * s, bottom: 6 * s),
          child: body,
        );
        styleLabel = 'Heading ${_level(block)} · $font · ${_fmt(pt)}pt$flagText';
        break;
      case 'list_item':
        {
          final isNum = block['list_style'] == 'number';
          content = Padding(
            padding: EdgeInsets.only(left: 28 * s, bottom: 3 * s),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 24 * s,
                  child: Text(
                    isNum ? '$number.' : '•',
                    style: _wordStyle(font, pt, s, height: _spacingOf(block)),
                  ),
                ),
                Expanded(child: body),
              ],
            ),
          );
          styleLabel =
              '${isNum ? 'List Number' : 'List Bullet'} · $font · ${_fmt(pt)}pt$flagText';
          break;
        }
      default:
        content = Padding(
          padding: EdgeInsets.only(bottom: 8 * s),
          child: body,
        );
        styleLabel =
            'Normal · $font · ${_fmt(pt)}pt · ×${_fmt(_spacingOf(block))}$flagText';
    }

    Color? bg;
    Color? bar;
    if (hasIssue) {
      bg = _highlightColor(blockIssues);
      bar = _borderColor(blockIssues);
    } else if (isFixed) {
      bg = _green.withOpacity(0.08);
      bar = _green;
    }
    if (isSelected && bg == null) bg = _blue.withOpacity(0.06);

    final side = BorderSide(color: isSelected ? _blue.withOpacity(0.6) : Colors.transparent);
    final border = Border(
      top: side,
      right: side,
      bottom: side,
      left: BorderSide(color: bar ?? (isSelected ? _blue.withOpacity(0.6) : Colors.transparent), width: 3),
    );

    return MouseRegion(
      cursor: SystemMouseCursors.text,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => _select(uid),
        child: Container(
          decoration: BoxDecoration(color: bg, border: border),
          padding: const EdgeInsets.symmetric(horizontal: 4),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (_showStyleTags)
                Padding(
                  padding: const EdgeInsets.only(bottom: 2),
                  child: Align(
                    alignment: Alignment.centerRight,
                    child: _styleTag(styleLabel, isFixed),
                  ),
                ),
              content,
            ],
          ),
        ),
      ),
    );
  }

  Widget _styleTag(String label, bool fixed) {
    final c = fixed ? _green : _wordBlue;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: c.withOpacity(0.10),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: c.withOpacity(0.35)),
      ),
      child: Text(
        fixed ? '✓ $label' : label,
        style: TextStyle(color: c, fontSize: 9, fontWeight: FontWeight.w600),
      ),
    );
  }

  Widget _buildWordTable(Map<String, dynamic> block, String font, double s) {
    final rows = _rawTableRows(block);
    if (rows.isEmpty) {
      return Padding(
        padding: EdgeInsets.symmetric(vertical: 8 * s),
        child: Tr('[Table — no cell data received from server]',
            style: _wordStyle(font, 10, s, italic: true)),
      );
    }
    // Pad ragged rows so Table doesn't throw.
    final cols = rows.map((r) => r.length).reduce((a, b) => a > b ? a : b);
    for (final r in rows) {
      while (r.length < cols) {
        r.add('');
      }
    }
    final pt = _num(block['font_size']) ?? 11;
    return Padding(
      padding: EdgeInsets.symmetric(vertical: 8 * s),
      child: Table(
        border: TableBorder.all(color: Colors.black87, width: 0.8),
        children: [
          for (var i = 0; i < rows.length; i++)
            TableRow(
              decoration: BoxDecoration(
                color: i == 0 ? const Color(0xFFF3F4F6) : Colors.white,
              ),
              children: [
                for (final cell in rows[i])
                  Padding(
                    padding: EdgeInsets.all(6 * s),
                    child: Text(
                      cell,
                      textAlign: i == 0 ? TextAlign.center : TextAlign.left,
                      style: _wordStyle(font, pt, s, bold: i == 0, height: 1.2),
                    ),
                  ),
              ],
            ),
        ],
      ),
    );
  }

  Widget _buildWordImage(
    Map<String, dynamic> block,
    List<Map<String, dynamic>> blockIssues,
    double s,
  ) {
    final rawPath = _rawImagePath(block);
    final imageUrl = _imageUrl(rawPath);
    final caption = block['caption'] as String? ?? '';
    final ethics = blockIssues.where((i) => (i['function'] as String? ?? '') == 'image_ethics').toList();
    final irrelevant = blockIssues.where((i) => (i['function'] as String? ?? '') == 'image_relevance').toList();
    final isUnethical = ethics.isNotEmpty;
    final isIrrelevant = irrelevant.isNotEmpty;
    final issue = isUnethical ? ethics.first : (isIrrelevant ? irrelevant.first : null);
    final flagColor = isUnethical ? _red : _yellow;

    return Container(
      margin: EdgeInsets.symmetric(vertical: 10 * s),
      decoration: issue != null
          ? BoxDecoration(
              color: flagColor.withOpacity(0.10),
              border: Border.all(color: flagColor.withOpacity(0.6), width: 1.5),
            )
          : null,
      padding: issue != null ? const EdgeInsets.all(8) : EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (issue != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Text(
                isUnethical ? 'Flagged — unethical image' : 'Warning — irrelevant image',
                style: TextStyle(
                  color: isUnethical ? _red : const Color(0xFFB45309),
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          Center(
            child: ConstrainedBox(
              constraints: BoxConstraints(maxHeight: 320 * s),
              child: imageUrl.isEmpty
                  ? Container(
                      height: 160,
                      width: double.infinity,
                      decoration: BoxDecoration(
                        color: Colors.grey.shade100,
                        border: Border.all(color: Colors.grey.shade300),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: const [
                          Icon(Icons.image_outlined, color: Colors.black45, size: 48),
                          SizedBox(height: 8),
                          Tr('[Figure / Image Placeholder]',
                            style: TextStyle(color: Colors.black54, fontSize: 12, fontStyle: FontStyle.italic),
                          ),
                        ],
                      ),
                    )
                  : _FallbackImage(urls: _imageUrls(rawPath.toString()), height: 160),
            ),
          ),
          if (caption.isNotEmpty)
            Padding(
              padding: EdgeInsets.only(top: 4 * s),
              child: Text(
                caption,
                textAlign: TextAlign.center,
                style: _wordStyle(widget.defaultFont, 10, s, italic: true),
              ),
            ),
          if (issue != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: () => _showReplaceDialog(block, issue),
                      icon: const Icon(Icons.image_search, size: 15),
                      label: const Tr('Replace', style: TextStyle(fontSize: 12)),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _blue,
                        foregroundColor: Colors.white,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => _confirmAndRemove(block, issue),
                      icon: const Icon(Icons.delete_outline, size: 15),
                      label: const Tr('Remove', style: TextStyle(fontSize: 12)),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: _red,
                        side: BorderSide(color: _red.withOpacity(0.55)),
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

  @override
  Widget build(BuildContext context) {
    _ap = context.watch<ThemeProvider>().palette;
    if (_blocks.isEmpty && widget.blocks.isEmpty) {
      return Center(
        child: Tr('No document content available for preview.', style: TextStyle(color: _textSec)),
      );
    }

    return CallbackShortcuts(
      bindings: {
        const SingleActivator(LogicalKeyboardKey.keyB, control: true): _toggleBold,
        const SingleActivator(LogicalKeyboardKey.keyB, meta: true): _toggleBold,
        const SingleActivator(LogicalKeyboardKey.keyI, control: true): _toggleItalic,
        const SingleActivator(LogicalKeyboardKey.keyI, meta: true): _toggleItalic,
        const SingleActivator(LogicalKeyboardKey.keyU, control: true): _toggleUnderline,
        const SingleActivator(LogicalKeyboardKey.keyU, meta: true): _toggleUnderline,
      },
      child: Container(
        color: _bg,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_showOriginal) ...[
              _buildOriginalColumn(),
              VerticalDivider(width: 1, color: _border),
            ],
            _buildWordColumn(),
          ],
        ),
      ),
    );
  }
}

/// Tries each candidate URL in order until one loads; logs which one worked.
class _FallbackImage extends StatefulWidget {
  final List<String> urls;
  final double height;
  const _FallbackImage({required this.urls, required this.height});
  @override
  State<_FallbackImage> createState() => _FallbackImageState();
}

class _FallbackImageState extends State<_FallbackImage> {
  int _i = 0;
  @override
  Widget build(BuildContext context) {
    if (_i >= widget.urls.length) {
      return Container(
        height: widget.height,
        color: Colors.grey.shade100,
        child: const Center(child: Icon(Icons.broken_image, color: Colors.black38, size: 40)),
      );
    }
    final url = widget.urls[_i];
    return Image.network(
      url,
      fit: BoxFit.contain,
      frameBuilder: (c, child, frame, sync) {
        if (frame != null && (sync || frame == 0)) debugPrint('[preview] image OK: $url');
        return child;
      },
      errorBuilder: (_, e, __) {
        debugPrint('[preview] image FAILED: $url');
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) setState(() => _i++);
        });
        return SizedBox(height: widget.height);
      },
    );
  }
}