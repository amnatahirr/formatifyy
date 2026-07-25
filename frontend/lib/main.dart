import 'dart:async';
import 'package:flutter/foundation.dart' show debugPrint;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:app_links/app_links.dart';
import 'config/dev_user_config.dart';
import 'screens/login_screen.dart';
import 'screens/student_dashboard.dart';
import 'screens/admin_dashboard.dart';
import 'screens/supervisor_dashboard.dart';
import 'screens/mobile_qr_upload_screen.dart';
import 'screens/mobile_qr_download_screen.dart';
import 'providers/auth_provider.dart';
import 'providers/document_provider.dart';
import 'providers/template_provider.dart';
import 'providers/upload_provider.dart';
import 'providers/image_formatter_provider.dart';
import 'providers/collaboration_provider.dart';
import 'providers/fyp_provider.dart';

final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

void main() {
  // Dev auto-login is OFF unless BOTH dart-defines are set:
  //   flutter run --dart-define=USER_ID=member2 --dart-define=ENABLE_DEV_BOOTSTRAP=true
  const userId = String.fromEnvironment('USER_ID', defaultValue: '');
  const enableBootstrap =
      bool.fromEnvironment('ENABLE_DEV_BOOTSTRAP', defaultValue: false);
  final shouldBootstrap = enableBootstrap && userId.isNotEmpty;
  if (shouldBootstrap) {
    DevUserConfig.initialize(userId);
  }
  runApp(MyApp(devUserKey: shouldBootstrap ? userId : null));
}


class MyApp extends StatefulWidget {
  final String? devUserKey;

  const MyApp({Key? key, this.devUserKey}) : super(key: key);

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  late final AppLinks _appLinks;
  StreamSubscription<Uri>? _linkSubscription;

  @override
  void initState() {
    super.initState();
    _initDeepLinks();
  }

  Future<void> _initDeepLinks() async {
    _appLinks = AppLinks();

    // Handle deep links while app is already running
    _linkSubscription = _appLinks.uriLinkStream.listen((uri) {
      _handleDeepLink(uri);
    });

    // Handle initial link when app is cold-started from a deep link
    final initialUri = await _appLinks.getInitialLink();
    if (initialUri != null) {
      _handleDeepLink(initialUri);
    }
  }

  void _handleDeepLink(Uri uri) {
    if (uri.scheme != 'formatify') return;

    final context = navigatorKey.currentContext;
    if (context == null) return;

    // QR companion deep links must not bypass login.
    final auth = Provider.of<AuthProvider>(context, listen: false);
    if (!auth.isLoggedIn) {
      debugPrint(
        '[DeepLink] Ignored $uri — user not authenticated. Sign in first.',
      );
      return;
    }

    final host = uri.queryParameters['host'] ?? '172.20.10.2:8000';

    if (uri.host == 'qr-upload') {
      final session = uri.queryParameters['session'];
      if (session != null) {
        navigatorKey.currentState?.push(
          MaterialPageRoute(
            builder: (_) => MobileQrUploadScreen(sessionId: session, host: host),
          ),
        );
      }
    } else if (uri.host == 'qr-download') {
      final id = uri.queryParameters['id'];
      if (id != null) {
        navigatorKey.currentState?.push(
          MaterialPageRoute(
            builder: (_) => MobileQrDownloadScreen(qrId: id, host: host),
          ),
        );
      }
    }
  }

