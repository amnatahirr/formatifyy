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

// ─────────────────────────────────────────────────────────────────────────────
// Extra helpers for rich document blocks (tables, images, styles, runs)
// ─────────────────────────────────────────────────────────────────────────────

/// First non-null value found under any of [keys].
dynamic _pick(Map<String, dynamic> json, List<String> keys) {
  for (final k in keys) {
    if (json.containsKey(k) && json[k] != null) return json[k];
  }
  return null;
}

String? _asStringOrNull(dynamic value) {
  if (value == null) return null;
  final s = value.toString();
  return s.isEmpty ? null : s;
}

double? _asDoubleOrNull(dynamic value) {
  if (value == null) return null;
  if (value is num) return value.toDouble();
  return double.tryParse('$value');
}

bool? _asBoolOrNull(dynamic value) {
  if (value == null) return null;
  if (value is bool) return value;
  if (value is num) return value != 0;
  final s = value.toString().toLowerCase();
  if (s == 'true' || s == '1') return true;
  if (s == 'false' || s == '0') return false;
  return null;
}

/// List of JSON objects, silently skipping anything that is not a map.
List<Map<String, dynamic>> _asMapList(dynamic value) {
  if (value is! List) return const [];
  return value.whereType<Map>().map((m) => Map<String, dynamic>.from(m)).toList();
}

