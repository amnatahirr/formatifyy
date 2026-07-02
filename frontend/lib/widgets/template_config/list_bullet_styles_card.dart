import 'package:flutter/material.dart';
import 'common_widgets.dart';

class ListBulletStylesCard extends StatelessWidget {
  final String bulletStyle;
  final Function(String) onBulletStyleChanged;
  final String numberingFormat;
  final Function(String) onNumberingFormatChanged;
  final TextEditingController bulletIndentController;

  const ListBulletStylesCard({
    super.key,
    required this.bulletStyle,
    required this.onBulletStyleChanged,
    required this.numberingFormat,
    required this.onNumberingFormatChanged,
    required this.bulletIndentController,
  });

  @override
  Widget build(BuildContext context) {
    return CommonWidgets.buildCardContainer(
      icon: Icons.list,
      title: 'List & Bullet Styles',
      subtitle: 'Bullet and numbering format',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CommonWidgets.buildSettingGroup(
            'Bullet Style',
            DropdownButton<String>(
              value: bulletStyle,
              isExpanded: true,
              underline: const SizedBox(),
              dropdownColor: const Color(0xFF1A1F2E),
              items: [
                'Filled Circle',
                'Empty Circle',
                'Square',
                'Dash',
                'Arrow',
              ].map((style) {
                return DropdownMenuItem<String>(
                  value: style,
                  child: Text(
                    style,
                    style: const TextStyle(color: Colors.white),
                  ),
                );
              }).toList(),
              onChanged: (value) => onBulletStyleChanged(value ?? 'Filled Circle'),
            ),
          ),
          const SizedBox(height: 16),
          CommonWidgets.buildSettingGroup(
            'Numbering Format',
            DropdownButton<String>(
              value: numberingFormat,
              isExpanded: true,
              underline: const SizedBox(),
              dropdownColor: const Color(0xFF1A1F2E),
              items: [
                '1, 2, 3 (Arabic)',
                'A, B, C (Uppercase)',
                'a, b, c (Lowercase)',
                'I, II, III (Roman)',
              ].map((format) {
                return DropdownMenuItem<String>(
                  value: format,
                  child: Text(
                    format,
                    style: const TextStyle(color: Colors.white),
                  ),
                );
              }).toList(),
              onChanged: (value) => onNumberingFormatChanged(value ?? '1, 2, 3 (Arabic)'),
            ),
          ),
          const SizedBox(height: 16),
          CommonWidgets.buildNumberInput(
            'List Indent',
            bulletIndentController,
            'mm',
          ),
          const SizedBox(height: 16),
          CommonWidgets.buildNumberInput(
            'Hanging Indent',
            TextEditingController(text: '8.35'),
            'mm',
          ),
          const SizedBox(height: 16),
          CommonWidgets.buildNumberInput(
            'Space Between Items',
            TextEditingController(text: '4'),
            'pt',
          ),
        ],
      ),
    );
  }
}
