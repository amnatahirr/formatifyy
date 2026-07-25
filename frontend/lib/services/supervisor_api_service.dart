import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

import '../config/api_config.dart';
import '../models/supervisor_models.dart';

class SupervisorApiService {
  final String _baseUrl = ApiConfig.getBaseUrl();

  Uri _uri(String path, [Map<String, dynamic>? queryParameters]) {
    final filtered = <String, String>{};
    queryParameters?.forEach((key, value) {
      if (value != null && value.toString().isNotEmpty) {
        filtered[key] = value.toString();
      }
    });
    return Uri.parse('$_baseUrl$path').replace(queryParameters: filtered);
  }

  Future<Directory> _downloadDirectory() async {
    if (Platform.isAndroid) {
      final downloads = Directory('/storage/emulated/0/Download');
      if (await downloads.exists()) return downloads;
    }
    if (Platform.isIOS) {
      return getApplicationDocumentsDirectory();
    }
    return await getDownloadsDirectory() ?? await getApplicationDocumentsDirectory();
  }

  String _filenameFromHeaders(http.Response response, String fallback) {
    final disposition = response.headers['content-disposition'];
    if (disposition != null && disposition.contains('filename=')) {
      final parts = disposition.split('filename=');
      if (parts.length > 1) {
        return parts[1].replaceAll('"', '').trim();
      }
    }
    return fallback;
  }

