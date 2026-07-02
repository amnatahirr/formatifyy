import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import '../config/api_config.dart';

class DocumentProvider extends ChangeNotifier {
  late final String baseUrl;
  late final String exportUrl;

  DocumentProvider() {
    final apiBase = ApiConfig.getBaseUrl();
    baseUrl = '$apiBase/documents';
    // apiBase already ends with /api
    exportUrl = '$apiBase/format-document/export';
    debugPrint('[v0] ApiConfig.baseUrl=${ApiConfig.baseUrl}');
    debugPrint('[v0] ApiConfig.getBaseUrl()=$apiBase');
    debugPrint('[v0] DocumentProvider.exportUrl=$exportUrl');
  }

  List<Map<String, dynamic>> _documents = [];
  bool _isLoading = false;
  String? _errorMessage;
  final Set<int> _reAnalyzingIds = {};

  List<Map<String, dynamic>> get documents => _documents;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool isReAnalyzing(int documentId) => _reAnalyzingIds.contains(documentId);

  Future<void> fetchDocuments(int userId) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await http.get(Uri.parse("$baseUrl/?user_id=$userId"));

      if (response.statusCode == 200) {
        _documents = List<Map<String, dynamic>>.from(
          json.decode(response.body),
        );
        debugPrint(
          "[v0] Fetched ${_documents.length} documents for user $userId",
        );
      } else {
        _errorMessage = "Failed to fetch documents";
        debugPrint("[v0] Fetch failed: ${response.body}");
      }
    } catch (e) {
      _errorMessage = "Network error: $e";
      debugPrint("[v0] Fetch error: $e");
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> reAnalyzeDocument(int documentId, int userId) async {
    if (_reAnalyzingIds.contains(documentId)) return false;
    _reAnalyzingIds.add(documentId);
    notifyListeners();
    try {
      final url = Uri.parse('$baseUrl/analyze/$documentId?user_id=$userId');
      final resp = await http.get(url);
      if (resp.statusCode == 200) {
        await fetchDocuments(userId);
        return true;
      }
      _errorMessage = 'Re-analysis failed: ${resp.body}';
      return false;
    } catch (e) {
      _errorMessage = 'Re-analysis error: $e';
      return false;
    } finally {
      _reAnalyzingIds.remove(documentId);
      notifyListeners();
    }
  }

  Future<bool> uploadDocument(File file, int templateId, int userId) async {
    try {
      var request = http.MultipartRequest(
        "POST",
        Uri.parse("$baseUrl/upload?template_id=$templateId&user_id=$userId"),
      );

      request.files.add(await http.MultipartFile.fromPath("file", file.path));
      var response = await request.send();
      final responseBody = await response.stream.bytesToString();

      if (response.statusCode == 200) {
        await fetchDocuments(userId); // refresh list
        return true;
      } else {
        _errorMessage = "Upload failed: $responseBody";
        debugPrint(
          "[v0] Upload failed with status ${response.statusCode}: $responseBody",
        );
        return false;
      }
    } catch (e) {
      _errorMessage = "Upload error: $e";
      debugPrint("[v0] Upload error: $e");
      return false;
    }
  }

  Future<bool> uploadPastedContent(
    String content,
    int templateId,
    int userId,
  ) async {
    try {
      final response = await http.post(
        Uri.parse(
          "$baseUrl/upload-text?template_id=$templateId&user_id=$userId",
        ),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"content": content}),
      );

      if (response.statusCode == 200) {
        await fetchDocuments(userId); // refresh list
        return true;
      } else {
        _errorMessage = "Upload failed: ${response.body}";
        debugPrint(
          "[v0] Upload failed with status ${response.statusCode}: ${response.body}",
        );
        return false;
      }
    } catch (e) {
      _errorMessage = "Upload error: $e";
      debugPrint("[v0] Upload error: $e");
      return false;
    }
  }

  Future<Map<String, dynamic>?> getPreview(int documentId, int userId) async {
    try {
      final url = Uri.parse(
        "${ApiConfig.getBaseUrl()}/format-document/from-document/$documentId?user_id=$userId",
      );
      debugPrint('[v0] Preview fetch URL: $url');
      final response = await http.get(url);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final elements = List<Map<String, dynamic>>.from(
          data['formatted_elements'] ?? const [],
        );
        return {
          'document_id': documentId,
          'formatted_content': elements.map((e) => e['text']).join('\n'),
          'formatted_lines': elements
              .map(
                (e) => {
                  'text': e['text'],
                  'type': e['type'] ?? 'paragraph',
                },
              )
              .toList(),
          'formatting_rules': {},
          'summary': data['summary'],
        };
      } else {
        _errorMessage = "Preview not available";
        debugPrint("[v0] Preview fetch failed: ${response.body}");
        return null;
      }
    } catch (e) {
      _errorMessage = "Preview error: $e";
      debugPrint("[v0] Preview error: $e");
      return null;
    }
  }

  Future<List<Map<String, dynamic>>> listGoogleDriveFiles(int userId) async {
    try {
      final url = '${ApiConfig.getBaseUrl()}/uploads/google-drive/files?user_id=$userId';
      final response = await http.get(Uri.parse(url));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final files = List<Map<String, dynamic>>.from(data['files'] ?? []);
        return files;
      } else {
        _errorMessage = "Failed to fetch Google Drive files";
        return [];
      }
    } catch (e) {
      _errorMessage = "Error fetching Google Drive files: $e";
      debugPrint("[v0] Google Drive fetch error: $e");
      return [];
    }
  }

  Future<bool> uploadFromGoogleDrive({
    required String fileId,
    required String fileName,
    required int templateId,
    required int userId,
  }) async {
    try {
      final url =
          '${ApiConfig.getBaseUrl()}/uploads/google-drive/import?user_id=$userId&file_id=$fileId&template_id=$templateId';
      final response = await http.post(Uri.parse(url));

      if (response.statusCode == 200) {
        await fetchDocuments(userId);
        return true;
      } else {
        _errorMessage = "Failed to import from Google Drive";
        debugPrint("[v0] Google Drive import failed: ${response.body}");
        return false;
      }
    } catch (e) {
      _errorMessage = "Error importing from Google Drive: $e";
      debugPrint("[v0] Google Drive import error: $e");
      return false;
    }
  }

 

  Future<bool> downloadDocument(
    int documentId,
    int userId, {
    String format = 'docx',
  }) async {
    try {
      final url =
          "$baseUrl/download/$documentId?user_id=$userId&format=$format";
      final response = await http.get(Uri.parse(url));

      if (response.statusCode == 200) {
        String fileName = "document_$documentId.$format";
        final directory =
            await getDownloadsDirectory() ??
            await getApplicationDocumentsDirectory();
        final file = File('${directory.path}/$fileName');
        await file.writeAsBytes(response.bodyBytes);
        _errorMessage = null;
        notifyListeners();
        return true;
      } else {
        _errorMessage = "Download failed: ${response.body}";
        return false;
      }
    } catch (e) {
      _errorMessage = "Download error: $e";
      return false;
    }
  }

  // -----------------------------
  // New: Formatted Document Download
  // -----------------------------
