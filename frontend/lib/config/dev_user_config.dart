/// Active tenant + module flags for UI gating (synced from /org/info after login).
///
/// Clients never store org api_key — only org_code + JWT (see [AuthTokenStore]).
class DevUserConfig {
  static String memberKey = 'member1';
  static int backendUserId = 1;
  static String username = 'student2';
  static String email = 'student2@comsats.edu.pk';
  static String role = 'student';

  /// Selected organization code (login gate / bound tenant).
  static String orgCode = '';

  static String orgName = '';
  static String orgPlan = 'university';
  static String primaryColor = '#7B61FF';
  static int documentsUsed = 0;
  static int documentsLimit = 999999;
  static bool allowSelfSignup = true;

  /// Comma-separated modules from org (UI gating only — backend enforces too).
  static String modulesCsv = 'core';

  static bool get hasFypModule =>
      modulesCsv.split(',').map((m) => m.trim()).contains('fyp');

  static bool get hasCoreModule =>
      modulesCsv.split(',').map((m) => m.trim()).contains('core') ||
      modulesCsv.trim().isEmpty;

  static String get modulesLabel => modulesCsv
      .split(',')
      .map((m) => m.trim())
      .where((m) => m.isNotEmpty)
      .join(', ');

  /// Super Admin master key (must match backend SUPER_ADMIN_KEY / .env).
  static String superAdminKey = 'super_secret_master_key_here';

  static void initialize(String key) {
    memberKey = key;
    switch (key) {
      case 'member2':
        backendUserId = 2;
        username = 'student1';
        email = 'student1@comsats.edu.pk';
        role = 'student';
        break;
      case 'member1':
      default:
        backendUserId = 1;
        username = 'student2';
        email = 'student2@comsats.edu.pk';
        role = 'student';
        break;
    }
  }

  static bool get isDevSession => memberKey.isNotEmpty;

  /// Bind tenant from /org/resolve (pre-login) — no api_key.
  static void bindTenant({
    required String code,
    String? name,
    String? plan,
    List<dynamic>? modules,
    bool? allowSignup,
    String? color,
  }) {
    orgCode = code.trim().toUpperCase();
    if (name != null && name.trim().isNotEmpty) orgName = name.trim();
    if (plan != null && plan.trim().isNotEmpty) orgPlan = plan.trim();
    if (color != null && color.trim().isNotEmpty) primaryColor = color.trim();
    if (modules != null) {
      modulesCsv = modules
          .map((e) => e.toString().trim())
          .where((e) => e.isNotEmpty)
          .join(',');
    }
    if (allowSignup != null) {
      allowSelfSignup = allowSignup;
    } else {
      allowSelfSignup = hasFypModule || orgPlan.toLowerCase() == 'university';
    }
  }

  /// Updates display / module flags from `/org/info` (after JWT login).
  static void applyOrgInfo(Map<String, dynamic> info) {
    final incomingCode = (info['org_code'] ?? '').toString().trim();
    if (incomingCode.isNotEmpty) orgCode = incomingCode;

    orgName = (info['org_name'] ?? orgName).toString();
    orgPlan = (info['plan'] ?? orgPlan).toString();
    primaryColor = (info['primary_color'] ?? primaryColor).toString();

    final mods = info['modules'];
    if (mods is List) {
      modulesCsv =
          mods.map((e) => e.toString().trim()).where((e) => e.isNotEmpty).join(',');
    } else if (mods != null && mods.toString().trim().isNotEmpty) {
      modulesCsv = mods.toString().trim();
    } else if (info['has_fyp'] == true) {
      modulesCsv = 'core,fyp';
    } else if (info.containsKey('has_fyp') && info['has_fyp'] != true) {
      modulesCsv = 'core';
    }

    if (info.containsKey('allow_self_signup')) {
      allowSelfSignup = info['allow_self_signup'] == true;
    } else {
      allowSelfSignup = hasFypModule || orgPlan.toLowerCase() == 'university';
    }

    final used = info['documents_used'];
    final limit = info['documents_limit'];
    if (used is int) {
      documentsUsed = used;
    } else if (used != null) {
      documentsUsed = int.tryParse(used.toString()) ?? documentsUsed;
    }
    if (limit is int) {
      documentsLimit = limit;
    } else if (limit != null) {
      documentsLimit = int.tryParse(limit.toString()) ?? documentsLimit;
    }
  }
}
