import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';
import '../utils/logout_confirm.dart';
import '../providers/analysis_job_provider.dart';
import 'analysis_jobs_sidebar_item.dart';
import 'tr.dart';
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
                    Tr('FORMATIFY',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: p.textPrimary,
                      ),
                    ),
                    Tr('Academic Edition',
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
                 AnalysisJobsSidebarItem(),
                
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
                            label: const Tr('Logout',
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
  Widget _buildAnalysisItem(BuildContext context, AppPalette p) {
  return Consumer<AnalysisJobProvider>(
    builder: (context, jp, _) {
      final jobs = jp.jobs;
      if (jobs.isEmpty) return const SizedBox.shrink();
      final running = jp.runningCount;
      final ready =
          jobs.where((j) => j.status == AnalysisStatus.completed).length;
      final label = running > 0
          ? 'Analysis ($running running)'
          : ready > 0
              ? 'Analysis ($ready ready)'
              : 'Analysis';

      return GestureDetector(
        onTap: () {
          if (jobs.length == 1) {
            jp.openJob(jobs.first);
          } else {
            _showJobsDialog(context, jp);
          }
        },
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: running > 0 ? p.accentSoft : Colors.transparent,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Row(
            children: [
              running > 0
                  ? SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: p.accent),
                    )
                  : const Icon(Icons.assessment,
                      color: Color(0xFF10B981), size: 20),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                    color: p.textSecondary,
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    },
  );
}

void _showJobsDialog(BuildContext context, AnalysisJobProvider jp) {
  showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Tr('Analyses'),
      content: SizedBox(
        width: 360,
        child: ListView(
          shrinkWrap: true,
          children: jp.jobs.map((j) {
            final done = j.status == AnalysisStatus.completed;
            final failed = j.status == AnalysisStatus.failed;
            return ListTile(
              leading: Icon(
                failed
                    ? Icons.error_outline
                    : done
                        ? Icons.check_circle_outline
                        : Icons.hourglass_top,
                color: failed
                    ? const Color(0xFFEF4444)
                    : done
                        ? const Color(0xFF10B981)
                        : const Color(0xFFF59E0B),
              ),
              title: Text(j.name, overflow: TextOverflow.ellipsis),
              subtitle: Text(failed ? 'Failed' : done ? 'Ready' : 'Running…'),
              onTap: () {
                Navigator.pop(ctx);
                jp.openJob(j);
              },
            );
          }).toList(),
        ),
      ),
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
