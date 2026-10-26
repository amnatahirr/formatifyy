import 'package:flutter/material.dart';
import 'common_widgets.dart';

/// Admin settings for table captions / LOT / validation.
/// Layout matches Heading Styles / Table Styles section cards.
class TableFormattingRulesCard extends StatelessWidget {
  final TextEditingController captionPatternController;
  final TextEditingController listOfTablesFormatController;
  final String numberingScheme; // global | chapter
  final ValueChanged<String> onNumberingSchemeChanged;
  final String captionPosition; // above | below
  final ValueChanged<String> onCaptionPositionChanged;
  final bool includeLot;
  final ValueChanged<bool> onIncludeLotChanged;
  final bool requireCaption;
  final ValueChanged<bool> onRequireCaptionChanged;
  final bool requireIntextReference;
  final ValueChanged<bool> onRequireIntextReferenceChanged;
  final TextEditingController maxEmptyCellPercentController;

  const TableFormattingRulesCard({
    super.key,
    required this.captionPatternController,
    required this.listOfTablesFormatController,
    required this.numberingScheme,
    required this.onNumberingSchemeChanged,
    required this.captionPosition,
    required this.onCaptionPositionChanged,
    required this.includeLot,
    required this.onIncludeLotChanged,
    required this.requireCaption,
    required this.onRequireCaptionChanged,
    required this.requireIntextReference,
    required this.onRequireIntextReferenceChanged,
    required this.maxEmptyCellPercentController,
  });

  static const _schemeOptions = [
    'Global sequential (Table 1, Table 2, …)',
    'Chapter-wise (Table 3.1, Table 3.2, …)',
  ];
  static const _positionOptions = [
    'Above table',
    'Below table',
  ];

  String get _schemeDisplay => numberingScheme == 'chapter'
      ? _schemeOptions[1]
      : _schemeOptions[0];

  String get _positionDisplay =>
      captionPosition == 'below' ? _positionOptions[1] : _positionOptions[0];

  Widget _section({required String title, required Widget child}) {
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
          child,
        ],
      ),
    );
  }

  Widget _toggleRow(String label, bool value, ValueChanged<bool> onChanged,
      {String? subtitle}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(fontSize: 12, color: Color(0xFF8B949E)),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: TextStyle(
                      fontSize: 11,
                      color: Colors.white.withOpacity(0.35),
                    ),
                  ),
                ],
              ],
            ),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: const Color(0xFF6366F1),
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
        ],
      ),
    );
  }

  Widget _labeledField(String label, Widget field) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: Colors.white70,
          ),
        ),
        const SizedBox(height: 8),
        field,
      ],
    );
  }

  Widget _textBox(TextEditingController controller, {String? hint}) {
    return TextField(
      controller: controller,
      style: const TextStyle(color: Colors.white, fontSize: 13),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: Color(0xFF4A5568), fontSize: 12),
        filled: true,
        fillColor: const Color(0xFF161B22),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: const BorderSide(color: Color(0xFF2D3748)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: const BorderSide(color: Color(0xFF2D3748)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: const BorderSide(color: Color(0xFF6366F1)),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return CommonWidgets.buildCardContainer(
      icon: Icons.table_chart,
      title: 'Table Formatting Rules',
      subtitle: 'Caption numbering, List of Tables, and validation',
      child: Column(
        children: [
          // ── Caption & Numbering ───────────────────────────────────────────
          _section(
            title: 'Caption & Numbering',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: CommonWidgets.buildDropdown(
                        'Numbering scheme',
                        _schemeDisplay,
                        _schemeOptions,
                        (v) => onNumberingSchemeChanged(
                          v.startsWith('Chapter') ? 'chapter' : 'global',
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: CommonWidgets.buildDropdown(
                        'Caption position',
                        _positionDisplay,
                        _positionOptions,
                        (v) => onCaptionPositionChanged(
                          v.startsWith('Below') ? 'below' : 'above',
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                _labeledField(
                  'Caption format pattern',
                  _textBox(
                    captionPatternController,
                    hint: 'Table {n}: {description}',
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  'Placeholders: {n}, {number}, {chapter}, {description}, {caption}',
                  style: TextStyle(
                    fontSize: 11,
                    color: Colors.white.withOpacity(0.4),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // ── List of Tables ────────────────────────────────────────────────
          _section(
            title: 'List of Tables',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _toggleRow(
                  'Include List of Tables',
                  includeLot,
                  onIncludeLotChanged,
                  subtitle: 'Generate LOT when document lists run',
                ),
                const SizedBox(height: 8),
                _labeledField(
                  'List of Tables format',
                  _textBox(
                    listOfTablesFormatController,
                    hint: 'Table {n}: {description}',
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // ── Validation ────────────────────────────────────────────────────
          _section(
            title: 'Validation',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _toggleRow(
                  'Require caption',
                  requireCaption,
                  onRequireCaptionChanged,
                ),
                _toggleRow(
                  'Require in-text reference',
                  requireIntextReference,
                  onRequireIntextReferenceChanged,
                  subtitle: 'Flag tables never cited as “Table N” in body text',
                ),
                const SizedBox(height: 8),
                CommonWidgets.buildNumberInput(
                  'Max empty cell %',
                  maxEmptyCellPercentController,
                  '%',
                ),
                const SizedBox(height: 4),
                Text(
                  'Warn when empty cells exceed this percentage',
                  style: TextStyle(
                    fontSize: 11,
                    color: Colors.white.withOpacity(0.4),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 12),

          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFF6366F1).withOpacity(0.08),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: const Color(0xFF6366F1).withOpacity(0.25),
              ),
            ),
            child: const Row(
              children: [
                Icon(Icons.info_outline, size: 14, color: Color(0xFF6366F1)),
                SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Table border, sizing, and cell layout settings are in the '
                    'Table Styles card below.',
                    style: TextStyle(fontSize: 11, color: Color(0xFF8B949E)),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
