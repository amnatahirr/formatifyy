import 'package:flutter/material.dart';
import 'common_widgets.dart';

/// Admin settings for Phase 1 image formatting (stored in template formatting_rules).
class ImageFormattingRulesCard extends StatelessWidget {
  final TextEditingController captionPatternController;
  final TextEditingController maxWidthPercentController;
  final String numberingScheme; // global | chapter
  final ValueChanged<String> onNumberingSchemeChanged;
  final String captionPosition; // below | above
  final ValueChanged<String> onCaptionPositionChanged;
  final bool includeLof;
  final ValueChanged<bool> onIncludeLofChanged;

  const ImageFormattingRulesCard({
    super.key,
    required this.captionPatternController,
    required this.maxWidthPercentController,
    required this.numberingScheme,
    required this.onNumberingSchemeChanged,
    required this.captionPosition,
    required this.onCaptionPositionChanged,
    required this.includeLof,
    required this.onIncludeLofChanged,
  });

  @override
  Widget build(BuildContext context) {
    return CommonWidgets.buildCardContainer(
      icon: Icons.image_outlined,
      title: 'Image & Caption Formatting',
      subtitle: 'Figure numbering, caption pattern, List of Figures',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CommonWidgets.buildSettingGroup(
            'Numbering scheme',
            DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: numberingScheme == 'chapter' ? 'chapter' : 'global',
                isExpanded: true,
                dropdownColor: const Color(0xFF1A1F2E),
                style: const TextStyle(color: Colors.white, fontSize: 13),
                items: const [
                  DropdownMenuItem(
                    value: 'global',
                    child: Text('Global sequential (Figure 1, Figure 2, …)'),
                  ),
                  DropdownMenuItem(
                    value: 'chapter',
                    child: Text('Chapter-wise (Figure 3.1, Figure 3.2, …)'),
                  ),
                ],
                onChanged: (v) {
                  if (v != null) onNumberingSchemeChanged(v);
                },
              ),
            ),
          ),
          const SizedBox(height: 12),
          CommonWidgets.buildSettingGroup(
            'Caption position',
            DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: captionPosition == 'above' ? 'above' : 'below',
                isExpanded: true,
                dropdownColor: const Color(0xFF1A1F2E),
                style: const TextStyle(color: Colors.white, fontSize: 13),
                items: const [
                  DropdownMenuItem(value: 'below', child: Text('Below image')),
                  DropdownMenuItem(value: 'above', child: Text('Above image')),
                ],
                onChanged: (v) {
                  if (v != null) onCaptionPositionChanged(v);
                },
              ),
            ),
          ),
          const SizedBox(height: 12),
          CommonWidgets.buildSettingGroup(
            'Caption format pattern',
            TextField(
              controller: captionPatternController,
              style: const TextStyle(color: Colors.white, fontSize: 13),
              decoration: const InputDecoration(
                isDense: true,
                border: InputBorder.none,
                hintText: 'Figure {n}: {caption}',
                hintStyle: TextStyle(color: Colors.white38, fontSize: 12),
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Placeholders: {n}, {chapter}, {caption}',
            style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.45)),
          ),
          const SizedBox(height: 12),
          CommonWidgets.buildSettingGroup(
            'Max image width (% of text area)',
            TextField(
              controller: maxWidthPercentController,
              keyboardType: TextInputType.number,
              style: const TextStyle(color: Colors.white, fontSize: 13),
              decoration: const InputDecoration(
                isDense: true,
                border: InputBorder.none,
                hintText: '80',
                hintStyle: TextStyle(color: Colors.white38, fontSize: 12),
              ),
            ),
          ),
          const SizedBox(height: 12),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            dense: true,
            title: const Text(
              'Include List of Figures',
              style: TextStyle(color: Colors.white, fontSize: 13),
            ),
            subtitle: Text(
              'Regenerate LOF when image formatting runs',
              style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 11),
            ),
            value: includeLof,
            activeColor: const Color(0xFF6366F1),
            onChanged: onIncludeLofChanged,
          ),
        ],
      ),
    );
  }
}
