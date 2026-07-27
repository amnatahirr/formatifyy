import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import '../config/api_config.dart';

class ImageReplacementService {
  final String imageBaseUrl;

  ImageReplacementService({required this.imageBaseUrl});

  /// Replace an irrelevant image and get re-validation results.
  Future<Map<String, dynamic>> replaceImage({
    required int documentId,
    required int imageIndex,
    required File imageFile,
    int? userId,
  }) async {
    try {
      var uri = Uri.parse('${ApiConfig.baseUrl}/documents/$documentId/replace-image');
      if (userId != null) {
        uri = uri.replace(queryParameters: {'user_id': userId.toString()});
      }

      final request = http.MultipartRequest('POST', uri);
      request.fields['image_index'] = imageIndex.toString();
      final extension = imageFile.path.split('.').last;
      request.files.add(
        await http.MultipartFile.fromPath(
          'file',
          imageFile.path,
          contentType: MediaType('image', extension),
        ),
      );

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final jsonResponse = jsonDecode(response.body) as Map<String, dynamic>;
        debugPrint('[ImageReplacement] ✓ Success: $jsonResponse');
        return jsonResponse;
      }
      final error = jsonDecode(response.body);
      throw Exception('Failed to replace image: ${error['detail'] ?? 'Unknown error'}');
    } catch (e) {
      debugPrint('[ImageReplacement] ✗ Error: $e');
      rethrow;
    }
  }

  /// Permanently remove an image (and nearby figure caption) from the DOCX.
  Future<Map<String, dynamic>> removeImage({
    required int documentId,
    required int imageIndex,
    int? userId,
  }) async {
    try {
      var uri = Uri.parse('${ApiConfig.baseUrl}/documents/$documentId/remove-image');
      if (userId != null) {
        uri = uri.replace(queryParameters: {'user_id': userId.toString()});
      }

      final request = http.MultipartRequest('POST', uri);
      request.fields['image_index'] = imageIndex.toString();

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final jsonResponse = jsonDecode(response.body) as Map<String, dynamic>;
        debugPrint('[ImageRemoval] ✓ Success: $jsonResponse');
        return jsonResponse;
      }
      final error = jsonDecode(response.body);
      throw Exception(
        'Failed to remove image: ${error['detail'] ?? response.body}',
      );
    } catch (e) {
      debugPrint('[ImageRemoval] ✗ Error: $e');
      rethrow;
    }
  }

  /// Re-check ethics + relevance for a replacement image (base64).
  Future<Map<String, dynamic>> recheckImage({
    required int documentId,
    required int userId,
    required String imageBase64,
    required String imageId,
    required String surroundingText,
  }) async {
    final uri = Uri.parse(
      '${ApiConfig.baseUrl}/documents/recheck-image/$documentId?user_id=$userId',
    );
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'image_base64': imageBase64,
        'image_id': imageId,
        'surrounding_text': surroundingText,
      }),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception('Recheck failed: ${response.body}');
  }
}
