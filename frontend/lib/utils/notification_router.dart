import '../models/app_notification.dart';
import '../config/dev_user_config.dart';

class NotificationRoute {
  final String routeName;
  final Map<String, dynamic>? arguments;

  NotificationRoute({required this.routeName, this.arguments});
}

NotificationRoute? routeNotification(AppNotification notification, String userRole) {
  final payload = notification.payload ?? {};
  final screen = payload['screen'] as String?;

  if (screen == 'analyze' && payload['document_id'] != null) {
    return NotificationRoute(
      routeName: '/analyze',
      arguments: {'documentId': payload['document_id'] as int},
    );
  }

  if (screen == 'submissions' && payload['submission_id'] != null) {
    if (userRole == 'student') {
      return NotificationRoute(
        routeName: '/status-tracker',
        arguments: {'submissionId': payload['submission_id'] as int},
      );
    }
  }

  if (screen == 'assignment_requests') {
    if (userRole == 'supervisor') {
      return NotificationRoute(
        routeName: '/supervisor-dashboard',
        arguments: {'initialTab': 2},
      );
    }
  }

  if (screen == 'comments' && payload['document_id'] != null) {
    return NotificationRoute(
      routeName: '/analyze',
      arguments: {'documentId': payload['document_id'] as int},
    );
  }

  if (screen == 'meeting_notes') {
    if (userRole == 'student') {
      return NotificationRoute(routeName: '/meeting-notes');
    }
  }

  if (screen == 'collaboration' && payload['project_id'] != null) {
    return NotificationRoute(
      routeName: '/collaboration/project',
      arguments: {
        'projectId': payload['project_id'] as int,
        'tab': payload['tab'] as int? ?? 0,
      },
    );
  }

  if (screen == 'deadlines' && DevUserConfig.hasFypModule) {
    return NotificationRoute(routeName: '/milestones');
  }

  if (screen == 'users' && userRole == 'admin') {
    return NotificationRoute(routeName: '/admin-dashboard', arguments: {'initialTab': 0});
  }

  if (screen == 'supervisors' && userRole == 'admin') {
    return NotificationRoute(routeName: '/admin-dashboard', arguments: {'initialTab': 1});
  }

  return null;
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
