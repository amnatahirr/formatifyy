import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kDarkModeKey = 'formatify_dark_mode';

/// Student (and shared) UI color tokens — dark GitHub-style navy vs soft blue-grey light.
class AppPalette {
  final bool isDark;

  const AppPalette._(this.isDark);

  static const dark = AppPalette._(true);
  static const light = AppPalette._(false);

  // Shared accent (same in both modes)
  Color get accent => const Color(0xFF3B82F6);
  Color get accentSoft =>
      isDark ? const Color(0xFF3B82F6).withOpacity(0.15) : const Color(0xFF3B82F6).withOpacity(0.12);
  Color get accentAlt => const Color(0xFF6366F1);

  Color get scaffold =>
      isDark ? const Color(0xFF0D1117) : const Color(0xFFF3F6FB);
  Color get surface =>
      isDark ? const Color(0xFF161B22) : const Color(0xFFFFFFFF);
  Color get surfaceAlt =>
      isDark ? const Color(0xFF0D1117) : const Color(0xFFE8EEF6);
  Color get surfaceElevated =>
      isDark ? const Color(0xFF1C2330) : const Color(0xFFF8FAFD);

  Color get border =>
      isDark ? Colors.white.withOpacity(0.10) : const Color(0xFFD5DDE8);
  Color get borderStrong =>
      isDark ? Colors.white.withOpacity(0.20) : const Color(0xFFB8C4D6);

  Color get textPrimary =>
      isDark ? Colors.white : const Color(0xFF0F172A);
  Color get textSecondary =>
      isDark ? Colors.white.withOpacity(0.60) : const Color(0xFF475569);
  Color get textMuted =>
      isDark ? Colors.white.withOpacity(0.45) : const Color(0xFF64748B);

  Color get iconMuted =>
      isDark ? Colors.white.withOpacity(0.55) : const Color(0xFF475569);

  Color get sidebarBg =>
      isDark ? const Color(0xFF161B22) : const Color(0xFFFFFFFF);
  Color get topBarBg =>
      isDark ? const Color(0xFF161B22) : const Color(0xFFFFFFFF);

  List<BoxShadow> get cardShadow => isDark
      ? const []
      : [
          BoxShadow(
            color: const Color(0xFF0F172A).withOpacity(0.06),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ];

  ThemeData get themeData {
    final base = isDark ? ThemeData.dark() : ThemeData.light();
    return base.copyWith(
      useMaterial3: true,
      brightness: isDark ? Brightness.dark : Brightness.light,
      scaffoldBackgroundColor: scaffold,
      primaryColor: accent,
      colorScheme: ColorScheme.fromSeed(
        seedColor: accent,
        brightness: isDark ? Brightness.dark : Brightness.light,
        primary: accent,
        surface: surface,
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: surface,
        titleTextStyle: TextStyle(
          color: textPrimary,
          fontSize: 18,
          fontWeight: FontWeight.w600,
        ),
        contentTextStyle: TextStyle(color: textSecondary, fontSize: 14),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) return accent;
          return isDark ? const Color(0xFF9CA3AF) : const Color(0xFF94A3B8);
        }),
        trackColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return accent.withOpacity(0.45);
          }
          return isDark ? Colors.white.withOpacity(0.12) : const Color(0xFFCBD5E1);
        }),
      ),
    );
  }
}

class ThemeProvider extends ChangeNotifier {
  /// Sign-in / sign-up always land on Dark Mode.
  static const bool defaultDarkMode = true;

  bool _isDarkMode = defaultDarkMode;
  bool _loaded = true;
  int? _boundUserId;

  bool get isDarkMode => _isDarkMode;
  bool get isLoaded => _loaded;
  int? get boundUserId => _boundUserId;
  AppPalette get palette => _isDarkMode ? AppPalette.dark : AppPalette.light;
  ThemeMode get themeMode => _isDarkMode ? ThemeMode.dark : ThemeMode.light;

  String _prefsKeyFor(int userId) => '${_kDarkModeKey}_u$userId';

  /// After sign-in / sign-up: always Dark Mode ON.
  /// Light Mode only applies if the user later toggles it in Settings.
  Future<void> bindToUser(int? userId) async {
    if (userId == null) {
      _boundUserId = null;
      _forceDark();
      return;
    }

    // Already bound for this session — keep current choice (incl. Light from Settings).
    if (_boundUserId == userId && _loaded) {
      return;
    }

    _boundUserId = userId;
    _forceDark();

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_kDarkModeKey);
      // Reset stored preference to dark so login never restores light.
      await prefs.setBool(_prefsKeyFor(userId), true);
    } catch (_) {}
  }

  void _forceDark() {
    _loaded = true;
    final changed = !_isDarkMode;
    _isDarkMode = true;
    if (changed) notifyListeners();
  }

  Future<void> resetToDefaultDark() => bindToUser(null);

  /// Explicit alias for signup / login success paths.
  Future<void> applyDefaultDarkForNewUser(int userId) => bindToUser(userId);

  /// Settings toggle — Light/Dark for the current session (and saved while logged in).
  /// Next sign-in still starts in Dark Mode via [bindToUser].
  Future<void> setDarkMode(bool value) async {
    if (_isDarkMode == value) return;
    _isDarkMode = value;
    notifyListeners();
    final userId = _boundUserId;
    if (userId == null) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_prefsKeyFor(userId), value);
    } catch (_) {}
  }

  Future<void> toggleDarkMode() => setDarkMode(!_isDarkMode);
}
