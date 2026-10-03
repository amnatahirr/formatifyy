// lib/models/template_preview_data.dart
import 'package:flutter/material.dart';
import '../utils/unit_utils.dart';

/// Resolved (already parsed + clamped) style of one heading level.
/// Spacing values are in points.
class HeadingPreviewStyle {
  const HeadingPreviewStyle({
    required this.size,
    required this.bold,
    required this.italic,
    required this.alignment,
    required this.transform,
    required this.spaceBefore,
    required this.spaceAfter,
  });

  final double size;
  final bool bold;
  final bool italic;
  final String alignment; // Left | Center | Right | Justify
  final String transform; // UPPERCASE | lowercase | Capitalize | None/Normal
  final double spaceBefore;
  final double spaceAfter;
}

/// Resolved table style. Padding is in twips (1/20 pt), border size in
/// eighths of a point - the same units Word/OOXML uses.
class TablePreviewStyle {
  const TablePreviewStyle({
    required this.fontName,
    required this.fontSize,
    required this.headerBold,
    required this.headerShading,
    required this.headerBg,
    required this.headerAlign,
    required this.numericAlign,
    required this.textAlign,
    required this.bandedRows,
    required this.bandColor,
    required this.borders,
    required this.borderColor,
    required this.borderSize,
    required this.borderStyle,
    required this.padTop,
    required this.padBottom,
    required this.padLeft,
    required this.padRight,
    required this.alignmentOnPage,
    required this.maxWidthPercent,
    required this.fixedRowHeight,
    required this.spaceBefore,
    required this.spaceAfter,
    required this.captionPattern,
    required this.captionAbove,
    required this.chapterNumbering,
  });

  final String fontName;
  final double fontSize;
  final bool headerBold;
  final bool headerShading;
  final Color headerBg;
  final String headerAlign; // left | center | right
  final String numericAlign;
  final String textAlign;
  final bool bandedRows;
  final Color bandColor;
  final bool borders;
  final Color borderColor;
  final double borderSize;
  final String borderStyle; // None | Single line | Double line | Academic standard
  final double padTop;
  final double padBottom;
  final double padLeft;
  final double padRight;
  final String alignmentOnPage; // left | center
  final double maxWidthPercent;
  final bool fixedRowHeight;
  final double spaceBefore;
  final double spaceAfter;
  final String captionPattern;
  final bool captionAbove;
  final bool chapterNumbering;
}

/// Everything the preview needs - a plain immutable snapshot of the form.
/// The screen builds it via `_buildPreviewData()`; the panel never touches
/// controllers or providers, so it is trivial to test and reuse.
class TemplatePreviewData {
  const TemplatePreviewData({
    required this.name,
    required this.pageSize,
    required this.marginTop,
    required this.marginBottom,
    required this.marginLeft,
    required this.marginRight,
    required this.fontFamily,
    required this.bodySize,
    required this.lineSpacing,
    required this.firstLineIndentIn,
    required this.bulletIndentIn,
    required this.paraBefore,
    required this.paraAfter,
    required this.justify,
    required this.bulletStyle,
    required this.numberingFormat,
    required this.headingNumbering,
    required this.headings,
    required this.table,
    required this.imageCaptionPattern,
    required this.imageCaptionAbove,
    required this.imageMaxWidthPercent,
    required this.imageChapterNumbering,
    required this.requiredSections,
  });

  final String name;
  final String pageSize;

  /// Margins in points.
  final double marginTop;
  final double marginBottom;
  final double marginLeft;
  final double marginRight;

  final String fontFamily;
  final double bodySize;
  final double lineSpacing; // multiplier (1.0 = single)
  final double firstLineIndentIn; // inches
  final double bulletIndentIn; // inches
  final double paraBefore; // pt
  final double paraAfter; // pt
  final bool justify;

  final String bulletStyle; // display label, e.g. "Filled Circle"
  final String numberingFormat; // display label, e.g. "1, 2, 3 (Arabic)"
  final String headingNumbering; // none | decimal | roman | alpha

  /// Exactly four entries: Heading 1..4.
  final List<HeadingPreviewStyle> headings;
  final TablePreviewStyle table;

  final String imageCaptionPattern;
  final bool imageCaptionAbove;
  final double imageMaxWidthPercent;
  final bool imageChapterNumbering;

  final List<String> requiredSections;

  Size get pageSizePt => UnitUtils.pageSizePt(pageSize);
}