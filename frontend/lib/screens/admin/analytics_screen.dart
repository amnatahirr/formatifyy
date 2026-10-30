import 'dart:math' as math;

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
  DateTime? _lastUpdated;

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
      if (mounted) {
        setState(() {
          _analytics = analytics;
          _lastUpdated = DateTime.now();
        });
      }
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

  String _timeLabel(DateTime t) {
    final h = t.hour % 12 == 0 ? 12 : t.hour % 12;
    final m = t.minute.toString().padLeft(2, '0');
    final ap = t.hour >= 12 ? 'PM' : 'AM';
    return '$h:$m $ap';
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

    // ---- Real values derived from the API response ----
    final last7 = analytics.documentsLast7Days;
    final last7Total = last7.fold<int>(0, (s, e) => s + e.count.toInt());
    var peakLabel = '';
    var peakCount = 0;
    for (final d in last7) {
      if (d.count.toInt() > peakCount) {
        peakCount = d.count.toInt();
        peakLabel = d.day;
      }
    }

    final monthly = analytics.monthlyDocuments;
    final monthlyTotal = monthly.fold<int>(0, (s, e) => s + e.count.toInt());

    final depts = analytics.departmentScores;
    var topDeptName = '';
    var topDeptScore = -1.0;
    for (final d in depts) {
      if (d.avgComplianceScore > topDeptScore) {
        topDeptScore = d.avgComplianceScore.toDouble();
        topDeptName = d.departmentName;
      }
    }

    final hasFyp = DevUserConfig.hasFypModule;

    final kpis = <Widget>[
      _KpiCard(
        title: 'Documents Analyzed',
        value: '${analytics.documentsAnalyzed}',
        icon: Icons.description_rounded,
        color: AdminColors.primary,
      ),
      _KpiCard(
        title: 'Success Rate',
        value: '${analytics.successRate.toStringAsFixed(1)}%',
        icon: Icons.trending_up_rounded,
        color: AdminColors.success,
        progress: (analytics.successRate / 100).clamp(0.0, 1.0).toDouble(),
      ),
      _KpiCard(
        title: 'This Month',
        value: '${analytics.documentsThisMonth}',
        icon: Icons.calendar_month_rounded,
        color: AdminColors.warning,
        hint: 'documents',
      ),
      if (hasFyp)
        _KpiCard(
          title: 'Students',
          value: '${analytics.totalStudents}',
          icon: Icons.people_alt_rounded,
          color: AdminColors.accent,
        ),
    ];

    final sevenDayCard = _ChartCard(
      title: 'Documents · Last 7 Days',
      subtitle: last7Total == 0
          ? 'No activity this week'
          : '$last7Total total · peak $peakLabel ($peakCount)',
      icon: Icons.show_chart_rounded,
      color: AdminColors.primary,
      child: SizedBox(
        height: 230,
        child: last7.isEmpty
            ? const _EmptyNote('No recent document activity yet.')
            : _AreaLineChart(
                labels: last7.map((e) => e.day.toString()).toList(),
                values: last7.map((e) => e.count.toDouble()).toList(),
                color: AdminColors.primary,
              ),
      ),
    );

    final monthlyCard = _ChartCard(
      title: 'Monthly Documents Analyzed',
      subtitle: monthlyTotal == 0
          ? 'No documents in the last 6 months'
          : '$monthlyTotal in the last ${monthly.length} months',
      icon: Icons.timeline_rounded,
      color: AdminColors.accent,
      child: SizedBox(
        height: 230,
        child: monthly.isEmpty
            ? const _EmptyNote('No monthly document trend yet.')
            : _AreaLineChart(
                labels: monthly.map((e) => e.month.toString()).toList(),
                values: monthly.map((e) => e.count.toDouble()).toList(),
                color: AdminColors.accent,
              ),
      ),
    );

    final issuesEmpty = analytics.issueBreakdown.every((e) => e.count == 0);
    final issuesCard = _ChartCard(
      title: 'Top Issue Types',
      subtitle: 'Share of detected issues',
      icon: Icons.bug_report_rounded,
      color: AdminColors.warning,
      child: SizedBox(
        height: 240,
        child: issuesEmpty
            ? const _EmptyNote('No issue breakdown yet — analyze documents to populate this chart.')
            : _RoundedBarChart(
                labels: analytics.issueBreakdown.map((e) => e.label.toString()).toList(),
                values: analytics.issueBreakdown
                    .map((e) => e.percentage.toDouble().clamp(0.0, 100.0).toDouble())
                    .toList(),
                color: AdminColors.warning,
                suffix: '%',
              ),
      ),
    );

    final deptCard = _ChartCard(
      title: 'Department Comparison',
      subtitle: depts.isEmpty
          ? 'No departments yet'
          : (topDeptScore > 0
              ? 'Highest: $topDeptName (${topDeptScore.toStringAsFixed(1)}%)'
              : 'Share of completed documents'),
      icon: Icons.apartment_rounded,
      color: AdminColors.success,
      child: SizedBox(
        height: 240,
        child: depts.isEmpty
            ? const _EmptyNote('No departments found yet.')
            : _RoundedBarChart(
                labels: depts.map((e) {
                  final n = e.departmentName.toString();
                  return n.length > 10 ? '${n.substring(0, 8)}…' : n;
                }).toList(),
                values: depts
                    .map((e) => e.avgComplianceScore.toDouble().clamp(0.0, 100.0).toDouble())
                    .toList(),
                color: AdminColors.success,
                suffix: '%',
              ),
      ),
    );

    final maxUses = analytics.topTemplates.fold<int>(
      0,
      (m, t) => math.max(m, t.uses.toInt()),
    );
    final templatesCard = _ChartCard(
      title: 'Top Templates',
      subtitle: '${analytics.totalTemplates} template${analytics.totalTemplates == 1 ? '' : 's'} in total',
      icon: Icons.layers_rounded,
      color: AdminColors.primary,
      child: analytics.topTemplates.isEmpty
          ? const _EmptyNote('No template usage recorded yet.')
          : Column(
              children: [
                for (var i = 0; i < analytics.topTemplates.length; i++)
                  _TemplateRow(
                    rank: i + 1,
                    name: analytics.topTemplates[i].name.toString(),
                    uses: analytics.topTemplates[i].uses.toInt(),
                    fraction: maxUses == 0
                        ? 0
                        : analytics.topTemplates[i].uses.toInt() / maxUses,
                  ),
              ],
            ),
    );

    final children = <Widget>[
      // ---- Header row ----
      Row(
        children: [
          if (_lastUpdated != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.04),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: Colors.white.withOpacity(0.08)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 7,
                    height: 7,
                    decoration: const BoxDecoration(
                      color: AdminColors.success,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'Live · updated ${_timeLabel(_lastUpdated!)}',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: Colors.white.withOpacity(0.65),
                    ),
                  ),
                ],
              ),
            ),
          const Spacer(),
          if (widget.embedded)
            OutlinedButton.icon(
              onPressed: _loadAnalytics,
              icon: const Icon(Icons.refresh_rounded, size: 18),
              label: const Tr('Refresh'),
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.white.withOpacity(0.85),
                side: BorderSide(color: Colors.white.withOpacity(0.14)),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
        ],
      ),
      const SizedBox(height: 18),

      // ---- KPI cards ----
      LayoutBuilder(
        builder: (context, c) {
          const gap = 14.0;
          final cols = c.maxWidth >= 900 ? kpis.length : 2;
          final w = (c.maxWidth - gap * (cols - 1)) / cols;
          return Wrap(
            spacing: gap,
            runSpacing: gap,
            children: [for (final k in kpis) SizedBox(width: w, child: k)],
          );
        },
      ),
      const SizedBox(height: 18),

      // ---- Charts ----
      _TwoColumn(left: sevenDayCard, right: monthlyCard),
      const SizedBox(height: 18),
      _TwoColumn(left: issuesCard, right: deptCard),
      const SizedBox(height: 18),
      templatesCard,
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

