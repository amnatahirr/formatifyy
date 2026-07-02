import 'package:flutter/material.dart';
import 'common_widgets.dart';

class FontSettingsCard extends StatelessWidget {
  final String primaryFontFamily;
  final Function(String) onFontFamilyChanged;
  final TextEditingController bodyFontSizeController;
  final bool justifyText;
  final Function(bool) onJustifyTextChanged;

  const FontSettingsCard({
    super.key,
    required this.primaryFontFamily,
    required this.onFontFamilyChanged,
    required this.bodyFontSizeController,
    required this.justifyText,
    required this.onJustifyTextChanged,
  });

  @override
  Widget build(BuildContext context) {
    return CommonWidgets.buildCardContainer(
      icon: Icons.text_fields,
      title: 'Font Settings',
      subtitle: 'Typography configuration',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CommonWidgets.buildSettingGroup(
            'Primary Font Family',
            DropdownButton<String>(
              value: primaryFontFamily,
              isExpanded: true,
              underline: const SizedBox(),
              dropdownColor: const Color(0xFF1A1F2E),
              items: [
                'Times New Roman',
                'Arial',
                'Calibri',
                'Georgia',
                'Courier New',
              ].map((font) {
                return DropdownMenuItem<String>(
                  value: font,
                  child: Text(
                    font,
                    style: const TextStyle(color: Colors.white),
                  ),
                );
              }).toList(),
              onChanged: (value) => onFontFamilyChanged(value ?? 'Times New Roman'),
            ),
          ),
          const SizedBox(height: 16),
          CommonWidgets.buildNumberInput(
            'Base Font Size',
            bodyFontSizeController,
            'pt',
          ),
          const SizedBox(height: 16),
          CommonWidgets.buildToggleSetting(
            'Justify Text',
            'Align text to both margins',
            justifyText,
            onJustifyTextChanged,
          ),
        ],
      ),
    );
  }
}
