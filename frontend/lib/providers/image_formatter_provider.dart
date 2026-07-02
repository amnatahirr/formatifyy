// lib/providers/image_formatter_provider.dart
//
// Drop into:  frontend/lib/providers/image_formatter_provider.dart
//
// Provides state management for the FYP Image Formatter feature.
// Call formatDocumentImages() from any screen; observe state via
// ChangeNotifier listeners.
//
// Registration (lib/main.dart):
//   ChangeNotifierProvider(create: (_) => ImageFormatterProvider()),

import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import '../config/api_config.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Data models
// ─────────────────────────────────────────────────────────────────────────────

class ImageFormatResult {
  final int     figNum;
  final String? rId;
  final double  origWidthIn;
  final double  origHeightIn;
  final double  dispWidthIn;
  final double  dispHeightIn;
  final bool    resized;
  final String  caption;

  const ImageFormatResult({
    required this.figNum,
    this.rId,
    required this.origWidthIn,
    required this.origHeightIn,
    required this.dispWidthIn,
    required this.dispHeightIn,
    required this.resized,
    required this.caption,
  });

  factory ImageFormatResult.fromJson(Map<String, dynamic> j) =>
      ImageFormatResult(
        figNum:       (j['fig_num']    as num).toInt(),
        rId:           j['rId']        as String?,
        origWidthIn:  (j['orig_w_in']  as num).toDouble(),
        origHeightIn: (j['orig_h_in']  as num).toDouble(),
        dispWidthIn:  (j['disp_w_in']  as num).toDouble(),
        dispHeightIn: (j['disp_h_in']  as num).toDouble(),
        resized:       j['resized']    as bool,
        caption:       j['caption']    as String,
      );
}

class FormatterSummary {
  final int                    documentId;
  final String                 status;           // success | no_images
  final String                 message;
  final String?                downloadUrl;
  final String?                outputFilename;
  final int                    totalImages;
  final int                    captionsAdded;
  final bool                   tofAdded;
  final List<ImageFormatResult> images;
  final List<String>           manualItems;
  final List<String>           manualSteps;

  const FormatterSummary({
    required this.documentId,
    required this.status,
    required this.message,
    this.downloadUrl,
    this.outputFilename,
    required this.totalImages,
    required this.captionsAdded,
    required this.tofAdded,
    required this.images,
    required this.manualItems,
    required this.manualSteps,
  });

  factory FormatterSummary.fromJson(Map<String, dynamic> j, int docId) =>
      FormatterSummary(
        documentId:    docId,
        status:        j['status']          as String,
        message:       j['message']         as String,
        downloadUrl:   j['download_url']    as String?,
        outputFilename: j['output_filename'] as String?,
        totalImages:   (j['total_images']   as num).toInt(),
        captionsAdded: (j['captions_added'] as num).toInt(),
        tofAdded:      j['tof_added']       as bool,
        images: (j['images'] as List<dynamic>)
            .map((e) => ImageFormatResult.fromJson(e as Map<String, dynamic>))
            .toList(),
        manualItems: List<String>.from(j['manual_items'] ?? []),
        manualSteps: List<String>.from(j['manual_steps'] ?? []),
      );
}

// ─────────────────────────────────────────────────────────────────────────────
// Provider
// ─────────────────────────────────────────────────────────────────────────────

class ImageFormatterProvider extends ChangeNotifier {
  final String _base = ApiConfig.getBaseUrl();

  bool              _loading     = false;
  bool              _downloading = false;
  FormatterSummary? _summary;
  String?           _error;
  String?           _savedPath;   // local path of last downloaded file

  bool              get isLoading     => _loading;
  bool              get isDownloading => _downloading;
  FormatterSummary? get summary       => _summary;
  String?           get error         => _error;
  String?           get savedPath     => _savedPath;
  bool              get hasResult     => _summary != null;

  // ── Format ─────────────────────────────────────────────────────────────────

  Future<void> formatDocumentImages({
    required int documentId,
    required int userId,
  }) async {
    _loading = true;
    _error   = null;
    _summary = null;
    notifyListeners();

    try {
      final uri = Uri.parse(
        '$_base/format-images/$documentId?user_id=$userId',
      );

      final resp = await http.post(uri).timeout(
        const Duration(minutes: 3),   // BLIP caption generation can be slow
      );

      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        _summary = FormatterSummary.fromJson(data, documentId);
      } else {
        final body = jsonDecode(resp.body) as Map<String, dynamic>? ?? {};
        _error = body['detail'] as String? ?? 'Formatting failed (${resp.statusCode})';
      }
    } catch (e) {
      _error = 'Network error: $e';
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  // ── Download formatted file ──────────────────────────────────────────────────
  // Uses the same http.get → writeAsBytes pattern as DocumentProvider.
  // Saves to the device Downloads folder and returns the local file path.

  Future<String?> downloadFormattedFile({
    required int documentId,
    required int userId,
  }) async {
    final fn = _summary?.outputFilename;
    if (fn == null) {
      _error = 'No formatted file available. Run formatting first.';
      notifyListeners();
      return null;
    }

    _downloading = true;
    _error       = null;
    notifyListeners();

    try {
      final url = Uri.parse(
        '$_base/format-images/download/$documentId'
        '?user_id=$userId&file=${Uri.encodeComponent(fn)}',
      );

      final response = await http.get(url).timeout(
        const Duration(minutes: 2),
      );

      if (response.statusCode == 200) {
        // Determine filename from Content-Disposition header or fall back to fn
        String fileName = fn;
        final cd = response.headers['content-disposition'];
        if (cd != null && cd.contains('filename=')) {
          fileName = cd.split('filename=').last.replaceAll('"', '').trim();
        }

        // Save to Downloads (or Documents on iOS / platforms without Downloads)
        final dir = await getDownloadsDirectory() ??
                    await getApplicationDocumentsDirectory();
        final file = File('${dir.path}/$fileName');
        await file.writeAsBytes(response.bodyBytes);

        _savedPath   = file.path;
        _downloading = false;
        notifyListeners();
        return file.path;
      } else {
        _error       = 'Download failed (${response.statusCode}): ${response.body}';
        _downloading = false;
        notifyListeners();
        return null;
      }
    } catch (e) {
      _error       = 'Download error: $e';
      _downloading = false;
      notifyListeners();
      return null;
    }
  }

  // ── Legacy helper kept for backward-compatibility ─────────────────────────

  Future<String?> buildDownloadUrl(int documentId, int userId) async {
    final fn = _summary?.outputFilename;
    if (fn == null) return null;
    return '$_base/format-images/download/$documentId'
        '?user_id=$userId&file=\${Uri.encodeComponent(fn)}';
  }

  void reset() {
    _loading = false;
    _summary = null;
    _error   = null;
    notifyListeners();
  }
}