// ---------------------------------------------------------------------------
// Layout helpers
// ---------------------------------------------------------------------------

class _TwoColumn extends StatelessWidget {
  final Widget left;
  final Widget right;

  const _TwoColumn({required this.left, required this.right});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, c) {
        if (c.maxWidth < 900) {
          return Column(
            children: [left, const SizedBox(height: 18), right],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: left),
            const SizedBox(width: 18),
            Expanded(child: right),
          ],
        );
      },
    );
  }
}

class _KpiCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final Color color;
  final String? hint;
  final double? progress;

  const _KpiCard({
    required this.title,
    required this.value,
    required this.icon,
    required this.color,
    this.hint,
    this.progress,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AdminColors.card,
            Color.alphaBlend(color.withOpacity(0.09), AdminColors.card),
          ],
        ),
        border: Border.all(color: color.withOpacity(0.25)),
        boxShadow: [
          BoxShadow(
            color: color.withOpacity(0.08),
            blurRadius: 18,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: color.withOpacity(0.16),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, size: 20, color: color),
              ),
              const Spacer(),
              if (hint != null)
                Text(
                  hint!,
                  style: TextStyle(
                    fontSize: 11.5,
                    color: Colors.white.withOpacity(0.4),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            value,
            style: const TextStyle(
              fontSize: 30,
              fontWeight: FontWeight.w800,
              color: Colors.white,
              height: 1.0,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            title,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: Colors.white.withOpacity(0.6),
            ),
          ),
          if (progress != null) ...[
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: progress,
                minHeight: 5,
                backgroundColor: Colors.white.withOpacity(0.08),
                valueColor: AlwaysStoppedAnimation<Color>(color),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _ChartCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final Color color;
  final Widget child;

  const _ChartCard({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.color,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        color: AdminColors.card,
        border: Border.all(color: Colors.white.withOpacity(0.08)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.18),
            blurRadius: 16,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: color.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, size: 18, color: color),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.white.withOpacity(0.5),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          child,
        ],
      ),
    );
  }
}

