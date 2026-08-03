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
  /// Org kind from API: `university` | `company`.
  static String orgType = 'university';
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

  /// University FYP tenants only.
  ///
  /// Starter / enterprise / `type=company` are never university.
  /// Semester + "University email" also require the `fyp` module — current
  /// semester (6/7) is an FYP field. Tenants labeled university but without
  /// fyp (legacy create mapping) get company-style signup fields.
  static bool get isUniversityOrg {
    final plan = orgPlan.toLowerCase().trim();
    final type = orgType.toLowerCase().trim();
    if (plan == 'starter' || plan == 'enterprise') return false;
    if (type == 'company') return false;
    if (!hasFypModule) return false;
    return plan == 'university' || type == 'university' || plan.isEmpty;
  }

  static bool get requiresSemesterOnSignup => isUniversityOrg;

  static String get signupEmailHint =>
      isUniversityOrg ? 'University email' : 'Email';

  static String get modulesLabel => modulesCsv
      .split(',')
      .map((m) => m.trim())
      .where((m) => m.isNotEmpty)
      .join(', ');

  /// UI label for a backend role — core-only orgs show `student` as Member.
  static String displayRoleLabel(String? role) {
    final r = (role ?? '').trim().toLowerCase();
    if (r.isEmpty) return 'User';
    if (!hasFypModule && r == 'student') return 'Member';
    return r[0].toUpperCase() + r.substring(1);
  }

  /// Super Admin master key (must match backend SUPER_ADMIN_KEY / .env).
  static String superAdminKey = 'super_secret_master_key_here';

  /// Clears tenant display flags so the next org cannot inherit FYP UI.
  static void clearTenant() {
    orgCode = '';
    orgName = '';
    orgPlan = 'university';
    orgType = 'university';
    primaryColor = '#7B61FF';
    documentsUsed = 0;
    documentsLimit = 999999;
    allowSelfSignup = true;
    modulesCsv = 'core';
  }

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
  /// Always overwrites plan/type/modules so switching orgs cannot leave
  /// stale university/FYP flags from the previous tenant.
  static void bindTenant({
    required String code,
    String? name,
    String? plan,
    String? type,
    List<dynamic>? modules,
    bool? allowSignup,
    String? color,
  }) {
    orgCode = code.trim().toUpperCase();
    orgName = (name != null && name.trim().isNotEmpty) ? name.trim() : orgName;
    orgPlan = (plan != null && plan.trim().isNotEmpty) ? plan.trim() : 'university';
    orgType = (type != null && type.trim().isNotEmpty) ? type.trim() : 'university';
    if (color != null && color.trim().isNotEmpty) primaryColor = color.trim();
    if (modules != null) {
      modulesCsv = modules
          .map((e) => e.toString().trim())
          .where((e) => e.isNotEmpty)
          .join(',');
    } else {
      modulesCsv = 'core';
    }
    // Self-registration is always available after resolving an org code.
    allowSelfSignup = allowSignup ?? true;
  }

  /// Updates display / module flags from `/org/info` (after JWT login).
  static void applyOrgInfo(Map<String, dynamic> info) {
    final incomingCode = (info['org_code'] ?? '').toString().trim();
    if (incomingCode.isNotEmpty) orgCode = incomingCode;

    orgName = (info['org_name'] ?? orgName).toString();
    orgPlan = (info['plan'] ?? orgPlan).toString();
    final incomingType = (info['type'] ?? '').toString().trim();
    if (incomingType.isNotEmpty) orgType = incomingType;
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

    // Self-registration is always available for resolved tenants.
    allowSelfSignup = info.containsKey('allow_self_signup')
        ? info['allow_self_signup'] == true
        : true;

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