  @override
  void dispose() {
    _linkSubscription?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(
          create: (_) => AuthProvider(devUserKey: widget.devUserKey),
        ),
        ChangeNotifierProvider(create: (_) => DocumentProvider()),
        ChangeNotifierProvider(create: (_) => TemplateProvider()),
        ChangeNotifierProvider(create: (_) => UploadProvider()),
        ChangeNotifierProvider(create: (_) => ImageFormatterProvider()),
        ChangeNotifierProvider(create: (_) => CollaborationProvider()),
        ChangeNotifierProvider(create: (_) => FypProvider()),
      ],
      child: MaterialApp(
        navigatorKey: navigatorKey,
        debugShowCheckedModeBanner: false,
        title: 'FORMATIFY',
        theme: ThemeData(
          useMaterial3: true,
          brightness: Brightness.dark,
          scaffoldBackgroundColor: const Color(0xFF0F1419),
          primaryColor: const Color(0xFF6366F1),
          secondaryHeaderColor: const Color(0xFF8B5CF6),
          cardColor: const Color(0xFF1A1F2E),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF141B27),
            elevation: 0,
            surfaceTintColor: Colors.transparent,
          ),
          navigationRailTheme: NavigationRailThemeData(
            backgroundColor: const Color(0xFF141B27),
            selectedIconTheme: const IconThemeData(color: Color(0xFF6366F1), size: 24),
            unselectedIconTheme: const IconThemeData(color: Color(0xFF64748B), size: 24),
            selectedLabelTextStyle: const TextStyle(color: Color(0xFF6366F1), fontWeight: FontWeight.w600),
          ),
          inputDecorationTheme: InputDecorationTheme(
            filled: true,
            fillColor: const Color(0xFF1A1F2E),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: const BorderSide(color: Color(0xFF2D3748)),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: const BorderSide(color: Color(0xFF2D3748)),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: const BorderSide(color: Color(0xFF6366F1), width: 2),
            ),
            labelStyle: const TextStyle(color: Color(0xFF94A3B8)),
          ),
          elevatedButtonTheme: ElevatedButtonThemeData(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF6366F1),
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              textStyle: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
          outlinedButtonTheme: OutlinedButtonThemeData(
            style: OutlinedButton.styleFrom(
              foregroundColor: const Color(0xFF6366F1),
              side: const BorderSide(color: Color(0xFF6366F1)),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
          ),
        ),
        routes: {
          '/login': (_) => const LoginScreen(),
          '/student-dashboard': (_) => const StudentDashboard(),
          '/admin-dashboard': (_) => const AdminDashboard(),
          '/supervisor-dashboard': (_) => const SupervisorDashboard(),
          '/new-report': (_) => const StudentDashboard(initialIndex: 1),
          '/collaboration': (_) => const StudentDashboard(initialIndex: 3),
          '/collaboration/project': (context) {
            final args = ModalRoute.of(context)?.settings.arguments;
            final projectId = args is int
                ? args
                : (args is Map ? args['projectId'] as int? : null);
            if (projectId == null) {
              return const StudentDashboard(initialIndex: 3);
            }
            final initialTab = args is Map ? (args['tab'] as int? ?? 0) : 0;
            return StudentDashboard(
              initialIndex: 3,
              initialProjectId: projectId,
              initialProjectTab: initialTab,
            );
          },
        },
        darkTheme: ThemeData(
          useMaterial3: true,
          brightness: Brightness.dark,
          scaffoldBackgroundColor: const Color(0xFF0F1419),
          primaryColor: const Color(0xFF6366F1),
        ),
        themeMode: ThemeMode.dark,
        // Same auth gate on mobile and desktop — Quick Access is reached from
        // the authenticated student dashboard, not as the app landing screen.
        home: const AuthCheck(),
      ),
    );
  }
}

class AuthCheck extends StatefulWidget {
  const AuthCheck({Key? key}) : super(key: key);

  @override
  State<AuthCheck> createState() => _AuthCheckState();
}

class _AuthCheckState extends State<AuthCheck> {
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _restore());
  }

  Future<void> _restore() async {
    final auth = context.read<AuthProvider>();
    // Always clear leftover bootstrap/dev sessions and never auto-login on
    // launch/hot-restart. User must sign in explicitly each cold start unless
    // we later re-enable opt-in "Remember me" restore.
    await auth.ensureCleanLaunch();
    if (mounted) setState(() => _ready = true);
  }

  @override
  Widget build(BuildContext context) {
    if (!_ready) {
      return const Scaffold(
        backgroundColor: Color(0xFF0F1419),
        body: Center(
          child: CircularProgressIndicator(color: Color(0xFF6366F1)),
        ),
      );
    }

    return Consumer<AuthProvider>(
      builder: (context, authProvider, _) {
        if (authProvider.isLoggedIn) {
          // Explicit --dart-define=USER_ID=… collab bootstrap stays on student shell.
          if (authProvider.isDevBootstrap) {
            return const StudentDashboard();
          }
          if (authProvider.isAdmin) {
            return const AdminDashboard();
          }
          if (authProvider.isSupervisor) {
            return const SupervisorDashboard();
          }
          return const StudentDashboard();
        }
        return const LoginScreen();
      },
    );
  }
}
