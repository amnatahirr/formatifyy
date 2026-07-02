import 'package:flutter/material.dart';
import 'common_widgets.dart';

class ParagraphStyleCard extends StatelessWidget {
  final TextEditingController firstLineIndentController;
  final TextEditingController spaceBeforeController;
  final TextEditingController spaceAfterController;
  final String spacingUnit;

  const ParagraphStyleCard({
    super.key,
    required this.firstLineIndentController,
    required this.spaceBeforeController,
    required this.spaceAfterController,
    required this.spacingUnit,
  });

  @override
  Widget build(BuildContext context) {
    return CommonWidgets.buildCardContainer(
      icon: Icons.notes,
      title: 'Paragraph Style',
      subtitle: 'Body text formatting',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CommonWidgets.buildNumberInput(
            'First Line Indent',
            firstLineIndentController,
            spacingUnit,
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: CommonWidgets.buildNumberInput(
                  'Space Before',
                  spaceBeforeController,
                  'pt',
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: CommonWidgets.buildNumberInput(
                  'Space After',
                  spaceAfterController,
                  'pt',
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          CommonWidgets.buildSettingGroup(
            'Text Alignment',
            DropdownButton<String>(
              value: 'Justify',
              isExpanded: true,
              underline: const SizedBox(),
              dropdownColor: const Color(0xFF1A1F2E),
              items: ['Left', 'Center', 'Right', 'Justify'].map((align) {
                return DropdownMenuItem<String>(
                  value: align,
                  child: Text(
                    align,
                    style: const TextStyle(color: Colors.white),
                  ),
                );
              }).toList(),
              onChanged: (value) {},
            ),
          ),
          const SizedBox(height: 16),
          CommonWidgets.buildToggleSetting(
            'Widow/Orphan Control',
            'Prevent single lines at page breaks',
            true,
            (value) {},
          ),
        ],
      ),
    );
  }
}
