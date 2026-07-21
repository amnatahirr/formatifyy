import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:async';
import 'package:url_launcher/url_launcher.dart';
import 'package:app_links/app_links.dart';
import '../config/api_config.dart';
import '../config/dev_user_config.dart';

class AuthProvider extends ChangeNotifier {
  late String baseUrl;

  String? _currentUser;
  String? _userEmail;
  int? _userId;
  String? _userRole;
  bool _isLoggedIn = false;
  String? _errorMessage;
  bool _isLoading = false;
  bool _hasGoogleDrive = false;
  String? _googleDriveEmail;
  bool _devBootstrap = false;

  String? get currentUser => _currentUser;
  String? get userEmail => _userEmail;
  String? get email => _userEmail;
  int? get userId => _userId;
  String? get userRole => _userRole;
  bool get isAdmin => _userRole == "admin";
  bool get isSupervisor => _userRole == "supervisor";
  bool get isStudent => _userRole == "student" || (_userRole != null && !isAdmin && !isSupervisor);
  bool get isLoggedIn => _isLoggedIn;
  String? get errorMessage => _errorMessage;
  bool get isLoading => _isLoading;
  bool get hasGoogleDrive => _hasGoogleDrive;
  String? get googleDriveEmail => _googleDriveEmail;
  bool get isDevBootstrap => _devBootstrap;

  AuthProvider({String? devUserKey}) {
    baseUrl = ApiConfig.getBaseUrl();
    if (devUserKey != null) {
      _bootstrapDevUser(devUserKey);
    }
  }

  /// Auto-login for local multi-instance testing via --dart-define=USER_ID=member1|member2
  void _bootstrapDevUser(String memberKey) {
    DevUserConfig.initialize(memberKey);
    _userId = DevUserConfig.backendUserId;
    _currentUser = DevUserConfig.username;
    _userEmail = DevUserConfig.email;
    _userRole = DevUserConfig.role;
    _isLoggedIn = true;
    _devBootstrap = true;
    debugPrint(
      '[DevUser] Bootstrapped $memberKey → id=$_userId (${_currentUser})',
    );
  }

