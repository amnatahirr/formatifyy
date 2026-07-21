import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/admin_models.dart';
import '../providers/auth_provider.dart';
import '../screens/admin/analytics_screen.dart';
import '../screens/admin/deadlines_screen.dart';
import '../screens/admin/supervisor_management_screen.dart';
import '../screens/admin/template_manager_screen.dart';
import '../services/admin_api_service.dart';
import '../widgets/admin/admin_ui.dart';

class AdminOverviewScreen extends StatefulWidget {
  const AdminOverviewScreen({super.key});

  @override
  State<AdminOverviewScreen> createState() => _AdminOverviewScreenState();
}

class _AdminOverviewScreenState extends State<AdminOverviewScreen> {
  final AdminApiService _api = AdminApiService();
  AdminOverviewModel? _overview;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadOverview();
  }

  Future<void> _loadOverview() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final overview = await _api.fetchOverview(userId);
      if (mounted) setState(() => _overview = overview);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _open(Widget screen) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => screen));
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const AdminPage(child: AdminLoadingView());
    }
    if (_error != null) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _loadOverview));
    }

    final overview = _overview;
    if (overview == null) {
      return AdminPage(
        onRefresh: _loadOverview,
        child: const AdminEmptyView(message: 'Dashboard data is not available yet. Pull to refresh once the backend is running.'),
      );
    }

    return AdminPage(
      onRefresh: _loadOverview,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const AdminPageHeader(
            title: 'Dashboard Overview',
            subtitle: 'Live metrics and shortcuts for university administration',
          ),
          const SizedBox(height: 24),
          adminResponsiveGrid(
            itemCount: 4,
            itemBuilder: (context, index) {
              final cards = [
                AdminStatCard(
                  title: 'Total Supervisors',
                  value: '${overview.stats.totalSupervisors}',
                  icon: Icons.supervisor_account_rounded,
                ),
                AdminStatCard(
                  title: 'Total Students',
                  value: '${overview.stats.totalStudents}',
                  icon: Icons.people_alt_rounded,
                  accent: AdminColors.accent,
                ),
                AdminStatCard(
                  title: 'Active Projects',
                  value: '${overview.stats.totalActiveProjects}',
                  icon: Icons.work_outline_rounded,
                  accent: AdminColors.warning,
                ),
                AdminStatCard(
                  title: 'Documents Checked',
                  value: '${overview.stats.totalDocumentsChecked}',
                  icon: Icons.description_outlined,
                  accent: AdminColors.success,
                ),
              ];
              return cards[index];
            },
          ),
          const SizedBox(height: 28),
          Text('Quick Actions', style: TextStyle(color: Colors.white.withOpacity(0.8), fontWeight: FontWeight.w600)),
          const SizedBox(height: 14),
          Wrap(
            spacing: 14,
            runSpacing: 14,
            children: [
              AdminActionTile(
                title: 'Supervisors',
                subtitle: 'Manage department supervisors',
                icon: Icons.supervisor_account_rounded,
                onTap: () => _open(const SupervisorManagementScreen()),
              ),
              AdminActionTile(
                title: 'Templates',
                subtitle: 'Department template rules',
                icon: Icons.layers_rounded,
                onTap: () => _open(const TemplateManagerScreen()),
              ),
              AdminActionTile(
                title: 'Deadlines',
                subtitle: 'Track submission dates',
                icon: Icons.event_note_rounded,
                onTap: () => _open(const DeadlinesScreen()),
              ),
              AdminActionTile(
                title: 'Analytics',
                subtitle: 'Usage and compliance trends',
                icon: Icons.bar_chart_rounded,
                onTap: () => _open(const AnalyticsScreen()),
              ),
            ],
          ),
          const SizedBox(height: 28),
          LayoutBuilder(
            builder: (context, constraints) {
              final stacked = constraints.maxWidth < 980;
              final activity = AdminSectionCard(
                title: 'Recent Activity',
                child: overview.recentActivity.isEmpty
                    ? Text('No documents were processed in the last 7 days.', style: TextStyle(color: Colors.white.withOpacity(0.6)))
                    : Column(
                        children: overview.recentActivity.map((day) {
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 12),
                            child: Row(
                              children: [
                                Container(
                                  width: 8,
                                  height: 8,
                                  decoration: const BoxDecoration(color: AdminColors.primary, shape: BoxShape.circle),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    '${day.count} document(s) on ${day.day}',
                                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500),
                                  ),
                                ),
                                Text(day.date, style: TextStyle(color: Colors.white.withOpacity(0.45), fontSize: 12)),
                              ],
                            ),
                          );
                        }).toList(),
                      ),
              );
              final quickStats = AdminSectionCard(
                title: 'Quick Stats',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _quickStatRow('Success Rate', '${overview.successRate.toStringAsFixed(1)}%'),
                    const SizedBox(height: 12),
                    _quickStatRow('This Month', '${overview.documentsThisMonth} documents'),
                    const SizedBox(height: 12),
                    _quickStatRow('Templates Used', '${overview.topTemplates.length} active'),
                    const SizedBox(height: 16),
                    Text('Top Templates', style: TextStyle(color: Colors.white.withOpacity(0.75), fontWeight: FontWeight.w600, fontSize: 12)),
                    const SizedBox(height: 8),
                    if (overview.topTemplates.isEmpty)
                      Text('No template usage recorded yet.', style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 12))
                    else
                      ...overview.topTemplates.take(3).map(
                            (template) => Padding(
                              padding: const EdgeInsets.only(bottom: 8),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Expanded(child: Text(template.name, style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 12))),
                                  Text('${template.uses} uses', style: const TextStyle(color: AdminColors.primary, fontSize: 12, fontWeight: FontWeight.w600)),
                                ],
                              ),
                            ),
                          ),
                  ],
                ),
              );
              if (stacked) {
                return Column(children: [activity, const SizedBox(height: 18), quickStats]);
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 2, child: activity),
                  const SizedBox(width: 18),
                  Expanded(child: quickStats),
                ],
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _quickStatRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500)),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: AdminColors.success.withOpacity(0.15),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(value, style: const TextStyle(color: AdminColors.success, fontWeight: FontWeight.w600, fontSize: 12)),
        ),
      ],
    );
  }
}
