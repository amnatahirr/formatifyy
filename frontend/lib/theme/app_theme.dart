import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kDarkModeKey = 'formatify_dark_mode';

/// Student (and shared) UI color tokens.
/// Dark: Formatify navy + purple accent/gradient (auth-aligned).
/// Light: unchanged soft blue-grey (do not modify light branches).
class AppPalette {
  final bool isDark;

  const AppPalette._(this.isDark);

  static const dark = AppPalette._(true);
  static const light = AppPalette._(false);

  // Accent — dark purple / light blue (light branch unchanged).
  Color get accent =>
      isDark ? const Color(0xFFA855F7) : const Color(0xFF3B82F6);
  Color get accentSoft =>
      isDark
          ? const Color(0xFFA855F7).withOpacity(0.15)
          : const Color(0xFF3B82F6).withOpacity(0.12);
  Color get accentAlt => const Color(0xFF6366F1);

  Color get scaffold =>
      isDark ? const Color(0xFF0A0E1A) : const Color(0xFFF3F6FB);
  Color get surface =>
      isDark ? const Color(0xFF151A3A) : const Color(0xFFFFFFFF);
  Color get surfaceAlt =>
      isDark ? const Color(0xFF0D1220) : const Color(0xFFE8EEF6);
  Color get surfaceElevated =>
      isDark ? const Color(0xFF1A2040) : const Color(0xFFF8FAFD);

  Color get border =>
      isDark
          ? const Color(0xFF8B5CF6).withOpacity(0.18)
          : const Color(0xFFD5DDE8);
  Color get borderStrong =>
      isDark
          ? const Color(0xFF6366F1).withOpacity(0.35)
          : const Color(0xFFB8C4D6);

  Color get textPrimary =>
      isDark ? Colors.white : const Color(0xFF0F172A);
  Color get textSecondary =>
      isDark ? Colors.white.withOpacity(0.60) : const Color(0xFF475569);
  Color get textMuted =>
      isDark ? Colors.white.withOpacity(0.45) : const Color(0xFF64748B);

  Color get iconMuted =>
      isDark ? Colors.white.withOpacity(0.55) : const Color(0xFF475569);

  Color get sidebarBg =>
      isDark ? const Color(0xFF111528) : const Color(0xFFFFFFFF);
  Color get topBarBg =>
      isDark ? const Color(0xFF111528) : const Color(0xFFFFFFFF);

  /// Low-opacity purple border token (alias of [border] in dark; light stays grey).
  Color get borderAccent => border;

  /// Dark input fill; light matches elevated surface white family.
  Color get inputFill =>
      isDark ? const Color(0xFF0C1028) : const Color(0xFFFFFFFF);

  /// Interactive link accent.
  Color get linkAccent =>
      isDark ? const Color(0xFFA855F7) : const Color(0xFF3B82F6);

  /// Ambient glow (auth-style orbs) — dark only; light unused.
  Color get glowPurple =>
      isDark ? const Color(0xFF7C3AED).withOpacity(0.38) : Colors.transparent;
  Color get glowIndigo =>
      isDark ? const Color(0xFF6366F1).withOpacity(0.14) : Colors.transparent;

  /// Primary CTA gradient stops.
  List<Color> get primaryGradientColors => isDark
      ? const [Color(0xFF6366F1), Color(0xFFA855F7), Color(0xFFC084FC)]
      : const [Color(0xFF3B82F6), Color(0xFF2563EB)];

  LinearGradient get primaryGradient => LinearGradient(
        begin: Alignment.centerLeft,
        end: Alignment.centerRight,
        colors: primaryGradientColors,
      );

  double get cardRadius => 18;
  double get inputRadius => 10;
  double get buttonRadius => 12;

