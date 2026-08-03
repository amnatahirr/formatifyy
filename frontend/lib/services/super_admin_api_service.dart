import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../config/dev_user_config.dart';

class SuperAdminApiService {
  final String _baseUrl = ApiConfig.getBaseUrl();

  Map<String, String> _headers({bool json = false}) {
    final h = <String, String>{
      'X-Super-Admin-Key': DevUserConfig.superAdminKey,
    };
    if (json) h['Content-Type'] = 'application/json';
    return h;
  }

  Uri _uri(String path) => Uri.parse('$_baseUrl$path');

  Future<dynamic> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final uri = _uri(path);
    late http.Response response;
    switch (method) {
      case 'GET':
        response = await http.get(uri, headers: _headers());
        break;
      case 'POST':
        response = await http.post(uri, headers: _headers(json: true), body: jsonEncode(body ?? {}));
        break;
      case 'PUT':
        response = await http.put(uri, headers: _headers(json: true), body: jsonEncode(body ?? {}));
        break;
      case 'PATCH':
        response = await http.patch(uri, headers: _headers());
        break;
      case 'DELETE':
        response = await http.delete(uri, headers: _headers());
        break;
      default:
        throw UnsupportedError(method);
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      String message = 'Request failed (${response.statusCode})';
      try {
        final data = jsonDecode(response.body);
        if (data is Map) message = (data['detail'] ?? data['message'] ?? message).toString();
      } catch (_) {}
      throw Exception(message);
    }
    if (response.body.isEmpty) return null;
    return jsonDecode(response.body);
  }

  Future<List<Map<String, dynamic>>> listOrganizations() async {
    final data = await _request('GET', '/super-admin/organizations');
    final map = Map<String, dynamic>.from(data as Map);
    return List<Map<String, dynamic>>.from(
      (map['organizations'] as List? ?? const []).map((e) => Map<String, dynamic>.from(e as Map)),
    );
  }

  Future<List<Map<String, dynamic>>> listAdmins() async {
    final data = await _request('GET', '/super-admin/admins');
    final map = Map<String, dynamic>.from(data as Map);
    return List<Map<String, dynamic>>.from(
      (map['admins'] as List? ?? const []).map((e) => Map<String, dynamic>.from(e as Map)),
    );
  }

  Future<Map<String, dynamic>> createOrganization(Map<String, dynamic> body) async {
    final data = await _request('POST', '/super-admin/organizations', body: body);
    return Map<String, dynamic>.from(data as Map);
  }

  /// Public login gate — resolve tenant by organization code.
  Future<Map<String, dynamic>> resolveOrganization(String code) async {
    final uri = Uri.parse('${ApiConfig.getBaseUrl()}/org/resolve').replace(
      queryParameters: {'code': code.trim()},
    );
    final response = await http.get(uri);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      String detail = 'Organization not found (${response.statusCode})';
      try {
        final data = jsonDecode(response.body);
        if (data is Map && data['detail'] != null) detail = data['detail'].toString();
      } catch (_) {}
      throw Exception(detail);
    }
    return Map<String, dynamic>.from(jsonDecode(response.body) as Map);
  }

  Future<Map<String, dynamic>> updateOrganization(int id, Map<String, dynamic> body) async {
    final data = await _request('PUT', '/super-admin/organizations/$id', body: body);
    return Map<String, dynamic>.from((data as Map)['organization'] as Map);
  }

  Future<Map<String, dynamic>> toggleOrganization(int id) async {
    final data = await _request('PATCH', '/super-admin/organizations/$id/toggle');
    return Map<String, dynamic>.from((data as Map)['organization'] as Map);
  }

  Future<void> deleteOrganization(int id) async {
    await _request('DELETE', '/super-admin/organizations/$id');
  }

  Future<Map<String, dynamic>> organizationStats(int id) async {
    final data = await _request('GET', '/super-admin/organizations/$id/stats');
    return Map<String, dynamic>.from(data as Map);
  }

  Future<Map<String, dynamic>> platformStats() async {
    final data = await _request('GET', '/super-admin/stats');
    return Map<String, dynamic>.from(data as Map);
  }

  Future<Map<String, dynamic>> resetApiKey(int id) async {
    final data = await _request('POST', '/super-admin/organizations/$id/reset-key');
    return Map<String, dynamic>.from((data as Map)['organization'] as Map);
  }

  Future<Map<String, dynamic>> fetchOrgInfo() async {
    final uri = Uri.parse('${ApiConfig.getBaseUrl()}/org/info');
    final response = await http.get(uri, headers: ApiConfig.getHeaders());
    if (response.statusCode < 200 || response.statusCode >= 300) {
      String detail = 'Could not load org info (${response.statusCode})';
      try {
        final data = jsonDecode(response.body);
        if (data is Map && data['detail'] != null) {
          detail = data['detail'].toString();
        }
      } catch (_) {}
      throw Exception(detail);
    }
    return Map<String, dynamic>.from(jsonDecode(response.body) as Map);
  }
}
