import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../providers/template_provider.dart';
import '../providers/auth_provider.dart';
import '../config/api_config.dart';

import 'tr.dart';
class TemplateListWidget extends StatefulWidget {
  const TemplateListWidget({Key? key}) : super(key: key);

  @override
  State<TemplateListWidget> createState() => _TemplateListWidgetState();
}

class _TemplateListWidgetState extends State<TemplateListWidget> {
  late String baseUrl;
  bool _isDeleting = false;

  @override
  void initState() {
    super.initState();
    baseUrl = ApiConfig.getBaseUrl();
  }

  Future<void> _deleteTemplate(int templateId) async {
    final authProvider = context.read<AuthProvider>();
    
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Tr('Delete Template'),
        content: const Tr('Are you sure you want to delete this template?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Tr('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Tr('Delete'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    setState(() => _isDeleting = true);

    try {
      final response = await http.delete(
        Uri.parse('$baseUrl/admin/templates/$templateId?user_id=${authProvider.userId}'),
        headers: {'Content-Type': 'application/json'},
      ).timeout(
        Duration(seconds: 10),
        onTimeout: () => throw TimeoutException('Connection timeout'),
      );

      if (response.statusCode == 200) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Tr('Template deleted successfully!'),
              backgroundColor: Colors.green,
            ),
          );
          
          // Reload templates
          final templateProvider = context.read<TemplateProvider>();
          // Get university_id from user (hardcoded as 1 for now)
          templateProvider.fetchUniversityTemplates(1);
        }
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Failed to delete template: ${response.body}'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isDeleting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<TemplateProvider>(
      builder: (context, templateProvider, _) {
        if (templateProvider.isLoading) {
          return const Center(
            child: CircularProgressIndicator(),
          );
        }

        if (templateProvider.errorMessage != null) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  Icons.error_outline,
                  size: 48,
                  color: Colors.red[300],
                ),
                const SizedBox(height: 16),
                Text(
                  templateProvider.errorMessage!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.red),
                ),
              ],
            ),
          );
        }

        if (templateProvider.templates.isEmpty) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  Icons.folder_open,
                  size: 64,
                  color: Colors.grey[300],
                ),
                const SizedBox(height: 16),
                Tr('No templates created yet',
                  style: TextStyle(
                    fontSize: 16,
                    color: Colors.grey[600],
                  ),
                ),
              ],
            ),
          );
        }

        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: templateProvider.templates.length,
          itemBuilder: (context, index) {
            final template = templateProvider.templates[index];
            final sections = template['required_sections'] as List<dynamic>?;
            final rules = template['formatting_rules'] as Map<String, dynamic>?;

            return Card(
              margin: const EdgeInsets.only(bottom: 16),
              elevation: 2,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Template name
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            template['name'] ?? 'Unnamed Template',
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        // Delete button
                        IconButton(
                          icon: const Icon(Icons.delete_outline, color: Colors.red),
                          onPressed: _isDeleting ? null : () => _deleteTemplate(template['id']),
                          tooltip: 'Delete template',
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),

                    // Required sections
                    if (sections != null && sections.isNotEmpty)
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Tr('Required Sections:',
                            style: TextStyle(
                              fontWeight: FontWeight.w600,
                              color: Colors.grey,
                              fontSize: 12,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: sections
                                .map(
                                  (section) => Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 8,
                                      vertical: 4,
                                    ),
                                    decoration: BoxDecoration(
                                      color: Colors.deepPurple.withOpacity(0.1),
                                      borderRadius: BorderRadius.circular(4),
                                      border: Border.all(
                                        color: Colors.deepPurple,
                                        width: 0.5,
                                      ),
                                    ),
                                    child: Text(
                                      section.toString(),
                                      style: const TextStyle(fontSize: 12),
                                    ),
                                  ),
                                )
                                .toList(),
                          ),
                          const SizedBox(height: 12),
                        ],
                      ),

                    // Formatting rules preview
                    if (rules != null && rules.isNotEmpty)
                      ExpansionTile(
                        title: const Tr('Formatting Rules'),
                        children: [
                          Padding(
                            padding: const EdgeInsets.all(12),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                _buildRuleItem(
                                  'Heading 1',
                                  'Font: ${rules['heading1_font'] ?? 'N/A'}, '
                                  'Size: ${rules['heading1_size'] ?? 'N/A'}',
                                ),
                                _buildRuleItem(
                                  'Heading 2',
                                  'Font: ${rules['heading2_font'] ?? 'N/A'}, '
                                  'Size: ${rules['heading2_size'] ?? 'N/A'}',
                                ),
                                _buildRuleItem(
                                  'Heading 3',
                                  'Font: ${rules['heading3_font'] ?? 'N/A'}, '
                                  'Size: ${rules['heading3_size'] ?? 'N/A'}',
                                ),
                                _buildRuleItem(
                                  'Body Text',
                                  'Font: ${rules['body_font'] ?? 'N/A'}, '
                                  'Size: ${rules['body_size'] ?? 'N/A'}',
                                ),
                                _buildRuleItem(
                                  'Line Spacing',
                                  '${rules['line_spacing'] ?? 'N/A'}',
                                ),
                                _buildRuleItem(
                                  'Margins',
                                  'Top: ${rules['margin_top'] ?? 'N/A'}", '
                                  'Bottom: ${rules['margin_bottom'] ?? 'N/A'}", '
                                  'Left: ${rules['margin_left'] ?? 'N/A'}", '
                                  'Right: ${rules['margin_right'] ?? 'N/A'}"',
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _buildRuleItem(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          SizedBox(
            width: 100,
            child: Text(
              label,
              style: const TextStyle(
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                color: Colors.grey[700],
                fontSize: 12,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
