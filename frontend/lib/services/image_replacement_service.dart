import 'dart:io';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:flutter/foundation.dart';
import '../config/api_config.dart';
import 'package:http_parser/http_parser.dart';

class ImageReplacementService {
  final String imageBaseUrl;

  ImageReplacementService({required this.imageBaseUrl});

  /// Replace an irrelevant image and get re-validation results
  /// Returns the new image path and validation results
  Future<Map<String, dynamic>> replaceImage({
    required int documentId,
    required int imageIndex,
    required File imageFile,
  }) async {
    try {
      final uri = Uri.parse('${ApiConfig.baseUrl}/documents/$documentId/replace-image');
      
      // Create multipart request
      final request = http.MultipartRequest('POST', uri);
      request.fields['image_index'] = imageIndex.toString();
      String extension = imageFile.path.split('.').last;
      request.files.add(
        await http.MultipartFile.fromPath(
          'file',
          imageFile.path,
          contentType: MediaType('image', extension),
        ),
      );

      // Send request
      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final jsonResponse = jsonDecode(response.body);
        debugPrint('[ImageReplacement] ✓ Success: $jsonResponse');
        return jsonResponse;
      } else {
        final error = jsonDecode(response.body);
        throw Exception('Failed to replace image: ${error['detail'] ?? 'Unknown error'}');
      }
    } catch (e) {
      debugPrint('[ImageReplacement] ✗ Error: $e');
      rethrow;
    }
  }

  /// Get replacement history for a document
  Future<Map<String, dynamic>> getImageHistory(int documentId) async {
    try {
      final uri = Uri.parse('${ApiConfig.baseUrl}/documents/$documentId/image-history');

      
      final response = await http.get(uri);

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Failed to fetch image history');
      }
    } catch (e) {
      debugPrint('[ImageHistory] Error: $e');
      rethrow;
    }
  }

  /// Rollback to previous image version
  Future<void> rollbackImage(
    int documentId,
    int imageIndex,
  ) async {
    try {
  
      final uri = Uri.parse(
        '${ApiConfig.baseUrl}/documents/$documentId/images/$imageIndex',
      );
      final response = await http.delete(uri);

      if (response.statusCode != 200) {
        throw Exception('Failed to rollback image');
      }
      debugPrint('[ImageRollback] ✓ Image rolled back');
    } catch (e) {
      debugPrint('[ImageRollback] Error: $e');
      rethrow;
    }
  }
}
