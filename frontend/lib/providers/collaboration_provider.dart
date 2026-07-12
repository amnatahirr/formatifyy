import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';
import '../config/dev_user_config.dart';

class CollaborationProvider extends ChangeNotifier {
  List<Map<String, dynamic>> projects = [];
  Map<String, dynamic>? currentProject;
  List<Map<String, dynamic>> sections = [];
  List<Map<String, dynamic>> history = [];
  List<Map<String, dynamic>> projectHistory = [];
  /// Cross-project recent commits for the Collaboration hub summary panel.
  List<Map<String, dynamic>> hubActivity = [];
  Map<String, dynamic>? mergeStatus;
  bool loading = false;
  String? error;
  String? lastLiveUpdate;

  int _activeUserId = DevUserConfig.backendUserId;

  /// Bind to the real logged-in user (AuthProvider). DevUserConfig is fallback only.
  void setActiveUserId(int userId) {
    if (_activeUserId != userId) {
      _activeUserId = userId;
      notifyListeners();
    }
  }

  int get activeUserId => _activeUserId;

  String _base(String path) =>
      '${ApiConfig.getBaseUrl()}$path${path.contains('?') ? '&' : '?'}user_id=$activeUserId';

  Future<void> fetchProjects() async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      final resp = await http.get(Uri.parse(_base('/vc/projects')));
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        projects = (data['projects'] as List? ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
      } else {
        error = resp.body;
      }
    } catch (e) {
      error = e.toString();
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>?> createProject({
    required String name,
    required String description,
    required int templateId,
    File? documentFile,
  }) async {
    loading = true;
    notifyListeners();
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse(_base('/vc/projects')),
      );
      request.fields['name'] = name;
      request.fields['description'] = description;
      request.fields['template_id'] = templateId.toString();
      if (documentFile != null) {
        request.files.add(
          await http.MultipartFile.fromPath('file', documentFile.path),
        );
      }

      final streamed = await request.send();
      final body = await streamed.stream.bytesToString();

      if (streamed.statusCode == 200) {
        final project = Map<String, dynamic>.from(jsonDecode(body) as Map);
        await fetchProjects();
        return project;
      }
      error = body;
      return null;
    } catch (e) {
      error = e.toString();
      return null;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<bool> joinProject(String inviteCode) async {
    try {
      final resp = await http.post(
        Uri.parse(_base('/vc/projects/join')),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'invite_code': inviteCode}),
      );
      if (resp.statusCode == 200) {
        currentProject = Map<String, dynamic>.from(jsonDecode(resp.body) as Map);
        sections = (currentProject!['sections'] as List? ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        await fetchProjects();
        notifyListeners();
        return true;
      }
      error = resp.body;
      notifyListeners();
      return false;
    } catch (e) {
      error = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<void> loadProject(int projectId) async {
    loading = true;
    notifyListeners();
    try {
      final resp = await http.get(
        Uri.parse(_base('/vc/projects/$projectId')),
      );
      if (resp.statusCode == 200) {
        currentProject = Map<String, dynamic>.from(jsonDecode(resp.body) as Map);
        sections = (currentProject!['sections'] as List? ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
      } else {
        error = resp.body;
      }
    } catch (e) {
      error = e.toString();
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<bool> inviteMember(int projectId, String email) async {
    final resp = await http.post(
      Uri.parse(_base('/vc/projects/$projectId/invite')),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email}),
    );
    return resp.statusCode == 200;
  }

  /// Upload/re-upload a .docx — creates new versioned import commits (never silent overwrite).
  Future<bool> uploadProjectDocument(int projectId, File documentFile) async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse(_base('/vc/projects/$projectId/document')),
      );
      request.files.add(
        await http.MultipartFile.fromPath('file', documentFile.path),
      );
      final streamed = await request.send();
      final body = await streamed.stream.bytesToString();
      if (streamed.statusCode == 200) {
        currentProject = Map<String, dynamic>.from(jsonDecode(body) as Map);
        sections = (currentProject!['sections'] as List? ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        await loadProjectHistory(projectId);
        await fetchProjects();
        return true;
      }
      error = body;
      return false;
    } catch (e) {
      error = e.toString();
      return false;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<bool> saveSection({
    required int projectId,
    required String sectionId,
    required String content,
    String message = '',
  }) async {
    final resp = await http.post(
      Uri.parse(_base('/vc/projects/$projectId/sections/$sectionId/commit')),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'content': content, 'message': message}),
    );
    if (resp.statusCode == 200) {
      await loadProject(projectId);
      return true;
    }
    error = resp.body;
    notifyListeners();
    return false;
  }

  Future<void> loadHistory(int projectId, String sectionId) async {
    final resp = await http.get(
      Uri.parse(_base('/vc/projects/$projectId/sections/$sectionId/history')),
    );
    if (resp.statusCode == 200) {
      final data = jsonDecode(resp.body) as Map<String, dynamic>;
      history = (data['history'] as List? ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      notifyListeners();
    }
  }

  Future<void> loadProjectHistory(int projectId) async {
    loading = true;
    notifyListeners();
    try {
      final resp = await http.get(
        Uri.parse(_base('/vc/projects/$projectId/history')),
      );
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        projectHistory = (data['history'] as List? ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
      } else {
        error = resp.body;
      }
    } catch (e) {
      error = e.toString();
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  /// Loads recent commits across the user's projects for the hub preview.
  Future<void> loadHubActivitySummary({int maxProjects = 5, int maxItems = 12}) async {
    if (projects.isEmpty) {
      hubActivity = [];
      notifyListeners();
      return;
    }

    final selected = projects.take(maxProjects).toList();
    final collected = <Map<String, dynamic>>[];

    for (final p in selected) {
      final projectId = p['id'] as int?;
      if (projectId == null) continue;
      try {
        final resp = await http.get(
          Uri.parse(_base('/vc/projects/$projectId/history')),
        );
        if (resp.statusCode != 200) continue;
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        final history = (data['history'] as List? ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        for (final c in history) {
          collected.add({
            ...c,
            'project_id': projectId,
            'project_name': p['name'] as String? ?? 'Project',
          });
        }
      } catch (_) {
        // Skip failed project history fetches for hub summary.
      }
    }

    collected.sort((a, b) {
      final aAt = a['created_at'] as String? ?? '';
      final bAt = b['created_at'] as String? ?? '';
      return bAt.compareTo(aAt);
    });
    hubActivity = collected.take(maxItems).toList();
    notifyListeners();
  }

  Future<bool> rollback(int projectId, String sectionId, int commitId) async {
    final resp = await http.post(
      Uri.parse(_base('/vc/projects/$projectId/sections/$sectionId/rollback')),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'commit_id': commitId}),
    );
    if (resp.statusCode == 200) {
      await loadProject(projectId);
      await loadHistory(projectId, sectionId);
      return true;
    }
    return false;
  }

  Future<bool> rollbackFromProjectHistory(
    int projectId,
    String sectionId,
    int commitId,
  ) async {
    final ok = await rollback(projectId, sectionId, commitId);
    if (ok) {
      await loadProjectHistory(projectId);
    }
    return ok;
  }

  Future<List<Map<String, dynamic>>> loadSectionImages(
    int projectId,
    String sectionId,
  ) async {
    final resp = await http.get(
      Uri.parse(_base('/vc/projects/$projectId/sections/$sectionId/images')),
    );
    if (resp.statusCode == 200) {
      final data = jsonDecode(resp.body) as Map<String, dynamic>;
      return (data['images'] as List? ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
    }
    return [];
  }

  Future<Map<String, dynamic>?> uploadSectionImage(
    int projectId,
    String sectionId,
    File imageFile,
  ) async {
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse(_base('/vc/projects/$projectId/sections/$sectionId/images')),
      );
      request.files.add(
        await http.MultipartFile.fromPath('file', imageFile.path),
      );
      final streamed = await request.send();
      final body = await streamed.stream.bytesToString();
      if (streamed.statusCode == 200) {
        return Map<String, dynamic>.from(jsonDecode(body) as Map);
      }
      error = body;
      notifyListeners();
      return null;
    } catch (e) {
      error = e.toString();
      notifyListeners();
      return null;
    }
  }

  Future<bool> deleteSectionImage(
    int projectId,
    String sectionId,
    int imageId,
  ) async {
    final resp = await http.delete(
      Uri.parse(
        _base('/vc/projects/$projectId/sections/$sectionId/images/$imageId'),
      ),
    );
    return resp.statusCode == 200;
  }

  String sectionImageUrl(int projectId, String sectionId, int imageId) =>
      '${ApiConfig.getBaseUrl()}/vc/projects/$projectId/sections/$sectionId/images/$imageId?user_id=$activeUserId';

  Future<Map<String, dynamic>?> startMerge(int projectId) async {
    loading = true;
    notifyListeners();
    try {
      final resp = await http.post(
        Uri.parse(_base('/vc/projects/$projectId/merge')),
      );
      if (resp.statusCode == 200) {
        mergeStatus = Map<String, dynamic>.from(jsonDecode(resp.body) as Map);
        return mergeStatus;
      }
      error = resp.body;
      return null;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> loadMergeStatus(int projectId, int mergeId) async {
    final resp = await http.get(
      Uri.parse(_base('/vc/projects/$projectId/merge/$mergeId')),
    );
    if (resp.statusCode == 200) {
      mergeStatus = Map<String, dynamic>.from(jsonDecode(resp.body) as Map);
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>?> resolveConflict({
    required int projectId,
    required int mergeId,
    required int conflictId,
    required String resolutionContent,
  }) async {
    final resp = await http.post(
      Uri.parse(
        _base('/vc/projects/$projectId/merge/$mergeId/resolve/$conflictId'),
      ),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'resolution_content': resolutionContent}),
    );
    if (resp.statusCode == 200) {
      final result = Map<String, dynamic>.from(jsonDecode(resp.body) as Map);
      await loadMergeStatus(projectId, mergeId);
      return result;
    }
    return null;
  }

  Future<Map<String, dynamic>?> completeMerge(int projectId, int mergeId) async {
    loading = true;
    notifyListeners();
    try {
      final resp = await http.post(
        Uri.parse(_base('/vc/projects/$projectId/merge/$mergeId/complete')),
      );
      if (resp.statusCode == 200) {
        final result = Map<String, dynamic>.from(jsonDecode(resp.body) as Map);
        mergeStatus = result;
        await loadProject(projectId);
        return result;
      }
      error = resp.body;
      return null;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  void applyLiveUpdate(Map<String, dynamic> event) {
    final sectionId = event['section_id'] as String?;
    if (sectionId == null) return;
    lastLiveUpdate =
        '${event['author_name']} updated $sectionId (v${event['version_number']})';
    final idx = sections.indexWhere((s) => s['section_id'] == sectionId);
    if (idx >= 0) {
      sections[idx] = {
        ...sections[idx],
        'latest_author': event['author_name'],
        'latest_version': event['version_number'],
        'latest_updated_at': event['timestamp'],
      };
    }
    notifyListeners();
  }

  String downloadUrl(int projectId, {int? mergeId}) {
    var url =
        '${ApiConfig.getBaseUrl()}/vc/projects/$projectId/download?user_id=$activeUserId';
    if (mergeId != null) url += '&merge_id=$mergeId';
    return url;
  }
}
