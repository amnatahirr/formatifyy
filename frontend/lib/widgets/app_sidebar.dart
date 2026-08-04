import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';
import '../utils/logout_confirm.dart';

class AppSidebar extends StatelessWidget {
  final int selectedIndex;
  final Function(int) onItemSelected;

  const AppSidebar({
    Key? key,
    required this.selectedIndex,
    required this.onItemSelected,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final p = context.watch<ThemeProvider>().palette;

    return Container(
      width: 200,
      decoration: BoxDecoration(
        color: p.sidebarBg,
        border: Border(
          right: BorderSide(color: p.isDark ? p.borderStrong : p.border),
        ),
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: p.accent,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: const Icon(
                    Icons.description,
                    color: Colors.white,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 12),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'FORMATIFY',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: p.textPrimary,
                      ),
                    ),
                    Text(
                      'Academic Edition',
                      style: TextStyle(
                        fontSize: 10,
                        color: p.textSecondary,
                        fontWeight: FontWeight.w400,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(vertical: 8),
              children: [
                _buildSidebarItem(context, p, 0, Icons.dashboard, 'Dashboard'),
                _buildSidebarItem(
                    context, p, 1, Icons.add_circle_outline, 'New Report'),
                _buildSidebarItem(context, p, 2, Icons.folder, 'My Reports'),
                _buildSidebarItem(
                    context, p, 3, Icons.people_outline, 'Collaboration'),
                _buildSidebarItem(context, p, 5, Icons.layers, 'Templates'),
                _buildSidebarItem(context, p, 6, Icons.settings, 'Settings'),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Container(
              decoration: BoxDecoration(
                color: p.surfaceAlt,
                borderRadius:
                    BorderRadius.circular(p.isDark ? p.cardRadius : 8),
                border: Border.all(
                  color: p.isDark ? p.borderStrong : p.border,
                ),
                boxShadow: p.isDark ? p.cardShadow : null,
              ),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Consumer<AuthProvider>(
                  builder: (context, auth, _) {
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 32,
                          height: 32,
                          decoration: BoxDecoration(
                            color: p.accent,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Center(
                            child: Text(
                              (auth.currentUser?.isNotEmpty ?? false)
                                  ? auth.currentUser![0].toUpperCase()
                                  : 'U',
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 12),
                        Text(
                          auth.currentUser ?? 'User',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: p.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          auth.email ?? 'user@example.com',
                          style: TextStyle(
                            fontSize: 10,
                            color: p.textSecondary,
                          ),
                        ),
                        const SizedBox(height: 12),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: () {
                              confirmAndLogout(
                                context,
                                afterLogout: () {
                                  Navigator.of(context).pushNamedAndRemoveUntil(
                                    '/login',
                                    (route) => false,
                                  );
                                },
                              );
                            },
                            icon: const Icon(Icons.logout, size: 14, color: Colors.white),
                            label: const Text(
                              'Logout',
                              style: TextStyle(
                                fontSize: 11,
                                color: Colors.white,
                              ),
                            ),
                            style: ElevatedButton.styleFrom(
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(vertical: 8),
                              minimumSize: const Size(0, 32),
                            ),
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSidebarItem(
    BuildContext context,
    AppPalette p,
    int index,
    IconData icon,
    String label,
  ) {
    final isSelected = selectedIndex == index;
    return GestureDetector(
      onTap: () => onItemSelected(index),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: isSelected ? p.accentSoft : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
          border: isSelected
              ? Border.all(color: p.accent, width: 1.5)
              : null,
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Icon(
                icon,
                color: isSelected ? p.accent : p.iconMuted,
                size: 20,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                    color: isSelected ? p.accent : p.textSecondary,
                    fontSize: 13,
                    fontWeight:
                        isSelected ? FontWeight.w600 : FontWeight.w400,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
