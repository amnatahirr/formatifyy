import 'package:flutter/material.dart';
import 'common_widgets.dart';

import '../tr.dart';
class DocumentSettingsCard extends StatelessWidget {
  final String pageSize;
  final String spacingUnit;
  final Function(String) onPageSizeChanged;
  final Function(String) onSpacingUnitChanged;
  final TextEditingController pageMarginTopController;
  final TextEditingController pageMarginBottomController;
  final TextEditingController pageMarginLeftController;
  final TextEditingController pageMarginRightController;
  final TextEditingController lineSpacingController;

  const DocumentSettingsCard({
    super.key,
    required this.pageSize,
    required this.spacingUnit,
    required this.onPageSizeChanged,
    required this.onSpacingUnitChanged,
    required this.pageMarginTopController,
    required this.pageMarginBottomController,
    required this.pageMarginLeftController,
    required this.pageMarginRightController,
    required this.lineSpacingController,
  });

  @override
  Widget build(BuildContext context) {
    return CommonWidgets.buildCardContainer(
      icon: Icons.description,
      title: 'Document Settings',
      subtitle: 'Paper size and margins',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CommonWidgets.buildSettingGroup(
            'Page Size',
            DropdownButton<String>(
              value: pageSize,
              isExpanded: true,
              underline: const SizedBox(),
              dropdownColor: const Color(0xFF1A1F2E),
              items: ['A4', 'Letter', 'Legal', 'A3'].map((size) {
                return DropdownMenuItem<String>(
                  value: size,
                  child: Text(
                    size == 'A4' ? 'A4 (210 × 297 mm)' : size,
                    style: const TextStyle(color: Colors.white),
                  ),
                );
              }).toList(),
              onChanged: (value) => onPageSizeChanged(value ?? 'A4'),
            ),
          ),
          const SizedBox(height: 16),
          CommonWidgets.buildSettingGroup(
            'Spacing and Margin Unit',
            DropdownButton<String>(
              value: spacingUnit,
              isExpanded: true,
              underline: const SizedBox(),
              dropdownColor: const Color(0xFF1A1F2E),
              items: const [
                DropdownMenuItem(value: 'mm', child: Tr('Millimeters (mm)', style: TextStyle(color: Colors.white))),
                DropdownMenuItem(value: 'cm', child: Tr('Centimeters (cm)', style: TextStyle(color: Colors.white))),
                DropdownMenuItem(value: 'in', child: Tr('Inches (in)', style: TextStyle(color: Colors.white))),
              ],
              onChanged: (value) => onSpacingUnitChanged(value ?? 'mm'),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: CommonWidgets.buildNumberInput(
                  'Top Margin',
                  pageMarginTopController,
                  spacingUnit,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: CommonWidgets.buildNumberInput(
                  'Bottom Margin',
                  pageMarginBottomController,
                  spacingUnit,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: CommonWidgets.buildNumberInput(
                  'Left Margin',
                  pageMarginLeftController,
                  spacingUnit,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: CommonWidgets.buildNumberInput(
                  'Right Margin',
                  pageMarginRightController,
                  spacingUnit,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          CommonWidgets.buildNumberInput(
            'Line Spacing',
            lineSpacingController,
            '',
          ),
        ],
      ),
    );
  }
}
