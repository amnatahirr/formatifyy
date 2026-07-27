import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';

/// Shows "Do you want to Logout?" with Cancel / Logout.
/// Returns `true` only if the user confirms Logout.
Future<bool> showLogoutConfirmation(BuildContext context) async {
  final result = await showDialog<bool>(
    context: context,
    barrierDismissible: true,
    builder: (dialogContext) {
      return AlertDialog(
        title: const Text('Logout'),
        content: const Text('Do you want to Logout?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            style: TextButton.styleFrom(foregroundColor: const Color(0xFFEF4444)),
            child: const Text('Logout'),
          ),
        ],
      );
    },
  );
  return result == true;
}

/// Confirm, then call [AuthProvider.logout]. Optional [afterLogout] runs only
/// after a confirmed logout (e.g. navigate to `/login`).
Future<void> confirmAndLogout(
  BuildContext context, {
  VoidCallback? afterLogout,
}) async {
  final confirmed = await showLogoutConfirmation(context);
  if (!confirmed || !context.mounted) return;
  await context.read<AuthProvider>().logout();
  if (!context.mounted) return;
  afterLogout?.call();
}
