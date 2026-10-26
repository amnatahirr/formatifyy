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

  /// StudentDashboard mounted ho to true.
  static bool hostAttached = false;

  static void open(AnalysisRequest r) {
    if (hostAttached) {
      request.value = r; // dashboard ke andar, sidebar wahi rahegi
    } else {
      navigatorKey.currentState?.push(MaterialPageRoute(
        builder: (_) => AnalyzeScreen(
          documentId: r.documentId,
          documentName: r.documentName,
          templateId: r.templateId,
          templateName: r.templateName,
          freeformAnalysis: r.freeform,
        ),
      ));
    }
  }

  static void close() => request.value = null;
}