import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/supervisor_models.dart';

class StudentApiService {
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

  Future<dynamic> _request(
    String method,
    String path, {
    Map<String, dynamic>? queryParameters,
  }) async {
    final uri = _uri(path, queryParameters);
    final response = await http.get(uri);
    final body = response.body.isEmpty ? null : jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = body is Map && body['detail'] != null ? body['detail'].toString() : response.body;
      throw Exception(detail.isEmpty ? 'Request failed (${response.statusCode})' : detail);
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
    return List<Map<String, dynamic>>.from(map['notes'] ?? const [])
        .map(MeetingNoteModel.fromJson)
        .toList();
  }
}
