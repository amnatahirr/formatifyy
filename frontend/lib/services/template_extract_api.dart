import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';

/// Client for POST /api/admin/templates/extract-from-document.
class TemplateExtractApi {
  TemplateExtractApi({String? baseUrl})
      : _baseUrl = baseUrl ?? ApiConfig.getBaseUrl();

  final String _baseUrl;

  /// Uploads a .docx and returns the draft map
  /// `{name, description, required_sections, formatting_rules}`.
  Future<Map<String, dynamic>> extractFromDocument(String filePath) async {
    final uri = Uri.parse('$_baseUrl/admin/templates/extract-from-document');
    final request = http.MultipartRequest('POST', uri);
    request.files.add(await http.MultipartFile.fromPath('file', filePath));

    final streamed = await request.send();
    final body = await streamed.stream.bytesToString();

    if (streamed.statusCode != 200) {
      throw TemplateExtractException(_parseDetail(body) ??
          'Extraction failed (${streamed.statusCode})');
    }

    final decoded = jsonDecode(body);
    if (decoded is! Map<String, dynamic>) {
      throw TemplateExtractException('Unexpected response from server');
    }
    final draft = decoded['draft'];
    if (draft is! Map) {
      throw TemplateExtractException('Server did not return a draft template');
    }
    return Map<String, dynamic>.from(draft);
  }

  String? _parseDetail(String body) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map && decoded['detail'] != null) {
        final detail = decoded['detail'];
        if (detail is String) return detail;
      }
    } catch (_) {}
    return body.trim().isEmpty ? null : body;
  }
}

class TemplateExtractException implements Exception {
  final String message;
  TemplateExtractException(this.message);

  @override
  String toString() => message;
}
