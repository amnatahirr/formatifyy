import 'package:flutter/material.dart';
import '../student_dashboard.dart';

/// Thin wrapper — opens StudentDashboard shell on Collaboration → Version History.
class ProjectHistoryScreen extends StatelessWidget {
  final int projectId;
  final String projectName;

  const ProjectHistoryScreen({
    super.key,
    required this.projectId,
    required this.projectName,
  });

  @override
  Widget build(BuildContext context) {
    return StudentDashboard(
      initialIndex: 3,
      initialProjectId: projectId,
      initialProjectTab: 2,
    );
  }
}
