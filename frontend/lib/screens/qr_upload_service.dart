import 'dart:convert';
import 'dart:async';
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
        'host': serverHost,
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

  /// Har 2 second baad server se poochta hai ke phone se file upload hui ya nahi.
  /// Upload hone par [onUploaded] chalta hai (document_id ke saath) aur polling band ho jati hai.
  /// Session expire ho to [onExpired] chalta hai.
  ///
  /// Returned Timer ko widget ke dispose() mein cancel() zaroor karein.
  static Timer startUploadPolling({
    required String token,
    required void Function(int? documentId) onUploaded,
    void Function()? onExpired,
  }) {
    return Timer.periodic(const Duration(seconds: 2), (timer) async {
      try {
        final res = await http
            .get(Uri.parse('$baseUrl/qr/upload/status/$token'))
            .timeout(const Duration(seconds: 5));

        if (res.statusCode == 404) {
          timer.cancel();
          onExpired?.call();
          return;
        }

        if (res.statusCode == 200) {
          final data = jsonDecode(res.body);
          if (data['uploaded'] == true) {
            timer.cancel();
            final id = data['document_id'];
            onUploaded(id is int ? id : int.tryParse(id?.toString() ?? ''));
          }
        }
      } catch (_) {
        // network error par chup-chaap agli poll tak ruk jao
      }
    });
  }
}