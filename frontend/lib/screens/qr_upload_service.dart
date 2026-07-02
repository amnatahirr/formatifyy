import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

class QRUploadService {
  // Your backend's LAN IP — phone needs this to reach your laptop
  static const String _serverIp = '172.20.10.2';
  static const String _serverPort = '8000';
  static String get serverHost => '$_serverIp:$_serverPort';
  static String get baseUrl => 'http://$serverHost';

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