  List<BoxShadow> get cardShadow => isDark
      ? [
          BoxShadow(
            color: const Color(0xFF6366F1).withOpacity(0.34),
            blurRadius: 32,
            spreadRadius: 2,
            offset: const Offset(0, 12),
          ),
          BoxShadow(
            color: Colors.black.withOpacity(0.35),
            blurRadius: 24,
            offset: const Offset(0, 8),
          ),
        ]
      : [
          BoxShadow(
            color: const Color(0xFF0F172A).withOpacity(0.06),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ];

  ThemeData get themeData {
    final base = isDark ? ThemeData.dark() : ThemeData.light();
    final radius = BorderRadius.circular(buttonRadius);
    final primaryButtonStyle = ButtonStyle(
      foregroundColor: const WidgetStatePropertyAll(Colors.white),
      backgroundColor: WidgetStatePropertyAll(
        isDark ? Colors.transparent : accent,
      ),
      shadowColor: WidgetStatePropertyAll(
        isDark
            ? const Color(0xFF7C3AED).withOpacity(0.45)
            : accent.withOpacity(0.25),
      ),
      elevation: WidgetStatePropertyAll(isDark ? 6 : 2),
      padding: const WidgetStatePropertyAll(
        EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      ),
      shape: WidgetStatePropertyAll(
        RoundedRectangleBorder(borderRadius: radius),
      ),
      backgroundBuilder: isDark
          ? (context, states, child) {
              final disabled = states.contains(WidgetState.disabled);
              return DecoratedBox(
                decoration: BoxDecoration(
                  gradient: disabled
                      ? LinearGradient(
                          colors: primaryGradientColors
                              .map((c) => c.withOpacity(0.35))
                              .toList(),
                        )
                      : primaryGradient,
                  borderRadius: radius,
                  boxShadow: disabled
                      ? null
                      : [
                          BoxShadow(
                            color: const Color(0xFF7C3AED).withOpacity(0.35),
                            blurRadius: 16,
                            offset: const Offset(0, 6),
                          ),
                        ],
                ),
                child: child,
              );
            }
          : null,
    );
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
      elevatedButtonTheme: ElevatedButtonThemeData(style: primaryButtonStyle),
      filledButtonTheme: FilledButtonThemeData(style: primaryButtonStyle),
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

  /// Ambient purple/indigo glow backdrop (dark only).
  /// Light paints [scaffold] only — no glow — so transparent Scaffolds still have a fill.
  Widget ambientGlowBackdrop({required Widget child}) {
    if (!isDark) {
      return ColoredBox(color: scaffold, child: child);
    }
    return Stack(
      fit: StackFit.expand,
      children: [
        ColoredBox(color: scaffold),
        Positioned(
          top: -140,
          left: -100,
          child: _AmbientGlowOrb(diameter: 420, color: glowPurple),
        ),
        Positioned(
          bottom: -160,
          left: -80,
          child: _AmbientGlowOrb(diameter: 380, color: glowIndigo),
        ),
        const Positioned.fill(
          child: IgnorePointer(
            child: CustomPaint(painter: _DottedGridPainter()),
          ),
        ),
        child,
      ],
    );
  }
}

class _AmbientGlowOrb extends StatelessWidget {
  final double diameter;
  final Color color;

  const _AmbientGlowOrb({required this.diameter, required this.color});

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Container(
        width: diameter,
        height: diameter,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: RadialGradient(
            colors: [
              color,
              color.withOpacity(0.35),
              Colors.transparent,
            ],
            stops: const [0.0, 0.45, 1.0],
          ),
        ),
      ),
    );
  }
}

/// Static dotted texture — does not repaint.
class _DottedGridPainter extends CustomPainter {
  const _DottedGridPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFFA855F7).withOpacity(0.12)
      ..style = PaintingStyle.fill;
    const step = 22.0;
    const radius = 1.1;
    for (double y = 0; y < size.height; y += step) {
      for (double x = 0; x < size.width; x += step) {
        canvas.drawCircle(Offset(x, y), radius, paint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
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
