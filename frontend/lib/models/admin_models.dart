int _asInt(dynamic value, [int fallback = 0]) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse('$value') ?? fallback;
}

double _asDouble(dynamic value, [double fallback = 0]) {
  if (value is double) return value;
  if (value is num) return value.toDouble();
  return double.tryParse('$value') ?? fallback;
}

class AdminStats {
  final int totalSupervisors;
  final int totalStudents;
  final int totalActiveProjects;
  final int totalDocumentsChecked;

  const AdminStats({
    required this.totalSupervisors,
    required this.totalStudents,
    required this.totalActiveProjects,
    required this.totalDocumentsChecked,
  });

  factory AdminStats.fromJson(Map<String, dynamic> json) => AdminStats(
        totalSupervisors: _asInt(json['total_supervisors']),
        totalStudents: _asInt(json['total_students']),
        totalActiveProjects: _asInt(json['total_active_projects']),
        totalDocumentsChecked: _asInt(json['total_documents_checked']),
      );
}

class AdminOverviewModel {
  final AdminStats stats;
  final double successRate;
  final int documentsThisMonth;
  final List<AdminTopTemplate> topTemplates;
  final List<AdminActivityDay> recentActivity;

  const AdminOverviewModel({
    required this.stats,
    required this.successRate,
    required this.documentsThisMonth,
    required this.topTemplates,
    required this.recentActivity,
  });

  factory AdminOverviewModel.fromJson(Map<String, dynamic> json) => AdminOverviewModel(
        stats: AdminStats.fromJson(json),
        successRate: _asDouble(json['success_rate']),
        documentsThisMonth: _asInt(json['documents_this_month']),
        topTemplates: List<Map<String, dynamic>>.from(json['top_templates'] ?? const [])
            .map(AdminTopTemplate.fromJson)
            .toList(),
        recentActivity: List<Map<String, dynamic>>.from(
          json['documents_last_7_days'] ?? json['recent_activity'] ?? const [],
        ).map(AdminActivityDay.fromJson).toList(),
      );
}

class AdminTopTemplate {
  final int id;
  final String name;
  final int uses;

  const AdminTopTemplate({required this.id, required this.name, required this.uses});

  factory AdminTopTemplate.fromJson(Map<String, dynamic> json) => AdminTopTemplate(
        id: _asInt(json['id']),
        name: (json['name'] ?? '').toString(),
        uses: _asInt(json['uses']),
      );
}

class AdminActivityDay {
  final String day;
  final String date;
  final int count;

  const AdminActivityDay({required this.day, required this.date, required this.count});

  factory AdminActivityDay.fromJson(Map<String, dynamic> json) => AdminActivityDay(
        day: (json['day'] ?? '').toString(),
        date: (json['date'] ?? '').toString(),
        count: _asInt(json['count']),
      );
}

class DepartmentSummary {
  final int id;
  final String name;
  final String code;
  final int minMembers;
  final int maxMembers;
  final int maxGroupsPerSupervisor;
  final int supervisorCount;
  final int templateCount;

  const DepartmentSummary({
    required this.id,
    required this.name,
    required this.code,
    required this.minMembers,
    required this.maxMembers,
    required this.maxGroupsPerSupervisor,
    required this.supervisorCount,
    required this.templateCount,
  });

  factory DepartmentSummary.fromJson(Map<String, dynamic> json) => DepartmentSummary(
        id: _asInt(json['id']),
        name: (json['name'] ?? '').toString(),
        code: (json['code'] ?? '').toString(),
        minMembers: _asInt(json['min_members'], 1),
        maxMembers: _asInt(json['max_members'], 3),
        maxGroupsPerSupervisor: _asInt(json['max_groups_per_supervisor'], 6),
        supervisorCount: _asInt(json['supervisor_count']),
        templateCount: _asInt(json['template_count']),
      );
}

class SupervisorModel {
  final int id;
  final String name;
  final String email;
  final int departmentId;
  final String departmentName;
  final int maxGroups;
  final int currentGroups;
  final bool isActive;
  final String createdAt;

  const SupervisorModel({
    required this.id,
    required this.name,
    required this.email,
    required this.departmentId,
    required this.departmentName,
    required this.maxGroups,
    required this.currentGroups,
    required this.isActive,
    required this.createdAt,
  });

