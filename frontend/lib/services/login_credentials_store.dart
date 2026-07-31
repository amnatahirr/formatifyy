import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// One saved / seeded login suggestion for the login form.
class SavedLoginAccount {
  final String email;
  final String? password;
  final String? roleLabel;

  const SavedLoginAccount({
    required this.email,
    this.password,
    this.roleLabel,
  });
}

/// Persists recent login emails (and optional passwords when Remember me is on)
/// so the login form can offer autofill suggestions for multiple accounts.
class LoginCredentialsStore {
  LoginCredentialsStore._();

  static const _kRememberMe = 'formatify.login.remember_me';
  static const _kLastEmail = 'formatify.login.last_email';
  static const _kEmails = 'formatify.login.emails';
  static const _kPasswords = 'formatify.login.passwords_json';
  static const _kRoles = 'formatify.login.roles_json';
  static const _maxEmails = 12;

  /// Default seeded tester accounts (matches backend database.py seeds).
  static const List<SavedLoginAccount> defaultTesterAccounts = [
    SavedLoginAccount(
      email: 'student@comsats.edu.pk',
      password: 'student123',
      roleLabel: 'Student',
    ),
    SavedLoginAccount(
      email: 'admin@comsats.edu.pk',
      password: 'admin123',
      roleLabel: 'Admin',
    ),
    SavedLoginAccount(
      email: 'supervisor@comsats.edu.pk',
      password: 'supervisor123',
      roleLabel: 'Supervisor',
    ),
  ];

  /// Ensure the three tester roles are always available in suggestions.
  static Future<void> ensureTesterAccounts() async {
    final prefs = await SharedPreferences.getInstance();
    final emails = _readEmailList(prefs);
    final passwords = _readPasswordMap(prefs);
    final roles = _readRoleMap(prefs);
    var changed = false;

    for (final account in defaultTesterAccounts) {
      final email = account.email.toLowerCase();
      if (!emails.contains(email)) {
        emails.add(email);
        changed = true;
      }
      // Keep seeded password unless the user already saved a different one.
      if (!passwords.containsKey(email) &&
          account.password != null &&
          account.password!.isNotEmpty) {
        passwords[email] = account.password!;
        changed = true;
      }
      if (account.roleLabel != null &&
          (roles[email] == null || roles[email]!.isEmpty)) {
        roles[email] = account.roleLabel!;
        changed = true;
      }
    }

    if (!changed) return;
    await prefs.setStringList(_kEmails, emails);
    await prefs.setString(_kPasswords, jsonEncode(passwords));
    await prefs.setString(_kRoles, jsonEncode(roles));
  }

  /// Save after a successful login.
  ///
  /// When [rememberMe] is true, email + password are stored for suggestions
  /// and pre-fill. When false, only that email's password is cleared — other
  /// saved accounts (student / admin / supervisor) are kept.
  static Future<void> saveSuccessfulLogin({
    required String email,
    required String password,
    required bool rememberMe,
    String? roleLabel,
  }) async {
    final normalized = email.trim().toLowerCase();
    if (normalized.isEmpty) return;

    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_kRememberMe, rememberMe);
    await prefs.setString(_kLastEmail, normalized);

    final emails = _readEmailList(prefs);
    emails.removeWhere((e) => e.toLowerCase() == normalized);
    emails.insert(0, normalized);
    // Keep tester defaults even if list grows
    for (final account in defaultTesterAccounts) {
      final e = account.email.toLowerCase();
      if (!emails.contains(e)) emails.add(e);
    }
    while (emails.length > _maxEmails) {
      // Prefer dropping non-default extras from the end
      final defaults = {
        for (final a in defaultTesterAccounts) a.email.toLowerCase(),
      };
      final dropIndex = emails.lastIndexWhere((e) => !defaults.contains(e));
      if (dropIndex >= 0) {
        emails.removeAt(dropIndex);
      } else {
        break;
      }
    }
    await prefs.setStringList(_kEmails, emails);

