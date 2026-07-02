import 'package:flutter/material.dart';

class TemplateHeader extends StatelessWidget {
  final Map<String, dynamic>? selectedTemplate;

  const TemplateHeader({
    super.key,
    this.selectedTemplate,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Template Configuration',
          style: TextStyle(
            fontSize: 28,
            fontWeight: FontWeight.w700,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          selectedTemplate != null
              ? 'Editing: ${selectedTemplate!['name'] ?? 'Unknown Template'}'
              : 'Select a template to modify or create a new one',
          style: TextStyle(fontSize: 14, color: Colors.white.withOpacity(0.6)),
        ),
      ],
    );
  }
}
