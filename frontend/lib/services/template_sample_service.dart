// lib/services/template_sample_service.dart
import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';

class SamplePreviewException implements Exception {
  SamplePreviewException(this.message);
  final String message;
  @override
  String toString() => message;
}

/// Asks the backend to render a real sample document from the template
/// payload (the same JSON you already send to POST/PUT /admin/templates).
class TemplateSampleService {
  TemplateSampleService._();

  static Future<Uint8List> fetchSamplePdf({
    required String baseUrl,
    required int userId,
    required Map<String, dynamic> templateData,
  }) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/admin/templates/preview-sample'
                '?user_id=$userId&fmt=pdf'),
            headers: ApiConfig.getHeaders(json: true),
            body: jsonEncode(templateData),
          )
          .timeout(const Duration(seconds: 60));

      if (response.statusCode == 200 && response.bodyBytes.isNotEmpty) {
        return response.bodyBytes;
      }
      throw SamplePreviewException(
          'Server could not build the sample (HTTP ${response.statusCode}).');
    } on TimeoutException {
      throw SamplePreviewException(
          'The sample took too long to generate. Please try again.');
    } on SamplePreviewException {
      rethrow;
    } catch (e) {
      throw SamplePreviewException('Could not reach the server: $e');
    }
  }
}