int _asInt(dynamic value, [int fallback = 0]) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse('$value') ?? fallback;
}

int? _asIntOrNull(dynamic value) {
  if (value == null) return null;
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse('$value');
}

double _asDouble(dynamic value, [double fallback = 0]) {
  if (value is double) return value;
  if (value is num) return value.toDouble();
  return double.tryParse('$value') ?? fallback;
}

List<String> _asStringList(dynamic value) {
  if (value is List) {
    return value.map((item) => item.toString().trim()).where((item) => item.isNotEmpty).toList();
  }
  if (value is String && value.trim().isNotEmpty) {
    return value.split(',').map((item) => item.trim()).where((item) => item.isNotEmpty).toList();
  }
  return const [];
}

class SupervisorGroupSummary {
  final int id;
  final String title;
  final String projectTitle;
  final String status;
  final double progress;
  final List<String> memberNames;
  final String deadlineDate;
  final bool isBehind;

  const SupervisorGroupSummary({
    required this.id,
    required this.title,
    required this.projectTitle,
    required this.status,
    required this.progress,
    required this.memberNames,
    required this.deadlineDate,
    required this.isBehind,
  });

  String get membersLabel => memberNames.isEmpty ? '—' : memberNames.join(', ');

  factory SupervisorGroupSummary.fromJson(Map<String, dynamic> json) {
    final rawProgress = _asDouble(json['progress']);
    final progress = rawProgress.clamp(0, 100).toDouble();
    return SupervisorGroupSummary(
      id: _asInt(json['id']),
      title: (json['title'] ?? '').toString(),
      projectTitle: (json['project_title'] ?? '').toString(),
      status: (json['status'] ?? 'accepted').toString(),
      progress: progress,
      memberNames: _asStringList(json['member_names']),
      deadlineDate: (json['deadline_date'] ?? '').toString(),
      isBehind: json['is_behind'] == true || json['track_status']?.toString() == 'behind',
    );
  }
}

class SupervisorHomeModel {
  final int supervisorId;
  final String supervisorName;
  final int pendingAssignmentRequests;
  final int documentsToReview;
  final int unreadReplies;
  final List<SupervisorGroupSummary> groups;

  const SupervisorHomeModel({
    required this.supervisorId,
    required this.supervisorName,
    required this.pendingAssignmentRequests,
    required this.documentsToReview,
    required this.unreadReplies,
    required this.groups,
  });

  factory SupervisorHomeModel.fromJson(Map<String, dynamic> json) => SupervisorHomeModel(
        supervisorId: _asInt(json['supervisor_id']),
        supervisorName: (json['supervisor_name'] ?? '').toString(),
        pendingAssignmentRequests: _asInt(json['pending_assignment_requests']),
        documentsToReview: _asInt(json['documents_to_review']),
        unreadReplies: _asInt(json['unread_replies']),
        groups: List<Map<String, dynamic>>.from(json['groups'] ?? const [])
            .map(SupervisorGroupSummary.fromJson)
            .toList(),
      );
}

class AssignmentRequestModel {
  final int id;
  final String groupName;
  final String projectTitle;
  final String studentLeaderName;
  final String studentLeaderEmail;
  final List<String> memberNames;
  final int? departmentId;
  final String departmentName;
  final String departmentCode;
  final String status;
  final String rejectionReason;
  final int? fypGroupId;

  const AssignmentRequestModel({
    required this.id,
    required this.groupName,
    required this.projectTitle,
    required this.studentLeaderName,
    required this.studentLeaderEmail,
    required this.memberNames,
    required this.departmentId,
    required this.departmentName,
    required this.departmentCode,
    required this.status,
    required this.rejectionReason,
    required this.fypGroupId,
  });

  String get topic => projectTitle;
  String get departmentLabel {
    if (departmentName.isNotEmpty && departmentCode.isNotEmpty) {
      return '$departmentName ($departmentCode)';
    }
    if (departmentName.isNotEmpty) return departmentName;
    if (departmentCode.isNotEmpty) return departmentCode;
    return '—';
  }

