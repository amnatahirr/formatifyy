import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../config/dev_user_config.dart';
import '../../models/admin_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/admin_api_service.dart';
import '../../widgets/admin/admin_ui.dart';

import '../../widgets/tr.dart';
class AnalyticsScreen extends StatefulWidget {
  final bool embedded;

  const AnalyticsScreen({super.key, this.embedded = false});

  @override
  State<AnalyticsScreen> createState() => _AnalyticsScreenState();
}

class _AnalyticsScreenState extends State<AnalyticsScreen> {
  final AdminApiService _api = AdminApiService();
  bool _loading = true;
  String? _error;
  AdminAnalyticsModel? _analytics;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadAnalytics());
  }

  Future<void> _loadAnalytics() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = 'Admin session not found. Please log in again.';
        });
      }
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final analytics = await _api.fetchAnalytics(userId);
      if (mounted) setState(() => _analytics = analytics);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final body = _buildBody();
    if (widget.embedded) {
      return body;
    }
    return AdminSubPage(
      title: 'Analytics',
      subtitle: 'System usage and compliance performance',
      onRefresh: _loadAnalytics,
      child: body,
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return widget.embedded
          ? const AdminPage(child: SizedBox(height: 280, child: AdminLoadingView()))
          : const AdminLoadingView();
    }
    if (_error != null) {
      return widget.embedded
          ? AdminPage(child: AdminErrorView(message: _error!, onRetry: _loadAnalytics))
          : AdminErrorView(message: _error!, onRetry: _loadAnalytics);
    }
    final analytics = _analytics;
    if (analytics == null) {
      return widget.embedded
          ? AdminPage(child: AdminEmptyView(message: 'Analytics are not available yet.', onAction: _loadAnalytics))
          : AdminEmptyView(message: 'Analytics are not available yet.', onAction: _loadAnalytics);
    }

    final children = <Widget>[
      if (widget.embedded) ...[
        Align(
          alignment: Alignment.centerRight,
          child: IconButton(
            tooltip: 'Refresh',
            onPressed: _loadAnalytics,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ),
        const SizedBox(height: 8),
      ],
      adminResponsiveGrid(
        itemCount: DevUserConfig.hasFypModule ? 4 : 3,
        itemBuilder: (context, index) {
          final cards = [
            AdminStatCard(
              title: 'Documents Analyzed',
              value: '${analytics.documentsAnalyzed}',
              icon: Icons.description_outlined,
            ),
            AdminStatCard(
              title: 'Avg Compliance',
              value: analytics.avgComplianceScore.toStringAsFixed(1),
              icon: Icons.verified_outlined,
              accent: AdminColors.success,
            ),
            AdminStatCard(
              title: 'Success Rate',
              value: '${analytics.successRate.toStringAsFixed(1)}%',
              icon: Icons.trending_up_rounded,
              accent: AdminColors.warning,
            ),
            if (DevUserConfig.hasFypModule)
              AdminStatCard(
                title: 'Students',
                value: '${analytics.totalStudents}',
                icon: Icons.people_alt_outlined,
                accent: AdminColors.accent,
              ),
          ];
          return cards[index];
        },
      ),
      const SizedBox(height: 18),
      AdminSectionCard(
        title: 'Documents (Last 7 Days)',
        child: SizedBox(
          height: 220,
          child: analytics.documentsLast7Days.isEmpty
              ? Tr('No recent document activity yet.', style: TextStyle(color: Colors.white.withOpacity(0.65)))
              : LineChart(
                  LineChartData(
                    minY: 0,
                    gridData: FlGridData(
                      show: true,
                      drawVerticalLine: false,
                      getDrawingHorizontalLine: (value) => FlLine(color: Colors.white.withOpacity(0.06), strokeWidth: 1),
                    ),
                    borderData: FlBorderData(show: false),
                    titlesData: FlTitlesData(
                      topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                      rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                      leftTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 28,
                          getTitlesWidget: (value, meta) => Text(
                            value.toInt().toString(),
                            style: TextStyle(fontSize: 10, color: Colors.white.withOpacity(0.55)),
                          ),
                        ),
                      ),
                      bottomTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          getTitlesWidget: (value, meta) {
                            final index = value.toInt();
                            if (index < 0 || index >= analytics.documentsLast7Days.length) {
                              return const SizedBox.shrink();
                            }
                            return Padding(
                              padding: const EdgeInsets.only(top: 8),
                              child: Text(
                                analytics.documentsLast7Days[index].day,
                                style: TextStyle(fontSize: 10, color: Colors.white.withOpacity(0.7)),
                              ),
                            );
                          },
                        ),
                      ),
                    ),
                    lineBarsData: [
                      LineChartBarData(
                        spots: analytics.documentsLast7Days.asMap().entries.map((entry) {
                          return FlSpot(entry.key.toDouble(), entry.value.count.toDouble());
                        }).toList(),
                        isCurved: true,
                        color: AdminColors.primary,
                        barWidth: 3,
                        belowBarData: BarAreaData(show: true, color: AdminColors.primary.withOpacity(0.15)),
                        dotData: const FlDotData(show: true),
                      ),
                    ],
                  ),
                ),
        ),
      ),
      const SizedBox(height: 18),
      AdminSectionCard(
        title: 'Top Issue Types',
        child: SizedBox(
          height: 240,
          child: analytics.issueBreakdown.every((e) => e.count == 0)
              ? Tr('No issue breakdown yet — analyze documents to populate this chart.', style: TextStyle(color: Colors.white.withOpacity(0.65)))
              : BarChart(
                  BarChartData(
                    alignment: BarChartAlignment.spaceAround,
                    maxY: 100,
                    gridData: const FlGridData(show: false),
                    borderData: FlBorderData(show: false),
                    titlesData: FlTitlesData(
                      topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                      rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                      leftTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 30,
                          getTitlesWidget: (value, meta) => Text(
                            '${value.toInt()}%',
                            style: TextStyle(fontSize: 10, color: Colors.white.withOpacity(0.55)),
                          ),
                        ),
                      ),
                      bottomTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          getTitlesWidget: (value, meta) {
                            final index = value.toInt();
                            if (index < 0 || index >= analytics.issueBreakdown.length) {
                              return const SizedBox.shrink();
                            }
                            return Padding(
                              padding: const EdgeInsets.only(top: 8),
                              child: Text(
                                analytics.issueBreakdown[index].label,
                                style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.7)),
                              ),
                            );
                          },
                        ),
                      ),
                    ),
                    barGroups: analytics.issueBreakdown.asMap().entries.map((entry) {
                      return BarChartGroupData(
                        x: entry.key,
                        barRods: [
                          BarChartRodData(
                            toY: entry.value.percentage.toDouble().clamp(0, 100),
                            width: 22,
                            borderRadius: BorderRadius.circular(6),
                            color: AdminColors.primary,
                          ),
                        ],
                      );
                    }).toList(),
                  ),
                ),
        ),
      ),
      const SizedBox(height: 18),
      AdminSectionCard(
        title: 'Department Comparison',
        child: SizedBox(
          height: 260,
          child: analytics.departmentScores.isEmpty
              ? Tr('No departments found yet.', style: TextStyle(color: Colors.white.withOpacity(0.65)))
              : BarChart(
                  BarChartData(
                    alignment: BarChartAlignment.spaceAround,
                    maxY: 100,
                    gridData: const FlGridData(show: false),
                    borderData: FlBorderData(show: false),
                    titlesData: FlTitlesData(
                      topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                      rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                      leftTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 28,
                          getTitlesWidget: (value, meta) => Text(
                            value.toInt().toString(),
                            style: TextStyle(fontSize: 10, color: Colors.white.withOpacity(0.55)),
                          ),
                        ),
                      ),
                      bottomTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          getTitlesWidget: (value, meta) {
                            final index = value.toInt();
                            if (index < 0 || index >= analytics.departmentScores.length) {
                              return const SizedBox.shrink();
                            }
                            final name = analytics.departmentScores[index].departmentName;
                            final short = name.length > 10 ? '${name.substring(0, 8)}…' : name;
                            return Padding(
                              padding: const EdgeInsets.only(top: 8),
                              child: Text(short, style: TextStyle(fontSize: 10, color: Colors.white.withOpacity(0.7))),
                            );
                          },
                        ),
                      ),
                    ),
                    barGroups: analytics.departmentScores.asMap().entries.map((entry) {
                      return BarChartGroupData(
                        x: entry.key,
                        barRods: [
                          BarChartRodData(
                            toY: entry.value.avgComplianceScore.clamp(0, 100),
                            width: 22,
                            borderRadius: BorderRadius.circular(6),
                            color: AdminColors.success,
                          ),
                        ],
                      );
                    }).toList(),
                  ),
                ),
        ),
      ),
      const SizedBox(height: 18),
      AdminSectionCard(
        title: 'Monthly Documents Analyzed',
        child: SizedBox(
          height: 240,
          child: analytics.monthlyDocuments.isEmpty
              ? Tr('No monthly document trend yet.', style: TextStyle(color: Colors.white.withOpacity(0.65)))
              : LineChart(
                  LineChartData(
                    minY: 0,
                    gridData: FlGridData(
                      show: true,
                      drawVerticalLine: false,
                      getDrawingHorizontalLine: (value) => FlLine(color: Colors.white.withOpacity(0.06), strokeWidth: 1),
                    ),
                    borderData: FlBorderData(show: false),
                    titlesData: FlTitlesData(
                      topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                      rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                      leftTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          reservedSize: 28,
                          getTitlesWidget: (value, meta) => Text(
                            value.toInt().toString(),
                            style: TextStyle(fontSize: 10, color: Colors.white.withOpacity(0.55)),
                          ),
                        ),
                      ),
                      bottomTitles: AxisTitles(
                        sideTitles: SideTitles(
                          showTitles: true,
                          getTitlesWidget: (value, meta) {
                            final index = value.toInt();
                            if (index < 0 || index >= analytics.monthlyDocuments.length) {
                              return const SizedBox.shrink();
                            }
                            return Padding(
                              padding: const EdgeInsets.only(top: 8),
                              child: Text(
                                analytics.monthlyDocuments[index].month,
                                style: TextStyle(fontSize: 10, color: Colors.white.withOpacity(0.7)),
                              ),
                            );
                          },
                        ),
                      ),
                    ),
                    lineBarsData: [
                      LineChartBarData(
                        spots: analytics.monthlyDocuments.asMap().entries.map((entry) {
                          return FlSpot(entry.key.toDouble(), entry.value.count.toDouble());
                        }).toList(),
                        isCurved: true,
                        color: AdminColors.accent,
                        barWidth: 3,
                        belowBarData: BarAreaData(show: true, color: AdminColors.accent.withOpacity(0.12)),
                        dotData: const FlDotData(show: true),
                      ),
                    ],
                  ),
                ),
        ),
      ),
      const SizedBox(height: 18),
      AdminSectionCard(
        title: 'Top Templates',
        child: analytics.topTemplates.isEmpty
            ? Tr('No template usage recorded yet.', style: TextStyle(color: Colors.white.withOpacity(0.65)))
            : Column(
                children: analytics.topTemplates.map((template) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(child: Text(template.name, style: const TextStyle(color: Colors.white))),
                        Text('${template.uses} uses', style: const TextStyle(color: AdminColors.primary, fontWeight: FontWeight.w600)),
                      ],
                    ),
                  );
                }).toList(),
              ),
      ),
      const SizedBox(height: 8),
      Text(
        'Templates: ${analytics.totalTemplates} · This month: ${analytics.documentsThisMonth} docs',
        style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 12),
      ),
    ];

    // Column inside AdminPage (SingleChildScrollView) — avoids nested ListView blank layout
    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: children,
    );

    if (widget.embedded) {
      return AdminPage(onRefresh: _loadAnalytics, child: content);
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
      child: content,
    );
  }
}
