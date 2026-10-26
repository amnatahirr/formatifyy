import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../theme/app_theme.dart';
import '../../widgets/admin/admin_ui.dart';
import 'document_page_view.dart';

/// Yellow for unresolved comments, gray for resolved-only paragraphs.
const Color _unresolvedHighlight = Color(0xFFFFF3C4);
const Color _resolvedHighlight = Color(0xFFE5E7EB);

/// A4 page width at 96 dpi (like Word's print layout).
const double _pageWidth = 794;

class DocumentReviewScreen extends StatefulWidget {
  final int groupId;
  final int documentId;
  final String? documentTitle;

  const DocumentReviewScreen({
    super.key,
    required this.groupId,
    required this.documentId,
    this.documentTitle,
  });

  @override
  State<DocumentReviewScreen> createState() => _DocumentReviewScreenState();
}

class _DocumentReviewScreenState extends State<DocumentReviewScreen> {
  final SupervisorApiService _api = SupervisorApiService();
  DocumentReviewModel? _review;
  String? _error;
  bool _loading = true;
  bool _busy = false;
  bool _downloading = false;
  bool _showStyleLabels = false;

  // Page view = real rendered pages (Word look). Analysis view = block view.
  bool _pageMode = true;
  bool _pagesLoading = true;
  DocumentPagesModel? _pages;

  @override
  void initState() {
    super.initState();
    _loadReview();
    _loadPages();
  }

