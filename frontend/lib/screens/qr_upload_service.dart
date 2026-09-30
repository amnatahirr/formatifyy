import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';
class QRUploadService {


   static String get serverHost => Uri.parse(ApiConfig.imageBaseUrl).authority;
  static String get baseUrl => ApiConfig.imageBaseUrl;

  static Future<Map<String, dynamic>> generateUploadQr(
    int userId,
    int templateId,
  ) async {
    final response = await http.post(
      Uri.parse('$baseUrl/qr/upload/generate'),
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: {
        'user_id': userId.toString(),
        'template_id': templateId.toString(),
        'host': serverHost, // ← THIS is what was missing
      },
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to generate upload QR: ${response.body}');
    }

    final data = jsonDecode(response.body);

    // Validate the response has what we need
    if (data['qr_base64'] == null) {
      throw Exception('Invalid QR response from server');
    }

    return data;
  }
}