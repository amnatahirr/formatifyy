import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:url_launcher/url_launcher.dart';
import '../config/api_config.dart';

class UploadProvider extends ChangeNotifier {
  final String baseUrl = ApiConfig.getBaseUrl();

  // Upload State
  bool isUploading = false;
  int uploadProgress = 0;
  String? uploadErrorMessage;
  String? lastUploadedDocumentId;
  List<DocumentSyncStatus> userDocuments = [];

  // Sync State
  bool isSyncing = false;
  Map<int, SyncStatus> documentSyncStatus = {};

  // Initialize Google Drive authentication for the logged-in user
  Future<bool> initializeGoogleDrive({
    required int userId,
  }) async {
    try {
      debugPrint("[v0] Initializing Google Drive for user $userId");

      final response = await http.post(
        Uri.parse("$baseUrl/uploads/google-drive/auth/init?user_id=$userId"),
        headers: {"Content-Type": "application/json"},
      ).timeout(
        const Duration(seconds: 10),
        onTimeout: () => throw TimeoutException('Auth init timeout'),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        debugPrint("[v0] Google Drive initialized for ${data['email']}");
        uploadErrorMessage = null;
        notifyListeners();
        return true;
      } else {
        uploadErrorMessage =
            "Failed to initialize Google Drive: ${response.statusCode}";
        debugPrint("[v0] Google Drive init failed: ${response.statusCode}");
        notifyListeners();
        return false;
      }
    } catch (e) {
      uploadErrorMessage = "Error initializing Google Drive: $e";
      debugPrint("[v0] Google Drive init error: $e");
      notifyListeners();
      return false;
    }
  }

