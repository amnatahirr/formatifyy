<<<<<<< HEAD
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';
import '../providers/template_provider.dart';
import '../widgets/admin/admin_ui.dart';

import '../widgets/tr.dart';
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

    return AdminPage(
      scrollable: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageHeader(
            title: 'All Created Templates',
            subtitle: 'Templates loaded from your university account',
            trailing: OutlinedButton.icon(
              onPressed: _loadTemplates,
              icon: const Icon(Icons.refresh),
              label: const Tr('Refresh'),
            ),
          ),
          const SizedBox(height: 20),
          Expanded(
            child: provider.isLoading
                ? const AdminLoadingView()
                : templates.isEmpty
                    ? AdminEmptyView(message: 'No templates found.', onAction: _loadTemplates, actionLabel: 'Refresh')
                    : ListView.separated(
                        itemCount: templates.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 12),
                        itemBuilder: (context, index) {
                          final t = templates[index];
                          final sections = (t['required_sections'] as List?)?.length ?? 0;
                          return Container(
                            padding: const EdgeInsets.all(16),
                            decoration: adminCardDecoration(),
                            child: Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(10),
                                  decoration: BoxDecoration(
                                    color: AdminColors.primary.withOpacity(0.14),
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  child: const Icon(Icons.description_outlined, color: AdminColors.primary),
                                ),
                                const SizedBox(width: 14),
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
=======
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/auth_provider.dart';
import '../providers/template_provider.dart';
import '../widgets/admin/admin_ui.dart';

import '../widgets/tr.dart';
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

    return AdminPage(
      scrollable: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageHeader(
            title: 'All Created Templates',
            subtitle: 'Templates loaded from your university account',
            trailing: OutlinedButton.icon(
              onPressed: _loadTemplates,
              icon: const Icon(Icons.refresh),
              label: const Tr('Refresh'),
            ),
          ),
          const SizedBox(height: 20),
          Expanded(
            child: provider.isLoading
                ? const AdminLoadingView()
                : templates.isEmpty
                    ? AdminEmptyView(message: 'No templates found.', onAction: _loadTemplates, actionLabel: 'Refresh')
                    : ListView.separated(
                        itemCount: templates.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 12),
                        itemBuilder: (context, index) {
                          final t = templates[index];
                          final sections = (t['required_sections'] as List?)?.length ?? 0;
                          return Container(
                            padding: const EdgeInsets.all(16),
                            decoration: adminCardDecoration(),
                            child: Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(10),
                                  decoration: BoxDecoration(
                                    color: AdminColors.primary.withOpacity(0.14),
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  child: const Icon(Icons.description_outlined, color: AdminColors.primary),
                                ),
                                const SizedBox(width: 14),
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
>>>>>>> origin/main
