import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Persists the JWT access token for authenticated API calls.
///
/// Uses secure storage when available; falls back to SharedPreferences if
/// Keychain/secure-storage hangs or fails (common on first macOS run).
class AuthTokenStore {
  AuthTokenStore._();

  static const _key = 'formatify.auth.access_token';
  static const _prefsKey = 'formatify.auth.access_token_prefs';
  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  static String? _memoryToken;

  static String? get token => _memoryToken;

  static bool get hasToken => (_memoryToken ?? '').isNotEmpty;

  static Future<T> _withTimeout<T>(Future<T> future) {
    return future.timeout(
      const Duration(seconds: 2),
      onTimeout: () => throw TimeoutException('secure storage timeout'),
    );
  }

  static Future<void> load() async {
    try {
      _memoryToken = await _withTimeout<String?>(_storage.read(key: _key));
    } catch (e) {
      debugPrint('[AuthTokenStore] secure load failed: $e');
      _memoryToken = null;
    }
    if ((_memoryToken ?? '').isEmpty) {
      try {
        final prefs = await SharedPreferences.getInstance()
            .timeout(const Duration(seconds: 2));
        _memoryToken = prefs.getString(_prefsKey);
      } catch (e) {
        debugPrint('[AuthTokenStore] prefs load failed: $e');
      }
    }
  }

  static Future<void> save(String token) async {
    _memoryToken = token;
    try {
      await _withTimeout<void>(_storage.write(key: _key, value: token));
    } catch (e) {
      debugPrint('[AuthTokenStore] secure save failed: $e');
    }
    try {
      final prefs = await SharedPreferences.getInstance()
          .timeout(const Duration(seconds: 2));
      await prefs.setString(_prefsKey, token);
    } catch (e) {
      debugPrint('[AuthTokenStore] prefs save failed: $e');
    }
  }

  static Future<void> clear() async {
    _memoryToken = null;
    try {
      await _withTimeout<void>(_storage.delete(key: _key));
    } catch (e) {
      debugPrint('[AuthTokenStore] secure clear failed: $e');
    }
    try {
      final prefs = await SharedPreferences.getInstance()
          .timeout(const Duration(seconds: 2));
      await prefs.remove(_prefsKey);
    } catch (e) {
      debugPrint('[AuthTokenStore] prefs clear failed: $e');
    }
  }
}

class TimeoutException implements Exception {
  TimeoutException(this.message);
  final String message;
  @override
  String toString() => message;
}
