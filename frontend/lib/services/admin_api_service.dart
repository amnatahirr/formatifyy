import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/admin_models.dart';

class AdminApiService {
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
    Map<String, dynamic>? body,
  }) async {
    final uri = _uri(path, queryParameters);
    http.Response response;
    final headers = ApiConfig.getHeaders(json: method != 'GET' && method != 'DELETE');

    switch (method) {
      case 'GET':
        response = await http.get(uri, headers: ApiConfig.getHeaders());
        break;
      case 'POST':
        response = await http.post(
          uri,
          headers: headers,
          body: jsonEncode(body ?? {}),
        );
        break;
      case 'PUT':
        response = await http.put(
          uri,
          headers: headers,
          body: jsonEncode(body ?? {}),
        );
        break;
      case 'PATCH':
        response = await http.patch(
          uri,
          headers: headers,
          body: jsonEncode(body ?? {}),
        );
        break;
      case 'DELETE':
        response = await http.delete(uri, headers: ApiConfig.getHeaders());
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

  Future<AdminOverviewModel> fetchOverview(int userId) async {
    final data = await _request('GET', '/admin/overview', queryParameters: {'user_id': userId});
    return AdminOverviewModel.fromJson(Map<String, dynamic>.from(data));
  }

  Future<AdminStats> fetchStats(int userId) async {
    final data = await _request('GET', '/admin/stats', queryParameters: {'user_id': userId});
    return AdminStats.fromJson(Map<String, dynamic>.from(data));
  }

  Future<List<DepartmentSummary>> fetchDepartments(int userId) async {
    final data = await _request('GET', '/admin/departments', queryParameters: {'user_id': userId});
    return List<Map<String, dynamic>>.from(data).map(DepartmentSummary.fromJson).toList();
  }

  Future<Map<String, dynamic>> createDepartment(int userId, Map<String, dynamic> body) async {
    final data = await _request('POST', '/admin/departments', queryParameters: {'user_id': userId}, body: body);
    return Map<String, dynamic>.from(data as Map);
  }

  Future<Map<String, dynamic>> updateDepartment(int userId, int id, Map<String, dynamic> body) async {
    final data = await _request('PUT', '/admin/departments/$id', queryParameters: {'user_id': userId}, body: body);
    return Map<String, dynamic>.from(data as Map);
  }

  Future<void> deleteDepartment(int userId, int id) async {
    await _request('DELETE', '/admin/departments/$id', queryParameters: {'user_id': userId});
  }

  Future<List<Map<String, dynamic>>> fetchUsers(int userId) async {
    final data = await _request('GET', '/admin/users', queryParameters: {'user_id': userId});
    final map = Map<String, dynamic>.from(data as Map);
    return List<Map<String, dynamic>>.from(map['users'] ?? const []);
  }

  Future<List<SupervisorModel>> fetchSupervisors(
    int userId, {
    int? departmentId,
    String? search,
  }) async {
    final data = await _request(
      'GET',
      '/admin/supervisors',
      queryParameters: {
        'user_id': userId,
        'department_id': departmentId,
        'search': search,
      },
    );
    return List<Map<String, dynamic>>.from(data).map(SupervisorModel.fromJson).toList();
  }

Future<Map<String, dynamic>> fetchPromotePreview(int userId) async {
  final data = await _request('GET', '/admin/promote-semester/preview', queryParameters: {'user_id': userId});
  return Map<String, dynamic>.from(data as Map);
}


Future<List<Map<String, dynamic>>> fetchPromoteStudents(int userId) async {
  final data = await _request('GET', '/admin/promote-semester/students', queryParameters: {'user_id': userId});
  final list = (data as Map)['students'] as List;
  return list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
}

Future<Map<String, dynamic>> promoteSemester(int userId, {List<int> excludeIds = const []}) async {
  final data = await _request(
    'POST',
    '/admin/promote-semester',
    queryParameters: {'user_id': userId},
    body: {'exclude_ids': excludeIds},
  );
  return Map<String, dynamic>.from(data as Map);
}

  Future<Map<String, dynamic>> createSupervisor(int userId, Map<String, dynamic> body) async {
    final data = await _request('POST', '/admin/supervisors', queryParameters: {'user_id': userId}, body: body);
    return Map<String, dynamic>.from(data as Map);
  }

  Future<void> updateSupervisor(int userId, int id, Map<String, dynamic> body) async {
    await _request('PUT', '/admin/supervisors/$id', queryParameters: {'user_id': userId}, body: body);
  }

  Future<void> toggleSupervisor(int userId, int id) async {
    await _request('PATCH', '/admin/supervisors/$id/toggle', queryParameters: {'user_id': userId});
  }

  Future<void> deleteSupervisor(int userId, int id) async {
    await _request('DELETE', '/admin/supervisors/$id', queryParameters: {'user_id': userId});
  }

  Future<Map<String, dynamic>> sendSupervisorCredentials(
    int userId,
    int supervisorId, {
    required String temporaryPassword,
  }) async {
    final data = await _request(
      'POST',
      '/admin/supervisors/$supervisorId/send-credentials',
      queryParameters: {'user_id': userId},
      body: {'temporary_password': temporaryPassword},
    );
    return Map<String, dynamic>.from(data as Map);
  }

  Future<List<AdminTemplateModel>> fetchTemplates(int userId, {int? departmentId}) async {
    final data = await _request(
      'GET',
      '/admin/templates',
      queryParameters: {'user_id': userId, 'department_id': departmentId},
    );
    return List<Map<String, dynamic>>.from(data).map(AdminTemplateModel.fromJson).toList();
  }

  Future<void> createTemplate(int userId, Map<String, dynamic> body, {int? departmentId}) async {
    await _request(
      'POST',
      '/admin/templates',
      queryParameters: {'user_id': userId, 'created_by': userId, 'university_id': 1, 'department_id': departmentId},
      body: body,
    );
  }

  Future<void> updateTemplate(int userId, int id, Map<String, dynamic> body, {int? departmentId}) async {
    await _request(
      'PUT',
      '/admin/templates/$id',
      queryParameters: {'user_id': userId, 'department_id': departmentId},
      body: body,
    );
  }

  Future<void> deleteTemplate(int userId, int id) async {
    await _request('DELETE', '/admin/templates/$id', queryParameters: {'user_id': userId});
  }

  Future<List<DeadlineModel>> fetchDeadlines(int userId) async {
    final data = await _request('GET', '/admin/deadlines', queryParameters: {'user_id': userId});
    return List<Map<String, dynamic>>.from(data).map(DeadlineModel.fromJson).toList();
  }

  Future<void> createDeadline(int userId, Map<String, dynamic> body) async {
    await _request('POST', '/admin/deadlines', queryParameters: {'user_id': userId}, body: body);
  }

  Future<void> updateDeadline(int userId, int id, Map<String, dynamic> body) async {
    await _request('PUT', '/admin/deadlines/$id', queryParameters: {'user_id': userId}, body: body);
  }

  Future<void> deleteDeadline(int userId, int id) async {
    await _request('DELETE', '/admin/deadlines/$id', queryParameters: {'user_id': userId});
  }

  Future<List<SemesterDeadlineModel>> fetchSemesterDeadlines(int userId) async {
    final data = await _request(
      'GET',
      '/admin/semester-deadlines',
      queryParameters: {'user_id': userId},
    );
    final map = Map<String, dynamic>.from(data as Map);
    return List<Map<String, dynamic>>.from(map['deadlines'] as List? ?? const [])
        .map(SemesterDeadlineModel.fromJson)
        .toList();
  }

  Future<SemesterDeadlineModel> createSemesterDeadline(
    int userId, {
    required int semester,
    required String deadlineDate,
  }) async {
    final data = await _request(
      'POST',
      '/admin/semester-deadlines',
      queryParameters: {'user_id': userId},
      body: {'semester': semester, 'deadline_date': deadlineDate},
    );
    final map = Map<String, dynamic>.from(data as Map);
    return SemesterDeadlineModel.fromJson(
      Map<String, dynamic>.from(map['deadline'] as Map),
    );
  }

  Future<SemesterDeadlineModel> updateSemesterDeadline(
    int userId,
    int id, {
    required String deadlineDate,
  }) async {
    final data = await _request(
      'PATCH',
      '/admin/semester-deadlines/$id',
      queryParameters: {'user_id': userId},
      body: {'deadline_date': deadlineDate},
    );
    final map = Map<String, dynamic>.from(data as Map);
    return SemesterDeadlineModel.fromJson(
      Map<String, dynamic>.from(map['deadline'] as Map),
    );
  }

  Future<AdminAnalyticsModel> fetchAnalytics(int userId) async {
    final data = await _request('GET', '/admin/analytics', queryParameters: {'user_id': userId});
    return AdminAnalyticsModel.fromJson(Map<String, dynamic>.from(data));
  }

  Future<List<AdminUniversityModel>> fetchUniversities(int userId) async {
    final data = await _request('GET', '/admin/universities', queryParameters: {'user_id': userId});
    return List<Map<String, dynamic>>.from(data).map(AdminUniversityModel.fromJson).toList();
  }

  Future<AdminSettingsModel> fetchSettings(int userId) async {
    final data = await _request('GET', '/admin/settings', queryParameters: {'user_id': userId});
    return AdminSettingsModel.fromJson(Map<String, dynamic>.from(data));
  }

  Future<AdminSettingsModel> updateSettings(int userId, Map<String, dynamic> body) async {
    final data = await _request('PUT', '/admin/settings', queryParameters: {'user_id': userId}, body: body);
    final settings = data is Map<String, dynamic> ? data['settings'] ?? data : data;
    return AdminSettingsModel.fromJson(Map<String, dynamic>.from(settings));
  }

  Future<FrontmatterConfigModel> fetchFrontmatterConfig(int userId) async {
    final data = await _request(
      'GET',
      '/admin/frontmatter-config',
      queryParameters: {'user_id': userId},
    );
    return FrontmatterConfigModel.fromJson(Map<String, dynamic>.from(data));
  }

  Future<FrontmatterConfigModel> updateFrontmatterConfig(
    int userId,
    Map<String, dynamic> body,
  ) async {
    final data = await _request(
      'PUT',
      '/admin/frontmatter-config',
      queryParameters: {'user_id': userId},
      body: body,
    );
    final config = data is Map<String, dynamic> ? data['config'] ?? data : data;
    return FrontmatterConfigModel.fromJson(Map<String, dynamic>.from(config));
  }

  Future<FrontmatterConfigModel> uploadFrontmatterLogo(int userId, String filePath) async {
    final uri = _uri('/admin/frontmatter-config/logo', {'user_id': userId});
    final request = http.MultipartRequest('POST', uri)
      ..files.add(await http.MultipartFile.fromPath('file', filePath));
    final streamed = await request.send();
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode < 200 || streamed.statusCode >= 300) {
      throw Exception(_multipartError(body, streamed.statusCode));
    }
    final data = jsonDecode(body);
    final config = data is Map<String, dynamic> ? data['config'] ?? data : data;
    return FrontmatterConfigModel.fromJson(Map<String, dynamic>.from(config));
  }

  Future<FrontmatterConfigModel> uploadFrontmatterTemplate(
    int userId,
    String kind,
    String filePath,
  ) async {
    final uri = _uri('/admin/frontmatter-config/templates/$kind', {'user_id': userId});
    final request = http.MultipartRequest('POST', uri)
      ..files.add(await http.MultipartFile.fromPath('file', filePath));
    final streamed = await request.send();
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode < 200 || streamed.statusCode >= 300) {
      throw Exception(_multipartError(body, streamed.statusCode));
    }
    final data = jsonDecode(body);
    final config = data is Map<String, dynamic> ? data['config'] ?? data : data;
    return FrontmatterConfigModel.fromJson(Map<String, dynamic>.from(config));
  }

  String _multipartError(String body, int statusCode) {
    try {
      final data = jsonDecode(body);
      if (data is Map<String, dynamic>) {
        return (data['detail'] ?? data['message'] ?? 'Upload failed ($statusCode)').toString();
      }
    } catch (_) {}
    return 'Upload failed ($statusCode)';
  }
}