  Future<bool> signup(
    String username,
    String email,
    String password, {
    int? universityId,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await http
          .post(
            Uri.parse("${baseUrl}/auth/signup"),
            headers: {"Content-Type": "application/json"},
            body: jsonEncode({
              "username": username,
              "email": email,
              "password": password,
              "university_id": universityId ?? 1,
            }),
          )
          .timeout(
            Duration(seconds: 10),
            onTimeout: () => throw TimeoutException('Connection timeout'),
          );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _userId = data["id"];
        _currentUser = data["username"];
        _userEmail = data["email"];
        _userRole = data.get("role", "student");
        _isLoggedIn = true;
        _devBootstrap = false;
        debugPrint("[v0] Signup successful: ${data['message']}");
        return true;
      } else {
        _errorMessage = jsonDecode(response.body)["detail"] ?? "Signup failed";
        debugPrint("[v0] Signup failed: ${response.body}");
        return false;
      }
    } on TimeoutException catch (e) {
      _errorMessage =
          "Connection timeout. Make sure your backend is running on http://localhost:8000";
      debugPrint("[v0] Signup timeout: $e");
      return false;
    } catch (e) {
      _errorMessage =
          "Network error: $e. Try using your machine IP instead of localhost.";
      debugPrint("[v0] Signup error: $e");
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> login(String email, String password) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await http
          .post(
            Uri.parse("${baseUrl}/auth/login"),
            headers: {"Content-Type": "application/json"},
            body: jsonEncode({"email": email, "password": password}),
          )
          .timeout(
            Duration(seconds: 10),
            onTimeout: () => throw TimeoutException('Connection timeout'),
          );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _userId = data["id"];
        _currentUser = data["username"];
        _userEmail = data["email"];
        _userRole = data["role"];
        _isLoggedIn = true;
        _devBootstrap = false;
        debugPrint(
          "[v0] Login successful for user: $_currentUser with role: $_userRole",
        );
        
        // Check if user has Google Drive connected
        await checkGoogleDriveStatus();
        
        return true;
      } else {
        _errorMessage = jsonDecode(response.body)["detail"] ?? "Login failed";
        debugPrint("[v0] Login failed: ${response.body}");
        return false;
      }
    } on TimeoutException catch (e) {
      _errorMessage =
          "Connection timeout. Make sure your backend is running on http://localhost:8000";
      debugPrint("[v0] Login timeout: $e");
      return false;
    } catch (e) {
      _errorMessage =
          "Network error: $e. Try using your machine IP instead of localhost.";
      debugPrint("[v0] Login error: $e");
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  void logout() {
    _currentUser = null;
    _userEmail = null;
    _userId = null;
    _userRole = null;
    _isLoggedIn = false;
    _errorMessage = null;
    _hasGoogleDrive = false;
    _googleDriveEmail = null;
    notifyListeners();
  }

  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }

  Future<bool> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    if (_userId == null) {
      _errorMessage = 'You must be logged in.';
      notifyListeners();
      return false;
    }

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/auth/change-password'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'user_id': _userId,
              'current_password': currentPassword,
              'new_password': newPassword,
            }),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        return true;
      }

      try {
        final data = jsonDecode(response.body);
        _errorMessage = (data['detail'] ?? 'Could not change password').toString();
      } catch (_) {
        _errorMessage = 'Could not change password';
      }
      return false;
    } catch (e) {
      _errorMessage = 'Network error: $e';
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Check if the current user has Google Drive tokens stored
  Future<void> checkGoogleDriveStatus() async {
    if (_userId == null) return;
    
    try {
      final response = await http.get(
        Uri.parse("${baseUrl}/auth/google/debug/tokens?user_id=$_userId"),
      ).timeout(Duration(seconds: 5));
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _hasGoogleDrive = data["tokens_found"] == true;
        debugPrint("[v0] Google Drive status for user $_userId: $_hasGoogleDrive");
        notifyListeners();
      }
    } catch (e) {
      debugPrint("[v0] Error checking Google Drive status: $e");
    }
  }

  /// Connect Google Drive to the currently logged-in user account.
  /// This links Google Drive tokens to the existing user instead of creating a new account.
  Future<bool> connectGoogleDrive() async {
    if (_userId == null) {
      _errorMessage = "Please login first before connecting Google Drive";
      notifyListeners();
      return false;
    }
    
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      debugPrint("[v0] Starting Google Drive connection for user $_userId...");

      // Get the authorization URL from backend with link_to_user_id parameter
      final authUrlResponse = await http
          .get(Uri.parse("${baseUrl}/auth/google/authorize?link_to_user_id=$_userId"))
          .timeout(
            Duration(seconds: 10),
            onTimeout: () => throw TimeoutException('Failed to get auth URL'),
          );

      if (authUrlResponse.statusCode != 200) {
        throw Exception("Failed to get Google OAuth URL");
      }

      final authUrl = Uri.parse(authUrlResponse.body.replaceAll('"', ''));
      debugPrint("[v0] Got Google auth URL for linking to user $_userId");

      if (await canLaunchUrl(authUrl)) {
        await launchUrl(authUrl, mode: LaunchMode.externalApplication);
        debugPrint("[v0] Opened Google authorization URL in browser");
        debugPrint("[v0] Waiting for OAuth callback...");
        
        // Poll for OAuth completion (up to 120 seconds)
        int attempts = 0;
        while (attempts < 60) {
          await Future.delayed(const Duration(seconds: 2));

          final statusResponse = await http
              .get(Uri.parse("${baseUrl}/auth/google/status"))
              .timeout(
                Duration(seconds: 10),
                onTimeout: () => throw TimeoutException('Status check timeout'),
              );

          if (statusResponse.statusCode == 200) {
            final data = jsonDecode(statusResponse.body);
            if (data["authenticated"] == true) {
              // Google Drive connected successfully
              _hasGoogleDrive = true;
              _googleDriveEmail = data["google_email"];
              debugPrint("[v0] Google Drive connected successfully for user $_userId");
              debugPrint("[v0] Google Drive email: $_googleDriveEmail");
              notifyListeners();
              return true;
            }
          }
          attempts++;
        }

        _errorMessage = "Google OAuth callback timed out. Please try again.";
        debugPrint("[v0] Google OAuth timed out after 120 seconds");
        return false;
      } else {
        _errorMessage = "Could not launch Google OAuth URL";
        debugPrint("[v0] Could not launch URL: $authUrl");
        return false;
      }
    } on TimeoutException catch (e) {
      _errorMessage = "Connection timeout. Make sure your backend is running.";
      debugPrint("[v0] Google Drive connection timeout: $e");
      return false;
    } catch (e) {
      _errorMessage = "Google Drive connection error: $e";
      debugPrint("[v0] Google Drive connection error: $e");
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Sign in with Google (creates new account or logs into existing Google account)
  Future<bool> googleSignIn() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      debugPrint("[v0] Starting Google OAuth flow...");

      // Get the authorization URL from backend (without link_to_user_id for sign-in)
      final authUrlResponse = await http
          .get(Uri.parse("${baseUrl}/auth/google/authorize"))
          .timeout(
            Duration(seconds: 10),
            onTimeout: () => throw TimeoutException('Failed to get auth URL'),
          );

      if (authUrlResponse.statusCode != 200) {
        throw Exception("Failed to get Google OAuth URL");
      }

      final authUrl = Uri.parse(authUrlResponse.body.replaceAll('"', ''));
      debugPrint("[v0] Got Google auth URL");

      if (await canLaunchUrl(authUrl)) {
        await launchUrl(authUrl, mode: LaunchMode.externalApplication);
        debugPrint("[v0] Opened Google authorization URL in browser");
        debugPrint("[v0] Waiting for OAuth callback...");
        
        // Poll for OAuth completion (up to 120 seconds)
        int attempts = 0;
        while (attempts < 60) {
          await Future.delayed(const Duration(seconds: 2));

          final statusResponse = await http
              .get(Uri.parse("${baseUrl}/auth/google/status"))
              .timeout(
                Duration(seconds: 10),
                onTimeout: () => throw TimeoutException('Status check timeout'),
              );

          if (statusResponse.statusCode == 200) {
            final data = jsonDecode(statusResponse.body);
            if (data["authenticated"] == true) {
              _userId = data["id"];
              _currentUser = data["username"];
              _userEmail = data["email"];
              _userRole = data["role"];
              _isLoggedIn = true;
              _hasGoogleDrive = data["has_google_drive"] == true;
              _googleDriveEmail = data["google_email"];
              debugPrint("[v0] Google Sign-In successful: $_userEmail");
              return true;
            }
          }
          attempts++;
        }

        _errorMessage = "Google OAuth callback timed out. Please try again.";
        debugPrint("[v0] Google OAuth timed out after 120 seconds");
        return false;
      } else {
        _errorMessage = "Could not launch Google OAuth URL";
        debugPrint("[v0] Could not launch URL: $authUrl");
        return false;
      }
    } on TimeoutException catch (e) {
      _errorMessage = "Connection timeout. Make sure your backend is running.";
      debugPrint("[v0] Google OAuth timeout: $e");
      return false;
    } catch (e) {
      _errorMessage = "Google Sign-In error: $e";
      debugPrint("[v0] Google Sign-In error: $e");
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> githubSignIn() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      debugPrint("[v0] Starting GitHub OAuth flow...");

      // Get the authorization URL from backend
      final authUrlResponse = await http
          .get(Uri.parse("${baseUrl}/auth/github/authorize"))
          .timeout(
            Duration(seconds: 10),
            onTimeout: () => throw TimeoutException('Failed to get auth URL'),
          );

      if (authUrlResponse.statusCode != 200) {
        throw Exception("Failed to get GitHub OAuth URL");
      }

      final authUrl = Uri.parse(authUrlResponse.body.replaceAll('"', ''));
      debugPrint("[v0] Got GitHub auth URL: $authUrl");

      if (await canLaunchUrl(authUrl)) {
        await launchUrl(authUrl, mode: LaunchMode.externalApplication);
        debugPrint("[v0] Opened GitHub authorization URL in browser");

        // Check backend for auth result every 2 seconds (up to 120 seconds)
        int attempts = 0;
        while (attempts < 60) {
          await Future.delayed(const Duration(seconds: 2));

          final statusResponse = await http
              .get(Uri.parse("${baseUrl}/auth/github/status"))
              .timeout(
                Duration(seconds: 10),
                onTimeout: () => throw TimeoutException('Status check timeout'),
              );

          if (statusResponse.statusCode == 200) {
            final data = jsonDecode(statusResponse.body);
            if (data["authenticated"] == true) {
              _userId = data["id"];
              _currentUser = data["username"];
              _userEmail = data["email"];
              _userRole = data["role"];
              _isLoggedIn = true;
              debugPrint("[v0] GitHub Sign-In successful: $_userEmail");
              return true;
            }
          }
          attempts++;
        }

        _errorMessage = "GitHub OAuth callback timed out. Please try again.";
        debugPrint("[v0] GitHub OAuth timed out after 120 seconds");
        return false;
      } else {
        _errorMessage = "Could not launch GitHub OAuth URL";
        debugPrint("[v0] Could not launch URL: $authUrl");
        return false;
      }
    } on TimeoutException catch (e) {
      _errorMessage = "Connection timeout. Make sure your backend is running.";
      debugPrint("[v0] GitHub OAuth timeout: $e");
      return false;
    } catch (e) {
      _errorMessage = "GitHub Sign-In error: $e";
      debugPrint("[v0] GitHub Sign-In error: $e");
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
  
  /// Update Google Drive connection status manually
  void setGoogleDriveConnected(bool connected, {String? email}) {
    _hasGoogleDrive = connected;
    _googleDriveEmail = email;
    notifyListeners();
  }
}
