import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class ImageEthicsResult {
  final String imagePath;
  final bool isSafe;
  final String? ethicsCategory;
  final List<String> ethicsWarnings;
  final String caption;
  final bool safeOverride;
  final double relevanceScore;
  final bool relevant;

  ImageEthicsResult({
    required this.imagePath,
    required this.isSafe,
    this.ethicsCategory,
    required this.ethicsWarnings,
    required this.caption,
    required this.safeOverride,
    required this.relevanceScore,
    required this.relevant,
  });

  factory ImageEthicsResult.fromJson(Map<String, dynamic> json) {
    return ImageEthicsResult(
      imagePath: json['image_path'] ?? '',
      isSafe: json['is_safe'] ?? true,
      ethicsCategory: json['ethics_category'],
      ethicsWarnings: List<String>.from(json['ethics_warnings'] ?? []),
      caption: json['ethics_caption'] ?? '',
      safeOverride: json['safe_override'] ?? false,
      relevanceScore: (json['relevance_score'] ?? 0.0).toDouble(),
      relevant: json['relevant'] ?? true,
    );
  }
}

class ImageCheckResponse {
  final int totalImages;
  final List<ImageEthicsResult> flaggedEthics;
  final List<ImageEthicsResult> flaggedRelevance;
  final List<ImageEthicsResult> allResults;

  ImageCheckResponse({
    required this.totalImages,
    required this.flaggedEthics,
    required this.flaggedRelevance,
    required this.allResults,
  });

  factory ImageCheckResponse.fromJson(Map<String, dynamic> json) {
    return ImageCheckResponse(
      totalImages: json['total_images'] ?? 0,
      flaggedEthics: (json['flagged_ethics'] as List)
          .map((e) => ImageEthicsResult.fromJson(e))
          .toList(),
      flaggedRelevance: (json['flagged_relevance'] as List)
          .map((e) => ImageEthicsResult.fromJson(e))
          .toList(),
      allResults: (json['all_results'] as List)
          .map((e) => ImageEthicsResult.fromJson(e))
          .toList(),
    );
  }
}

class ImageEthicsProvider extends ChangeNotifier {
  ImageCheckResponse? _result;
  bool _isLoading = false;
  String? _error;

  ImageCheckResponse? get result => _result;
  bool get isLoading => _isLoading;
  String? get error => _error;

  // Flagged ethics — shown as errors on analysis screen
  List<ImageEthicsResult> get flaggedEthics => _result?.flaggedEthics ?? [];

  // Flagged relevance — separate section
  List<ImageEthicsResult> get flaggedRelevance =>
      _result?.flaggedRelevance ?? [];

  // ✅ ALL results — used by analyze_screen to match ethics status per image
  List<ImageEthicsResult> get allResults => _result?.allResults ?? [];

  // True if any unethical image exists — disables Format button
  bool get hasUnethicalImages => flaggedEthics.isNotEmpty;

  // ✅ Call with document_id — backend fetches the file itself
  Future<void> checkImagesByDocumentId(
    int documentId,
    String baseUrl,
    String userId,
  ) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final uri = Uri.parse(
        'http://172.20.10.2:8000/check-images-by-id?document_id=$documentId&user_id=$userId',
      );
      final response = await http.post(uri);
      final body = response.body;

      if (response.statusCode == 200) {
        final json = jsonDecode(body);
        _result = ImageCheckResponse.fromJson(json);
      } else {
        _error = 'Server error: ${response.statusCode}';
        debugPrint('Ethics error body: $body');
      }
    } catch (e) {
      _error = 'Connection error: $e';
      debugPrint('Ethics exception: $e');
    }

    _isLoading = false;
    notifyListeners();
  }

  // Original method kept for direct file path usage
  Future<void> checkImages(String docxFilePath) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final uri = Uri.parse('http://172.20.10.2:8000/check-images');
      final request = http.MultipartRequest('POST', uri);

      request.files.add(
        await http.MultipartFile.fromPath('file', docxFilePath),
      );

      final response = await request.send();
      final body = await response.stream.bytesToString();

      if (response.statusCode == 200) {
        final json = jsonDecode(body);
        _result = ImageCheckResponse.fromJson(json);
      } else {
        _error = 'Server error: ${response.statusCode}';
      }
    } catch (e) {
      _error = 'Connection error: $e';
    }

    _isLoading = false;
    notifyListeners();
  }

  void reset() {
    _result = null;
    _error = null;
    _isLoading = false;
    notifyListeners();
  }
}
