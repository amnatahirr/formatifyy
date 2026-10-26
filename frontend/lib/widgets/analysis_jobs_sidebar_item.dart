import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/analysis_job_provider.dart';
import '../theme/app_theme.dart';

class AnalysisJobsSidebarItem extends StatelessWidget {
  const AnalysisJobsSidebarItem({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final p = context.watch<ThemeProvider>().palette;
    return Consumer<AnalysisJobProvider>(
      builder: (context, jp, _) {
        final jobs = jp.jobs;
        if (jobs.isEmpty) return const SizedBox.shrink();
        final running = jp.runningCount;
        final ready =
            jobs.where((j) => j.status == AnalysisStatus.completed).length;
        final label = running > 0
            ? 'Analysis · $running running'
            : ready > 0
                ? 'Analysis · $ready ready'
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
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
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
        title: const Text('Analyses'),
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
                subtitle:
                    Text(failed ? 'Failed' : done ? 'Ready' : 'Running…'),
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
}