import 'package:flutter/material.dart';
import '../student_dashboard.dart';

/// Thin wrapper — opens StudentDashboard shell on Collaboration → Editor tab.
class ProjectWorkspaceScreen extends StatelessWidget {
  final int projectId;

  const ProjectWorkspaceScreen({super.key, required this.projectId});

  @override
  Widget build(BuildContext context) {
    return StudentDashboard(
      initialIndex: 3,
      initialProjectId: projectId,
      initialProjectTab: 0,
    );
  }
}
