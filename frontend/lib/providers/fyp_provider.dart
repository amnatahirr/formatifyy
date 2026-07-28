import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../config/api_config.dart';

/// Holds FYP assignment-request state for the student Choose Supervisor flow.
class FypProvider extends ChangeNotifier {
  late final String _baseUrl;

  FypProvider() {
    _baseUrl = ApiConfig.getBaseUrl();
  }

  List<Map<String, dynamic>> _supervisors = [];
  List<Map<String, dynamic>> _departments = [];
  List<Map<String, dynamic>> _requests = [];
  Map<String, dynamic>? _assignmentStatus;
  int? _fypGroupId;
  List<Map<String, dynamic>> _milestones = [];
  Map<String, dynamic>? _plagiarismReport;
  List<Map<String, dynamic>> _submissions = [];
  Map<String, dynamic>? _latestSubmission;
  Map<String, dynamic>? _semesterDeadline;
  bool _isLoading = false;
  bool _isSubmitting = false;
  bool _isStatusLoading = false;
  bool _isMilestonesLoading = false;
  bool _isPlagiarismLoading = false;
  bool _isSubmissionsLoading = false;
  bool _isSemesterDeadlineLoading = false;
  String? _errorMessage;

  List<Map<String, dynamic>> get supervisors => _supervisors;
  List<Map<String, dynamic>> get departments => _departments;
  List<Map<String, dynamic>> get requests => _requests;
  Map<String, dynamic>? get assignmentStatus => _assignmentStatus;
  /// Cached group id from an accepted assignment — key for other FYP screens.
  int? get fypGroupId => _fypGroupId;

  /// True when student already has a pending or accepted supervisor request.
  /// Used to hide "Choose Supervisor" from the dashboard.
  bool get hasChosenSupervisor {
    if (_fypGroupId != null) return true;
    final status = (_assignmentStatus?['status'] ?? '').toString().toLowerCase();
    return status == 'pending' || status == 'accepted';
  }

  /// Show Choose Supervisor only when none exists or the last request was rejected.
  bool get canChooseSupervisor => !hasChosenSupervisor;
  List<Map<String, dynamic>> get milestones => _milestones;
  Map<String, dynamic>? get plagiarismReport => _plagiarismReport;
  List<Map<String, dynamic>> get submissions => _submissions;
  Map<String, dynamic>? get latestSubmission => _latestSubmission;
  /// Admin global semester deadline for this student's current_semester.
  Map<String, dynamic>? get semesterDeadline => _semesterDeadline;
  bool get isLoading => _isLoading;
  bool get isSubmitting => _isSubmitting;
  bool get isStatusLoading => _isStatusLoading;
  bool get isMilestonesLoading => _isMilestonesLoading;
  bool get isPlagiarismLoading => _isPlagiarismLoading;
  bool get isSubmissionsLoading => _isSubmissionsLoading;
  bool get isSemesterDeadlineLoading => _isSemesterDeadlineLoading;
  String? get errorMessage => _errorMessage;

  void setFypGroupId(int? groupId) {
    if (_fypGroupId == groupId) return;
    _fypGroupId = groupId;
    notifyListeners();
  }

  List<Map<String, dynamic>> supervisorsForDepartment(int? departmentId) {
    if (departmentId == null) return _supervisors;
    return _supervisors
        .where((s) => s['department_id'] == departmentId)
        .toList();
  }

  Uri _uri(String path, [Map<String, dynamic>? query]) {
    final filtered = <String, String>{};
    query?.forEach((key, value) {
      if (value != null && value.toString().isNotEmpty) {
        filtered[key] = value.toString();
      }
    });
    return Uri.parse('$_baseUrl$path').replace(queryParameters: filtered);
  }

  /// Yield so notifyListeners never runs in the same sync turn as a widget build.
  Future<void> _notifyAfterAsyncGap() async {
    await Future<void>.delayed(Duration.zero);
    notifyListeners();
  }

