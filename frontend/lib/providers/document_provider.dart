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

  /// Cached GET /documents/missing-section-previews payloads keyed by document id.
  final Map<int, List<Map<String, dynamic>>> _missingSectionPreviews = {};
  int? _lastFetchedUserId;

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

  List<Map<String, dynamic>> missingSectionPreviewsFor(int documentId) =>
      List<Map<String, dynamic>>.from(
        _missingSectionPreviews[documentId] ?? const [],
      );

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
        _lastFetchedUserId = userId;
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
        debugPrint('[v0] Preview element keys: '
            '${elements.expand((e) => e.keys).toSet()} '
            'types: ${elements.map((e) => e['type']).toSet()} '
            'top-level: ${data.keys.toList()}');
        return {
          'document_id': documentId,
          'formatted_content': elements.map((e) => e['text']).join('\n'),
          // Keep EVERY field the backend sends (images, tables, page, fonts…).
          'formatted_lines': elements
              .map(
                (e) => <String, dynamic>{
                  ...e,
                  'text': e['text'] ?? '',
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
  Future<Directory> _downloadDirectory() async {
    if (Platform.isAndroid) {
      final downloads = Directory('/storage/emulated/0/Download');
      if (await downloads.exists()) return downloads;
      return await getDownloadsDirectory() ??
          await getApplicationDocumentsDirectory();
    }
    if (Platform.isIOS) {
      return await getApplicationDocumentsDirectory();
    }
    return await getDownloadsDirectory() ??
        await getApplicationDocumentsDirectory();
  }

  String _fileNameFromResponse(
    http.Response response, {
    required String fallback,
    String? forceExtension,
  }) {
    String fileName = fallback;
    final contentDisposition = response.headers['content-disposition'];
    if (contentDisposition != null && contentDisposition.contains('filename=')) {
      final parts = contentDisposition.split('filename=');
      if (parts.length > 1) {
        var serverFileName = parts[1].replaceAll('"', '').trim();
        // content-disposition may be: filename=foo.docx; filename*=UTF-8''...
        if (serverFileName.contains(';')) {
          serverFileName = serverFileName.split(';').first.trim();
        }
        if (serverFileName.isNotEmpty) {
          fileName = serverFileName;
        }
      }
    }
    if (forceExtension != null && forceExtension.isNotEmpty) {
      final ext = forceExtension.startsWith('.')
          ? forceExtension
          : '.$forceExtension';
      final baseName = fileName.contains('.')
          ? fileName.substring(0, fileName.lastIndexOf('.'))
          : fileName;
      fileName = '$baseName$ext';
    }
    return fileName;
  }

  /// Split ``report.docx`` → (``report``, ``.docx``).
  (String stem, String ext) _splitFileName(String fileName) {
    final dot = fileName.lastIndexOf('.');
    if (dot <= 0 || dot == fileName.length - 1) {
      return (fileName, '');
    }
    return (fileName.substring(0, dot), fileName.substring(dot));
  }

  /// True when Windows (or another OS) has the file open / locked.
  bool _isFileLockedError(Object e) {
    final msg = e.toString().toLowerCase();
    return msg.contains('being used by another process') ||
        msg.contains('errno = 32') ||
        msg.contains('errno: 32') ||
        msg.contains('pathaccessexception') ||
        msg.contains('sharing violation') ||
        msg.contains('cannot open file') ||
        msg.contains('access is denied');
  }

  /// Write bytes, retrying with ``name (1).ext``, ``name (2).ext``, … if the
  /// preferred path is locked (e.g. Word still has the previous download open).
  Future<File> _writeBytesAvoidingLocks(
    Directory directory,
    String preferredName,
    List<int> bytes,
  ) async {
    final (stem, ext) = _splitFileName(preferredName);
    Object? lastError;

    Future<File?> tryWrite(String name) async {
      final file = File('${directory.path}${Platform.pathSeparator}$name');
      try {
        await file.writeAsBytes(bytes, flush: true);
        return file;
      } catch (e) {
        lastError = e;
        if (!_isFileLockedError(e)) rethrow;
        debugPrint('[v0] Download path locked, trying another name: $name → $e');
        return null;
      }
    }

    final first = await tryWrite(preferredName);
    if (first != null) return first;

    for (var i = 1; i <= 30; i++) {
      final alt = await tryWrite('$stem ($i)$ext');
      if (alt != null) return alt;
    }

    // Last resort: timestamped name
    final stamp = DateTime.now().millisecondsSinceEpoch;
    final stamped = await tryWrite('${stem}_$stamp$ext');
    if (stamped != null) return stamped;

    throw lastError ??
        Exception('Could not save download — file may be open in another app.');
  }

  Future<bool> _writeDownloadResponse(
    http.Response response, {
    required String fallbackName,
    String? forceExtension,
  }) async {
    if (response.statusCode != 200) {
      _errorMessage = "Download failed: ${response.body}";
      return false;
    }
    final fileName = _fileNameFromResponse(
      response,
      fallback: fallbackName,
      forceExtension: forceExtension,
    );
    final directory = await _downloadDirectory();
    try {
      final file = await _writeBytesAvoidingLocks(
        directory,
        fileName,
        response.bodyBytes,
      );
      _lastDownloadedPath = file.path;
      _errorMessage = null;
      notifyListeners();
      debugPrint('[v0] File saved to: ${file.path}');
      return true;
    } catch (e) {
      _errorMessage =
          'Could not save the file. Close it in Word (or another app) and try again.';
      debugPrint('[v0] Download write failed: $e');
      return false;
    }
  }

  Future<bool> downloadFormattedDocument(
    int documentId,
    int userId, {
    String format = 'docx',
    bool applyBullets = true,
    bool autoDetectBullets = true,
  }) async {
    try {
      final url = Uri.parse(
        "$exportUrl/$documentId?user_id=$userId&format=$format"
        "&apply_bullets=$applyBullets&auto_detect_bullets=$autoDetectBullets",
      );

      debugPrint('[v0] Downloading formatted document from: $url');
      final response = await http.get(url, headers: ApiConfig.getHeaders());
      final saveExt = format == 'tex' ? 'zip' : format;
      return await _writeDownloadResponse(
        response,
        fallbackName: "formatted_document_$documentId.$saveExt",
        forceExtension: saveExt,
      );
    } catch (e) {
      _errorMessage = "Formatted download error: $e";
      debugPrint('[v0] Download error: $e');
      return false;
    }
  }

  /// Persist the current formatted working document into My Reports.
  Future<bool> saveFormattedDocument(int documentId, int userId) async {
    try {
      final url = Uri.parse(
        "$baseUrl/$documentId/save-formatted?user_id=$userId",
      );
      debugPrint('[v0] Saving formatted document: $url');
      final response = await http.post(
        url,
        headers: ApiConfig.getHeaders(json: true),
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        // Reflect immediately in My Reports without a full refetch race.
        final idx = _documents.indexWhere((d) => d['id'] == documentId);
        if (idx >= 0) {
          _documents[idx] = {
            ..._documents[idx],
            'has_formatted': true,
          };
        }
        _errorMessage = null;
        notifyListeners();
        // Refresh list so status / timestamps stay accurate.
        await fetchDocuments(userId);
        debugPrint('[v0] Formatted document saved: $data');
        return true;
      }
      try {
        final body = json.decode(response.body);
        _errorMessage = body is Map && body['detail'] != null
            ? body['detail'].toString()
            : "Save formatted failed: ${response.body}";
      } catch (_) {
        _errorMessage = "Save formatted failed: ${response.body}";
      }
      debugPrint('[v0] Save formatted failed: $_errorMessage');
      return false;
    } catch (e) {
      _errorMessage = "Save formatted error: $e";
      debugPrint('[v0] Save formatted error: $e');
      return false;
    }
  }

  /// Auto-save draft: silently persist title/content without creating a version.
  /// Returns true on HTTP 200; false on any error (caller decides retry logic).
  Future<bool> saveDraft(
    int documentId,
    int userId, {
    String? title,
    String? content,
  }) async {
    try {
      final url = Uri.parse(
        "$baseUrl/$documentId/draft?user_id=$userId",
      );
      final response = await http.patch(
        url,
        headers: ApiConfig.getHeaders(json: true),
        body: jsonEncode({
          if (title != null) 'title': title,
          if (content != null) 'content': content,
        }),
      );
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Download the original uploaded (unformatted) file.
  Future<bool> downloadOriginalDocument(int documentId, int userId) async {
    try {
      final url = Uri.parse(
        "$baseUrl/$documentId/download-original?user_id=$userId",
      );
      debugPrint('[v0] Downloading original document from: $url');
      final response = await http.get(url);
      return await _writeDownloadResponse(
        response,
        fallbackName: "original_document_$documentId",
      );
    } catch (e) {
      _errorMessage = "Original download error: $e";
      debugPrint('[v0] Original download error: $e');
      return false;
    }
  }

  /// Download a previously saved formatted document from My Reports.
  Future<bool> downloadSavedFormattedDocument(
    int documentId,
    int userId, {
    String format = 'docx',
  }) async {
    try {
      final url = Uri.parse(
        "$baseUrl/$documentId/download-formatted?user_id=$userId&format=$format",
      );
      debugPrint('[v0] Downloading saved formatted document from: $url');
      final response = await http.get(url, headers: ApiConfig.getHeaders());
      if (response.statusCode == 404) {
        try {
          final body = json.decode(response.body);
          _errorMessage = body is Map && body['detail'] != null
              ? body['detail'].toString()
              : 'No saved formatted document yet.';
        } catch (_) {
          _errorMessage =
              'No saved formatted document yet. Save it from Analysis first.';
        }
        return false;
      }
      final saveExt = format == 'tex' ? 'zip' : format;
      return await _writeDownloadResponse(
        response,
        fallbackName: "formatted_document_$documentId.$saveExt",
        forceExtension: saveExt,
      );
    } catch (e) {
      _errorMessage = "Saved formatted download error: $e";
      debugPrint('[v0] Saved formatted download error: $e');
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

  /// Rename a report. Returns the saved name, or null on failure.
  Future<String?> renameDocument(
    int documentId,
    int userId,
    String newName,
  ) async {
    try {
      final response = await http.patch(
        Uri.parse("$baseUrl/$documentId/rename?user_id=$userId"),
        headers: ApiConfig.getHeaders(json: true),
        body: jsonEncode({"name": newName}),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final saved = (data['filename'] ?? newName).toString();
        final idx = _documents.indexWhere((d) => d['id'] == documentId);
        if (idx >= 0) {
          _documents[idx] = {..._documents[idx], 'filename': saved};
        }
        _errorMessage = null;
        notifyListeners();
        return saved;
      }
      _errorMessage = _detail(response.body) ?? "Rename failed: ${response.body}";
      notifyListeners();
      return null;
    } catch (e) {
      _errorMessage = "Rename error: $e";
      notifyListeners();
      return null;
    }
  }

  Future<List<Map<String, dynamic>>> fetchMissingSectionPreviews(
    int documentId, {
    bool suggest = false,
    int? userId,
  }) async {
    try {
      final uid = userId ?? _lastFetchedUserId;
      if (uid == null) {
        return missingSectionPreviewsFor(documentId);
      }
      final url =
          '${ApiConfig.getBaseUrl()}/documents/missing-section-previews/$documentId'
          '?user_id=$uid&suggest=$suggest';
      final response = await http.get(
        Uri.parse(url),
        headers: ApiConfig.getHeaders(),
      );
      if (response.statusCode != 200) {
        debugPrint(
          '[v0] missing section previews failed: ${response.statusCode} ${response.body}',
        );
        return missingSectionPreviewsFor(documentId);
      }
      final data = json.decode(response.body) as Map<String, dynamic>;
      final previews = (data['previews'] as List? ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      _missingSectionPreviews[documentId] = previews;
      notifyListeners();
      return previews;
    } catch (e) {
      debugPrint('[v0] missing section previews error: $e');
      return missingSectionPreviewsFor(documentId);
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