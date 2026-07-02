import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import '../config/api_config.dart';
import '../providers/auth_provider.dart';

class AdminOverviewScreen extends StatefulWidget {
  const AdminOverviewScreen({Key? key}) : super(key: key);

  @override
  State<AdminOverviewScreen> createState() => _AdminOverviewScreenState();
}

class _AdminOverviewScreenState extends State<AdminOverviewScreen> {
  Map<String, dynamic>? _analytics;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadAnalytics();
  }

  Future<void> _loadAnalytics() async {
    final auth = context.read<AuthProvider>();
    if (auth.userId == null) return;

    setState(() => _isLoading = true);
    try {
      final response = await http.get(
        Uri.parse('${ApiConfig.getBaseUrl()}/admin/analytics?user_id=${auth.userId}'),
      );
      if (response.statusCode == 200) {
        setState(() => _analytics = jsonDecode(response.body));
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final data = _analytics ?? {};
    final topTemplates = List<Map<String, dynamic>>.from(data['top_templates'] ?? []);
    final recentDays = List<Map<String, dynamic>>.from(data['documents_last_7_days'] ?? []);

    return Container(
      color: const Color(0xFF0F1419),
      padding: const EdgeInsets.all(32),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Dashboard Overview',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            if (_isLoading) ...[
              const SizedBox(height: 12),
              const LinearProgressIndicator(),
            ],
            const SizedBox(height: 32),
            GridView.count(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              crossAxisCount: 4,
              crossAxisSpacing: 24,
              mainAxisSpacing: 24,
              children: [
                _buildStatCard('Total Students', '${data['total_students'] ?? 0}', Icons.people),
                _buildStatCard('Active Templates', '${data['total_templates'] ?? 0}', Icons.layers),
                _buildStatCard('This Month Docs', '${data['documents_this_month'] ?? 0}', Icons.calendar_month),
                _buildStatCard('Total Documents', '${data['total_documents'] ?? 0}', Icons.description),
              ],
            ),
            const SizedBox(height: 32),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(flex: 2, child: _buildActivityCard(recentDays)),
                const SizedBox(width: 24),
                Expanded(
                  child: _buildQuickStatsCard(
                    successRate: (data['success_rate'] ?? 0).toString(),
                    topTemplates: topTemplates,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatCard(String title, String value, IconData icon) {
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
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Icon(icon, color: const Color(0xFF6366F1), size: 24),
              Icon(Icons.trending_up, color: const Color(0xFF10B981), size: 16),
            ],
          ),
          const SizedBox(height: 16),
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
            title,
            style: TextStyle(
              fontSize: 12,
              color: Colors.white.withOpacity(0.6),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActivityCard(List<Map<String, dynamic>> recentDays) {
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
            'Recent Activity',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 16),
          if (recentDays.isEmpty)
            Text(
              'No activity in the last 7 days',
              style: TextStyle(color: Colors.white.withOpacity(0.5)),
            )
          else
            ...recentDays.map(
              (d) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _buildActivityItem(
                  'Documents processed',
                  '${d['count'] ?? 0} on ${d['day'] ?? ''}',
                  'Recent',
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildActivityItem(String action, String details, String time) {
    return Row(
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: const BoxDecoration(
            color: Color(0xFF6366F1),
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                action,
                style: const TextStyle(
                  fontSize: 13,
                  color: Colors.white,
                  fontWeight: FontWeight.w500,
                ),
              ),
              Text(
                details,
                style: TextStyle(
                  fontSize: 11,
                  color: Colors.white.withOpacity(0.5),
                ),
              ),
            ],
          ),
        ),
        Text(
          time,
          style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.4)),
        ),
      ],
    );
  }

  Widget _buildQuickStatsCard({
    required String successRate,
    required List<Map<String, dynamic>> topTemplates,
  }) {
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
            'Quick Stats',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 16),
          _buildStatusItem('Success Rate', '$successRate%', true),
          const SizedBox(height: 12),
          _buildStatusItem('Templates Used', '${topTemplates.length}', true),
          const SizedBox(height: 16),
          Text(
            'Top Templates',
            style: TextStyle(
              fontSize: 12,
              color: Colors.white.withOpacity(0.7),
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 8),
          if (topTemplates.isEmpty)
            Text(
              'No template usage yet',
              style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.5)),
            )
          else
            ...topTemplates.take(3).map(
              (t) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  '- ${(t['name'] ?? 'Template')} (${t['uses'] ?? 0})',
                  style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.7)),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildStatusItem(String name, String status, bool isActive) {
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
                color: Colors.white,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          decoration: BoxDecoration(
            color: isActive
                ? const Color(0xFF10B981).withOpacity(0.2)
                : const Color(0xFFEF4444).withOpacity(0.2),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(
            status,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: isActive
                  ? const Color(0xFF10B981)
                  : const Color(0xFFEF4444),
            ),
          ),
        ),
      ],
    );
  }
}