  Future<String> _saveDownloadBytes({
    required http.Response response,
    required String fallbackFilename,
  }) async {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      String message = 'Download failed (${response.statusCode})';
      try {
        final data = jsonDecode(response.body);
        if (data is Map<String, dynamic>) {
          message = (data['detail'] ?? data['message'] ?? message).toString();
        }
      } catch (_) {}
      throw Exception(message);
    }
    final filename = _filenameFromHeaders(response, fallbackFilename);
    final directory = await _downloadDirectory();
    final file = File('${directory.path}/$filename');
    await file.writeAsBytes(response.bodyBytes);
    return file.path;
  }

  Future<dynamic> _request(
    String method,
    String path, {
    Map<String, dynamic>? queryParameters,
    Map<String, dynamic>? body,
  }) async {
    final uri = _uri(path, queryParameters);
    http.Response response;

    switch (method) {
      case 'GET':
        response = await http.get(uri);
        break;
      case 'POST':
        response = await http.post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body ?? {}),
        );
        break;
      default:
        throw UnsupportedError('Unsupported HTTP method: $method');
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      String message = 'Request failed (${response.statusCode})';
      try {
        final data = jsonDecode(response.body);
        if (data is Map<String, dynamic>) {
          message = (data['detail'] ?? data['message'] ?? message).toString();
        }
      } catch (_) {}
      throw Exception(message);
    }

    if (response.body.isEmpty) return null;
    return jsonDecode(response.body);
  }

  Future<SupervisorHomeModel> fetchHome(int userId) async {
    final data = await _request(
      'GET',
      '/supervisor/home',
      queryParameters: {'user_id': userId},
    );
    return SupervisorHomeModel.fromJson(Map<String, dynamic>.from(data as Map));
  }

  Future<List<SupervisorGroupSummary>> fetchMyGroups(
    int userId, {
    String filter = 'all',
  }) async {
    final data = await _request(
      'GET',
      '/supervisor/groups',
      queryParameters: {
        'user_id': userId,
        'filter': filter,
      },
    );
    final map = Map<String, dynamic>.from(data as Map);
    return List<Map<String, dynamic>>.from(map['groups'] ?? const [])
        .map(SupervisorGroupSummary.fromJson)
        .toList();
  }

  Future<SupervisorGroupDetailModel> fetchGroupDetail(int userId, int groupId) async {
    final data = await _request(
      'GET',
      '/supervisor/groups/$groupId',
      queryParameters: {'user_id': userId},
    );
    return SupervisorGroupDetailModel.fromJson(Map<String, dynamic>.from(data as Map));
  }

  Future<List<AssignmentRequestModel>> fetchAssignmentRequests(
    int userId, {
    String status = 'pending',
  }) async {
    final data = await _request(
      'GET',
      '/supervisor/assignment-requests',
      queryParameters: {
        'user_id': userId,
        'status': status,
      },
    );
    final map = Map<String, dynamic>.from(data as Map);
    return List<Map<String, dynamic>>.from(map['requests'] ?? const [])
        .map(AssignmentRequestModel.fromJson)
        .toList();
  }

  Future<Map<String, dynamic>> acceptAssignmentRequest(int userId, int requestId) async {
    final data = await _request(
      'POST',
      '/supervisor/assignment-requests/$requestId/accept',
      queryParameters: {'user_id': userId},
    );
    return Map<String, dynamic>.from(data as Map);
  }

  Future<Map<String, dynamic>> rejectAssignmentRequest(
    int userId,
    int requestId, {
    required String reason,
  }) async {
    final data = await _request(
      'POST',
      '/supervisor/assignment-requests/$requestId/reject',
      queryParameters: {'user_id': userId},
      body: {'reason': reason},
    );
    return Map<String, dynamic>.from(data as Map);
  }

  Future<DocumentReviewModel> fetchDocumentReview({
    required int userId,
    required int groupId,
    required int documentId,
  }) async {
    final data = await _request(
      'GET',
      '/supervisor/groups/$groupId/documents/$documentId/review',
      queryParameters: {'user_id': userId},
    );
    return DocumentReviewModel.fromJson(Map<String, dynamic>.from(data as Map));
  }

  Future<DocumentReviewModel> addParagraphComment({
    required int userId,
    required int groupId,
    required int documentId,
    required int paragraphId,
    required String commentText,
  }) async {
    final data = await _request(
      'POST',
      '/supervisor/groups/$groupId/documents/$documentId/paragraphs/$paragraphId/comments',
      queryParameters: {'user_id': userId},
      body: {'comment_text': commentText},
    );
    final map = Map<String, dynamic>.from(data as Map);
    // Rebuild a review model from returned paragraphs + existing metadata via follow-up fetch
    // Prefer returned paragraphs when present by re-fetching full review for consistency.
    if (map['paragraphs'] is List) {
      final review = await fetchDocumentReview(
        userId: userId,
        groupId: groupId,
        documentId: documentId,
      );
      return review;
    }
    return fetchDocumentReview(userId: userId, groupId: groupId, documentId: documentId);
  }

  Future<DocumentReviewModel> resolveParagraphComments({
    required int userId,
    required int groupId,
    required int documentId,
    required int paragraphId,
  }) async {
    await _request(
      'POST',
      '/supervisor/groups/$groupId/documents/$documentId/paragraphs/$paragraphId/resolve',
      queryParameters: {'user_id': userId},
    );
    return fetchDocumentReview(userId: userId, groupId: groupId, documentId: documentId);
  }

  Future<List<FinalSubmissionModel>> fetchSubmissions(
    int userId, {
    String status = 'pending',
  }) async {
    final data = await _request(
      'GET',
      '/supervisor/submissions',
      queryParameters: {
        'user_id': userId,
        'status': status,
      },
    );
    final map = Map<String, dynamic>.from(data as Map);
    return List<Map<String, dynamic>>.from(map['submissions'] ?? const [])
        .map(FinalSubmissionModel.fromJson)
        .toList();
  }

  Future<FinalSubmissionModel> fetchSubmissionDetail(int userId, int submissionId) async {
    final data = await _request(
      'GET',
      '/supervisor/submissions/$submissionId',
      queryParameters: {'user_id': userId},
    );
    return FinalSubmissionModel.fromJson(Map<String, dynamic>.from(data as Map));
  }

  /// Download the original file attached to a final submission.
  Future<String> downloadSubmissionFile({
    required int userId,
    required int submissionId,
    String? preferredFilename,
  }) async {
    final uri = _uri(
      '/supervisor/submissions/$submissionId/download',
      {'user_id': userId},
    );
    final response = await http.get(uri);
    return _saveDownloadBytes(
      response: response,
      fallbackFilename: preferredFilename?.trim().isNotEmpty == true
          ? preferredFilename!.trim()
          : 'submission_$submissionId.docx',
    );
  }

  /// Download a group document under review.
  Future<String> downloadGroupDocument({
    required int userId,
    required int groupId,
    required int documentId,
    String? preferredFilename,
  }) async {
    final uri = _uri(
      '/supervisor/groups/$groupId/documents/$documentId/download',
      {'user_id': userId},
    );
    final response = await http.get(uri);
    return _saveDownloadBytes(
      response: response,
      fallbackFilename: preferredFilename?.trim().isNotEmpty == true
          ? preferredFilename!.trim()
          : 'document_$documentId.docx',
    );
  }

  Future<FinalSubmissionModel> approveSubmission(int userId, int submissionId, {String? note}) async {
    final data = await _request(
      'POST',
      '/supervisor/submissions/$submissionId/approve',
      queryParameters: {'user_id': userId},
      body: {'note': note ?? ''},
    );
    final map = Map<String, dynamic>.from(data as Map);
    return FinalSubmissionModel.fromJson(Map<String, dynamic>.from(map['submission'] as Map));
  }

  Future<FinalSubmissionModel> requestSubmissionRevision(
    int userId,
    int submissionId, {
    required String note,
  }) async {
    final data = await _request(
      'POST',
      '/supervisor/submissions/$submissionId/request-revision',
      queryParameters: {'user_id': userId},
      body: {'note': note},
    );
    final map = Map<String, dynamic>.from(data as Map);
    return FinalSubmissionModel.fromJson(Map<String, dynamic>.from(map['submission'] as Map));
  }

  Future<FinalSubmissionModel> rejectSubmission(
    int userId,
    int submissionId, {
    required String reason,
  }) async {
    final data = await _request(
      'POST',
      '/supervisor/submissions/$submissionId/reject',
      queryParameters: {'user_id': userId},
      body: {'reason': reason},
    );
    final map = Map<String, dynamic>.from(data as Map);
    return FinalSubmissionModel.fromJson(Map<String, dynamic>.from(map['submission'] as Map));
  }

  Future<List<PlagiarismMonitorGroup>> fetchPlagiarismMonitor(int userId) async {
    final data = await _request(
      'GET',
      '/supervisor/plagiarism-monitor',
      queryParameters: {'user_id': userId},
    );
    final map = Map<String, dynamic>.from(data as Map);
    return List<Map<String, dynamic>>.from(map['groups'] ?? const [])
        .map(PlagiarismMonitorGroup.fromJson)
        .toList();
  }

  Future<PlagiarismMonitorGroup> fetchPlagiarismMonitorDetail(int userId, int groupId) async {
    final data = await _request(
      'GET',
      '/supervisor/plagiarism-monitor/$groupId',
      queryParameters: {'user_id': userId},
    );
    return PlagiarismMonitorGroup.fromJson(Map<String, dynamic>.from(data as Map));
  }

  Future<Map<String, dynamic>> flagPlagiarism(
    int userId,
    int groupId, {
    String? note,
  }) async {
    final data = await _request(
      'POST',
      '/supervisor/plagiarism-monitor/$groupId/flag',
      queryParameters: {'user_id': userId},
      body: {'note': note ?? ''},
    );
    return Map<String, dynamic>.from(data as Map);
  }

  Future<List<MeetingNoteModel>> fetchMeetingNotes(int userId, int groupId) async {
    final data = await _request(
      'GET',
      '/supervisor/groups/$groupId/meeting-notes',
      queryParameters: {'user_id': userId},
    );
    final map = Map<String, dynamic>.from(data as Map);
    return List<Map<String, dynamic>>.from(
      (map['notes'] as List? ?? const []).map(
        (e) => Map<String, dynamic>.from(e as Map),
      ),
    ).map(MeetingNoteModel.fromJson).toList();
  }

  Future<MeetingNoteModel> createMeetingNote({
    required int userId,
    required int groupId,
    required String meetingDate,
    required String topic,
    required String actionItems,
  }) async {
    final data = await _request(
      'POST',
      '/supervisor/groups/$groupId/meeting-notes',
      queryParameters: {'user_id': userId},
      body: {
        'meeting_date': meetingDate,
        'topic': topic,
        'action_items': actionItems,
      },
    );
    final map = Map<String, dynamic>.from(data as Map);
    return MeetingNoteModel.fromJson(Map<String, dynamic>.from(map['note'] as Map));
  }
}
