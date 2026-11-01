import 'package:flutter/material.dart';
import '../main.dart' show navigatorKey;
import '../screens/analyze_screen.dart';

class AnalysisRequest {
  final int documentId;
  final String documentName;
  final int templateId;
  final String templateName;
  final bool freeform;
  const AnalysisRequest({
    required this.documentId,
    required this.documentName,
    required this.templateId,
    required this.templateName,
    this.freeform = false,
  });
}

class AnalysisNav {
  /// Dashboard ke content area mein dikhne wali analysis.
  static final ValueNotifier<AnalysisRequest?> request = ValueNotifier(null);


  static Object? _host;
  static bool get hostAttached => _host != null;
    static void attach(Object host) => _host = host;
     static void detach(Object host) {
    if (identical(_host, host)) _host = null;
  }


static void open(AnalysisRequest r) {
  request.value = r; // hamesha request save karo

  if (!hostAttached) {
    debugPrint('AnalysisNav.open with no host. Caller:\n${StackTrace.current}');
    navigatorKey.currentState?.pushNamedAndRemoveUntil(
      '/student-dashboard',
      (_) => false,
    );
  }
}

  static void close() => request.value = null;
}