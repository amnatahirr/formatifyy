import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../config/api_config.dart';

class TemplateProvider extends ChangeNotifier {
  late String baseUrl;
  List<Map<String, dynamic>> _templates = [];
  Map<String, dynamic>? _selectedTemplate;
  bool _isLoading = false;
  String? _errorMessage;

  List<Map<String, dynamic>> get templates => _templates;
  Map<String, dynamic>? get selectedTemplate => _selectedTemplate;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  TemplateProvider() {
    baseUrl = ApiConfig.getBaseUrl();
  }

  Future<void> fetchTemplates(int userId) async {
    // Generic method that fetches user templates
    await fetchUserTemplates(userId);
  }

  Future<void> fetchUserTemplates(int userId) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await http
          .get(
            Uri.parse("$baseUrl/templates/user/$userId"),
            headers: ApiConfig.getHeaders(),
          )
          .timeout(
            Duration(seconds: 10),
            onTimeout: () => throw TimeoutException('Connection timeout'),
          );

      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        _templates = List<Map<String, dynamic>>.from(
          data.map(
            (template) => {
              'id': template['id'],
              'name': template['name'],
              'description': template['description'] ?? '',
              'required_sections': template['required_sections'] ?? [],
              'formatting_rules': template['formatting_rules'] ?? {},
              'university_id': template['university_id'],
            },
          ),
        );
        debugPrint(
          "[v0] Fetched ${_templates.length} templates for user $userId",
        );
      } else {
        _errorMessage = "Failed to fetch templates";
        debugPrint("[v0] Failed to fetch templates: ${response.body}");
      }
    } catch (e) {
      _errorMessage = "Error: $e";
      debugPrint("[v0] Error fetching templates: $e");
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> fetchUniversityTemplates(int universityId) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await http
          .get(
            Uri.parse("$baseUrl/templates/university/$universityId"),
            headers: ApiConfig.getHeaders(),
          )
          .timeout(
            Duration(seconds: 10),
            onTimeout: () => throw TimeoutException('Connection timeout'),
          );

      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        _templates = List<Map<String, dynamic>>.from(
          data.map(
            (template) => {
              'id': template['id'],
              'name': template['name'],
              'description': template['description'] ?? '',
              'required_sections': template['required_sections'] ?? [],
              'formatting_rules': template['formatting_rules'] ?? {},
              'university_id': template['university_id'],
              'created_by': template['created_by'],
              'created_at': template['created_at'],
            },
          ),
        );
        debugPrint(
          "[v0] Fetched ${_templates.length} templates for university $universityId",
        );
      } else {
        _errorMessage = "Failed to fetch templates";
        debugPrint("[v0] Failed to fetch templates: ${response.body}");
      }
    } catch (e) {
      _errorMessage = "Error: $e";
      debugPrint("[v0] Error fetching templates: $e");
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  void selectTemplate(Map<String, dynamic> template) {
    _selectedTemplate = template;
    debugPrint("[v0] Selected template: ${template['name']}");
    notifyListeners();
  }

  void clearSelection() {
    _selectedTemplate = null;
    notifyListeners();
  }

  Future<void> refreshTemplates(int universityId) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      await fetchUniversityTemplates(universityId);
      debugPrint("[v0] Refreshed templates for university $universityId");
    } catch (e) {
      _errorMessage = "Error refreshing templates: $e";
      debugPrint("[v0] Error refreshing templates: $e");
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> createTemplate(
    int userId,
    int universityId,
    String name,
    List<String> requiredSections,
    Map<String, dynamic> formattingRules,
  ) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final uri = Uri.parse("$baseUrl/admin/templates").replace(
        queryParameters: {
          "user_id": userId.toString(),
          "university_id": universityId.toString(),
        },
      );

      debugPrint("[v0] Creating template with URI: $uri");

      final response = await http
          .post(
            uri,
            headers: ApiConfig.getHeaders(json: true),
            body: jsonEncode({
              "name": name,
              "required_sections": requiredSections,
              "formatting_rules": formattingRules,
            }),
          )
          .timeout(
            Duration(seconds: 15),
            onTimeout: () => throw TimeoutException('Connection timeout'),
          );

      if (response.statusCode == 200 || response.statusCode == 201) {
        debugPrint("[v0] Template created successfully");
        // Refresh templates list after creation
        await fetchUniversityTemplates(universityId);
        return true;
      } else {
        _errorMessage = "Failed to create template: ${response.body}";
        debugPrint("[v0] Failed to create template: ${response.body}");
        return false;
      }
    } catch (e) {
      _errorMessage = "Error creating template: $e";
      debugPrint("[v0] Error creating template: $e");
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