// -----------------------------
// Fixed: Formatted Document Download with user_id
// -----------------------------
Future<bool> downloadFormattedDocument(
  int documentId,
  int userId, {  // Add userId parameter
  String format = 'docx',
  bool applyBullets = true,
  bool autoDetectBullets = true,
}) async {
  try {
    // FIXED: Added user_id to the URL and bullet parameters
    final url = Uri.parse(
      "$exportUrl/$documentId?user_id=$userId&format=$format"
      "&apply_bullets=$applyBullets&auto_detect_bullets=$autoDetectBullets"
    );
    
    debugPrint('[v0] Downloading formatted document from: $url'); // For debugging
    
    final response = await http.get(url);

    if (response.statusCode == 200) {
      String fileName = "formatted_document_$documentId.$format";
      
     // With this — always trust the format the user selected:
final contentDisposition = response.headers['content-disposition'];
if (contentDisposition != null && contentDisposition.contains('filename=')) {
  final parts = contentDisposition.split('filename=');
  if (parts.length > 1) {
    final serverFileName = parts[1].replaceAll('"', '').trim();
    // Use server name but force the correct extension
    final baseName = serverFileName.contains('.')
        ? serverFileName.substring(0, serverFileName.lastIndexOf('.'))
        : serverFileName;
    fileName = '$baseName.$format';
  }
}

      // Get downloads directory
      final directory = await getDownloadsDirectory() ?? 
                       await getApplicationDocumentsDirectory();
      final file = File('${directory.path}/$fileName');
      
      // Write file
      await file.writeAsBytes(response.bodyBytes);
      
      debugPrint('[v0] File saved to: ${file.path}');
      
      _errorMessage = null;
      notifyListeners();
      return true;
    } else {
      _errorMessage = "Formatted download failed: ${response.body}";
      debugPrint('[v0] Download failed with status ${response.statusCode}: ${response.body}');
      return false;
    }
  } catch (e) {
    _errorMessage = "Formatted download error: $e";
    debugPrint('[v0] Download error: $e');
    return false;
  }
}
  Future<bool> createReportFromText({
    required String title,
    required String content,
    required int templateId,
    required int userId,
  }) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/create-report?user_id=$userId"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "title": title,
          "content": content,
          "template_id": templateId,
        }),
      );

      if (response.statusCode == 200) {
        _errorMessage = null;
        await fetchDocuments(userId); // refresh list
        notifyListeners();
        debugPrint("[v0] Report created successfully");
        return true;
      } else {
        _errorMessage = "Failed to create report: ${response.body}";
        debugPrint("[v0] Create report failed: ${response.body}");
        return false;
      }
    } catch (e) {
      _errorMessage = "Create report error: $e";
      debugPrint("[v0] Create report error: $e");
      return false;
    }
  }

  Future<bool> saveDocumentContent(
    int documentId,
    String content,
    int userId,
  ) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/$documentId/save?user_id=$userId"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"content": content}),
      );

      if (response.statusCode == 200) {
        _errorMessage = null;
        await fetchDocuments(userId); // refresh list
        notifyListeners();
        return true;
      } else {
        _errorMessage = "Failed to save document: ${response.body}";
        debugPrint("[v0] Save failed: ${response.body}");
        return false;
      }
    } catch (e) {
      _errorMessage = "Save error: $e";
      debugPrint("[v0] Save error: $e");
      return false;
    }
  }

  Future<bool> deleteDocument(int documentId, int userId) async {
    try {
      final url = "$baseUrl/$documentId?user_id=$userId";
      final response = await http.delete(Uri.parse(url));

      if (response.statusCode == 200) {
        _errorMessage = null;
        // Refresh the documents list
        await fetchDocuments(userId);
        notifyListeners();
        return true;
      } else {
        _errorMessage = "Delete failed: ${response.body}";
        debugPrint("[v0] Delete failed with status ${response.statusCode}: ${response.body}");
        return false;
      }
    } catch (e) {
      _errorMessage = "Delete error: $e";
      debugPrint("[v0] Delete error: $e");
      return false;
    }
  }
}