class _EmptyNote extends StatelessWidget {
  final String text;

  const _EmptyNote(this.text);

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.insights_rounded,
            size: 30,
            color: Colors.white.withOpacity(0.22),
          ),
          const SizedBox(height: 10),
          Tr(
            text,
            style: TextStyle(
              color: Colors.white.withOpacity(0.55),
              fontSize: 13,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

class _TemplateRow extends StatelessWidget {
  final int rank;
  final String name;
  final int uses;
  final double fraction;

  const _TemplateRow({
    required this.rank,
    required this.name,
    required this.uses,
    required this.fraction,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: rank == 1
                  ? AdminColors.primary.withOpacity(0.25)
                  : Colors.white.withOpacity(0.06),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              '$rank',
              style: TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w800,
                color: rank == 1 ? Colors.white : Colors.white.withOpacity(0.6),
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w600,
                          fontSize: 13.5,
                        ),
                      ),
                    ),
                    Text(
                      '$uses use${uses == 1 ? '' : 's'}',
                      style: const TextStyle(
                        color: AdminColors.primary,
                        fontWeight: FontWeight.w700,
                        fontSize: 12.5,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                ClipRRect(
                  borderRadius: BorderRadius.circular(999),
                  child: LinearProgressIndicator(
                    value: fraction.clamp(0.0, 1.0).toDouble(),
                    minHeight: 6,
                    backgroundColor: Colors.white.withOpacity(0.07),
                    valueColor: const AlwaysStoppedAnimation<Color>(
                      AdminColors.primary,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Charts
// ---------------------------------------------------------------------------

class _AreaLineChart extends StatelessWidget {
  final List<String> labels;
  final List<double> values;
  final Color color;

  const _AreaLineChart({
    required this.labels,
    required this.values,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final maxValue = values.isEmpty ? 0.0 : values.reduce(math.max);
    final maxY = math.max(4.0, (maxValue * 1.25).ceilToDouble());
    final interval = math.max(1.0, (maxY / 4).ceilToDouble());

    return LineChart(
      LineChartData(
        minY: 0,
        maxY: maxY,
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          horizontalInterval: interval,
          getDrawingHorizontalLine: (value) => FlLine(
            color: Colors.white.withOpacity(0.06),
            strokeWidth: 1,
            dashArray: const [4, 4],
          ),
        ),
        borderData: FlBorderData(show: false),
        titlesData: FlTitlesData(
          topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 30,
              interval: interval,
              getTitlesWidget: (value, meta) => Text(
                value.toInt().toString(),
                style: TextStyle(
                  fontSize: 10.5,
                  color: Colors.white.withOpacity(0.45),
                ),
              ),
            ),
          ),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              interval: 1,
              getTitlesWidget: (value, meta) {
                final index = value.toInt();
                if (index < 0 || index >= labels.length) {
                  return const SizedBox.shrink();
                }
                return Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    labels[index],
                    style: TextStyle(
                      fontSize: 10.5,
                      color: Colors.white.withOpacity(0.65),
                    ),
                  ),
                );
              },
            ),
          ),
        ),
        lineBarsData: [
          LineChartBarData(
            spots: [
              for (var i = 0; i < values.length; i++) FlSpot(i.toDouble(), values[i]),
            ],
            isCurved: true,
            curveSmoothness: 0.28,
            preventCurveOverShooting: true,
            gradient: LinearGradient(
              colors: [color, color.withOpacity(0.65)],
            ),
            barWidth: 3.2,
            isStrokeCapRound: true,
            dotData: FlDotData(
              show: true,
              getDotPainter: (spot, percent, bar, index) => FlDotCirclePainter(
                radius: 4,
                color: AdminColors.card,
                strokeWidth: 2.4,
                strokeColor: color,
              ),
            ),
            belowBarData: BarAreaData(
              show: true,
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [color.withOpacity(0.28), color.withOpacity(0.0)],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RoundedBarChart extends StatelessWidget {
  final List<String> labels;
  final List<double> values;
  final Color color;
  final String suffix;

  const _RoundedBarChart({
    required this.labels,
    required this.values,
    required this.color,
    this.suffix = '',
  });

  @override
  Widget build(BuildContext context) {
    return BarChart(
      BarChartData(
        alignment: BarChartAlignment.spaceAround,
        minY: 0,
        maxY: 100,
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          horizontalInterval: 25,
          getDrawingHorizontalLine: (value) => FlLine(
            color: Colors.white.withOpacity(0.06),
            strokeWidth: 1,
            dashArray: const [4, 4],
          ),
        ),
        borderData: FlBorderData(show: false),
        titlesData: FlTitlesData(
          topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 38,
              interval: 25,
              getTitlesWidget: (value, meta) => Text(
                '${value.toInt()}$suffix',
                style: TextStyle(
                  fontSize: 10.5,
                  color: Colors.white.withOpacity(0.45),
                ),
              ),
            ),
          ),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (value, meta) {
                final index = value.toInt();
                if (index < 0 || index >= labels.length) {
                  return const SizedBox.shrink();
                }
                return Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    labels[index],
                    style: TextStyle(
                      fontSize: 10.5,
                      color: Colors.white.withOpacity(0.65),
                    ),
                  ),
                );
              },
            ),
          ),
        ),
        barGroups: [
          for (var i = 0; i < values.length; i++)
            BarChartGroupData(
              x: i,
              barRods: [
                BarChartRodData(
                  toY: values[i],
                  width: 24,
                  borderRadius: const BorderRadius.vertical(
                    top: Radius.circular(8),
                  ),
                  gradient: LinearGradient(
                    begin: Alignment.bottomCenter,
                    end: Alignment.topCenter,
                    colors: [color.withOpacity(0.55), color],
                  ),
                  backDrawRodData: BackgroundBarChartRodData(
                    show: true,
                    toY: 100,
                    color: Colors.white.withOpacity(0.04),
                  ),
                ),
              ],
            ),
        ],
      ),
    );
  }
}