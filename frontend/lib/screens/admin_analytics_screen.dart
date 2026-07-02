import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import '../config/api_config.dart';
import '../providers/auth_provider.dart';

class AdminAnalyticsScreen extends StatefulWidget {
  const AdminAnalyticsScreen({Key? key}) : super(key: key);

  @override
  State<AdminAnalyticsScreen> createState() => _AdminAnalyticsScreenState();
}

class _AdminAnalyticsScreenState extends State<AdminAnalyticsScreen> {
  Map<String, dynamic>? _analytics;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _loadAnalytics();
  }

  Future<void> _loadAnalytics() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _loading = true);
    try {
      final res = await http.get(
        Uri.parse('${ApiConfig.getBaseUrl()}/admin/analytics?user_id=$userId'),
      );
      if (res.statusCode == 200) {
        setState(() => _analytics = jsonDecode(res.body));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final data = _analytics ?? {};
    final topTemplates = List<Map<String, dynamic>>.from(data['top_templates'] ?? []);
    final days = List<Map<String, dynamic>>.from(data['documents_last_7_days'] ?? []);
    return Container(
      color: const Color(0xFF0F1419),
      padding: const EdgeInsets.all(32),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Analytics',
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'System usage and performance metrics',
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.white.withOpacity(0.6),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 32),
            if (_loading) const LinearProgressIndicator(),
            const SizedBox(height: 8),
            GridView.count(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisCount: 4,
              crossAxisSpacing: 24,
              mainAxisSpacing: 24,
              children: [
                _buildMetricCard(
                  'Documents Formatted',
                  '${data['total_documents'] ?? 0}',
                  'Total processed documents',
                ),
                _buildMetricCard(
                  'Students',
                  '${data['total_students'] ?? 0}',
                  'Registered as student',
                ),
                _buildMetricCard('Success Rate', '${data['success_rate'] ?? 0}%', 'Completed docs'),
                _buildMetricCard('Templates', '${data['total_templates'] ?? 0}', 'Available templates'),
              ],
            ),
            const SizedBox(height: 32),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(flex: 2, child: _buildChartCard(days)),
                const SizedBox(width: 24),
                Expanded(child: _buildTopTemplatesCard(topTemplates)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricCard(String title, String value, String change) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F2E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF2D3748)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(
              fontSize: 12,
              color: Colors.white.withOpacity(0.6),
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            value,
            style: const TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.w700,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            change,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: Color(0xFF10B981),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChartCard(List<Map<String, dynamic>> days) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F2E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF2D3748)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Formatting Requests (Last 7 Days)',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 20),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: days.isEmpty
                ? [Text('No recent data', style: TextStyle(color: Colors.white.withOpacity(0.6)))]
                : days
                    .map((d) => _buildBarChart((d['day'] ?? '').toString(), (d['count'] ?? 0).toDouble()))
                    .toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildBarChart(String day, double height) {
    final maxHeight = 300.0;
    final normalizedHeight = (height / maxHeight) * 150;
    return Column(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        Container(
          width: 30,
          height: normalizedHeight,
          decoration: BoxDecoration(
            color: const Color(0xFF6366F1),
            borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          day,
          style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.6)),
        ),
      ],
    );
  }

  Widget _buildTopTemplatesCard(List<Map<String, dynamic>> templates) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F2E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF2D3748)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Top Templates',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 16),
          if (templates.isEmpty)
            Text('No template usage yet', style: TextStyle(color: Colors.white.withOpacity(0.6)))
          else
            ...templates.map((t) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _buildTemplateListItem(
                    (t['name'] ?? 'Template').toString(),
                    (t['uses'] ?? 0) as int,
                  ),
                )),
        ],
      ),
    );
  }

  Widget _buildTemplateListItem(String name, int uses) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              name,
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: Colors.white,
              ),
            ),
          ],
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: const Color(0xFF6366F1).withOpacity(0.1),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(
            '$uses uses',
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: Color(0xFF6366F1),
            ),
          ),
        ),
      ],
    );
  }
}
