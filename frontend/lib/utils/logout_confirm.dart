import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';

import '../widgets/tr.dart';

/// Shows "Do you want to Logout?" with Cancel / Logout.
/// Returns `true` only if the user confirms Logout.
Future<bool> showLogoutConfirmation(BuildContext context) async {
  final p = context.read<ThemeProvider>().palette;

  final result = await showDialog<bool>(
    context: context,
    barrierDismissible: true,
    builder: (dialogContext) {
      return AlertDialog(
        backgroundColor: p.surface,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: p.border),
        ),
        title: Tr(
          'Logout',
          style: TextStyle(
            color: p.textPrimary,
            fontSize: 18,
            fontWeight: FontWeight.w600,
          ),
        ),
        content: Tr(
          'Do you want to Logout?',
          style: TextStyle(color: p.textSecondary, fontSize: 14),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            style: TextButton.styleFrom(foregroundColor: p.textSecondary),
            child: const Tr('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            style: TextButton.styleFrom(
              foregroundColor: const Color(0xFFEF4444),
            ),
            child: const Tr('Logout'),
          ),
        ],
      );
    },
  );
  return result == true;
}

/// Confirm, then call [AuthProvider.logout]. Always returns to the login
/// screen afterwards; optional [afterLogout] runs just before navigation.
Future<void> confirmAndLogout(
  BuildContext context, {
  VoidCallback? afterLogout,
}) async {
  final confirmed = await showLogoutConfirmation(context);
  if (!confirmed || !context.mounted) return;

  // Capture everything that needs context BEFORE any await.
  final navigator = Navigator.of(context, rootNavigator: true);
  final auth = context.read<AuthProvider>();
  final theme = context.read<ThemeProvider>();

  try {
    await auth.logout();
  } catch (e) {
    debugPrint('[logout] auth.logout failed: $e');
  }
  try {
    await theme.resetToDefaultDark();
  } catch (e) {
    debugPrint('[logout] theme reset failed: $e');
  }
  try {
    afterLogout?.call();
  } catch (e) {
    debugPrint('[logout] afterLogout failed: $e');
  }

  navigator.pushNamedAndRemoveUntil('/', (route) => false);
}