  factory SupervisorModel.fromJson(Map<String, dynamic> json) => SupervisorModel(
        id: _asInt(json['id']),
        name: (json['name'] ?? '').toString(),
        email: (json['email'] ?? '').toString(),
        departmentId: _asInt(json['department_id']),
        departmentName: (json['department_name'] ?? '').toString(),
        maxGroups: _asInt(json['max_groups'], 6),
        currentGroups: _asInt(json['current_groups']),
        isActive: (json['is_active'] ?? 0) == 1 || json['is_active'] == true,
        createdAt: (json['created_at'] ?? '').toString(),
      );
}

class AdminTemplateModel {
  final int id;
  final int? departmentId;
  final String name;
  final String description;
  final List<dynamic> requiredSections;
  final Map<String, dynamic> formattingRules;
  final String createdAt;

  const AdminTemplateModel({
    required this.id,
    required this.departmentId,
    required this.name,
    required this.description,
    required this.requiredSections,
    required this.formattingRules,
    required this.createdAt,
  });

  String get rulesPreview {
    final raw = formattingRules.isNotEmpty ? formattingRules.toString() : description;
    return raw.length <= 100 ? raw : '${raw.substring(0, 100)}...';
  }

  factory AdminTemplateModel.fromJson(Map<String, dynamic> json) => AdminTemplateModel(
        id: _asInt(json['id']),
        departmentId: json['department_id'] == null ? null : _asInt(json['department_id']),
        name: (json['name'] ?? '').toString(),
        description: (json['description'] ?? '').toString(),
        requiredSections: List<dynamic>.from(json['required_sections'] ?? const []),
        formattingRules: Map<String, dynamic>.from(json['formatting_rules'] ?? const {}),
        createdAt: (json['created_at'] ?? '').toString(),
      );
}

class DeadlineModel {
  final int id;
  final String title;
  final String description;
  final String dueDate;
  final int? departmentId;
  final String? departmentName;
  final bool appliesToAll;

  const DeadlineModel({
    required this.id,
    required this.title,
    required this.description,
    required this.dueDate,
    required this.departmentId,
    required this.departmentName,
    required this.appliesToAll,
  });

  factory DeadlineModel.fromJson(Map<String, dynamic> json) => DeadlineModel(
        id: _asInt(json['id']),
        title: (json['title'] ?? '').toString(),
        description: (json['description'] ?? '').toString(),
        dueDate: (json['due_date'] ?? '').toString(),
        departmentId: json['department_id'] == null ? null : _asInt(json['department_id']),
        departmentName: json['department_name']?.toString(),
        appliesToAll: (json['applies_to_all'] ?? 0) == 1 || json['applies_to_all'] == true,
      );
}

class AnalyticsIssueBreakdown {
  final String label;
  final int percentage;
  final int count;

  const AnalyticsIssueBreakdown({required this.label, required this.percentage, required this.count});

  factory AnalyticsIssueBreakdown.fromJson(Map<String, dynamic> json) => AnalyticsIssueBreakdown(
        label: (json['label'] ?? '').toString(),
        percentage: _asInt(json['percentage']),
        count: _asInt(json['count']),
      );
}

class AnalyticsDepartmentScore {
  final int departmentId;
  final String departmentName;
  final double avgComplianceScore;
  final int documentsAnalyzed;

  const AnalyticsDepartmentScore({
    required this.departmentId,
    required this.departmentName,
    required this.avgComplianceScore,
    required this.documentsAnalyzed,
  });

  factory AnalyticsDepartmentScore.fromJson(Map<String, dynamic> json) => AnalyticsDepartmentScore(
        departmentId: _asInt(json['department_id']),
        departmentName: (json['department_name'] ?? '').toString(),
        avgComplianceScore: _asDouble(json['avg_compliance_score']),
        documentsAnalyzed: _asInt(json['documents_analyzed']),
      );
}

class AnalyticsMonthlyDocuments {
  final String month;
  final int count;

  const AnalyticsMonthlyDocuments({required this.month, required this.count});

  factory AnalyticsMonthlyDocuments.fromJson(Map<String, dynamic> json) => AnalyticsMonthlyDocuments(
        month: (json['month'] ?? '').toString(),
        count: _asInt(json['count']),
      );
}

class AdminAnalyticsModel {
  final int documentsAnalyzed;
  final int totalDocuments;
  final int totalStudents;
  final int totalTemplates;
  final int documentsThisMonth;
  final double successRate;
  final double avgComplianceScore;
  final List<AnalyticsIssueBreakdown> issueBreakdown;
  final List<AnalyticsDepartmentScore> departmentScores;
  final List<AnalyticsMonthlyDocuments> monthlyDocuments;
  final List<AdminTopTemplate> topTemplates;
  final List<AdminActivityDay> documentsLast7Days;

