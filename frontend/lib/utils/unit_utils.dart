// lib/utils/unit_utils.dart
import 'package:flutter/material.dart';

/// Small, dependency-free helpers used by the live template preview.
/// Everything here is defensive: bad admin input must never crash the UI.
class UnitUtils {
  UnitUtils._();

  static const double ptPerMm = 72 / 25.4;

  /// Converts [value] expressed in [unit] (mm, cm, in, pt) to PDF points.
  static double toPoints(double value, String unit) {
    switch (unit.toLowerCase().trim()) {
      case 'mm':
        return value * ptPerMm;
      case 'cm':
        return value * ptPerMm * 10;
      case 'in':
      case 'inch':
      case 'inches':
        return value * 72;
      case 'pt':
      default:
        return value;
    }
  }

  /// Parses [s] to a double, falling back to [def] and clamping to [min]/[max].
  static double parse(String s, double def, {double? min, double? max}) {
    var v = double.tryParse(s.trim().replaceAll(',', '.')) ?? def;
    if (v.isNaN || v.isInfinite) v = def;
    if (min != null && v < min) v = min;
    if (max != null && v > max) v = max;
    return v;
  }

  /// Parses "FFAA00", "#FFAA00" or "FA0" into a Color, or returns [fallback].
  static Color parseHex(String s, Color fallback) {
    var h = s.replaceAll('#', '').trim();
    if (h.length == 3) h = h.split('').map((c) => '$c$c').join();
    if (h.length != 6) return fallback;
    final v = int.tryParse(h, radix: 16);
    return v == null ? fallback : Color(0xFF000000 | v);
  }

  /// Page size in points (portrait).
  static Size pageSizePt(String name) {
    switch (name.toUpperCase().trim()) {
      case 'LETTER':
        return const Size(612, 792);
      case 'LEGAL':
        return const Size(612, 1008);
      case 'A5':
        return const Size(419.53, 595.28);
      case 'A4':
      default:
        return const Size(595.28, 841.89);
    }
  }
}