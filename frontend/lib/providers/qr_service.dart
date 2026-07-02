import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';

class QRService {
  static const String _serverIp = '172.20.10.2';
  static const String _serverPort = '8000';
  static String get serverHost => '$_serverIp:$_serverPort';
  static String get baseUrl => 'http://$serverHost';

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