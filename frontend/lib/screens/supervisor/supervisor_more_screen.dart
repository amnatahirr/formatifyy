import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../widgets/admin/admin_ui.dart';

/// Mobile "More" hub — secondary supervisor tools + account.
class SupervisorMoreScreen extends StatelessWidget {
  final VoidCallback onOpenNotifications;
  final VoidCallback onOpenPlagiarism;
  final VoidCallback onOpenProfile;
  final int unreadCount;

  const SupervisorMoreScreen({
    super.key,
    required this.onOpenNotifications,
    required this.onOpenPlagiarism,
    required this.onOpenProfile,
    this.unreadCount = 0,
  });

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    return AdminPage(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageHeader(
            title: 'More',
            subtitle: auth.currentUser ?? 'Supervisor tools & account',
          ),
          const SizedBox(height: 18),
          AdminSectionCard(
            title: 'Quick access',
            child: Column(
              children: [
                _MoreTile(
                  icon: Icons.notifications_outlined,
                  label: 'Notifications',
                  subtitle: unreadCount > 0
                      ? '$unreadCount unread'
                      : 'Submissions & student replies',
                  badge: unreadCount,
                  onTap: onOpenNotifications,
                ),
                const SizedBox(height: 10),
                _MoreTile(
                  icon: Icons.policy_rounded,
                  label: 'Plagiarism Monitor',
                  subtitle: 'Check group similarity risks',
                  onTap: onOpenPlagiarism,
                ),
                const SizedBox(height: 10),
                _MoreTile(
                  icon: Icons.person_rounded,
                  label: 'Profile & Password',
                  subtitle: auth.userEmail ?? 'Account settings',
                  onTap: onOpenProfile,
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: () => context.read<AuthProvider>().logout(),
              icon: const Icon(Icons.logout_rounded, size: 18),
              label: const Text('Log out'),
              style: OutlinedButton.styleFrom(
                foregroundColor: AdminColors.danger,
                side: BorderSide(color: AdminColors.danger.withOpacity(0.55)),
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MoreTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String subtitle;
  final VoidCallback onTap;
  final int badge;

  const _MoreTile({
    required this.icon,
    required this.label,
    required this.subtitle,
    required this.onTap,
    this.badge = 0,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        decoration: BoxDecoration(
          color: AdminColors.background.withOpacity(0.45),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AdminColors.border.withOpacity(0.7)),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AdminColors.primary.withOpacity(0.14),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: AdminColors.primary, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                      fontSize: 14,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.5),
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
            if (badge > 0)
              Container(
                margin: const EdgeInsets.only(right: 8),
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AdminColors.primary,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  badge > 99 ? '99+' : '$badge',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            Icon(Icons.chevron_right_rounded, color: Colors.white.withOpacity(0.45)),
          ],
        ),
      ),
    );
  }
}