  factory AssignmentRequestModel.fromJson(Map<String, dynamic> json) {
    final members = _asStringList(json['member_names']);
    final leader = (json['student_leader_name'] ?? '').toString();
    return AssignmentRequestModel(
      id: _asInt(json['id']),
      groupName: (json['group_name'] ?? '').toString(),
      projectTitle: (json['project_title'] ?? json['topic'] ?? '').toString(),
      studentLeaderName: leader,
      studentLeaderEmail: (json['student_leader_email'] ?? '').toString(),
      memberNames: members.isNotEmpty ? members : (leader.isEmpty ? const [] : [leader]),
      departmentId: json['department_id'] == null ? null : _asInt(json['department_id']),
      departmentName: (json['department_name'] ?? '').toString(),
      departmentCode: (json['department_code'] ?? '').toString(),
      status: (json['status'] ?? 'pending').toString(),
      rejectionReason: (json['rejection_reason'] ?? '').toString(),
      fypGroupId: json['fyp_group_id'] == null ? null : _asInt(json['fyp_group_id']),
    );
  }
}

class GroupMilestoneModel {
  final int id;
  final String name;
  final int sortOrder;
  final bool isCompleted;

  const GroupMilestoneModel({
    required this.id,
    required this.name,
    required this.sortOrder,
    required this.isCompleted,
  });

  factory GroupMilestoneModel.fromJson(Map<String, dynamic> json) => GroupMilestoneModel(
        id: _asInt(json['id']),
        name: (json['name'] ?? '').toString(),
        sortOrder: _asInt(json['sort_order']),
        isCompleted: json['is_completed'] == true || json['is_completed'] == 1,
      );
}

class GroupDocumentSummary {
  final int id;
  final String title;
  final String filename;
  final String status;
  final String submittedAt;

  const GroupDocumentSummary({
    required this.id,
    required this.title,
    required this.filename,
    required this.status,
    required this.submittedAt,
  });

  String get statusLabel {
    switch (status.toLowerCase()) {
      case 'approved':
        return 'Approved';
      case 'revision':
        return 'Revision';
      default:
        return 'Pending';
    }
  }

  factory GroupDocumentSummary.fromJson(Map<String, dynamic> json) => GroupDocumentSummary(
        id: _asInt(json['id']),
        title: (json['title'] ?? '').toString(),
        filename: (json['filename'] ?? '').toString(),
        status: (json['status'] ?? 'pending').toString().toLowerCase(),
        submittedAt: (json['submitted_at'] ?? '').toString(),
      );
}

class SupervisorGroupDetailModel {
  final SupervisorGroupSummary group;
  final List<GroupMilestoneModel> milestones;
  final GroupDocumentSummary? latestDocument;

  const SupervisorGroupDetailModel({
    required this.group,
    required this.milestones,
    required this.latestDocument,
  });

  factory SupervisorGroupDetailModel.fromJson(Map<String, dynamic> json) {
    final groupJson = Map<String, dynamic>.from(json['group'] as Map? ?? const {});
    return SupervisorGroupDetailModel(
      group: SupervisorGroupSummary.fromJson(groupJson),
      milestones: List<Map<String, dynamic>>.from(json['milestones'] ?? const [])
          .map(GroupMilestoneModel.fromJson)
          .toList(),
      latestDocument: json['latest_document'] == null
          ? null
          : GroupDocumentSummary.fromJson(Map<String, dynamic>.from(json['latest_document'] as Map)),
    );
  }
}

class DocumentCommentModel {
  final int id;
  final String commentText;
  final bool isResolved;
  final String createdAt;
  final String resolvedAt;
  final int? supervisorId;
  final int? parentCommentId;

  const DocumentCommentModel({
    required this.id,
    required this.commentText,
    required this.isResolved,
    required this.createdAt,
    this.resolvedAt = '',
    this.supervisorId,
    this.parentCommentId,
  });

  factory DocumentCommentModel.fromJson(Map<String, dynamic> json) => DocumentCommentModel(
        id: _asInt(json['id']),
        commentText: (json['comment_text'] ?? '').toString(),
        isResolved: json['is_resolved'] == true || json['is_resolved'] == 1,
        createdAt: (json['created_at'] ?? '').toString(),
        resolvedAt: (json['resolved_at'] ?? '').toString(),
        supervisorId: json['supervisor_id'] == null ? null : _asInt(json['supervisor_id']),
        parentCommentId:
            json['parent_comment_id'] == null ? null : _asInt(json['parent_comment_id']),
      );
}

class DocumentParagraphModel {
  final int id;
  final int sortOrder;
  final String text;
  final String highlight;
  final bool hasUnresolvedComments;
  final List<DocumentCommentModel> comments;

  const DocumentParagraphModel({
    required this.id,
    required this.sortOrder,
    required this.text,
    required this.highlight,
    required this.hasUnresolvedComments,
    required this.comments,
  });

