import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';
import '../providers/template_provider.dart';

class AdminTemplatesListScreen extends StatefulWidget {
  const AdminTemplatesListScreen({super.key});

  @override
  State<AdminTemplatesListScreen> createState() => _AdminTemplatesListScreenState();
}

class _AdminTemplatesListScreenState extends State<AdminTemplatesListScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadTemplates());
  }

  Future<void> _loadTemplates() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    await context.read<TemplateProvider>().fetchUserTemplates(userId);
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<TemplateProvider>();
    final templates = provider.templates;

    return Container(
      color: const Color(0xFF0F1419),
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'All Created Templates',
            style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700, color: Colors.white),
          ),
          const SizedBox(height: 6),
          Text(
            'View all templates already created for your university.',
            style: TextStyle(color: Colors.white.withOpacity(0.6)),
          ),
          const SizedBox(height: 20),
          Align(
            alignment: Alignment.centerRight,
            child: OutlinedButton.icon(
              onPressed: _loadTemplates,
              icon: const Icon(Icons.refresh),
              label: const Text('Refresh'),
            ),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: provider.isLoading
                ? const Center(child: CircularProgressIndicator())
                : templates.isEmpty
                    ? const Center(
                        child: Text(
                          'No templates found.',
                          style: TextStyle(color: Colors.white70),
                        ),
                      )
                    : ListView.separated(
                        itemCount: templates.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 12),
                        itemBuilder: (context, index) {
                          final t = templates[index];
                          final sections = (t['required_sections'] as List?)?.length ?? 0;
                          return Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: const Color(0xFF1A1F2E),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: const Color(0xFF2D3748)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.description, color: Color(0xFF6366F1)),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        (t['name'] ?? 'Template').toString(),
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 15,
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        '$sections required section(s)',
                                        style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 12),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
