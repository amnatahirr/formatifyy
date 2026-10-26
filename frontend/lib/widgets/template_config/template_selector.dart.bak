import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/template_provider.dart';

class TemplateSelector extends StatelessWidget {
  final int? selectedTemplateId;
  final Function(int?) onTemplateChanged;

  const TemplateSelector({
    super.key,
    required this.selectedTemplateId,
    required this.onTemplateChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Consumer<TemplateProvider>(
      builder: (context, templateProvider, _) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Select Template',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Choose an existing template to modify, or leave blank to create a new one',
              style: TextStyle(fontSize: 12, color: Colors.white54),
            ),
            const SizedBox(height: 12),
            Container(
              decoration: BoxDecoration(
                color: const Color(0xFF1A1F2E),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0xFF2D3748)),
              ),
              child: DropdownButton<int?>(
                value: selectedTemplateId,
                isExpanded: true,
                underline: const SizedBox(),
                dropdownColor: const Color(0xFF1A1F2E),
                hint: const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 12),
                  child: Text(
                    'Select a template...',
                    style: TextStyle(color: Colors.white54),
                  ),
                ),
                items: [
                  const DropdownMenuItem<int?>(
                    value: null,
                    child: Padding(
                      padding: EdgeInsets.symmetric(horizontal: 12),
                      child: Text(
                        'Create New Template',
                        style: TextStyle(color: Colors.white54),
                      ),
                    ),
                  ),
                  ...templateProvider.templates.map((template) {
                    return DropdownMenuItem<int?>(
                      value: template['id'] as int?,
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        child: Text(
                          template['name'] ?? 'Unknown',
                          style: const TextStyle(color: Colors.white),
                        ),
                      ),
                    );
                  }).toList(),
                ],
                onChanged: onTemplateChanged,
              ),
            ),
          ],
        );
      },
    );
  }
}