  Future<void> _loadPages() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _pagesLoading = true);
    try {
      final json = await _api.fetchDocumentPagesJson(
        userId: userId,
        groupId: widget.groupId,
        documentId: widget.documentId,
      );
      if (mounted) setState(() => _pages = DocumentPagesModel.fromJson(json));
    } catch (_) {
      // Server could not render the pages: fall back to the block view.
      if (mounted) setState(() => _pageMode = false);
    } finally {
      if (mounted) setState(() => _pagesLoading = false);
    }
  }

  Future<Uint8List> _loadPageImage(int page) {
    final userId = context.read<AuthProvider>().userId!;
    return _api.fetchDocumentPageImage(
      userId: userId,
      groupId: widget.groupId,
      documentId: widget.documentId,
      page: page,
    );
  }

  Future<void> _loadReview() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final review = await _api.fetchDocumentReview(
        userId: userId,
        groupId: widget.groupId,
        documentId: widget.documentId,
      );
      if (mounted) setState(() => _review = review);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _downloadFile() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _downloading = true);
    try {
      final path = await _api.downloadGroupDocument(
        userId: userId,
        groupId: widget.groupId,
        documentId: widget.documentId,
        preferredFilename: _review?.document.filename,
      );
      if (!mounted) return;
      showAdminSnackBar(context, 'Saved to $path');
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _downloading = false);
    }
  }

  Future<void> _addComment(DocumentParagraphModel paragraph) async {
    final controller = TextEditingController();
    String? errorText;
    final previewText = _blockPreviewText(paragraph);
    final comment = await showDialog<String>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              backgroundColor: AdminColors.surface,
              shape: adminDialogShape(),
              title: const Text('Add Comment'),
              content: SizedBox(
                width: 440,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'This comment will be linked to the selected paragraph and the student will be notified.',
                      style: TextStyle(color: Colors.white.withOpacity(0.7), height: 1.4),
                    ),
                    const SizedBox(height: 14),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AdminColors.surfaceAlt,
                        borderRadius: BorderRadius.circular(adminTileRadius),
                        border: Border.all(color: AdminColors.borderStrong),
                      ),
                      child: Text(
                        previewText,
                        maxLines: 4,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(color: Colors.white.withOpacity(0.75), height: 1.4, fontSize: 13),
                      ),
                    ),
                    const SizedBox(height: 14),
                    TextField(
                      controller: controller,
                      maxLines: 4,
                      autofocus: true,
                      style: const TextStyle(color: Colors.white),
                      decoration: adminFieldDecoration(
                        label: 'Comment',
                        hint: 'Write feedback for the student…',
                      ).copyWith(errorText: errorText),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext),
                  child: const Text('Cancel'),
                ),
                ElevatedButton(
                  onPressed: () {
                    final text = controller.text.trim();
                    if (text.isEmpty) {
                      setDialogState(() => errorText = 'Enter a comment');
                      return;
                    }
                    Navigator.pop(dialogContext, text);
                  },
                  child: const Text('Add Comment'),
                ),
              ],
            );
          },
        );
      },
    );
    controller.dispose();
    if (comment == null || comment.trim().isEmpty) return;

    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _busy = true);
    try {
      final review = await _api.addParagraphComment(
        userId: userId,
        groupId: widget.groupId,
        documentId: widget.documentId,
        paragraphId: paragraph.id,
        commentText: comment.trim(),
      );
      if (!mounted) return;
      setState(() => _review = review);
      showAdminSnackBar(context, 'Comment added. Student notified.');
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _resolveComments(DocumentParagraphModel paragraph) async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _busy = true);
    try {
      final review = await _api.resolveParagraphComments(
        userId: userId,
        groupId: widget.groupId,
        documentId: widget.documentId,
        paragraphId: paragraph.id,
      );
      if (!mounted) return;
      setState(() => _review = review);
      showAdminSnackBar(context, 'Comments marked as resolved.');
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _onParagraphLongPress(DocumentParagraphModel paragraph) async {
    if (_busy) return;
    final action = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) {
        return Container(
          margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          decoration: BoxDecoration(
            color: AdminColors.surface,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: AdminColors.borderStrong),
            boxShadow: adminCardGlow(opacity: 0.2),
          ),
          child: SafeArea(
            top: false,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const SizedBox(height: 10),
                Container(
                  width: 42,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.22),
                    borderRadius: BorderRadius.circular(99),
                  ),
                ),
                ListTile(
                  leading: const Icon(Icons.add_comment_outlined, color: AdminColors.primary),
                  title: const Text('Add Comment', style: TextStyle(color: Colors.white)),
                  onTap: () => Navigator.pop(sheetContext, 'comment'),
                ),
                if (paragraph.hasUnresolvedComments)
                  ListTile(
                    leading: const Icon(Icons.check_circle_outline, color: AdminColors.success),
                    title: const Text('Mark Resolved', style: TextStyle(color: Colors.white)),
                    subtitle: Text(
                      'Turns this paragraph gray',
                      style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 12),
                    ),
                    onTap: () => Navigator.pop(sheetContext, 'resolve'),
                  ),
                ListTile(
                  leading: Icon(Icons.close_rounded, color: Colors.white.withOpacity(0.6)),
                  title: Text('Cancel', style: TextStyle(color: Colors.white.withOpacity(0.75))),
                  onTap: () => Navigator.pop(sheetContext),
                ),
                const SizedBox(height: 8),
              ],
            ),
          ),
        );
      },
    );

    if (action == 'comment') {
      await _addComment(paragraph);
    } else if (action == 'resolve') {
      await _resolveComments(paragraph);
    }
  }

  @override
  Widget build(BuildContext context) {
    final title = _review?.document.title.isNotEmpty == true
        ? _review!.document.title
        : (widget.documentTitle ?? 'Document Review');

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: AppPalette.dark.innerGlowBackdrop(
        child: Column(
          children: [
            Container(
              height: 72,
              decoration: BoxDecoration(
                color: AdminColors.surface,
                border: Border(bottom: BorderSide(color: AdminColors.borderStrong)),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  IconButton(
                    tooltip: 'Back',
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.arrow_back_rounded, color: Colors.white),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title,
                          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Colors.white),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        Text(
                          'Long-press a paragraph, table or image to add a comment',
                          style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.5)),
                        ),
                      ],
                    ),
                  ),
                  if (_busy || _downloading)
                    const Padding(
                      padding: EdgeInsets.only(right: 8),
                      child: SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: AdminColors.primary),
                      ),
                    ),
                  IconButton(
                    tooltip: _pageMode ? 'Analysis view' : 'Page view',
                    onPressed: () => setState(() => _pageMode = !_pageMode),
                    icon: Icon(
                      _pageMode ? Icons.view_agenda_outlined : Icons.description_outlined,
                      color: Colors.white,
                    ),
                  ),
                  if (!_pageMode)
                  IconButton(
                    tooltip: _showStyleLabels ? 'Hide style names' : 'Show style names',
                    onPressed: () => setState(() => _showStyleLabels = !_showStyleLabels),
                    icon: Icon(
                      Icons.text_format_rounded,
                      color: _showStyleLabels ? AdminColors.primary : Colors.white,
                    ),
                  ),
                  IconButton(
                    tooltip: 'Download file',
                    onPressed: (_busy || _downloading) ? null : _downloadFile,
                    icon: const Icon(Icons.download_rounded, color: Colors.white),
                  ),
                ],
              ),
            ),
            Expanded(child: _buildBody()),
          ],
        ),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const AdminPage(child: AdminLoadingView(label: 'Loading document...'));
    }
    if (_error != null) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _loadReview));
    }
    final review = _review;
    if (review == null) {
      return const AdminPage(
        child: AdminEmptyView(
          icon: Icons.description_outlined,
          title: 'Review unavailable',
          message: 'Document review data is unavailable.',
        ),
      );
    }

    if (_pageMode) {
      if (_pagesLoading) {
        return const AdminPage(child: AdminLoadingView(label: 'Preparing pages...'));
      }
      final pages = _pages;
      if (pages != null && pages.pages.isNotEmpty) {
        return Column(
          children: [
            const SizedBox(height: 10),
            const Wrap(
              spacing: 10,
              runSpacing: 8,
              children: [
                _LegendChip(color: _unresolvedHighlight, label: 'Unresolved comment'),
                _LegendChip(color: _resolvedHighlight, label: 'Resolved comment'),
              ],
            ),
            Expanded(
              child: DocumentPageView(
                pages: pages,
                paragraphsById: {for (final p in review.paragraphs) p.id: p},
                loadPage: _loadPageImage,
                onLongPress: _onParagraphLongPress,
              ),
            ),
          ],
        );
      }
    }

    return AdminPage(
      onRefresh: _loadReview,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageMeta(
            text: review.groupTitle.isEmpty
                ? 'Review submission paragraph by paragraph'
                : '${review.groupTitle} · ${review.document.statusLabel}',
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 8,
            children: const [
              _LegendChip(color: _unresolvedHighlight, label: 'Unresolved comment'),
              _LegendChip(color: _resolvedHighlight, label: 'Resolved comment'),
              _LegendChip(color: Colors.white, label: 'No comment', bordered: true),
            ],
          ),
          const SizedBox(height: 20),
          if (review.paragraphs.isEmpty)
            const AdminEmptyView(
              icon: Icons.notes_rounded,
              title: 'Nothing to review',
              message: 'This document has no paragraphs to review yet.',
            )
          else
            _WordPage(
              paragraphs: _coalesceTocParagraphs(review.paragraphs),
              showStyleLabels: _showStyleLabels,
              onLongPress: _onParagraphLongPress,
            ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Safe access helpers (model may not expose every field yet)
// ─────────────────────────────────────────────────────────────────────────────

T? _try<T>(T? Function() read) {
  try {
    return read();
  } catch (_) {
    return null; // field not present on the model yet
  }
}

String _normalizeTocLine(String text) =>
    text.replaceAll('\r', ' ').replaceAll('\n', ' ').replaceAll(RegExp(r'\s+'), ' ').trim();

bool _styleIsToc(String? styleName) {
  final s = (styleName ?? '').toLowerCase();
  return s.startsWith('toc') && !s.contains('heading');
}

bool _isTocPrefixFragment(String text) {
  final t = _normalizeTocLine(text);
  if (t.isEmpty || t.length > 96) return false;
  if (RegExp(r'\.{2,}\s*\d+\s*$').hasMatch(t)) return false;
  if (RegExp(r'^\d+(?:\.\d+)*\.?\s*$').hasMatch(t)) return true;
  if (RegExp(r'^\d+(?:\.\d+)*\.?\s+').hasMatch(t)) {
    if (t.endsWith('—') || t.endsWith('–') || t.endsWith('-')) return true;
    final words = t.split(RegExp(r'\s+')).where((w) => w.isNotEmpty).length;
    if (words <= 8 && !RegExp(r'(?<!\d)\d+\s*$').hasMatch(t)) return true;
  }
  return false;
}

bool _tocTailHasPage(DocumentParagraphModel p, String text) {
  if (p.pageNumber != null) return true;
  if (text.contains('\t') || RegExp(r'\.{2,}\s*\d+\s*$').hasMatch(text)) return true;
  return RegExp(r'(?<!\d)\d+\s*$').hasMatch(text);
}

bool _paragraphIsTocish(DocumentParagraphModel p) {
  if (p.blockType == 'toc') return true;
  return _styleIsToc(p.styleName);
}

bool _shouldMergeTocPair(DocumentParagraphModel a, DocumentParagraphModel b) {
  final t0 = _normalizeTocLine(a.text);
  final t1 = _normalizeTocLine(b.text);
  if (t0.isEmpty || t1.isEmpty) return false;
  if (!_paragraphIsTocish(a) && !_paragraphIsTocish(b)) return false;
  if (!_isTocPrefixFragment(t0)) return false;
  return _tocTailHasPage(b, t1);
}

DocumentParagraphModel _mergeTocPair(DocumentParagraphModel a, DocumentParagraphModel b) {
  final text = _normalizeTocLine('${a.text} ${b.text}');
  final highlight = a.highlight == 'unresolved' || b.highlight == 'unresolved'
      ? 'unresolved'
      : (a.highlight == 'resolved' || b.highlight == 'resolved' ? 'resolved' : 'none');
  return DocumentParagraphModel(
    id: b.id,
    sortOrder: a.sortOrder,
    displayIndex: a.displayIndex,
    text: text,
    blockType: 'toc',
    blockLabel: b.blockLabel.isNotEmpty ? b.blockLabel : 'Table of Contents',
    highlight: highlight,
    hasUnresolvedComments: a.hasUnresolvedComments || b.hasUnresolvedComments,
    comments: [...a.comments, ...b.comments],
    styleName: b.styleName ?? a.styleName,
    fontSize: b.fontSize ?? a.fontSize,
    isBold: b.isBold ?? a.isBold,
    isItalic: b.isItalic ?? a.isItalic,
    isUnderline: b.isUnderline ?? a.isUnderline,
    alignment: b.alignment ?? a.alignment,
    fontName: b.fontName ?? a.fontName,
    colorHex: b.colorHex ?? a.colorHex,
    indentLevel: b.indentLevel ?? a.indentLevel,
    isListItem: b.isListItem ?? a.isListItem,
    listMarker: b.listMarker ?? a.listMarker,
    runs: b.runs.isNotEmpty ? b.runs : a.runs,
    tableRows: b.tableRows.isNotEmpty ? b.tableRows : a.tableRows,
    images: b.images.isNotEmpty ? b.images : a.images,
    imageUrl: b.imageUrl ?? a.imageUrl,
    imageBase64: b.imageBase64 ?? a.imageBase64,
    pageNumber: b.pageNumber ?? a.pageNumber,
  );
}

List<DocumentParagraphModel> _coalesceTocParagraphs(List<DocumentParagraphModel> paragraphs) {
  final out = <DocumentParagraphModel>[];
  var i = 0;
  while (i < paragraphs.length) {
    final cur = paragraphs[i];
    if (i + 1 < paragraphs.length && _shouldMergeTocPair(cur, paragraphs[i + 1])) {
      out.add(_mergeTocPair(cur, paragraphs[i + 1]));
      i += 2;
      continue;
    }
    if (cur.blockType == 'toc' && cur.text.contains('\n')) {
      out.add(DocumentParagraphModel(
        id: cur.id,
        sortOrder: cur.sortOrder,
        displayIndex: cur.displayIndex,
        text: _normalizeTocLine(cur.text),
        blockType: cur.blockType,
        blockLabel: cur.blockLabel,
        highlight: cur.highlight,
        hasUnresolvedComments: cur.hasUnresolvedComments,
        comments: cur.comments,
        styleName: cur.styleName,
        fontSize: cur.fontSize,
        isBold: cur.isBold,
        isItalic: cur.isItalic,
        isUnderline: cur.isUnderline,
        alignment: cur.alignment,
        fontName: cur.fontName,
        colorHex: cur.colorHex,
        indentLevel: cur.indentLevel,
        isListItem: cur.isListItem,
        listMarker: cur.listMarker,
        runs: cur.runs,
        tableRows: cur.tableRows,
        images: cur.images,
        imageUrl: cur.imageUrl,
        imageBase64: cur.imageBase64,
        pageNumber: cur.pageNumber,
      ));
      i += 1;
      continue;
    }
    out.add(cur);
    i += 1;
  }
  return out;
}

String _blockPreviewText(DocumentParagraphModel p) {
  final dynamic d = p;
  final text = _try<String>(() => d.text as String?) ?? '';
  if (text.trim().isNotEmpty) return text;
  final rows = _readTableRows(p);
  if (rows.isNotEmpty) {
    return 'Table: ${rows.first.map((c) => c.text).join(' | ')}';
  }
  if (_readImages(p).isNotEmpty) return '[Image]';
  return '(empty paragraph)';
}

// ─────────────────────────────────────────────────────────────────────────────
// Rich content readers: runs, tables, images
// ─────────────────────────────────────────────────────────────────────────────

/// One formatted piece of text inside a paragraph (Word "run").
class _Run {
  final String text;
  final bool? bold;
  final bool? italic;
  final bool? underline;
  final bool? strike;
  final Color? color;
  final Color? background;
  final double? sizePt;
  final String? fontName;
  final bool? superscript;
  final bool? subscript;

  const _Run({
    required this.text,
    this.bold,
    this.italic,
    this.underline,
    this.strike,
    this.color,
    this.background,
    this.sizePt,
    this.fontName,
    this.superscript,
    this.subscript,
  });
}

/// Nesting depth of a TOC line from its numbering: "4." -> 1, "3.1." -> 2, "4.3.1." -> 3.
int _tocLevelFromText(String text) {
  final m = RegExp(r'^\s*(\d+(?:\.\d+)*)\.?\s').firstMatch(text);
  if (m == null) return 1;
  return m.group(1)!.split('.').length.clamp(1, 6).toInt();
}

Color? _parseColor(String? hex) {
  if (hex == null) return null;
  var h = hex.replaceAll('#', '').trim();
  if (h.isEmpty || h.toLowerCase() == 'auto') return null;
  if (h.length == 6) h = 'FF$h';
  final v = int.tryParse(h, radix: 16);
  return v == null ? null : Color(v);
}

_Run? _runFrom(dynamic r) {
  if (r is String) return _Run(text: r);
  if (r is Map) {
    final text = (r['text'] ?? '').toString();
    return _Run(
      text: text,
      bold: r['bold'] as bool? ?? r['isBold'] as bool?,
      italic: r['italic'] as bool? ?? r['isItalic'] as bool?,
      underline: r['underline'] as bool? ?? r['isUnderline'] as bool?,
      strike: r['strike'] as bool? ?? r['isStrike'] as bool?,
      color: _parseColor((r['color'] ?? r['colorHex']) as String?),
      background: _parseColor((r['highlight'] ?? r['backgroundHex']) as String?),
      sizePt: (r['fontSize'] as num?)?.toDouble() ?? (r['size'] as num?)?.toDouble(),
      fontName: (r['fontName'] ?? r['font']) as String?,
      superscript: r['superscript'] as bool?,
      subscript: r['subscript'] as bool?,
    );
  }
  final dynamic o = r;
  final text = _try<String>(() => o.text as String?);
  if (text == null) return null;
  return _Run(
    text: text,
    bold: _try<bool>(() => o.isBold as bool?) ?? _try<bool>(() => o.bold as bool?),
    italic: _try<bool>(() => o.isItalic as bool?) ?? _try<bool>(() => o.italic as bool?),
    underline: _try<bool>(() => o.isUnderline as bool?) ?? _try<bool>(() => o.underline as bool?),
    strike: _try<bool>(() => o.isStrike as bool?),
    color: _parseColor(_try<String>(() => o.colorHex as String?)),
    background: _parseColor(_try<String>(() => o.backgroundHex as String?)),
    sizePt: _try<num>(() => o.fontSize as num?)?.toDouble(),
    fontName: _try<String>(() => o.fontName as String?),
    superscript: _try<bool>(() => o.superscript as bool?),
    subscript: _try<bool>(() => o.subscript as bool?),
  );
}

List<_Run> _readRuns(DocumentParagraphModel p) {
  final dynamic d = p;
  final raw = _try<List>(() => d.runs as List?);
  if (raw == null) return const [];
  final out = <_Run>[];
  for (final r in raw) {
    final run = _runFrom(r);
    if (run != null && run.text.isNotEmpty) out.add(run);
  }
  return out;
}

class _Cell {
  final String text;
  final bool bold;
  final Color? fill;
  final TextAlign? align;
  final int colSpan;

  const _Cell({
    required this.text,
    this.bold = false,
    this.fill,
    this.align,
    this.colSpan = 1,
  });
}

/// Reads `tableRows` — a List of rows, each row a List of cells.
/// A cell is either a String or a Map {text, bold, fillHex, align}.
List<List<_Cell>> _readTableRows(DocumentParagraphModel p) {
  final dynamic d = p;
  final raw = _try<List>(() => d.tableRows as List?) ?? _try<List>(() => d.rows as List?);
  if (raw == null) return const [];
  final rows = <List<_Cell>>[];
  for (final row in raw) {
    if (row is! List) continue;
    final cells = <_Cell>[];
    for (final c in row) {
      if (c is Map) {
        cells.add(_Cell(
          text: (c['text'] ?? '').toString(),
          bold: c['bold'] as bool? ?? c['isBold'] as bool? ?? false,
          fill: _parseColor((c['fillHex'] ?? c['fill_hex'] ?? c['shading']) as String?),
          align: c['align'] == null
              ? null
              : _WordStyle.parseAlign(c['align'].toString(), TextAlign.left),
          colSpan: (c['colSpan'] as num?)?.toInt() ??
              (c['col_span'] as num?)?.toInt() ??
              1,
        ));
      } else {
        cells.add(_Cell(text: (c ?? '').toString()));
      }
    }
    if (cells.isNotEmpty) rows.add(cells);
  }
  return rows;
}

class _ImageSrc {
  final String? url;
  final Uint8List? bytes;
  final double? widthPx;
  final double? heightPx;
  final String? alt;

  const _ImageSrc({this.url, this.bytes, this.widthPx, this.heightPx, this.alt});
}

Uint8List? _decodeBase64(String? b64) {
  if (b64 == null || b64.isEmpty) return null;
  try {
    final clean = b64.contains(',') ? b64.substring(b64.indexOf(',') + 1) : b64;
    return base64Decode(clean);
  } catch (_) {
    return null;
  }
}

_ImageSrc? _imageFrom(dynamic i) {
  if (i is String) {
    if (i.startsWith('http') || i.startsWith('/')) return _ImageSrc(url: i);
    final bytes = _decodeBase64(i);
    return bytes == null ? null : _ImageSrc(bytes: bytes);
  }
  if (i is Map) {
    final bytes = _decodeBase64((i['base64'] ?? i['data']) as String?);
    final url = (i['url'] ?? i['imageUrl']) as String?;
    if (bytes == null && (url == null || url.isEmpty)) return null;
    return _ImageSrc(
      url: url,
      bytes: bytes,
      widthPx: (i['widthPx'] as num?)?.toDouble() ?? (i['width'] as num?)?.toDouble(),
      heightPx: (i['heightPx'] as num?)?.toDouble() ?? (i['height'] as num?)?.toDouble(),
      alt: i['alt'] as String?,
    );
  }
  return null;
}

/// Reads `images` (list) or a single `imageUrl` / `imageBase64`.
List<_ImageSrc> _readImages(DocumentParagraphModel p) {
  final dynamic d = p;
  final out = <_ImageSrc>[];
  final list = _try<List>(() => d.images as List?);
  if (list != null) {
    for (final i in list) {
      final src = _imageFrom(i);
      if (src != null) out.add(src);
    }
  }
  if (out.isEmpty) {
    final url = _try<String>(() => d.imageUrl as String?);
    final b64 = _try<String>(() => d.imageBase64 as String?);
    if (url != null && url.isNotEmpty) {
      out.add(_ImageSrc(url: url));
    } else {
      final bytes = _decodeBase64(b64);
      if (bytes != null) out.add(_ImageSrc(bytes: bytes));
    }
  }
  return out;
}

// ─────────────────────────────────────────────────────────────────────────────
// Word-like page
// ─────────────────────────────────────────────────────────────────────────────

/// Renders all blocks on a white A4-style sheet, like Word's Print Layout.
class _WordPage extends StatelessWidget {
  final List<DocumentParagraphModel> paragraphs;
  final bool showStyleLabels;
  final void Function(DocumentParagraphModel) onLongPress;

  const _WordPage({
    required this.paragraphs,
    required this.showStyleLabels,
    required this.onLongPress,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final available = constraints.maxWidth;
        final narrow = available < 700;
        // Keep real Word proportions on wide screens; shrink margins a bit on phones.
        final fontScale = narrow ? 0.9 : 1.0;
        final marginH = narrow ? 24.0 : 72.0;
        final marginV = narrow ? 28.0 : 72.0;

        return Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: _pageWidth),
            child: Container(
              width: double.infinity,
              padding: EdgeInsets.symmetric(horizontal: marginH, vertical: marginV),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(2),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.35),
                    blurRadius: 24,
                    offset: const Offset(0, 10),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  for (final p in paragraphs)
                    _WordBlock(
                      key: ValueKey('block_${p.id}'),
                      paragraph: p,
                      style: _WordStyle.resolve(p),
                      fontScale: fontScale,
                      showStyleLabel: showStyleLabels,
                      onLongPress: () => onLongPress(p),
                    ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

enum _BlockKind { paragraph, table, image, toc }

/// Visual style of one paragraph, as Word would show it.
///
/// Values come from the paragraph model when the backend sends them
/// (fontSize, isBold, isItalic, isUnderline, alignment, fontName, colorHex,
/// styleName, indentLevel, isListItem, blockType, tableRows, images, runs).
/// Anything missing falls back to a sensible default derived from the
/// block label / style name (Title, Heading 1-3, List, TOC, Normal).
class _WordStyle {
  final double fontSizePt;
  final bool bold;
  final bool italic;
  final bool underline;
  final TextAlign align;
  final String fontName;
  final Color color;
  final double indentLevel;
  final bool isListItem;
  final double spaceBeforePt;
  final double spaceAfterPt;
  final String label;
  final _BlockKind kind;
  final int tocLevel;
  final String? listMarker;

  const _WordStyle({
    required this.fontSizePt,
    required this.bold,
    required this.italic,
    required this.underline,
    required this.align,
    required this.fontName,
    required this.color,
    required this.indentLevel,
    required this.isListItem,
    required this.spaceBeforePt,
    required this.spaceAfterPt,
    required this.label,
    required this.kind,
    required this.tocLevel,
    required this.listMarker,
  });

  static TextAlign parseAlign(String? v, TextAlign fallback) {
    switch ((v ?? '').toLowerCase()) {
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

  factory _WordStyle.resolve(DocumentParagraphModel p) {
    final dynamic d = p;
    final styleName = _try<String>(() => d.styleName as String?) ?? '';
    final blockLabel = _try<String>(() => d.blockLabel as String?) ?? '';
    final blockType = (_try<String>(() => d.blockType as String?) ?? '').toLowerCase();
    final key = (styleName.isNotEmpty ? styleName : blockLabel).toLowerCase();
    final text = _try<String>(() => d.text as String?) ?? '';

    // ── Block kind ──────────────────────────────────────────────
    _BlockKind kind = _BlockKind.paragraph;
    if (blockType == 'table' || _readTableRows(p).isNotEmpty) {
      kind = _BlockKind.table;
    } else if (blockType == 'image' || (text.trim().isEmpty && _readImages(p).isNotEmpty)) {
      kind = _BlockKind.image;
    } else if (blockType == 'toc' ||
        blockType == 'toc_entry' ||
        RegExp(r'^toc\s*\d').hasMatch(key) ||
        key.startsWith('table of contents') && !key.contains('heading')) {
      kind = _BlockKind.toc;
    }

    int tocLevel = 1;
    if (kind == _BlockKind.toc) {
      final lvl = RegExp(r'(\d+)').firstMatch(styleName.toLowerCase());
      tocLevel = lvl != null
          ? (int.tryParse(lvl.group(1)!) ?? 1)
          : _tocLevelFromText(text);
    }

    // ── Defaults by style (Word's built-in look) ────────────────
    double size = 12;
    bool bold = false;
    bool italic = false;
    TextAlign align = TextAlign.left;
    Color color = Colors.black;
    double before = 0;
    double after = 8;

    // Backend block_type (from the docx extractor) — base layout before style names.
    switch (blockType) {
      case 'heading':
        size = 18;
        bold = true;
        color = const Color(0xFF1F3864);
        before = 18;
        after = 8;
        break;
      case 'subheading':
        size = 15;
        bold = true;
        color = const Color(0xFF2F5496);
        before = 14;
        after = 6;
        break;
      case 'bullet':
        after = 4;
        break;
      case 'line':
        size = 11;
        after = 4;
        break;
      case 'paragraph':
        align = TextAlign.justify;
        break;
      default:
        break;
    }

    // NOTE: "subtitle" must be tested before "title" (it contains "title").
    if (kind == _BlockKind.toc) {
      // TOC entries: plain body text (the blockLabel "Table of Contents" used to
      // match the heading branch below -> blue, bold, 16 pt).
      size = 11;
      after = 6;
    } else if (key.contains('subtitle')) {
      size = 15;
      italic = true;
      align = TextAlign.center;
      color = const Color(0xFF595959);
      after = 14;
    } else if (RegExp(r'^(title|document title)\b').hasMatch(key.trim())) {
      size = 26;
      bold = true;
      align = TextAlign.center;
      before = 12;
      after = 16;
    } else if (key.contains('toc heading') || key.contains('table of contents')) {
      size = 16;
      bold = true;
      color = const Color(0xFF2F5496);
      before = 12;
      after = 10;
    } else if (key.contains('heading 1') || key == 'h1' || key.contains('heading1')) {
      size = 18;
      bold = true;
      color = const Color(0xFF1F3864);
      before = 18;
      after = 8;
    } else if (key.contains('heading 2') || key == 'h2' || key.contains('heading2')) {
      size = 15;
      bold = true;
      color = const Color(0xFF2F5496);
      before = 14;
      after = 6;
    } else if (key.contains('heading 3') || key == 'h3' || key.contains('heading3')) {
      size = 13;
      bold = true;
      color = const Color(0xFF1F3763);
      before = 10;
      after = 4;
    } else if (key.contains('heading')) {
      size = 14;
      bold = true;
      before = 12;
      after = 6;
    } else if (kind == _BlockKind.toc) {
      size = 11;
      after = 3;
      if (tocLevel == 1) bold = false;
    } else if (key.contains('caption')) {
      size = 10;
      italic = true;
      color = const Color(0xFF44546A);
      align = TextAlign.center;
      after = 10;
    } else if (key.contains('list') || key.contains('bullet')) {
      after = 4;
    } else {
      align = TextAlign.justify;
    }

    final fontSize = _try<num>(() => d.fontSize as num?)?.toDouble() ?? size;
    final isBold = _try<bool>(() => d.isBold as bool?) ?? bold;
    final isItalic = _try<bool>(() => d.isItalic as bool?) ?? italic;
    final isUnderline = _try<bool>(() => d.isUnderline as bool?) ?? false;
    final alignment = parseAlign(_try<String>(() => d.alignment as String?), align);
    final fontName = _try<String>(() => d.fontName as String?) ?? 'Calibri';
    final parsedColor = _parseColor(_try<String>(() => d.colorHex as String?));
    final indent = _try<num>(() => d.indentLevel as num?)?.toDouble() ?? 0;
    final isList = _try<bool>(() => d.isListItem as bool?) ??
        blockType == 'bullet' ||
        key.contains('list') ||
        key.contains('bullet');
    final marker = _try<String>(() => d.listMarker as String?);

    return _WordStyle(
      fontSizePt: fontSize,
      bold: isBold,
      italic: isItalic,
      underline: isUnderline,
      align: alignment,
      fontName: fontName,
      color: parsedColor ?? color,
      indentLevel: indent,
      isListItem: isList,
      spaceBeforePt: before,
      spaceAfterPt: after,
      label: styleName.isNotEmpty ? styleName : blockLabel,
      kind: kind,
      tocLevel: tocLevel,
      listMarker: marker,
    );
  }

  String get fontFamilyFirst => fontName;

  List<String> get fontFallback => fallbackFor(fontName);

  static List<String> fallbackFor(String name) {
    final n = name.toLowerCase();
    if (n.contains('times') || n.contains('serif') || n.contains('cambria') || n.contains('georgia')) {
      return const ['Times New Roman', 'Georgia', 'Noto Serif', 'serif'];
    }
    if (n.contains('courier') || n.contains('consolas') || n.contains('mono')) {
      return const ['Courier New', 'Consolas', 'monospace'];
    }
    return const ['Calibri', 'Carlito', 'Arial', 'Roboto', 'sans-serif'];
  }
}

class _WordBlock extends StatelessWidget {
  final DocumentParagraphModel paragraph;
  final _WordStyle style;
  final double fontScale;
  final bool showStyleLabel;
  final VoidCallback onLongPress;

  const _WordBlock({
    super.key,
    required this.paragraph,
    required this.style,
    required this.fontScale,
    required this.showStyleLabel,
    required this.onLongPress,
  });

  Color? get _highlightColor {
    switch (paragraph.highlight) {
      case 'unresolved':
        return _unresolvedHighlight;
      case 'resolved':
        return _resolvedHighlight;
      default:
        return null;
    }
  }

  double get _px => style.fontSizePt * (96 / 72) * fontScale;

  TextStyle _baseTextStyle() {
    return TextStyle(
      fontSize: _px,
      height: 1.4,
      color: style.color,
      fontWeight: style.bold ? FontWeight.w700 : FontWeight.w400,
      fontStyle: style.italic ? FontStyle.italic : FontStyle.normal,
      decoration: style.underline ? TextDecoration.underline : TextDecoration.none,
      fontFamily: style.fontFamilyFirst,
      fontFamilyFallback: style.fontFallback,
    );
  }

  /// Builds a rich TextSpan from runs (bold / italic / colors / sizes inside
  /// one paragraph), falling back to plain text.
  InlineSpan _richText(TextStyle base, String fallbackText) {
    final runs = _readRuns(paragraph);
    if (runs.isEmpty) {
      return TextSpan(text: fallbackText.replaceAll('\t', '    '), style: base);
    }
    return TextSpan(
      style: base,
      children: [
        for (final r in runs)
          TextSpan(
            text: r.text.replaceAll('\t', '    '),
            style: TextStyle(
              fontWeight: r.bold == null ? null : (r.bold! ? FontWeight.w700 : FontWeight.w400),
              fontStyle: r.italic == null ? null : (r.italic! ? FontStyle.italic : FontStyle.normal),
              color: r.color,
              backgroundColor: r.background,
              fontSize: r.sizePt == null ? null : r.sizePt! * (96 / 72) * fontScale,
              fontFamily: r.fontName,
              fontFamilyFallback: r.fontName == null ? null : _WordStyle.fallbackFor(r.fontName!),
              decoration: TextDecoration.combine([
                if (r.underline ?? style.underline) TextDecoration.underline,
                if (r.strike == true) TextDecoration.lineThrough,
              ]),
            ),
          ),
      ],
    );
  }

  Widget _paragraphBody(String text) {
    final base = _baseTextStyle();
    final span = _richText(base, text);
    if (style.isListItem) {
      return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${style.listMarker ?? '•'}  ', style: base),
          Expanded(child: Text.rich(span, textAlign: style.align)),
        ],
      );
    }
    return Text.rich(span, textAlign: style.align);
  }

  /// Table of contents line: "Title ........ 12" with dotted leader and a
  /// right-aligned page number. Never wraps the number onto its own line.
  Widget _tocBody(String text) {
    final base = _baseTextStyle();
    final clean = text.replaceAll('\r', '').trim();
    String title = clean;
    String page = '';

    final dynamic d = paragraph;
    final explicitPage = _try<String>(() => d.pageNumber?.toString());
    if (explicitPage != null && explicitPage.isNotEmpty) {
      page = explicitPage;
      title = clean.replaceAll(RegExp(r'[\t\.\s]+\d+\s*$'), '').trim();
    } else {
      final m = RegExp(r'^(.*?)(?:\t+|\s*\.{2,}\s*|\s{3,})(\d+|[ivxlcdm]+)\s*$',
              caseSensitive: false)
          .firstMatch(clean);
      if (m != null) {
        title = m.group(1)!.trim();
        page = m.group(2)!;
      }
    }
    title = title.replaceAll('\t', ' ');

    final indent = (style.tocLevel - 1).clamp(0, 6) * 16.0 * fontScale;
    if (page.isEmpty) {
      return Padding(
        padding: EdgeInsets.only(left: indent),
        child: Text(title, style: base),
      );
    }
    return Padding(
      padding: EdgeInsets.only(left: indent),
      child: LayoutBuilder(
        builder: (context, constraints) {
          double measure(String s) {
            final tp = TextPainter(
              text: TextSpan(text: s, style: base),
              textDirection: TextDirection.ltr,
              maxLines: 1,
            )..layout();
            return tp.width;
          }

          const gap = 6.0;
          final avail = constraints.maxWidth;
          final titleW = measure(title);
          final pageW = measure(page);
          final dotW = measure('.');
          // Width left for the dotted leader once title and number are placed.
          final dotsW = avail - titleW - pageW - gap * 2 - 2;

          // Long title (no room for a leader): let it wrap, number stays right.
          if (!avail.isFinite || dotsW < dotW * 3) {
            return Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(child: Text(title, style: base)),
                Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: Text(page, style: base),
                ),
              ],
            );
          }

          final dotCount = (dotsW / dotW).floor();
          return Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Flexible(child: Text(title, style: base)),
              const SizedBox(width: gap),
              SizedBox(
                width: dotsW,
                child: Text(
                  '.' * dotCount,
                  maxLines: 1,
                  softWrap: false,
                  overflow: TextOverflow.clip,
                  style: base,
                ),
              ),
              const SizedBox(width: gap),
              Text(page, style: base),
            ],
          );
        },
      ),
    );
  }

  Widget _tableBody() {
    final rows = _readTableRows(paragraph);
    if (rows.isEmpty) return _imagePlaceholder('Table preview unavailable');
    final colCount = rows.fold<int>(
      1,
      (m, r) => r.fold<int>(0, (a, c) => a + c.colSpan) > m ? r.fold<int>(0, (a, c) => a + c.colSpan) : m,
    );
    final cellStyle = _baseTextStyle().copyWith(
      fontSize: 11 * (96 / 72) * fontScale,
      height: 1.3,
      color: Colors.black,
    );

    final tableRows = <TableRow>[];
    for (final row in rows) {
      final cells = <Widget>[];
      int used = 0;
      for (final c in row) {
        cells.add(Container(
          color: c.fill,
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
          child: Text(
            c.text.replaceAll('\t', '    '),
            textAlign: c.align ?? TextAlign.left,
            style: cellStyle.copyWith(fontWeight: c.bold ? FontWeight.w700 : FontWeight.w400),
          ),
        ));
        used += 1;
        // Pad merged cells so every row has the same column count.
        for (var i = 1; i < c.colSpan && used < colCount; i++) {
          cells.add(const SizedBox.shrink());
          used++;
        }
      }
      while (used < colCount) {
        cells.add(const SizedBox.shrink());
        used++;
      }
      tableRows.add(TableRow(children: cells));
    }

    // Wide tables scroll sideways instead of crushing the text.
    final minWidth = colCount * 110.0;
    return LayoutBuilder(
      builder: (context, constraints) {
        final table = Table(
          defaultColumnWidth: const FlexColumnWidth(),
          defaultVerticalAlignment: TableCellVerticalAlignment.top,
          border: TableBorder.all(color: const Color(0xFF7F7F7F), width: 0.8),
          children: tableRows,
        );
        if (constraints.maxWidth >= minWidth) return table;
        return SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SizedBox(width: minWidth, child: table),
        );
      },
    );
  }

  Widget _imageBody() {
    final images = _readImages(paragraph);
    if (images.isEmpty) return _imagePlaceholder('Image preview unavailable');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        for (final img in images)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: _buildImage(img),
          ),
      ],
    );
  }

  Widget _imagePlaceholder(String message) {
    return Container(
      height: 90,
      width: double.infinity,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: const Color(0xFFF3F4F6),
        border: Border.all(color: const Color(0xFFD1D5DB)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.broken_image_outlined, color: Color(0xFF6B7280), size: 20),
          const SizedBox(width: 8),
          Text(message, style: const TextStyle(color: Color(0xFF6B7280), fontSize: 12)),
        ],
      ),
    );
  }

  Widget _buildImage(_ImageSrc img) {
    final width = img.widthPx == null ? null : img.widthPx! * fontScale;
    Widget image;
    if (img.bytes != null) {
      image = Image.memory(
        img.bytes!,
        width: width,
        fit: BoxFit.contain,
        errorBuilder: (_, __, ___) => _imagePlaceholder('Image could not be displayed'),
      );
    } else {
      image = Image.network(
        img.url!,
        width: width,
        fit: BoxFit.contain,
        loadingBuilder: (context, child, progress) {
          if (progress == null) return child;
          return const SizedBox(
            height: 90,
            child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
          );
        },
        errorBuilder: (_, __, ___) => _imagePlaceholder('Image could not be loaded'),
      );
    }
    // Never wider than the page text area.
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: double.infinity),
      child: FittedBox(
        fit: BoxFit.scaleDown,
        alignment: Alignment.center,
        child: image,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final topLevel = paragraph.comments.where((c) => c.parentCommentId == null);
    final unresolved = topLevel.where((c) => !c.isResolved).toList();
    final resolvedTop = topLevel.where((c) => c.isResolved).toList();
    final replies = paragraph.comments.where((c) => c.parentCommentId != null).toList();

    final dynamic d = paragraph;
    final text = _try<String>(() => d.text as String?) ?? '';

    final leftIndent = style.indentLevel * 28.0 + (style.isListItem ? 20.0 : 0.0);

    Widget content;
    switch (style.kind) {
      case _BlockKind.table:
        content = _tableBody();
        break;
      case _BlockKind.image:
        content = _imageBody();
        break;
      case _BlockKind.toc:
        content = _tocBody(text);
        break;
      case _BlockKind.paragraph:
        // A paragraph can also carry inline images (e.g. a picture in a text line).
        final inlineImages = _readImages(paragraph);
        content = inlineImages.isEmpty
            ? _paragraphBody(text)
            : Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (text.trim().isNotEmpty) _paragraphBody(text),
                  _imageBody(),
                ],
              );
        break;
    }

    final hasHighlight = paragraph.highlight == 'unresolved' || paragraph.highlight == 'resolved';

    return Padding(
      padding: EdgeInsets.only(
        top: style.spaceBeforePt * 1.333 * fontScale,
        bottom: style.spaceAfterPt * 1.333 * fontScale,
      ),
      child: InkWell(
        onLongPress: onLongPress,
        borderRadius: BorderRadius.circular(4),
        child: Container(
          width: double.infinity,
          decoration: BoxDecoration(
            color: _highlightColor,
            borderRadius: BorderRadius.circular(4),
            border: paragraph.highlight == 'unresolved'
                ? Border(left: BorderSide(color: AdminColors.warning, width: 3))
                : paragraph.highlight == 'resolved'
                    ? const Border(left: BorderSide(color: Color(0xFF9CA3AF), width: 3))
                    : null,
          ),
          padding: EdgeInsets.fromLTRB(
            leftIndent + (hasHighlight ? 8 : 0),
            hasHighlight ? 4 : 0,
            hasHighlight ? 8 : 0,
            hasHighlight ? 4 : 0,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (showStyleLabel && style.label.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 2),
                  child: Text(
                    '${style.label} · ${style.fontSizePt.toStringAsFixed(style.fontSizePt % 1 == 0 ? 0 : 1)} pt'
                    '${style.bold ? ' · Bold' : ''}${style.italic ? ' · Italic' : ''}'
                    '${style.kind == _BlockKind.table ? ' · Table' : ''}'
                    '${style.kind == _BlockKind.image ? ' · Image' : ''}',
                    style: const TextStyle(
                      fontSize: 10,
                      color: Color(0xFF2563EB),
                      fontWeight: FontWeight.w600,
                      fontFamily: 'Roboto',
                    ),
                  ),
                ),
              content,
              if (unresolved.isNotEmpty || replies.isNotEmpty || resolvedTop.isNotEmpty)
                _CommentNotes(
                  unresolved: unresolved.map((c) => c.commentText as String).toList(),
                  replies: replies.map((c) => c.commentText as String).toList(),
                  resolvedCount: unresolved.isEmpty ? resolvedTop.length : 0,
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Word-style comment notes shown right under the block they belong to.
class _CommentNotes extends StatelessWidget {
  final List<String> unresolved;
  final List<String> replies;
  final int resolvedCount;

  const _CommentNotes({
    required this.unresolved,
    required this.replies,
    required this.resolvedCount,
  });

  @override
  Widget build(BuildContext context) {
    const baseFont = 'Roboto';
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final text in unresolved)
            _note(
              icon: Icons.comment_outlined,
              color: const Color(0xFF92400E),
              bg: const Color(0xFFFFFBEB),
              border: const Color(0xFFF59E0B),
              text: text,
              font: baseFont,
            ),
          for (final text in replies)
            Padding(
              padding: const EdgeInsets.only(left: 18),
              child: _note(
                icon: Icons.reply_rounded,
                color: const Color(0xFF1D4ED8),
                bg: const Color(0xFFEFF6FF),
                border: const Color(0xFF60A5FA),
                text: 'Student: $text',
                font: baseFont,
              ),
            ),
          if (resolvedCount > 0)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Row(
                children: [
                  const Icon(Icons.check_circle_outline, size: 13, color: Color(0xFF4B5563)),
                  const SizedBox(width: 4),
                  Text(
                    '$resolvedCount resolved comment${resolvedCount == 1 ? '' : 's'}',
                    style: const TextStyle(
                      fontSize: 11,
                      color: Color(0xFF4B5563),
                      fontWeight: FontWeight.w600,
                      fontFamily: baseFont,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _note({
    required IconData icon,
    required Color color,
    required Color bg,
    required Color border,
    required String text,
    required String font,
  }) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(6),
        border: Border(left: BorderSide(color: border, width: 3)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              text,
              textAlign: TextAlign.left,
              style: TextStyle(
                fontSize: 12,
                height: 1.35,
                color: color,
                fontWeight: FontWeight.w600,
                fontFamily: font,
                decoration: TextDecoration.none,
                fontStyle: FontStyle.normal,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _LegendChip extends StatelessWidget {
  final Color color;
  final String label;
  final bool bordered;

  const _LegendChip({
    required this.color,
    required this.label,
    this.bordered = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: bordered ? AdminColors.borderStrong : color.withOpacity(0.8)),
      ),
      child: Text(
        label,
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: Color(0xFF1F2937),
        ),
      ),
    );
  }
}