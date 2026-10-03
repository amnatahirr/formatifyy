import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';

class QRService {
  static String get serverHost => ApiConfig.serverHost;
  static String get baseUrl => ApiConfig.imageBaseUrl;

  static Future<Map<String, dynamic>> generateQr(int documentId, {String fileType = 'pdf'}) async {
    final response = await http.post(
      Uri.parse('$baseUrl/qr/generate'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'document_id': documentId,
        'file_type': fileType,
        'host': serverHost, // ← THE FIX
      }),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to generate QR: ${response.body}');
    }

    final data = jsonDecode(response.body);

    if (data['qr_base64'] == null) {
      throw Exception('Invalid QR response from server');
    }

    return data;
  }
}