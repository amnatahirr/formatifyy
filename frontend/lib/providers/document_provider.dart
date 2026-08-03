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
  bool _isSubmittingFinal = false;
  String? _errorMessage;
  String? _lastSubmitErrorCode;
  String? _lastDownloadedPath;
  final Set<int> _reAnalyzingIds = {};

  /// Cached AI Tools analyze payloads (grammar/plagiarism/stats) keyed by document id.
  final Map<int, Map<String, dynamic>> _analysisByDocumentId = {};

  /// Last document created/uploaded on New Report — used for supervisor submit.
  int? _pendingSubmitDocumentId;
  String? _pendingSubmitFilename;
  String? _pendingSubmitTitle;

  /// Prior final_submission.source_document_id when resubmitting after "revision".
  int? _resubmitSourceDocumentId;
  int? _resubmitPriorSubmissionId;

  List<Map<String, dynamic>> get documents => _documents;
  bool get isLoading => _isLoading;
  bool get isSubmittingFinal => _isSubmittingFinal;
  String? get errorMessage => _errorMessage;
  /// e.g. `deadline_passed` from final-submissions 403 payload.
  String? get lastSubmitErrorCode => _lastSubmitErrorCode;
  /// Absolute path of the last successful [downloadFormattedDocument] save.
  String? get lastDownloadedPath => _lastDownloadedPath;
  bool isReAnalyzing(int documentId) => _reAnalyzingIds.contains(documentId);

  int? get pendingSubmitDocumentId => _pendingSubmitDocumentId;
  String? get pendingSubmitFilename => _pendingSubmitFilename;
  String? get pendingSubmitTitle => _pendingSubmitTitle;
  int? get resubmitSourceDocumentId => _resubmitSourceDocumentId;
  int? get resubmitPriorSubmissionId => _resubmitPriorSubmissionId;

  Map<String, dynamic>? analysisReportFor(int documentId) =>
      _analysisByDocumentId[documentId];

  /// Slim snapshot matching final_submissions / supervisor analysis_report shape.
  static Map<String, dynamic> slimAnalysisReport(Map<String, dynamic> raw) {
    return {
      'stats': raw['stats'] is Map
          ? Map<String, dynamic>.from(raw['stats'] as Map)
          : <String, dynamic>{},
      'structure': raw['structure'] is Map
          ? Map<String, dynamic>.from(raw['structure'] as Map)
          : <String, dynamic>{},
      'compliance_score': raw['compliance_score'],
      'issues': List<dynamic>.from(raw['issues'] as List? ?? const []),
    };
  }

  void cacheAnalysisReport(int documentId, Map<String, dynamic> report) {
    _analysisByDocumentId[documentId] = slimAnalysisReport(report);
    notifyListeners();
  }

  void markReadyForSupervisorSubmit({
    required int documentId,
    required String filename,
    String? title,
  }) {
    _pendingSubmitDocumentId = documentId;
    _pendingSubmitFilename = filename;
    _pendingSubmitTitle = (title != null && title.trim().isNotEmpty)
        ? title.trim()
        : filename;
    notifyListeners();
  }

  /// Start a revision resubmit from Status Tracker into New Report (screen 4).
  /// Passes [sourceDocumentId] from the prior final_submission for traceability.
  void beginResubmitFromSubmission({
    required int? sourceDocumentId,
    required int priorSubmissionId,
    required String title,
    required String filename,
  }) {
    _resubmitSourceDocumentId = sourceDocumentId;
    _resubmitPriorSubmissionId = priorSubmissionId;
    if (sourceDocumentId != null) {
      markReadyForSupervisorSubmit(
        documentId: sourceDocumentId,
        filename: filename,
        title: title,
      );
    } else {
      _pendingSubmitDocumentId = null;
      _pendingSubmitFilename = filename;
      _pendingSubmitTitle = title;
      notifyListeners();
    }
  }

  void clearPendingSupervisorSubmit() {
    _pendingSubmitDocumentId = null;
    _pendingSubmitFilename = null;
    _pendingSubmitTitle = null;
    _resubmitSourceDocumentId = null;
    _resubmitPriorSubmissionId = null;
    notifyListeners();
  }

  Future<void> fetchDocuments(int userId) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await http.get(
        Uri.parse("$baseUrl/?user_id=$userId"),
        headers: ApiConfig.getHeaders(),
      );

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
      final resp = await http.get(url, headers: ApiConfig.getHeaders());
      if (resp.statusCode == 200) {
        final data = json.decode(resp.body);
        if (data is Map) {
          cacheAnalysisReport(
            documentId,
            Map<String, dynamic>.from(data),
          );
        }
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

  /// Insert into final_submissions (status=pending) for supervisor GET /submissions.
  Future<Map<String, dynamic>?> submitFinalSubmission({
    required int userId,
    required int groupId,
    required String title,
    required String filename,
    required String studentContactEmail,
    int? sourceDocumentId,
    Map<String, dynamic>? analysisReport,
  }) async {
    _isSubmittingFinal = true;
    _errorMessage = null;
    _lastSubmitErrorCode = null;
    notifyListeners();
    try {
      final report = analysisReport ??
          (sourceDocumentId != null
              ? _analysisByDocumentId[sourceDocumentId]
              : null);
      final uri = Uri.parse(
        '${ApiConfig.getBaseUrl()}/student/final-submissions',
      ).replace(queryParameters: {'user_id': userId.toString()});

      final response = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'group_id': groupId,
          'title': title,
          'filename': filename,
          'student_contact_email': studentContactEmail,
          if (sourceDocumentId != null) 'source_document_id': sourceDocumentId,
          if (report != null) 'analysis_report': report,
        }),
      );

      if (response.statusCode == 200) {
        final data = Map<String, dynamic>.from(jsonDecode(response.body) as Map);
        clearPendingSupervisorSubmit();
        return data;
      }
      final parsed = _parseSubmitError(response.body);
      _lastSubmitErrorCode = parsed.$1;
      _errorMessage = parsed.$2 ?? 'Failed to submit for review';
      return null;
    } catch (e) {
      _errorMessage = 'Network error: $e';
      _lastSubmitErrorCode = null;
      debugPrint('[DocumentProvider] submitFinalSubmission error: $e');
      return null;
    } finally {
      _isSubmittingFinal = false;
      notifyListeners();
    }
  }

  /// Returns (errorCode, message) from FastAPI detail (string or object).
  (String?, String?) _parseSubmitError(String body) {
    try {
      final data = jsonDecode(body);
      if (data is Map && data['detail'] != null) {
        final detail = data['detail'];
        if (detail is Map) {
          return (
            detail['code']?.toString(),
            (detail['message'] ?? detail['detail'] ?? detail).toString(),
          );
        }
        return (null, detail.toString());
      }
    } catch (_) {}
    return (null, null);
  }

  String? _detail(String body) {
    try {
      final data = jsonDecode(body);
      if (data is Map && data['detail'] != null) {
        final detail = data['detail'];
        if (detail is Map) {
          return (detail['message'] ?? detail).toString();
        }
        return detail.toString();
      }
    } catch (_) {}
    return null;
  }

  Future<bool> uploadDocument(File file, int templateId, int userId) async {
    try {
      var request = http.MultipartRequest(
        "POST",
        Uri.parse("$baseUrl/upload?template_id=$templateId&user_id=$userId"),
      );
      request.headers.addAll(ApiConfig.getHeaders());

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

  /// Template-free upload. Returns `{document_id, filename}` or null.
  Future<Map<String, dynamic>?> uploadDocumentFreeform(File file, int userId) async {
    try {
      var request = http.MultipartRequest(
        "POST",
        Uri.parse("$baseUrl/upload-freeform?user_id=$userId"),
      );
      request.headers.addAll(ApiConfig.getHeaders());
      request.files.add(await http.MultipartFile.fromPath("file", file.path));
      var response = await request.send();
      final responseBody = await response.stream.bytesToString();
      if (response.statusCode == 200) {
        final data = jsonDecode(responseBody) as Map<String, dynamic>;
        await fetchDocuments(userId);
        return {
          'document_id': data['document_id'],
          'filename': data['filename'] ?? file.path.split(RegExp(r'[\\/]')).last,
          'is_freeform': true,
        };
      }
      _errorMessage = "Freeform upload failed: $responseBody";
      return null;
    } catch (e) {
      _errorMessage = "Freeform upload error: $e";
      return null;
    }
  }

  Future<Map<String, dynamic>?> uploadPastedContentFreeform(
    String content,
    int userId,
  ) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/upload-text-freeform?user_id=$userId"),
        headers: ApiConfig.getHeaders(json: true),
        body: jsonEncode({"content": content}),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        await fetchDocuments(userId);
        return {
          'document_id': data['document_id'],
          'filename': data['filename'] ?? 'Pasted Content',
          'is_freeform': true,
        };
      }
      _errorMessage = "Freeform upload failed: ${response.body}";
      return null;
    } catch (e) {
      _errorMessage = "Freeform upload error: $e";
      return null;
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
        headers: ApiConfig.getHeaders(json: true),
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
      final response = await http.get(
        Uri.parse(url),
        headers: ApiConfig.getHeaders(),
      );

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
      final response = await http.post(
        Uri.parse(url),
        headers: ApiConfig.getHeaders(),
      );

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

      // Prefer public Downloads on Android phones; otherwise app documents.
      Directory directory;
      if (Platform.isAndroid) {
        final downloads = Directory('/storage/emulated/0/Download');
        directory = await downloads.exists()
            ? downloads
            : (await getDownloadsDirectory() ??
                await getApplicationDocumentsDirectory());
      } else if (Platform.isIOS) {
        directory = await getApplicationDocumentsDirectory();
      } else {
        directory = await getDownloadsDirectory() ??
            await getApplicationDocumentsDirectory();
      }
      final file = File('${directory.path}/$fileName');
      
      // Write file
      await file.writeAsBytes(response.bodyBytes);

      debugPrint('[v0] File saved to: ${file.path}');

      _lastDownloadedPath = file.path;
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
        Uri.parse(
          "$baseUrl/upload-text?template_id=$templateId&user_id=$userId",
        ),
        headers: ApiConfig.getHeaders(json: true),
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