  factory DocumentParagraphModel.fromJson(Map<String, dynamic> json) => DocumentParagraphModel(
        id: _asInt(json['id']),
        sortOrder: _asInt(json['sort_order']),
        text: (json['text'] ?? '').toString(),
        highlight: (json['highlight'] ?? 'none').toString(),
        hasUnresolvedComments: json['has_unresolved_comments'] == true,
        comments: List<Map<String, dynamic>>.from(json['comments'] ?? const [])
            .map(DocumentCommentModel.fromJson)
            .toList(),
      );
}

class DocumentReviewModel {
  final int groupId;
  final String groupTitle;
  final GroupDocumentSummary document;
  final List<DocumentParagraphModel> paragraphs;

  const DocumentReviewModel({
    required this.groupId,
    required this.groupTitle,
    required this.document,
    required this.paragraphs,
  });

  factory DocumentReviewModel.fromJson(Map<String, dynamic> json) => DocumentReviewModel(
        groupId: _asInt(json['group_id']),
        groupTitle: (json['group_title'] ?? '').toString(),
        document: GroupDocumentSummary.fromJson(Map<String, dynamic>.from(json['document'] as Map)),
        paragraphs: List<Map<String, dynamic>>.from(json['paragraphs'] ?? const [])
            .map(DocumentParagraphModel.fromJson)
            .toList(),
      );
}

class AnalysisIssueModel {
  final String function;
  final String severity;
  final String reason;
  final String original;
  final String suggestion;
  final double? similarity;

  const AnalysisIssueModel({
    required this.function,
    required this.severity,
    required this.reason,
    required this.original,
    required this.suggestion,
    required this.similarity,
  });

  factory AnalysisIssueModel.fromJson(Map<String, dynamic> json) {
    final sim = json['similarity'];
    return AnalysisIssueModel(
      function: (json['function'] ?? '').toString(),
      severity: (json['severity'] ?? 'minor').toString(),
      reason: (json['reason'] ?? json['description'] ?? json['message'] ?? '').toString(),
      original: (json['original'] ?? '').toString(),
      suggestion: (json['suggestion'] ?? '').toString(),
      similarity: sim == null ? null : _asDouble(sim),
    );
  }
}

class AnalysisSummaryModel {
  final int grammarIssues;
  final int plagiarismIssues;
  final double plagiarismScore;
  final int totalIssues;
  final int majorIssues;
  final int minorIssues;
  final double complianceScore;
  final String structureStatus;

  const AnalysisSummaryModel({
    required this.grammarIssues,
    required this.plagiarismIssues,
    required this.plagiarismScore,
    required this.totalIssues,
    required this.majorIssues,
    required this.minorIssues,
    required this.complianceScore,
    required this.structureStatus,
  });

  factory AnalysisSummaryModel.fromJson(Map<String, dynamic> json) => AnalysisSummaryModel(
        grammarIssues: _asInt(json['grammar_issues']),
        plagiarismIssues: _asInt(json['plagiarism_issues']),
        plagiarismScore: _asDouble(json['plagiarism_score']),
        totalIssues: _asInt(json['total_issues']),
        majorIssues: _asInt(json['major_issues']),
        minorIssues: _asInt(json['minor_issues']),
        complianceScore: _asDouble(json['compliance_score']),
        structureStatus: (json['structure_status'] ?? '').toString(),
      );
}

class FinalSubmissionModel {
  final int id;
  final int groupId;
  final String groupTitle;
  final String projectTitle;
  final String title;
  final String filename;
  final String status;
  final String submittedAt;
  final String decisionNote;
  final int? sourceDocumentId;
  final int? groupDocumentId;
  final AnalysisSummaryModel analysisSummary;
  final List<AnalysisIssueModel> grammarIssues;
  final List<AnalysisIssueModel> plagiarismIssues;

  const FinalSubmissionModel({
    required this.id,
    required this.groupId,
    required this.groupTitle,
    required this.projectTitle,
    required this.title,
    required this.filename,
    required this.status,
    required this.submittedAt,
    required this.decisionNote,
    this.sourceDocumentId,
    this.groupDocumentId,
    required this.analysisSummary,
    required this.grammarIssues,
    required this.plagiarismIssues,
  });

  bool get canPreviewInApp => groupDocumentId != null;

  String get statusLabel {
    switch (status.toLowerCase()) {
      case 'approved':
        return 'Approved';
      case 'revision':
        return 'Revision';
      case 'rejected':
        return 'Rejected';
      default:
        return 'Pending';
    }
  }