  // Upload file from local storage.
  // App (Android/iOS/desktop): filePath do.
  // Web (browser, phone ka browser bhi): bytes + filename do.
  Future<bool> uploadLocalFile({
    required int userId,
    required int templateId,
    String? filePath,
    Uint8List? bytes,
    String? filename,
    String? sessionId,
  }) async {
    isUploading = true;
    uploadErrorMessage = null;
    uploadProgress = 0;
    notifyListeners();

    try {
      final http.MultipartFile file;
      if (bytes != null) {
        debugPrint("[v0] Uploading file from bytes: $filename (${bytes.length} bytes)");
        file = http.MultipartFile.fromBytes(
          'file',
          bytes,
          filename: filename ?? 'upload',
        );
      } else if (filePath != null) {
        debugPrint("[v0] Uploading local file: $filePath");
        file = await http.MultipartFile.fromPath('file', filePath);
      } else {
        throw ArgumentError('No file data provided (filePath or bytes required)');
      }

      final request = http.MultipartRequest(
        'POST',
        Uri.parse("$baseUrl/uploads/local-upload"),
      )
        ..fields['user_id'] = userId.toString()
        ..fields['template_id'] = templateId.toString()
        ..files.add(file);

      if (sessionId != null) {
        request.fields['session_id'] = sessionId;
      }

      final streamedResponse = await request.send().timeout(
        const Duration(minutes: 5),
        onTimeout: () => throw TimeoutException('Upload timeout'),
      );

      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        lastUploadedDocumentId = data['document_id'].toString();
        uploadProgress = 100;
        debugPrint("[v0] Local file uploaded: ${data['document_id']}");

        // Start monitoring sync status
        startMonitoringSyncStatus(
          data['document_id'],
          userId,
        );

        notifyListeners();
        return true;
      } else {
        String detail = '';
        try {
          detail = jsonDecode(response.body)['detail']?.toString() ?? '';
        } catch (_) {}
        uploadErrorMessage =
            "Upload failed: ${response.statusCode}${detail.isNotEmpty ? ' - $detail' : ''}";
        debugPrint("[v0] Upload failed: ${response.body}");
        notifyListeners();
        return false;
      }
    } on TimeoutException catch (e) {
      uploadErrorMessage = "Upload timeout: ${e.message}";
      debugPrint("[v0] Upload timeout: $e");
      notifyListeners();
      return false;
    } catch (e) {
      uploadErrorMessage = "Upload error: $e";
      debugPrint("[v0] Upload error: $e");
      notifyListeners();
      return false;
    } finally {
      isUploading = false;
      notifyListeners();
    }
  }

  // Open Google Drive picker to select files
  Future<bool> openGoogleDrivePicker({
    required int userId,
  }) async {
    try {
      debugPrint("[v0] Opening Google Drive picker for user $userId");

      final uri = Uri.parse("$baseUrl/auth/google/drive-picker")
          .replace(queryParameters: {
        'user_id': userId.toString(),
      });

      final response = await http.get(uri).timeout(
        const Duration(seconds: 10),
        onTimeout: () =>
            throw TimeoutException('Failed to get Drive picker URL'),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final pickerUrl = data['picker_url'];
        final sessionId = data['session_id'];

        debugPrint("[v0] Got Drive picker session: $sessionId");
        debugPrint("[v0] Opening URL: $pickerUrl");

        // Open Google Drive in browser
        final driveUri = Uri.parse(pickerUrl);
        if (await canLaunchUrl(driveUri)) {
          await launchUrl(driveUri, mode: LaunchMode.externalApplication);
          debugPrint("[v0] Opened Google Drive picker");
          uploadErrorMessage = null;
          notifyListeners();
          return true;
        } else {
          uploadErrorMessage = "Could not open Google Drive";
          debugPrint("[v0] Could not launch Drive picker URL");
          notifyListeners();
          return false;
        }
      } else {
        uploadErrorMessage =
            jsonDecode(response.body)['detail'] ?? "Failed to get Drive picker";
        debugPrint("[v0] Error response: ${response.body}");
        notifyListeners();
        return false;
      }
    } on TimeoutException catch (e) {
      uploadErrorMessage = "Timeout: ${e.message}";
      debugPrint("[v0] Timeout: $e");
      notifyListeners();
      return false;
    } catch (e) {
      uploadErrorMessage = "Error: $e";
      debugPrint("[v0] Drive picker error: $e");
      notifyListeners();
      return false;
    }
  }

  // Download a file from Google Drive
  Future<bool> downloadFromGoogleDrive({
    required int userId,
    required String fileId,
    required String filename,
    required int templateId,
  }) async {
    try {
      debugPrint("[v0] Downloading file $fileId from Google Drive");
      isUploading = true;
      uploadProgress = 0;
      uploadErrorMessage = null;
      notifyListeners();

      final uri = Uri.parse("$baseUrl/uploads/download-from-google-drive")
          .replace(queryParameters: {
        'user_id': userId.toString(),
        'file_id': fileId,
        'filename': filename,
        'template_id': templateId.toString(),
      });

      final response = await http.post(uri).timeout(
        const Duration(seconds: 60),
        onTimeout: () => throw TimeoutException('Download timeout'),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        lastUploadedDocumentId = data['document_id'].toString();

        debugPrint("[v0] File downloaded successfully from Google Drive");
        debugPrint("[v0] Document ID: ${data['document_id']}");

        // Start monitoring sync status
        startMonitoringSyncStatus(
          data['document_id'],
          userId,
        );

        uploadProgress = 100;
        uploadErrorMessage = null;
        notifyListeners();
        return true;
      } else {
        uploadErrorMessage =
            jsonDecode(response.body)['detail'] ?? "Download failed";
        debugPrint("[v0] Download failed: ${response.body}");
        notifyListeners();
        return false;
      }
    } on TimeoutException catch (e) {
      uploadErrorMessage = "Download timeout";
      debugPrint("[v0] Timeout: $e");
      notifyListeners();
      return false;
    } catch (e) {
      uploadErrorMessage = "Download error: $e";
      debugPrint("[v0] Download error: $e");
      notifyListeners();
      return false;
    } finally {
      isUploading = false;
      notifyListeners();
    }
  }

  // Export document to Google Drive
  Future<bool> exportToGoogleDrive({
    required int userId,
    required int documentId,
    String? folderId,
  }) async {
    isUploading = true;
    uploadErrorMessage = null;
    notifyListeners();

    try {
      debugPrint("[v0] Exporting document to Google Drive: $documentId");

      final uri = Uri.parse("$baseUrl/uploads/google-drive/export").replace(
        queryParameters: {
          'user_id': userId.toString(),
          'document_id': documentId.toString(),
          if (folderId != null) 'folder_id': folderId,
        },
      );

      final response = await http.post(uri).timeout(
        const Duration(seconds: 30),
        onTimeout: () => throw TimeoutException('Export timeout'),
      );

      if (response.statusCode == 200) {
        debugPrint("[v0] Document exported to Google Drive");
        notifyListeners();
        return true;
      } else {
        uploadErrorMessage = "Export failed";
        notifyListeners();
        return false;
      }
    } catch (e) {
      uploadErrorMessage = "Export error: $e";
      debugPrint("[v0] Export error: $e");
      notifyListeners();
      return false;
    } finally {
      isUploading = false;
      notifyListeners();
    }
  }

  // Start monitoring sync status (polling)
  void startMonitoringSyncStatus(int documentId, int userId) {
    debugPrint("[v0] Starting sync monitoring for doc $documentId");

    Future.doWhile(() async {
      await Future.delayed(const Duration(seconds: 2));

      try {
        final response = await http
            .get(
              Uri.parse(
                "$baseUrl/uploads/sync-status/$documentId?user_id=$userId",
              ),
            )
            .timeout(const Duration(seconds: 5));

        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);

          documentSyncStatus[documentId] = SyncStatus(
            documentId: documentId,
            syncStatus: data['sync_status'] ?? 'unknown',
            source: data['source'],
            documentStatus: data['document_status'] ?? 'unknown',
            lastSynced: data['last_synced'] != null
                ? DateTime.parse(data['last_synced'])
                : null,
          );

          debugPrint("[v0] Sync status: ${data['sync_status']}");
          notifyListeners();

          // Stop polling when complete or failed
          return data['document_status'] != 'completed' &&
              data['document_status'] != 'failed';
        }
      } catch (e) {
        debugPrint("[v0] Sync status check error: $e");
      }

      return true; // Continue polling
    });
  }

  // Get user documents with sync status
  Future<void> loadUserDocuments(int userId) async {
    try {
      debugPrint("[v0] Loading documents for user $userId");

      final response = await http
          .get(
            Uri.parse(
              "$baseUrl/uploads/user-documents?user_id=$userId&include_sync_status=true",
            ),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        userDocuments = (data['documents'] as List)
            .map((doc) => DocumentSyncStatus.fromJson(doc))
            .toList();

        debugPrint("[v0] Loaded ${userDocuments.length} documents");
        notifyListeners();
      }
    } catch (e) {
      debugPrint("[v0] Error loading documents: $e");
      notifyListeners();
    }
  }

  void clearError() {
    uploadErrorMessage = null;
    notifyListeners();
  }
}