/// Table rows: List<List<cell>>, where a cell is a String or a Map.
List<List<dynamic>> _asTableRows(dynamic value) {
  if (value is! List) return const [];
  final rows = <List<dynamic>>[];
  for (final row in value) {
    if (row is List) {
      rows.add(
        row.map((c) => c is Map ? Map<String, dynamic>.from(c) : (c ?? '').toString()).toList(),
      );
    }
  }
  return rows;
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
  final int? currentSemester;
  final bool isGraduated;

  const SupervisorGroupSummary({
    required this.id,
    required this.title,
    required this.projectTitle,
    required this.status,
    required this.progress,
    required this.memberNames,
    required this.deadlineDate,
    required this.isBehind,
    this.currentSemester,
    this.isGraduated = false,
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
      currentSemester: _asIntOrNull(json['current_semester']),
      isGraduated: json['is_graduated'] == true || json['is_graduated'] == 1,
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

  // Additional milestone properties
  final int? semester;
  final String phase;
  final String? deadlineDate;
  final String status;
  final int? daysLeft;
  final String reworkNote;
  final bool extended;
  final bool isManaged;

  const GroupMilestoneModel({
    required this.id,
    required this.name,
    required this.sortOrder,
    required this.isCompleted,
    this.semester,
    this.phase = '',
    this.deadlineDate,
    this.status = 'pending',
    this.daysLeft,
    this.reworkNote = '',
    this.extended = false,
    this.isManaged = false,
  });

  factory GroupMilestoneModel.fromJson(
    Map<String, dynamic> json,
  ) =>
      GroupMilestoneModel(
        id: _asInt(json['id']),
        name: (json['name'] ?? '').toString(),
        sortOrder: _asInt(json['sort_order']),
        isCompleted: json['is_completed'] == true ||
            json['is_completed'] == 1,
        semester: _asIntOrNull(json['semester']),
        phase: (json['phase'] ?? '').toString(),
        deadlineDate: _asStringOrNull(json['deadline_date']),
        status: (json['status'] ??
                ((json['is_completed'] == true ||
                        json['is_completed'] == 1)
                    ? 'completed'
                    : 'pending'))
            .toString(),
        daysLeft: _asIntOrNull(json['days_left']),
        reworkNote: (json['rework_note'] ?? '').toString(),
        extended: json['extended'] == true ||
            json['extended'] == 1,
        isManaged: json['is_managed'] == true ||
            json['is_managed'] == 1,
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

/// One block of a submitted document: paragraph, heading, list item,
/// table, image or table-of-contents entry.
///
/// Every formatting field is optional, so older backend responses that only
/// send `text` / `block_type` / `block_label` keep working. Keys are accepted
/// in snake_case (preferred) and camelCase.
class DocumentParagraphModel {
  final int id;
  final int sortOrder;
  final int displayIndex;
  final String text;

  /// paragraph | heading | subheading | bullet | line | table | image | toc
  final String blockType;
  final String blockLabel;
  final String highlight;
  final bool hasUnresolvedComments;
  final List<DocumentCommentModel> comments;

  // ── Word formatting (all optional) ──
  final String? styleName; // "Heading 1", "Title", "TOC 2", "List Bullet" ...
  final double? fontSize; // points
  final bool? isBold;
  final bool? isItalic;
  final bool? isUnderline;
  final String? alignment; // left | center | right | justify
  final String? fontName;
  final String? colorHex; // "1F3864" or "#1F3864"
  final double? indentLevel;
  final bool? isListItem;
  final String? listMarker; // "•", "1.", "a)" ...

  /// Inline formatting: [{text, bold, italic, underline, strike, colorHex,
  /// backgroundHex, fontSize, fontName, superscript, subscript}]
  final List<Map<String, dynamic>> runs;

  /// Table content: rows -> cells. A cell is a String or
  /// {text, bold, fill_hex, align, col_span}.
  final List<List<dynamic>> tableRows;

  /// Images: [{url | base64, widthPx, heightPx, alt}]
  final List<Map<String, dynamic>> images;
  final String? imageUrl;
  final String? imageBase64;

  /// TOC entries: page number printed on the right.
  final int? pageNumber;

  const DocumentParagraphModel({
    required this.id,
    required this.sortOrder,
    required this.displayIndex,
    required this.text,
    required this.blockType,
    required this.blockLabel,
    required this.highlight,
    required this.hasUnresolvedComments,
    required this.comments,
    this.styleName,
    this.fontSize,
    this.isBold,
    this.isItalic,
    this.isUnderline,
    this.alignment,
    this.fontName,
    this.colorHex,
    this.indentLevel,
    this.isListItem,
    this.listMarker,
    this.runs = const [],
    this.tableRows = const [],
    this.images = const [],
    this.imageUrl,
    this.imageBase64,
    this.pageNumber,
  });

  factory DocumentParagraphModel.fromJson(Map<String, dynamic> json) {
    final sortOrder = _asInt(json['sort_order']);
    final blockType = (json['block_type'] ?? 'paragraph').toString().toLowerCase();
    final blockLabel = (json['block_label'] ?? '').toString().trim();

    return DocumentParagraphModel(
      id: _asInt(json['id']),
      sortOrder: sortOrder,
      displayIndex: _asInt(json['display_index'] ?? sortOrder),
      text: (json['text'] ?? '').toString(),
      blockType: blockType.isEmpty ? 'paragraph' : blockType,
      blockLabel: blockLabel.isNotEmpty
          ? blockLabel
          : switch (blockType) {
              'heading' => 'Heading',
              'subheading' => 'Subheading',
              'bullet' => 'Bullet',
              'line' => 'Line',
              'table' => 'Table',
              'image' => 'Image',
              'toc' => 'Table of Contents',
              _ => 'Paragraph',
            },
      highlight: (json['highlight'] ?? 'none').toString(),
      hasUnresolvedComments: json['has_unresolved_comments'] == true,
      comments: List<Map<String, dynamic>>.from(json['comments'] ?? const [])
          .map(DocumentCommentModel.fromJson)
          .toList(),
      styleName: _asStringOrNull(_pick(json, ['style_name', 'styleName'])),
      fontSize: _asDoubleOrNull(_pick(json, ['font_size', 'fontSize'])),
      isBold: _asBoolOrNull(_pick(json, ['is_bold', 'isBold', 'bold'])),
      isItalic: _asBoolOrNull(_pick(json, ['is_italic', 'isItalic', 'italic'])),
      isUnderline: _asBoolOrNull(_pick(json, ['is_underline', 'isUnderline', 'underline'])),
      alignment: _asStringOrNull(_pick(json, ['alignment', 'align'])),
      fontName: _asStringOrNull(_pick(json, ['font_name', 'fontName'])),
      colorHex: _asStringOrNull(_pick(json, ['color_hex', 'colorHex', 'color'])),
      indentLevel: _asDoubleOrNull(_pick(json, ['indent_level', 'indentLevel'])),
      isListItem: _asBoolOrNull(_pick(json, ['is_list_item', 'isListItem'])),
      listMarker: _asStringOrNull(_pick(json, ['list_marker', 'listMarker'])),
      runs: _asMapList(json['runs']).map(_normalizeRun).toList(),
      tableRows: _asTableRows(_pick(json, ['table_rows', 'tableRows', 'rows'])),
      images: _asMapList(json['images']).map(_normalizeImage).toList(),
      imageUrl: _asStringOrNull(_pick(json, ['image_url', 'imageUrl'])),
      imageBase64: _asStringOrNull(_pick(json, ['image_base64', 'imageBase64'])),
      pageNumber: _asIntOrNull(_pick(json, ['page_number', 'pageNumber'])),
    );
  }

  /// The review screen reads camelCase keys from run / image maps; map the
  /// snake_case backend keys onto them once, here.
  static Map<String, dynamic> _normalizeRun(Map<String, dynamic> r) => {
        'text': (r['text'] ?? '').toString(),
        'bold': _asBoolOrNull(_pick(r, ['bold', 'is_bold'])),
        'italic': _asBoolOrNull(_pick(r, ['italic', 'is_italic'])),
        'underline': _asBoolOrNull(_pick(r, ['underline', 'is_underline'])),
        'strike': _asBoolOrNull(_pick(r, ['strike', 'is_strike'])),
        'colorHex': _asStringOrNull(_pick(r, ['color_hex', 'colorHex', 'color'])),
        'backgroundHex':
            _asStringOrNull(_pick(r, ['highlight_hex', 'background_hex', 'backgroundHex'])),
        'fontSize': _asDoubleOrNull(_pick(r, ['font_size', 'fontSize', 'size'])),
        'fontName': _asStringOrNull(_pick(r, ['font_name', 'fontName', 'font'])),
        'superscript': _asBoolOrNull(r['superscript']),
        'subscript': _asBoolOrNull(r['subscript']),
      };

  static Map<String, dynamic> _normalizeImage(Map<String, dynamic> i) => {
        'url': _asStringOrNull(_pick(i, ['url', 'image_url'])),
        'base64': _asStringOrNull(_pick(i, ['base64', 'data'])),
        'widthPx': _asDoubleOrNull(_pick(i, ['width_px', 'widthPx', 'width'])),
        'heightPx': _asDoubleOrNull(_pick(i, ['height_px', 'heightPx', 'height'])),
        'alt': _asStringOrNull(i['alt']),
      };
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