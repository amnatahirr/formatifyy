import '../models/app_notification.dart';

class NotificationRoute {
  final String routeName;
  final Map<String, dynamic>? arguments;

  NotificationRoute({required this.routeName, this.arguments});
}

NotificationRoute? routeNotification(AppNotification notification, String userRole) {
  final payload = notification.payload ?? {};
  final screen = payload['screen'] as String?;
  final isAdmin = userRole == 'admin';
  final isSuperAdmin = userRole == 'super_admin' || userRole == 'superadmin';
  final isSupervisor = userRole == 'supervisor';

  NotificationRoute analyzeRoute() {
    final docId = payload['document_id'];
    if (docId is! int) {
      return NotificationRoute(routeName: '/notifications');
    }
    return NotificationRoute(
      routeName: '/analyze',
      arguments: {
        'documentId': docId,
        'documentName': payload['document_name'],
        'templateId': payload['template_id'],
        'templateName': payload['template_name'],
        'freeform': payload['freeform'] ?? false,
      },
    );
  }

  switch (screen) {
    case 'analyze':
    case 'comments':
      return analyzeRoute();

    case 'submissions':
      if (isSupervisor) {
        return NotificationRoute(
          routeName: '/supervisor-dashboard',
          arguments: {'initialTab': 3},
        );
      }
      if (payload['submission_id'] != null) {
        return NotificationRoute(
          routeName: '/status-tracker',
          arguments: {'submissionId': payload['submission_id'] as int},
        );
      }
      break;

    case 'assignment_requests':
      if (isSupervisor) {
        return NotificationRoute(
          routeName: '/supervisor-dashboard',
          arguments: {'initialTab': 1},
        );
      }
      break;

    case 'meeting_notes':
      if (userRole == 'student') {
        return NotificationRoute(routeName: '/meeting-notes');
      }
      break;

    case 'collaboration':
      if (payload['project_id'] != null) {
        return NotificationRoute(
          routeName: '/collaboration/project',
          arguments: {
            'projectId': payload['project_id'] as int,
            'tab': payload['tab'] as int? ?? 0,
          },
        );
      }
      break;

    case 'deadlines':
      return NotificationRoute(routeName: '/milestones');

    case 'templates':
      if (isAdmin) {
        return NotificationRoute(
          routeName: '/admin-dashboard',
          arguments: {'initialId': 3},
        );
      }
      if (isSuperAdmin) {
        return NotificationRoute(routeName: '/super-admin');
      }
      return NotificationRoute(routeName: '/student-dashboard');

    case 'users':
      if (isAdmin) {
        return NotificationRoute(
          routeName: '/admin-dashboard',
          arguments: {'initialId': 6},
        );
      }
      if (isSuperAdmin) {
        return NotificationRoute(routeName: '/super-admin');
      }
      break;

    case 'supervisors':
      if (isAdmin) {
        return NotificationRoute(
          routeName: '/admin-dashboard',
          arguments: {'initialId': 2},
        );
      }
      if (isSuperAdmin) {
        return NotificationRoute(routeName: '/super-admin');
      }
      break;

    case 'notifications':
      return NotificationRoute(routeName: '/notifications');
  }

  // Unknown or unhandled screen: open the notifications list instead of
  // showing an error snackbar.
  return NotificationRoute(routeName: '/notifications');
}

String getErrorMessageForType(String type) {
  switch (type) {
    case 'analysis_finished':
      return 'The document for this analysis has been deleted.';
    case 'submission_approved':
    case 'submission_revision_requested':
    case 'submission_rejected':
      return 'The submission for this notification is no longer available.';
    case 'new_assignment_request':
      return 'This assignment request has been removed.';
    case 'student_submitted':
      return 'The submitted document is no longer available.';
    case 'supervisor_comment':
    case 'meeting_note':
      return 'The document or project for this comment has been deleted.';
    case 'collaboration_invite':
      return 'The project for this invitation has been deleted.';
    case 'merge_conflict':
    case 'member_commit':
      return 'The project for this update has been deleted.';
    case 'deadline_reminder_3_days':
    case 'deadline_reminder_1_day':
    case 'deadline_today':
      return 'The milestone for this deadline has been removed.';
    case 'supervisor_created':
    case 'new_user_signup':
      return 'The user referenced in this notification is no longer available.';
    default:
      return 'The target of this notification is no longer available.';
  }
}