// Models
class GoogleDriveFile {
  final String id;
  final String name;
  final String mimeType;
  final String modifiedTime;
  final int? fileSize;

  GoogleDriveFile({
    required this.id,
    required this.name,
    required this.mimeType,
    required this.modifiedTime,
    this.fileSize,
  });

  factory GoogleDriveFile.fromJson(Map<String, dynamic> json) {
    return GoogleDriveFile(
      id: json['id'],
      name: json['name'],
      mimeType: json['mimeType'],
      modifiedTime: json['modifiedTime'],
      // Drive API size aksar String hota hai, isliye safe parse
      fileSize: json['size'] == null ? null : int.tryParse(json['size'].toString()),
    );
  }
}

class SyncStatus {
  final int documentId;
  final String syncStatus;
  final String? source;
  final String documentStatus;
  final DateTime? lastSynced;

  SyncStatus({
    required this.documentId,
    required this.syncStatus,
    this.source,
    required this.documentStatus,
    this.lastSynced,
  });
}

class DocumentSyncStatus {
  final int id;
  final String filename;
  final String status;
  final DateTime createdAt;
  final String? source;
  final String? syncStatus;
  final String? googleDriveId;
  final DateTime? lastSynced;

  DocumentSyncStatus({
    required this.id,
    required this.filename,
    required this.status,
    required this.createdAt,
    this.source,
    this.syncStatus,
    this.googleDriveId,
    this.lastSynced,
  });

  factory DocumentSyncStatus.fromJson(Map<String, dynamic> json) {
    return DocumentSyncStatus(
      id: json['id'],
      filename: json['filename'],
      status: json['status'],
      createdAt: DateTime.parse(json['created_at']),
      source: json['source'],
      syncStatus: json['sync_status'],
      googleDriveId: json['google_drive_id'],
      lastSynced: json['last_synced'] != null
          ? DateTime.parse(json['last_synced'])
          : null,
    );
  }
}