    final passwords = _readPasswordMap(prefs);
    if (rememberMe && password.isNotEmpty) {
      passwords[normalized] = password;
    } else if (!rememberMe) {
      // Don't wipe seeded tester passwords if this is a default account
      final isDefault = defaultTesterAccounts.any(
        (a) => a.email.toLowerCase() == normalized,
      );
      if (!isDefault) {
        passwords.remove(normalized);
      }
    }
    await prefs.setString(_kPasswords, jsonEncode(passwords));

    if (roleLabel != null && roleLabel.trim().isNotEmpty) {
      final roles = _readRoleMap(prefs);
      roles[normalized] = roleLabel.trim();
      await prefs.setString(_kRoles, jsonEncode(roles));
    }
  }

  static Future<List<String>> suggestedEmails() async {
    await ensureTesterAccounts();
    final prefs = await SharedPreferences.getInstance();
    return _orderedEmails(prefs);
  }

  static Future<List<SavedLoginAccount>> suggestedAccounts() async {
    await ensureTesterAccounts();
    final prefs = await SharedPreferences.getInstance();
    final emails = _orderedEmails(prefs);
    final passwords = _readPasswordMap(prefs);
    final roles = _readRoleMap(prefs);
    final defaultRoles = {
      for (final a in defaultTesterAccounts)
        a.email.toLowerCase(): a.roleLabel ?? '',
    };

    return [
      for (final email in emails)
        SavedLoginAccount(
          email: email,
          password: passwords[email],
          roleLabel: (roles[email]?.isNotEmpty == true)
              ? roles[email]
              : (defaultRoles[email]?.isNotEmpty == true
                  ? defaultRoles[email]
                  : null),
        ),
    ];
  }

  static Future<String?> passwordFor(String email) async {
    await ensureTesterAccounts();
    final prefs = await SharedPreferences.getInstance();
    final map = _readPasswordMap(prefs);
    return map[email.trim().toLowerCase()];
  }

  /// Last remembered session for one-tap pre-fill on the login screen.
  static Future<({String? email, String? password, bool rememberMe})>
      loadPrefill() async {
    await ensureTesterAccounts();
    final prefs = await SharedPreferences.getInstance();
    final rememberMe = prefs.getBool(_kRememberMe) ?? true;
    final last = (prefs.getString(_kLastEmail) ?? '').trim().toLowerCase();
    if (!rememberMe || last.isEmpty) {
      return (email: null, password: null, rememberMe: rememberMe);
    }
    final map = _readPasswordMap(prefs);
    return (
      email: last,
      password: map[last],
      rememberMe: rememberMe,
    );
  }

  /// Tester defaults first (Student, Admin, Supervisor), then other emails.
  static List<String> _orderedEmails(SharedPreferences prefs) {
    final stored = _readEmailList(prefs);
    final defaults = [
      for (final a in defaultTesterAccounts) a.email.toLowerCase(),
    ];
    final ordered = <String>[];
    for (final d in defaults) {
      if (stored.contains(d) || true) {
        // Always include defaults after ensureTesterAccounts
        if (!ordered.contains(d)) ordered.add(d);
      }
    }
    for (final e in stored) {
      if (!ordered.contains(e)) ordered.add(e);
    }
    return ordered;
  }

  static List<String> _readEmailList(SharedPreferences prefs) {
    final raw = prefs.getStringList(_kEmails) ?? const <String>[];
    return raw
        .map((e) => e.trim().toLowerCase())
        .where((e) => e.isNotEmpty)
        .toList();
  }

  static Map<String, String> _readPasswordMap(SharedPreferences prefs) {
    final raw = prefs.getString(_kPasswords);
    if (raw == null || raw.isEmpty) return <String, String>{};
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map) return <String, String>{};
      return decoded.map(
        (key, value) =>
            MapEntry(key.toString().toLowerCase(), value.toString()),
      );
    } catch (_) {
      return <String, String>{};
    }
  }

  static Map<String, String> _readRoleMap(SharedPreferences prefs) {
    final raw = prefs.getString(_kRoles);
    if (raw == null || raw.isEmpty) return <String, String>{};
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map) return <String, String>{};
      return decoded.map(
        (key, value) =>
            MapEntry(key.toString().toLowerCase(), value.toString()),
      );
    } catch (_) {
      return <String, String>{};
    }
  }
}