  const AdminAnalyticsModel({
    required this.documentsAnalyzed,
    required this.totalDocuments,
    required this.totalStudents,
    required this.totalTemplates,
    required this.documentsThisMonth,
    required this.successRate,
    required this.avgComplianceScore,
    required this.issueBreakdown,
    required this.departmentScores,
    required this.monthlyDocuments,
    required this.topTemplates,
    required this.documentsLast7Days,
  });

  factory AdminAnalyticsModel.fromJson(Map<String, dynamic> json) => AdminAnalyticsModel(
        documentsAnalyzed: _asInt(json['documents_analyzed'] ?? json['total_documents']),
        totalDocuments: _asInt(json['total_documents'] ?? json['documents_analyzed']),
        totalStudents: _asInt(json['total_students']),
        totalTemplates: _asInt(json['total_templates']),
        documentsThisMonth: _asInt(json['documents_this_month']),
        successRate: _asDouble(json['success_rate']),
        avgComplianceScore: _asDouble(json['avg_compliance_score']),
        issueBreakdown: List<Map<String, dynamic>>.from(json['issue_breakdown'] ?? const [])
            .map(AnalyticsIssueBreakdown.fromJson)
            .toList(),
        departmentScores: List<Map<String, dynamic>>.from(json['department_scores'] ?? const [])
            .map(AnalyticsDepartmentScore.fromJson)
            .toList(),
        monthlyDocuments: List<Map<String, dynamic>>.from(json['monthly_documents'] ?? const [])
            .map(AnalyticsMonthlyDocuments.fromJson)
            .toList(),
        topTemplates: List<Map<String, dynamic>>.from(json['top_templates'] ?? const [])
            .map(AdminTopTemplate.fromJson)
            .toList(),
        documentsLast7Days: List<Map<String, dynamic>>.from(json['documents_last_7_days'] ?? const [])
            .map(AdminActivityDay.fromJson)
            .toList(),
      );
}

class AdminUniversityModel {
  final int id;
  final String name;
  final String country;
  final String createdAt;
  final int userCount;
  final int studentCount;

  const AdminUniversityModel({
    required this.id,
    required this.name,
    required this.country,
    required this.createdAt,
    required this.userCount,
    required this.studentCount,
  });

  factory AdminUniversityModel.fromJson(Map<String, dynamic> json) => AdminUniversityModel(
        id: _asInt(json['id']),
        name: (json['name'] ?? '').toString(),
        country: (json['country'] ?? '').toString(),
        createdAt: (json['created_at'] ?? '').toString(),
        userCount: _asInt(json['user_count']),
        studentCount: _asInt(json['student_count']),
      );
}

class AdminSettingsModel {
  final String systemName;
  final String version;
  final String environment;
  final bool emailNotifications;
  final bool systemNotifications;
  final bool maintenanceMode;
  final int apiRateLimit;
  final int apiTimeoutSeconds;
  final int maxFileSizeMb;

  const AdminSettingsModel({
    required this.systemName,
    required this.version,
    required this.environment,
    required this.emailNotifications,
    required this.systemNotifications,
    required this.maintenanceMode,
    required this.apiRateLimit,
    required this.apiTimeoutSeconds,
    required this.maxFileSizeMb,
  });

  factory AdminSettingsModel.fromJson(Map<String, dynamic> json) => AdminSettingsModel(
        systemName: (json['system_name'] ?? '').toString(),
        version: (json['version'] ?? '').toString(),
        environment: (json['environment'] ?? '').toString(),
        emailNotifications: json['email_notifications'] == true || json['email_notifications'] == 'true',
        systemNotifications: json['system_notifications'] == true || json['system_notifications'] == 'true',
        maintenanceMode: json['maintenance_mode'] == true || json['maintenance_mode'] == 'true',
        apiRateLimit: _asInt(json['api_rate_limit'], 10000),
        apiTimeoutSeconds: _asInt(json['api_timeout_seconds'], 30),
        maxFileSizeMb: _asInt(json['max_file_size_mb'], 100),
      );

  Map<String, dynamic> toJson() => {
        'system_name': systemName,
        'version': version,
        'environment': environment,
        'email_notifications': emailNotifications,
        'system_notifications': systemNotifications,
        'maintenance_mode': maintenanceMode,
        'api_rate_limit': apiRateLimit,
        'api_timeout_seconds': apiTimeoutSeconds,
        'max_file_size_mb': maxFileSizeMb,
      };
}