  factory FinalSubmissionModel.fromJson(Map<String, dynamic> json) {
    final summaryJson = Map<String, dynamic>.from(json['analysis_summary'] as Map? ?? const {});
    return FinalSubmissionModel(
      id: _asInt(json['id']),
      groupId: _asInt(json['group_id']),
      groupTitle: (json['group_title'] ?? '').toString(),
      projectTitle: (json['project_title'] ?? '').toString(),
      title: (json['title'] ?? '').toString(),
      filename: (json['filename'] ?? '').toString(),
      status: (json['status'] ?? 'pending').toString(),
      submittedAt: (json['submitted_at'] ?? '').toString(),
      decisionNote: (json['decision_note'] ?? '').toString(),
      sourceDocumentId: _asIntOrNull(json['source_document_id']),
      groupDocumentId: _asIntOrNull(json['group_document_id']),
      analysisSummary: AnalysisSummaryModel.fromJson(summaryJson),
      grammarIssues: List<Map<String, dynamic>>.from(json['grammar_issues'] ?? const [])
          .map(AnalysisIssueModel.fromJson)
          .toList(),
      plagiarismIssues: List<Map<String, dynamic>>.from(json['plagiarism_issues'] ?? const [])
          .map(AnalysisIssueModel.fromJson)
          .toList(),
    );
  }
}

class PlagiarismMatchModel {
  final String source;
  final double similarity;
  final String sentence;
  final String matchType;
  final String severity;
  final String reason;

  const PlagiarismMatchModel({
    required this.source,
    required this.similarity,
    required this.sentence,
    required this.matchType,
    required this.severity,
    required this.reason,
  });

  factory PlagiarismMatchModel.fromJson(Map<String, dynamic> json) => PlagiarismMatchModel(
        source: (json['source'] ?? 'Unknown source').toString(),
        similarity: _asDouble(json['similarity']),
        sentence: (json['sentence'] ?? '').toString(),
        matchType: (json['match_type'] ?? '').toString(),
        severity: (json['severity'] ?? 'minor').toString(),
        reason: (json['reason'] ?? '').toString(),
      );
}

class PlagiarismMonitorGroup {
  final int groupId;
  final String title;
  final String projectTitle;
  final double progress;
  final double plagiarismScore;
  final String riskLevel;
  final int matchCount;
  final String dataSource;
  final List<String> memberNames;
  final List<PlagiarismMatchModel> matches;

  const PlagiarismMonitorGroup({
    required this.groupId,
    required this.title,
    required this.projectTitle,
    required this.progress,
    required this.plagiarismScore,
    required this.riskLevel,
    required this.matchCount,
    required this.dataSource,
    required this.memberNames,
    required this.matches,
  });

  factory PlagiarismMonitorGroup.fromJson(Map<String, dynamic> json) => PlagiarismMonitorGroup(
        groupId: _asInt(json['group_id']),
        title: (json['title'] ?? '').toString(),
        projectTitle: (json['project_title'] ?? '').toString(),
        progress: _asDouble(json['progress']),
        plagiarismScore: _asDouble(json['plagiarism_score']),
        riskLevel: (json['risk_level'] ?? 'safe').toString(),
        matchCount: _asInt(json['match_count']),
        dataSource: (json['data_source'] ?? '').toString(),
        memberNames: _asStringList(json['member_names']),
        matches: List<Map<String, dynamic>>.from(json['matches'] ?? const [])
            .map(PlagiarismMatchModel.fromJson)
            .toList(),
      );
}

class MeetingNoteModel {
  final int id;
  final int groupId;
  final int? supervisorId;
  final String meetingDate;
  final String topic;
  final String actionItems;
  final String createdAt;
  final String groupTitle;
  final String projectTitle;
  final String supervisorName;

  const MeetingNoteModel({
    required this.id,
    required this.groupId,
    this.supervisorId,
    required this.meetingDate,
    required this.topic,
    required this.actionItems,
    required this.createdAt,
    required this.groupTitle,
    required this.projectTitle,
    required this.supervisorName,
  });

  factory MeetingNoteModel.fromJson(Map<String, dynamic> json) => MeetingNoteModel(
        id: _asInt(json['id']),
        groupId: _asInt(json['group_id']),
        // Schema uses supervisor_id (not created_by).
        supervisorId: json['supervisor_id'] == null
            ? null
            : _asInt(json['supervisor_id']),
        meetingDate: (json['meeting_date'] ?? '').toString(),
        topic: (json['topic'] ?? '').toString(),
        actionItems: (json['action_items'] ?? '').toString(),
        createdAt: (json['created_at'] ?? '').toString(),
        groupTitle: (json['group_title'] ?? '').toString(),
        projectTitle: (json['project_title'] ?? '').toString(),
        supervisorName: (json['supervisor_name'] ?? '').toString(),
      );
}
