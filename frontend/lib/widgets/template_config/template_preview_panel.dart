// lib/widgets/template_config/template_preview_panel.dart
import 'package:flutter/material.dart';
import '../../models/template_preview_data.dart';

import '../tr.dart';
/// Live, Word-like preview of the template being configured.
/// Pure presentation: give it a [TemplatePreviewData] and it renders a paper
/// page (true A4/Letter proportions) using the admin's current settings.
class TemplatePreviewPanel extends StatefulWidget {
  const TemplatePreviewPanel({
    super.key,
    required this.data,
    this.onOpenWordPreview,
  });

  final TemplatePreviewData data;

  /// Optional: shows an "Exact Word preview" button that opens the
  /// server-rendered sample document.
  final VoidCallback? onOpenWordPreview;

  @override
  State<TemplatePreviewPanel> createState() => _TemplatePreviewPanelState();
}

class _TemplatePreviewPanelState extends State<TemplatePreviewPanel> {
  static const _bg = Color(0xFF161B22);
  static const _border = Color(0xFF30363D);
  double _zoom = 1.0;

  void _setZoom(double v) => setState(() => _zoom = v.clamp(0.6, 1.6));

  @override
  Widget build(BuildContext context) {
    final page = widget.data.pageSizePt;
    return Container(
      color: _bg,
      child: Column(
        children: [
          _buildToolbar(),
          const Divider(height: 1, color: _border),
          Expanded(
            child: LayoutBuilder(
              builder: (context, c) {
                final fit = (c.maxWidth - 32).clamp(240.0, 4000.0);
                final paperWidth = fit * _zoom;
                return SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: SizedBox(
                      width: paperWidth,
                      child: FittedBox(
                        fit: BoxFit.fitWidth,
                        alignment: Alignment.topCenter,
                        // Repaint only the paper when the form changes.
                        child: RepaintBoundary(
                          child: SizedBox(
                            width: page.width,
                            child: _Paper(data: widget.data),
                          ),
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          const Divider(height: 1, color: _border),
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Tr('Approximate preview - the generated .docx may differ slightly.',
              style: TextStyle(fontSize: 10.5, color: Color(0xFF8B949E)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildToolbar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: [
          const Icon(Icons.visibility_outlined,
              size: 18, color: Color(0xFF6366F1)),
          const SizedBox(width: 8),
          const Expanded(
            child: Tr('Live Preview',
              style: TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w700),
            ),
          ),
          IconButton(
            tooltip: 'Zoom out',
            visualDensity: VisualDensity.compact,
            icon: const Icon(Icons.remove, size: 18, color: Colors.white70),
            onPressed: () => _setZoom(_zoom - 0.2),
          ),
          Text('${(_zoom * 100).round()}%',
              style: const TextStyle(color: Colors.white70, fontSize: 12)),
          IconButton(
            tooltip: 'Zoom in',
            visualDensity: VisualDensity.compact,
            icon: const Icon(Icons.add, size: 18, color: Colors.white70),
            onPressed: () => _setZoom(_zoom + 0.2),
          ),
          if (widget.onOpenWordPreview != null) ...[
            const SizedBox(width: 4),
            Tooltip(
              message: 'Generate the exact sample document from the server',
              child: OutlinedButton.icon(
                onPressed: widget.onOpenWordPreview,
                icon: const Icon(Icons.description_outlined, size: 16),
                label: const Tr('Word preview'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFF6366F1),
                  side: const BorderSide(color: Color(0xFF6366F1)),
                  visualDensity: VisualDensity.compact,
                  textStyle: const TextStyle(fontSize: 12),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// The paper
// ─────────────────────────────────────────────────────────────────────────────

class _Paper extends StatelessWidget {
  const _Paper({required this.data});
  final TemplatePreviewData data;

  static const _fallbackFonts = [
    'Times New Roman',
    'Liberation Serif',
    'Times',
    'Georgia',
    'serif',
  ];

  static const _loremA =
      'This is a sample paragraph that shows how body text will look in the '
      'final document. It uses the configured font, size, line spacing, '
      'alignment and first-line indent, so the administrator can judge '
      'readability before publishing the template.';
  static const _loremB =
      'A second paragraph follows to show paragraph spacing. Citations such '
      'as (Author, 2024) and cross references such as Table 1 and Figure 1 '
      'appear in running text exactly like this.';

  // ── style helpers ──────────────────────────────────────────────────────────

  TextStyle _style(
    double size, {
    bool bold = false,
    bool italic = false,
    double? height,
    String? font,
  }) {
    return TextStyle(
      fontFamily: font ?? data.fontFamily,
      fontFamilyFallback: _fallbackFonts,
      fontSize: size,
      fontWeight: bold ? FontWeight.w700 : FontWeight.w400,
      fontStyle: italic ? FontStyle.italic : FontStyle.normal,
      color: Colors.black,
      decoration: TextDecoration.none,
      // Word "single" spacing is ~1.15 x font size for common serif fonts.
      height: height ?? data.lineSpacing * 1.15,
    );
  }

  TextAlign _align(String a) {
    switch (a.toLowerCase()) {
      case 'center':
        return TextAlign.center;
      case 'right':
        return TextAlign.right;
      case 'justify':
      case 'justified':
        return TextAlign.justify;
      default:
        return TextAlign.left;
    }
  }

  String _transform(String s, String t) {
    switch (t.toLowerCase()) {
      case 'uppercase':
        return s.toUpperCase();
      case 'lowercase':
        return s.toLowerCase();
      case 'capitalize':
      case 'title case':
        return s
            .split(' ')
            .map((w) => w.isEmpty ? w : w[0].toUpperCase() + w.substring(1))
            .join(' ');
      default:
        return s;
    }
  }

  // ── numbering helpers ──────────────────────────────────────────────────────

  String _headingPrefix(int level) {
    switch (data.headingNumbering) {
      case 'decimal':
        return const ['1', '1.1', '1.1.1', '1.1.1.1'][level - 1];
      case 'roman':
        return const ['I.', 'A.', '1.', 'a.'][level - 1];
      case 'alpha':
        return const ['A.', '1.', 'a.', 'i.'][level - 1];
      default:
        return '';
    }
  }

  String _bulletChar() {
    final s = data.bulletStyle.toLowerCase();
    if (s.contains('hollow') || s.contains('open')) return '\u25E6';
    if (s.contains('square')) return '\u25AA';
    if (s.contains('dash')) return '\u2013';
    if (s.contains('arrow')) return '\u27A4';
    if (s.contains('check')) return '\u2713';
    return '\u2022';
  }

  static String _roman(int n) {
    const v = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1];
    const s = [
      'M', 'CM', 'D', 'CD', 'C', 'XC', 'L', 'XL', 'X', 'IX', 'V', 'IV', 'I'
    ];
    var out = '';
    for (var i = 0; i < v.length; i++) {
      while (n >= v[i]) {
        out += s[i];
        n -= v[i];
      }
    }
    return out;
  }

  String _numberLabel(int n) {
    final f = data.numberingFormat;
    if (f.contains('I, II')) return '${_roman(n)}.';
    if (f.contains('i, ii')) return '${_roman(n).toLowerCase()}.';
    if (f.contains('A, B')) return '${String.fromCharCode(64 + n)}.';
    if (f.contains('a, b')) return '${String.fromCharCode(96 + n)}.';
    return '$n.';
  }

  String _caption(String pattern, String desc, bool chapter) {
    return pattern
        .replaceAll('{n}', chapter ? '1.1' : '1')
        .replaceAll('{description}', desc)
        .replaceAll('{caption}', desc);
  }

  // ── building blocks ────────────────────────────────────────────────────────

  Widget _heading(int level, String text) {
    final h = data.headings[level - 1];
    final prefix = _headingPrefix(level);
    final label = _transform(text, h.transform);
    return Padding(
      padding: EdgeInsets.only(top: h.spaceBefore, bottom: h.spaceAfter),
      child: SizedBox(
        width: double.infinity,
        child: Text(
          prefix.isEmpty ? label : '$prefix  $label',
          textAlign: _align(h.alignment),
          style: _style(h.size, bold: h.bold, italic: h.italic, height: 1.25),
        ),
      ),
    );
  }

  Widget _paragraph(String text) {
    final indent = (data.firstLineIndentIn * 72).clamp(0.0, 200.0);
    return Padding(
      padding: EdgeInsets.only(top: data.paraBefore, bottom: data.paraAfter),
      child: SizedBox(
        width: double.infinity,
        child: Text.rich(
          TextSpan(children: [
            if (indent > 0)
              WidgetSpan(
                alignment: PlaceholderAlignment.baseline,
                baseline: TextBaseline.alphabetic,
                child: SizedBox(width: indent, height: 1),
              ),
            TextSpan(text: text),
          ]),
          textAlign: data.justify ? TextAlign.justify : TextAlign.left,
          style: _style(data.bodySize),
        ),
      ),
    );
  }

  Widget _listItem(String marker, String text) {
    final indent = (data.bulletIndentIn * 72).clamp(0.0, 200.0);
    return Padding(
      padding: EdgeInsets.only(left: indent),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 22,
            child: Text(marker, style: _style(data.bodySize)),
          ),
          Expanded(child: Text(text, style: _style(data.bodySize))),
        ],
      ),
    );
  }

  Widget _tocRow(String name, int page) {
    final s = _style(data.bodySize, height: 1.5);
    return Row(
      children: [
        Text(name, style: s),
        Expanded(
          child: ClipRect(
            child: Text(
              ' ${'.' * 200}',
              maxLines: 1,
              softWrap: false,
              overflow: TextOverflow.clip,
              style: s,
            ),
          ),
        ),
        Text(' $page', style: s),
      ],
    );
  }

  Widget _captionWidget(String text, double size, {String? font}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: SizedBox(
        width: double.infinity,
        child: Text(
          text,
          textAlign: TextAlign.center,
          style: _style(size, height: 1.2, font: font),
        ),
      ),
    );
  }

  Widget _sampleTable() {
    final t = data.table;
    const headers = ['Variable', 'Mean', 'SD', 'p-value'];
    const rows = [
      ['Age (years)', '24.3', '3.1', '0.021'],
      ['Test score', '78.5', '10.4', '0.003'],
      ['Study hours', '5.2', '1.8', '0.147'],
    ];

    final bw = (t.borderSize / 8).clamp(0.25, 6.0);
    final side = BorderSide(color: t.borderColor, width: bw);
    final doubleSide = BorderSide(color: t.borderColor, width: bw * 2);
    final style = t.borderStyle.toLowerCase();
    final academic = style.startsWith('academic');

    TableBorder border;
    if (!t.borders || style == 'none') {
      border = const TableBorder();
    } else if (style.startsWith('double')) {
      border = TableBorder.all(color: t.borderColor, width: bw * 2);
    } else if (academic) {
      border = TableBorder(top: doubleSide.copyWith(width: bw), bottom: side);
    } else {
      border = TableBorder.all(color: t.borderColor, width: bw);
    }

    final pad = EdgeInsets.fromLTRB(
        t.padLeft / 20, t.padTop / 20, t.padRight / 20, t.padBottom / 20);

    Widget cell(String text, {required bool header, required int col, required int row}) {
      final align = header
          ? _align(t.headerAlign)
          : _align(col == 0 ? t.textAlign : t.numericAlign);
      return Container(
        constraints: BoxConstraints(minHeight: t.fixedRowHeight ? 22 : 0),
        padding: pad,
        alignment: align == TextAlign.center
            ? Alignment.center
            : align == TextAlign.right
                ? Alignment.centerRight
                : Alignment.centerLeft,
        child: Text(
          text,
          textAlign: align,
          style: _style(t.fontSize,
              bold: header && t.headerBold, height: 1.15, font: t.fontName),
        ),
      );
    }

    final tableRows = <TableRow>[
      TableRow(
        decoration: BoxDecoration(
          color: t.headerShading ? t.headerBg : null,
          border: (academic && t.borders)
              ? Border(bottom: side)
              : null,
        ),
        children: [
          for (var c = 0; c < headers.length; c++)
            cell(headers[c], header: true, col: c, row: 0),
        ],
      ),
      for (var r = 0; r < rows.length; r++)
        TableRow(
          decoration: BoxDecoration(
            color: (t.bandedRows && r.isOdd) ? t.bandColor : null,
          ),
          children: [
            for (var c = 0; c < rows[r].length; c++)
              cell(rows[r][c], header: false, col: c, row: r + 1),
          ],
        ),
    ];

    final table = Align(
      alignment: t.alignmentOnPage == 'left'
          ? Alignment.centerLeft
          : Alignment.center,
      child: FractionallySizedBox(
        widthFactor: (t.maxWidthPercent / 100).clamp(0.3, 1.0),
        child: Table(
          border: border,
          defaultVerticalAlignment: TableCellVerticalAlignment.middle,
          columnWidths: const {0: FlexColumnWidth(2)},
          children: tableRows,
        ),
      ),
    );

    final caption = _captionWidget(
      _caption(t.captionPattern, 'Descriptive statistics of the sample',
          t.chapterNumbering),
      data.bodySize - 1,
    );

    return Padding(
      padding: EdgeInsets.only(top: t.spaceBefore, bottom: t.spaceAfter),
      child: Column(
        children: [
          if (t.captionAbove) caption,
          table,
          if (!t.captionAbove) caption,
        ],
      ),
    );
  }

  Widget _sampleFigure() {
    final caption = _captionWidget(
      _caption(data.imageCaptionPattern, 'Conceptual framework of the study',
          data.imageChapterNumbering),
      data.bodySize - 1,
    );
    final box = Align(
      alignment: Alignment.center,
      child: FractionallySizedBox(
        widthFactor: (data.imageMaxWidthPercent / 100).clamp(0.2, 1.0),
        child: Container(
          height: 110,
          decoration: BoxDecoration(
            color: const Color(0xFFF1F3F5),
            border: Border.all(color: const Color(0xFFCED4DA)),
          ),
          child: const Center(
            child: Icon(Icons.image_outlined,
                size: 36, color: Color(0xFFADB5BD)),
          ),
        ),
      ),
    );
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        children: [
          if (data.imageCaptionAbove) caption,
          box,
          if (!data.imageCaptionAbove) caption,
        ],
      ),
    );
  }

  // ── build ──────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final page = data.pageSizePt;
    // Keep at least ~40% of the page width for text, whatever the admin types.
    final maxSide = page.width * 0.3;
    final ml = data.marginLeft.clamp(0.0, maxSide);
    final mr = data.marginRight.clamp(0.0, maxSide);
    final mt = data.marginTop.clamp(0.0, page.height * 0.25);
    final mb = data.marginBottom.clamp(0.0, page.height * 0.25);

    final sections = data.requiredSections
        .where((s) => s.trim().isNotEmpty)
        .take(12)
        .toList();

    return MediaQuery(
      // The paper must not scale with the OS accessibility font size.
      data: MediaQuery.of(context).copyWith(textScaler: TextScaler.noScaling),
      child: DefaultTextStyle(
        style: _style(data.bodySize),
        child: Container(
          constraints: BoxConstraints(minHeight: page.height),
          decoration: const BoxDecoration(
            color: Colors.white,
            boxShadow: [
              BoxShadow(
                  color: Color(0x66000000), blurRadius: 18, offset: Offset(0, 6))
            ],
          ),
          child: Stack(
            children: [
              Padding(
                padding: EdgeInsets.fromLTRB(ml, mt, mr, mb),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (sections.isNotEmpty) ...[
                      SizedBox(
                        width: double.infinity,
                        child: Tr('TABLE OF CONTENTS',
                          textAlign: TextAlign.center,
                          style: _style(data.bodySize + 1,
                              bold: true, height: 1.6),
                        ),
                      ),
                      for (var i = 0; i < sections.length; i++)
                        _tocRow(sections[i], i + 1),
                      const SizedBox(height: 18),
                    ],
                    _heading(1, 'Introduction'),
                    _paragraph(_loremA),
                    _paragraph(_loremB),
                    _heading(2, 'Background of the Study'),
                    _paragraph(_loremA),
                    _heading(3, 'Research Objectives'),
                    _listItem(_bulletChar(), 'To examine the main factors.'),
                    _listItem(_bulletChar(), 'To compare the observed groups.'),
                    _listItem(_bulletChar(), 'To recommend practical actions.'),
                    _heading(4, 'Scope and Delimitations'),
                    _listItem(_numberLabel(1), 'First numbered item.'),
                    _listItem(_numberLabel(2), 'Second numbered item.'),
                    _listItem(_numberLabel(3), 'Third numbered item.'),
                    _heading(2, 'Results'),
                    _paragraph(
                        'Table 1 summarises the sample, and Figure 1 shows the framework.'),
                    _sampleTable(),
                    _sampleFigure(),
                  ],
                ),
              ),
              // Dashed-looking margin guide so margins are visible at a glance.
              Positioned.fill(
                child: IgnorePointer(
                  child: CustomPaint(
                    painter: _MarginGuidePainter(
                      EdgeInsets.fromLTRB(ml, mt, mr, mb),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MarginGuidePainter extends CustomPainter {
  _MarginGuidePainter(this.margins);
  final EdgeInsets margins;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Rect.fromLTRB(
      margins.left,
      margins.top,
      size.width - margins.right,
      size.height - margins.bottom,
    );
    final p = Paint()
      ..color = const Color(0x336366F1)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.6;
    canvas.drawRect(rect, p);
  }

  @override
  bool shouldRepaint(covariant _MarginGuidePainter old) =>
      old.margins != margins;
}