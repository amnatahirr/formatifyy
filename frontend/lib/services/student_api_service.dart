import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/supervisor_models.dart';

class StudentApiService {
  StudentApiService();

  /// Same config source as DocumentProvider (`ApiConfig.getBaseUrl()`).
  String get _baseUrl => ApiConfig.getBaseUrl();

  Uri _uri(String path, [Map<String, dynamic>? queryParameters]) {
    final filtered = <String, String>{};
    queryParameters?.forEach((key, value) {
      if (value != null && value.toString().isNotEmpty) {
        filtered[key] = value.toString();
      }
    });
    return Uri.parse('$_baseUrl$path').replace(queryParameters: filtered);
  }

  Future<dynamic> _request(
    String method,
    String path, {
    Map<String, dynamic>? queryParameters,
  }) async {
    final uri = _uri(path, queryParameters);
    final response = await http.get(uri);
    final body = response.body.isEmpty ? null : jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = body is Map && body['detail'] != null
          ? body['detail'].toString()
          : response.body;
      throw Exception(
        detail.isEmpty ? 'Request failed (${response.statusCode})' : detail,
      );
    }
    return body;
  }

  Future<List<MeetingNoteModel>> fetchMeetingNotes(int userId) async {
    final data = await _request(
      'GET',
      '/student/meeting-notes',
      queryParameters: {'user_id': userId},
    );
    final map = Map<String, dynamic>.from(data as Map);
    final notes = List<Map<String, dynamic>>.from(
      (map['notes'] as List? ?? const []).map(
        (e) => Map<String, dynamic>.from(e as Map),
      ),
    ).map(MeetingNoteModel.fromJson).toList();

    // Newest meeting_date first (backend also sorts DESC; keep client defensive).
    notes.sort((a, b) {
      final byDate = b.meetingDate.compareTo(a.meetingDate);
      if (byDate != 0) return byDate;
      return b.createdAt.compareTo(a.createdAt);
    });
    return notes;
  }

  Future<Map<String, dynamic>> fetchNotifications({
    required int userId,
    required String email,
  }) async {
    final data = await _request(
      'GET',
      '/student/notifications',
      queryParameters: {
        'user_id': userId,
        'email': email,
      },
    );
    return Map<String, dynamic>.from(data as Map);
  }

  Future<Map<String, dynamic>> markNotificationRead({
    required int userId,
    required String email,
    required int notificationId,
  }) async {
    final uri = _uri(
      '/student/notifications/$notificationId/read',
      {'user_id': userId, 'email': email},
    );
    final response = await http.patch(uri);
    final body = response.body.isEmpty ? null : jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = body is Map && body['detail'] != null
          ? body['detail'].toString()
          : response.body;
      throw Exception(
        detail.isEmpty ? 'Request failed (${response.statusCode})' : detail,
      );
    }
    return Map<String, dynamic>.from(body as Map);
  }

  Future<DocumentReviewModel> fetchDocumentComments({
    required int userId,
    required int groupId,
    required int documentId,
  }) async {
    final data = await _request(
      'GET',
      '/student/groups/$groupId/documents/$documentId/comments',
      queryParameters: {'user_id': userId},
    );
    return DocumentReviewModel.fromJson(Map<String, dynamic>.from(data as Map));
  }

  Future<Map<String, dynamic>> resolveComment({
    required int userId,
    required int commentId,
  }) async {
    final uri = _uri('/student/comments/$commentId/resolve', {'user_id': userId});
    final response = await http.post(uri);
    final body = response.body.isEmpty ? null : jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = body is Map && body['detail'] != null
          ? body['detail'].toString()
          : response.body;
      throw Exception(
        detail.isEmpty ? 'Request failed (${response.statusCode})' : detail,
      );
    }
    return Map<String, dynamic>.from(body as Map? ?? const {});
  }

  Future<void> replyToComment({
    required int userId,
    required int commentId,
    required String replyText,
  }) async {
    final uri = _uri('/student/comments/$commentId/reply', {'user_id': userId});
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'reply_text': replyText}),
    );
    final body = response.body.isEmpty ? null : jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = body is Map && body['detail'] != null
          ? body['detail'].toString()
          : response.body;
      throw Exception(
        detail.isEmpty ? 'Request failed (${response.statusCode})' : detail,
      );
    }
  }
}