  Future<void> fetchSupervisors(int userId) async {
    _isLoading = true;
    _errorMessage = null;
    await _notifyAfterAsyncGap();
    try {
      final response = await http.get(
        _uri('/student/supervisors', {'user_id': userId}),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        _supervisors = List<Map<String, dynamic>>.from(
          (data['supervisors'] as List? ?? const []).map(
            (e) => Map<String, dynamic>.from(e as Map),
          ),
        );
        _departments = List<Map<String, dynamic>>.from(
          (data['departments'] as List? ?? const []).map(
            (e) => Map<String, dynamic>.from(e as Map),
          ),
        );
      } else {
        _errorMessage = _detail(response.body) ?? 'Failed to load supervisors';
      }
    } catch (e) {
      _errorMessage = 'Network error: $e';
      debugPrint('[FypProvider] fetchSupervisors error: $e');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> fetchMyRequests(int userId) async {
    try {
      final response = await http.get(
        _uri('/student/assignment-requests', {'user_id': userId}),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        _requests = List<Map<String, dynamic>>.from(
          (data['requests'] as List? ?? const []).map(
            (e) => Map<String, dynamic>.from(e as Map),
          ),
        );
        notifyListeners();
      }
    } catch (e) {
      debugPrint('[FypProvider] fetchMyRequests error: $e');
    }
  }

  /// Latest assignment status for [email] (student_leader_email match).
  /// When accepted, caches [fypGroupId] for other FYP screens.
  Future<Map<String, dynamic>?> fetchAssignmentStatus({
    required int userId,
    required String email,
  }) async {
    _isStatusLoading = true;
    _errorMessage = null;
    await _notifyAfterAsyncGap();
    try {
      final response = await http.get(
        _uri('/student/assignment-requests/status', {
          'user_id': userId,
          'email': email.trim(),
        }),
      );
      if (response.statusCode == 200) {
        final data = Map<String, dynamic>.from(jsonDecode(response.body) as Map);
        _assignmentStatus = data;
        final status = (data['status'] ?? '').toString().toLowerCase();
        final groupId = data['fyp_group_id'];
        if (status == 'accepted' && groupId is int) {
          _fypGroupId = groupId;
        } else if (status == 'accepted' && groupId != null) {
          _fypGroupId = int.tryParse(groupId.toString());
        }
        return data;
      }
      _errorMessage = _detail(response.body) ?? 'Failed to load status';
      return null;
    } catch (e) {
      _errorMessage = 'Network error: $e';
      debugPrint('[FypProvider] fetchAssignmentStatus error: $e');
      return null;
    } finally {
      _isStatusLoading = false;
      notifyListeners();
    }
  }

  /// Load group_milestones for [groupId] (same fields as supervisor group detail).
  Future<List<Map<String, dynamic>>> fetchMilestones({
    required int userId,
    required int groupId,
  }) async {
    _isMilestonesLoading = true;
    _errorMessage = null;
    await _notifyAfterAsyncGap();
    try {
      final response = await http.get(
        _uri('/student/groups/$groupId/milestones', {'user_id': userId}),
      );
      if (response.statusCode == 200) {
        final data = Map<String, dynamic>.from(jsonDecode(response.body) as Map);
        _milestones = List<Map<String, dynamic>>.from(
          (data['milestones'] as List? ?? const []).map(
            (e) => Map<String, dynamic>.from(e as Map),
          ),
        );
        return _milestones;
      }
      _errorMessage = _detail(response.body) ?? 'Failed to load milestones';
      _milestones = [];
      return const [];
    } catch (e) {
      _errorMessage = 'Network error: $e';
      _milestones = [];
      debugPrint('[FypProvider] fetchMilestones error: $e');
      return const [];
    } finally {
      _isMilestonesLoading = false;
      notifyListeners();
    }
  }

  /// Latest plagiarism snapshot for [groupId] from final_submissions.analysis_report.
  Future<Map<String, dynamic>?> fetchPlagiarismReport({
    required int userId,
    required int groupId,
  }) async {
    _isPlagiarismLoading = true;
    _errorMessage = null;
    await _notifyAfterAsyncGap();
    try {
      final response = await http.get(
        _uri('/student/groups/$groupId/plagiarism', {'user_id': userId}),
      );
      if (response.statusCode == 200) {
        _plagiarismReport =
            Map<String, dynamic>.from(jsonDecode(response.body) as Map);
        return _plagiarismReport;
      }
      _errorMessage = _detail(response.body) ?? 'Failed to load plagiarism report';
      _plagiarismReport = null;
      return null;
    } catch (e) {
      _errorMessage = 'Network error: $e';
      _plagiarismReport = null;
      debugPrint('[FypProvider] fetchPlagiarismReport error: $e');
      return null;
    } finally {
      _isPlagiarismLoading = false;
      notifyListeners();
    }
  }

  /// Status Tracker: final_submissions for [groupId].
  Future<List<Map<String, dynamic>>> fetchSubmissions({
    required int userId,
    required int groupId,
  }) async {
    _isSubmissionsLoading = true;
    _errorMessage = null;
    await _notifyAfterAsyncGap();
    try {
      final response = await http.get(
        _uri('/student/groups/$groupId/submissions', {'user_id': userId}),
      );
      if (response.statusCode == 200) {
        final data = Map<String, dynamic>.from(jsonDecode(response.body) as Map);
        _submissions = List<Map<String, dynamic>>.from(
          (data['submissions'] as List? ?? const []).map(
            (e) => Map<String, dynamic>.from(e as Map),
          ),
        );
        final latest = data['latest'];
        _latestSubmission = latest is Map
            ? Map<String, dynamic>.from(latest)
            : (_submissions.isNotEmpty ? _submissions.first : null);
        return _submissions;
      }
      _errorMessage = _detail(response.body) ?? 'Failed to load submissions';
      _submissions = [];
      _latestSubmission = null;
      return const [];
    } catch (e) {
      _errorMessage = 'Network error: $e';
      _submissions = [];
      _latestSubmission = null;
      debugPrint('[FypProvider] fetchSubmissions error: $e');
      return const [];
    } finally {
      _isSubmissionsLoading = false;
      notifyListeners();
    }
  }

  /// Admin-managed global deadline for this student's `current_semester`.
  Future<Map<String, dynamic>?> fetchSemesterDeadline({
    required int userId,
  }) async {
    _isSemesterDeadlineLoading = true;
    await _notifyAfterAsyncGap();
    try {
      final response = await http.get(
        _uri('/student/semester-deadline', {'user_id': userId}),
      );
      if (response.statusCode == 200) {
        _semesterDeadline =
            Map<String, dynamic>.from(jsonDecode(response.body) as Map);
        return _semesterDeadline;
      }
      _semesterDeadline = null;
      return null;
    } catch (e) {
      _semesterDeadline = null;
      debugPrint('[FypProvider] fetchSemesterDeadline error: $e');
      return null;
    } finally {
      _isSemesterDeadlineLoading = false;
      notifyListeners();
    }
  }

  /// Creates a pending assignment request. Returns the created request map on success.
  Future<Map<String, dynamic>?> createAssignmentRequest({
    required int userId,
    required int supervisorId,
    required String groupName,
    required String projectTitle,
    required String studentLeaderName,
    required String studentLeaderEmail,
    required List<String> memberNames,
    int? departmentId,
    String? cosupervisorName,
  }) async {
    _isSubmitting = true;
    _errorMessage = null;
    await _notifyAfterAsyncGap();
    try {
      final response = await http.post(
        _uri('/student/assignment-requests', {'user_id': userId}),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'supervisor_id': supervisorId,
          'group_name': groupName,
          'project_title': projectTitle,
          'student_leader_name': studentLeaderName,
          'student_leader_email': studentLeaderEmail,
          'member_names': memberNames,
          'department_id': departmentId,
          if (cosupervisorName != null && cosupervisorName.trim().isNotEmpty)
            'cosupervisor_name': cosupervisorName.trim(),
        }),
      );
      final body = response.body.isEmpty ? null : jsonDecode(response.body);
      if (response.statusCode >= 200 && response.statusCode < 300) {
        final map = Map<String, dynamic>.from(body as Map);
        final request = Map<String, dynamic>.from(map['request'] as Map);
        _requests = [request, ..._requests];
        // Immediately mark as chosen so Choose Supervisor disappears from nav.
        _assignmentStatus = {
          'found': true,
          'status': 'pending',
          'id': request['id'],
          'group_name': request['group_name'] ?? groupName,
          'project_title': request['project_title'] ?? projectTitle,
          'supervisor_id': request['supervisor_id'] ?? supervisorId,
          'supervisor_name': request['supervisor_name'] ?? '',
          'cosupervisor_name': request['cosupervisor_name'] ?? cosupervisorName ?? '',
          'fyp_group_id': null,
          'rejection_reason': '',
        };
        return request;
      }
      _errorMessage = body is Map && body['detail'] != null
          ? body['detail'].toString()
          : 'Failed to submit request (${response.statusCode})';
      return null;
    } catch (e) {
      _errorMessage = 'Network error: $e';
      debugPrint('[FypProvider] createAssignmentRequest error: $e');
      return null;
    } finally {
      _isSubmitting = false;
      notifyListeners();
    }
  }

  String? _detail(String body) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map && decoded['detail'] != null) {
        return decoded['detail'].toString();
      }
    } catch (_) {}
    return body.trim().isEmpty ? null : body;
  }
}
