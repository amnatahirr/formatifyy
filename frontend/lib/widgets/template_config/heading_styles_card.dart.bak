import 'package:flutter/material.dart';
import 'common_widgets.dart';

class HeadingStylesCard extends StatelessWidget {
  final String spacingUnit;
  final String numberingStyle;
  final Function(String) onNumberingStyleChanged;

  final TextEditingController heading1SizeController;
  final TextEditingController heading1SpaceBeforeController;
  final TextEditingController heading1SpaceAfterController;
  final String heading1Weight;
  final bool heading1Italic;
  final String heading1Alignment;
  final String heading1Transform;
  final Function(String) onHeading1WeightChanged;
  final Function(bool) onHeading1ItalicChanged;
  final Function(String) onHeading1AlignmentChanged;
  final Function(String) onHeading1TransformChanged;

  final TextEditingController heading2SizeController;
  final TextEditingController heading2SpaceBeforeController;
  final TextEditingController heading2SpaceAfterController;
  final String heading2Weight;
  final bool heading2Italic;
  final String heading2Alignment;
  final String heading2Transform;
  final Function(String) onHeading2WeightChanged;
  final Function(bool) onHeading2ItalicChanged;
  final Function(String) onHeading2AlignmentChanged;
  final Function(String) onHeading2TransformChanged;

  final TextEditingController heading3SizeController;
  final TextEditingController heading3SpaceBeforeController;
  final TextEditingController heading3SpaceAfterController;
  final String heading3Weight;
  final bool heading3Italic;
  final String heading3Alignment;
  final String heading3Transform;
  final Function(String) onHeading3WeightChanged;
  final Function(bool) onHeading3ItalicChanged;
  final Function(String) onHeading3AlignmentChanged;
  final Function(String) onHeading3TransformChanged;

  const HeadingStylesCard({
    super.key,
    required this.spacingUnit,
    required this.numberingStyle,
    required this.onNumberingStyleChanged,
    required this.heading1SizeController,
    required this.heading1SpaceBeforeController,
    required this.heading1SpaceAfterController,
    required this.heading1Weight,
    required this.heading1Italic,
    required this.heading1Alignment,
    required this.heading1Transform,
    required this.onHeading1WeightChanged,
    required this.onHeading1ItalicChanged,
    required this.onHeading1AlignmentChanged,
    required this.onHeading1TransformChanged,
    required this.heading2SizeController,
    required this.heading2SpaceBeforeController,
    required this.heading2SpaceAfterController,
    required this.heading2Weight,
    required this.heading2Italic,
    required this.heading2Alignment,
    required this.heading2Transform,
    required this.onHeading2WeightChanged,
    required this.onHeading2ItalicChanged,
    required this.onHeading2AlignmentChanged,
    required this.onHeading2TransformChanged,
    required this.heading3SizeController,
    required this.heading3SpaceBeforeController,
    required this.heading3SpaceAfterController,
    required this.heading3Weight,
    required this.heading3Italic,
    required this.heading3Alignment,
    required this.heading3Transform,
    required this.onHeading3WeightChanged,
    required this.onHeading3ItalicChanged,
    required this.onHeading3AlignmentChanged,
    required this.onHeading3TransformChanged,
  });

  @override
  Widget build(BuildContext context) {
    return CommonWidgets.buildCardContainer(
      icon: Icons.format_size,
      title: 'Heading Styles',
      subtitle: 'Configure H1, H2, H3 formatting',
      child: Column(
        children: [
          CommonWidgets.buildDropdown(
            'Heading Numbering Style',
            numberingStyle,
            const [
              'None',
              '1, 1.1, 1.1.1',
              'I, A, 1',
              'A, 1, a',
            ],
            onNumberingStyleChanged,
          ),
          const SizedBox(height: 16),
          _buildHeadingConfig(
            'Heading 1 (Chapter Title)',
            heading1SizeController,
            heading1SpaceBeforeController,
            heading1SpaceAfterController,
            heading1Weight,
            heading1Italic,
            heading1Alignment,
            heading1Transform,
            onHeading1WeightChanged,
            onHeading1ItalicChanged,
            onHeading1AlignmentChanged,
            onHeading1TransformChanged,
          ),
          const SizedBox(height: 16),
          _buildHeadingConfig(
            'Heading 2 (Section Title)',
            heading2SizeController,
            heading2SpaceBeforeController,
            heading2SpaceAfterController,
            heading2Weight,
            heading2Italic,
            heading2Alignment,
            heading2Transform,
            onHeading2WeightChanged,
            onHeading2ItalicChanged,
            onHeading2AlignmentChanged,
            onHeading2TransformChanged,
          ),
          const SizedBox(height: 16),
          _buildHeadingConfig(
            'Heading 3 (Subsection)',
            heading3SizeController,
            heading3SpaceBeforeController,
            heading3SpaceAfterController,
            heading3Weight,
            heading3Italic,
            heading3Alignment,
            heading3Transform,
            onHeading3WeightChanged,
            onHeading3ItalicChanged,
            onHeading3AlignmentChanged,
            onHeading3TransformChanged,
          ),
        ],
      ),
    );
  }

  Widget _buildHeadingConfig(
    String title,
    TextEditingController sizeController,
    TextEditingController spaceBeforeController,
    TextEditingController spaceAfterController,
    String weight,
    bool italic,
    String alignment,
    String transform,
    Function(String) onWeightChanged,
    Function(bool) onItalicChanged,
    Function(String) onAlignmentChanged,
    Function(String) onTransformChanged,
  ) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1419),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFF2D3748)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: CommonWidgets.buildNumberInput('Font Size', sizeController, 'pt'),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: CommonWidgets.buildDropdown(
                  'Weight',
                  weight,
                  ['Light', 'Normal', 'Medium', 'Bold', 'Extra Bold'],
                  onWeightChanged,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Checkbox(
                value: italic,
                onChanged: (value) => onItalicChanged(value ?? false),
              ),
              const Text('Italic', style: TextStyle(color: Colors.white70)),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: CommonWidgets.buildDropdown(
                  'Alignment',
                  alignment,
                  ['Left', 'Center', 'Right', 'Justify'],
                  onAlignmentChanged,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: CommonWidgets.buildDropdown(
                  'Transform',
                  transform,
                  ['Normal', 'UPPERCASE', 'lowercase', 'Capitalize'],
                  onTransformChanged,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: CommonWidgets.buildNumberInput(
                  'Space Before',
                  spaceBeforeController,
                  spacingUnit,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: CommonWidgets.buildNumberInput(
                  'Space After',
                  spaceAfterController,
                  spacingUnit,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
