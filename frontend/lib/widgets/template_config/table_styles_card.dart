import 'package:flutter/material.dart';
import 'common_widgets.dart';

class TableStylesCard extends StatelessWidget {
  // ── Font ─────────────────────────────────────────────────────────────────
  final TextEditingController fontSizeController;
  final String fontName;
  final Function(String) onFontNameChanged;

  // ── Header row ────────────────────────────────────────────────────────────
  final bool headerBold;
  final Function(bool) onHeaderBoldChanged;
  final String headerAlign;
  final Function(String) onHeaderAlignChanged;
  final TextEditingController headerBgColorController;

  // ── Body rows ─────────────────────────────────────────────────────────────
  final String bodyAlign;
  final Function(String) onBodyAlignChanged;
  final bool bandedRows;
  final Function(bool) onBandedRowsChanged;
  final TextEditingController bandColorController;

  // ── Borders ───────────────────────────────────────────────────────────────
  final bool borders;
  final Function(bool) onBordersChanged;
  final TextEditingController borderColorController;
  final TextEditingController borderSizeController;

  // ── Padding (twips) ───────────────────────────────────────────────────────
  final TextEditingController paddingTopController;
  final TextEditingController paddingBottomController;
  final TextEditingController paddingLeftController;
  final TextEditingController paddingRightController;

  // ── Layout ────────────────────────────────────────────────────────────────
  final bool centerTable;
  final Function(bool) onCenterTableChanged;
  final bool autoFit;
  final Function(bool) onAutoFitChanged;
  final bool repeatHeader;
  final Function(bool) onRepeatHeaderChanged;

  // ── Extended table formatting ─────────────────────────────────────────────
  final String borderStyle; // none | single_line | double_line | academic_standard
  final Function(String) onBorderStyleChanged;
  final bool headerRowShading;
  final Function(bool) onHeaderRowShadingChanged;
  final TextEditingController maxWidthPercentController;
  final TextEditingController minColumnWidthController;
  final String wideTableHandling;
  final Function(String) onWideTableHandlingChanged;
  final String numericColumnAlign;
  final Function(String) onNumericColumnAlignChanged;
  final String textColumnAlign;
  final Function(String) onTextColumnAlignChanged;
  final String rowHeightPolicy;
  final Function(String) onRowHeightPolicyChanged;
  final TextEditingController spaceBeforeController;
  final TextEditingController spaceAfterController;
  final String alignmentOnPage; // Center | Left
  final Function(String) onAlignmentOnPageChanged;

  const TableStylesCard({
    super.key,
    required this.fontSizeController,
    required this.fontName,
    required this.onFontNameChanged,
    required this.headerBold,
    required this.onHeaderBoldChanged,
    required this.headerAlign,
    required this.onHeaderAlignChanged,
    required this.headerBgColorController,
    required this.bodyAlign,
    required this.onBodyAlignChanged,
    required this.bandedRows,
    required this.onBandedRowsChanged,
    required this.bandColorController,
    required this.borders,
    required this.onBordersChanged,
    required this.borderColorController,
    required this.borderSizeController,
    required this.paddingTopController,
    required this.paddingBottomController,
    required this.paddingLeftController,
    required this.paddingRightController,
    required this.centerTable,
    required this.onCenterTableChanged,
    required this.autoFit,
    required this.onAutoFitChanged,
    required this.repeatHeader,
    required this.onRepeatHeaderChanged,
    required this.borderStyle,
    required this.onBorderStyleChanged,
    required this.headerRowShading,
    required this.onHeaderRowShadingChanged,
    required this.maxWidthPercentController,
    required this.minColumnWidthController,
    required this.wideTableHandling,
    required this.onWideTableHandlingChanged,
    required this.numericColumnAlign,
    required this.onNumericColumnAlignChanged,
    required this.textColumnAlign,
    required this.onTextColumnAlignChanged,
    required this.rowHeightPolicy,
    required this.onRowHeightPolicyChanged,
    required this.spaceBeforeController,
    required this.spaceAfterController,
    required this.alignmentOnPage,
    required this.onAlignmentOnPageChanged,
  });

  // ── Helpers ───────────────────────────────────────────────────────────────

  Color _hexToColor(String hex) {
    try {
      final clean = hex.replaceAll('#', '');
      if (clean.length == 6) {
        return Color(int.parse('FF$clean', radix: 16));
      }
    } catch (_) {}
    return Colors.transparent;
  }

  Widget _colorPreview(TextEditingController ctrl) {
    return ValueListenableBuilder<TextEditingValue>(
      valueListenable: ctrl,
      builder: (_, val, __) {
        final color = _hexToColor(val.text);
        return Container(
          width: 24,
          height: 24,
          margin: const EdgeInsets.only(left: 8),
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(4),
            border: Border.all(color: const Color(0xFF4A5568), width: 1),
          ),
        );
      },
    );
  }

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

  Widget _toggleRow(String label, bool value, Function(bool) onChanged) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: const TextStyle(fontSize: 12, color: Color(0xFF8B949E)),
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

  Widget _hexInput(String label, TextEditingController ctrl) {
    return Row(
      children: [
        Expanded(
          child: _buildTextField(label, ctrl, hint: 'e.g. D6E4F0'),
        ),
        _colorPreview(ctrl),
      ],
    );
  }

  Widget _buildTextField(
    String label,
    TextEditingController ctrl, {
    String? hint,
    TextInputType keyboardType = TextInputType.text,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 11, color: Color(0xFF8B949E)),
        ),
        const SizedBox(height: 4),
        TextFormField(
          controller: ctrl,
          keyboardType: keyboardType,
          style: const TextStyle(color: Colors.white, fontSize: 13),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: const TextStyle(color: Color(0xFF4A5568), fontSize: 12),
            filled: true,
            fillColor: const Color(0xFF161B22),
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
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
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return CommonWidgets.buildCardContainer(
      icon: Icons.table_chart_outlined,
      title: 'Table Styles',
      subtitle:
          'Borders, sizing, cell formatting & layout (applied to detected tables)',
      child: Column(
        children: [
          // ── 1. Font ──────────────────────────────────────────────────────
          _section(
            title: 'Font (cell_font_family / cell_font_size)',
            child: Row(
              children: [
                Expanded(
                  flex: 2,
                  child: CommonWidgets.buildDropdown(
                    'Font Family',
                    fontName,
                    [
                      'Times New Roman',
                      'Calibri',
                      'Arial',
                      'Georgia',
                      'Garamond',
                      'Cambria',
                      'Verdana',
                      'Tahoma',
                    ],
                    onFontNameChanged,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: CommonWidgets.buildNumberInput(
                    'Font Size',
                    fontSizeController,
                    'pt',
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // ── 2. Header Row ─────────────────────────────────────────────────
          _section(
            title: 'Header Row',
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: CommonWidgets.buildDropdown(
                        'Alignment',
                        headerAlign,
                        ['Left', 'Center', 'Right', 'Justify'],
                        onHeaderAlignChanged,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _hexInput(
                        'Background Colour (hex)',
                        headerBgColorController,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                _toggleRow('Bold header text', headerBold,
                    onHeaderBoldChanged),
                _toggleRow('Header row shading', headerRowShading,
                    onHeaderRowShadingChanged),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // ── 3. Body Rows / cell alignment ─────────────────────────────────
          _section(
            title: 'Cell Formatting',
            child: Column(
              children: [
                CommonWidgets.buildDropdown(
                  'Default body alignment',
                  bodyAlign,
                  ['Left', 'Center', 'Right', 'Justify'],
                  onBodyAlignChanged,
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: CommonWidgets.buildDropdown(
                        'Numeric columns',
                        numericColumnAlign,
                        ['Left', 'Center', 'Right'],
                        onNumericColumnAlignChanged,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: CommonWidgets.buildDropdown(
                        'Text columns',
                        textColumnAlign,
                        ['Left', 'Center', 'Right'],
                        onTextColumnAlignChanged,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                CommonWidgets.buildDropdown(
                  'Row height policy',
                  rowHeightPolicy,
                  ['Auto', 'Fixed minimum'],
                  onRowHeightPolicyChanged,
                ),
                const SizedBox(height: 8),
                _toggleRow(
                    'Banded / alternating rows', bandedRows, onBandedRowsChanged),
                if (bandedRows) ...[
                  const SizedBox(height: 8),
                  _hexInput('Band Colour (hex)', bandColorController),
                ],
              ],
            ),
          ),

          const SizedBox(height: 16),

          // ── 4. Borders ────────────────────────────────────────────────────
          _section(
            title: 'Borders & Style',
            child: Column(
              children: [
                CommonWidgets.buildDropdown(
                  'Border style',
                  borderStyle,
                  [
                    'None',
                    'Single line',
                    'Double line',
                    'Academic standard',
                  ],
                  onBorderStyleChanged,
                ),
                const SizedBox(height: 8),
                _toggleRow(
                    'Show borders', borders, onBordersChanged),
                if (borders) ...[
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        flex: 2,
                        child: _hexInput(
                            'Border Colour (hex)', borderColorController),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: CommonWidgets.buildNumberInput(
                          'Thickness',
                          borderSizeController,
                          'hp',
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),

          const SizedBox(height: 16),

          // ── 5. Cell Padding ───────────────────────────────────────────────
          _section(
            title: 'Cell Padding (twips)',
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: CommonWidgets.buildNumberInput(
                          'Top', paddingTopController, 'tw'),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: CommonWidgets.buildNumberInput(
                          'Bottom', paddingBottomController, 'tw'),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: CommonWidgets.buildNumberInput(
                          'Left', paddingLeftController, 'tw'),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: CommonWidgets.buildNumberInput(
                          'Right', paddingRightController, 'tw'),
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // ── 6. Sizing ─────────────────────────────────────────────────────
          _section(
            title: 'Sizing',
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: CommonWidgets.buildNumberInput(
                        'Max width %',
                        maxWidthPercentController,
                        '%',
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: CommonWidgets.buildNumberInput(
                        'Min column width',
                        minColumnWidthController,
                        'in',
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                CommonWidgets.buildDropdown(
                  'Wide table handling',
                  wideTableHandling,
                  [
                    'Shrink font',
                    'Landscape page',
                    'Flag for manual review',
                  ],
                  onWideTableHandlingChanged,
                ),
                const SizedBox(height: 8),
                _toggleRow(
                    'Auto-fit columns', autoFit, onAutoFitChanged),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // ── 7. Layout Options ─────────────────────────────────────────────
          _section(
            title: 'Layout',
            child: Column(
              children: [
                CommonWidgets.buildDropdown(
                  'Alignment on page',
                  alignmentOnPage,
                  ['Center', 'Left'],
                  onAlignmentOnPageChanged,
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: CommonWidgets.buildNumberInput(
                        'Space before',
                        spaceBeforeController,
                        'pt',
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: CommonWidgets.buildNumberInput(
                        'Space after',
                        spaceAfterController,
                        'pt',
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                _toggleRow('Centre table on page (legacy)', centerTable,
                    onCenterTableChanged),
                _toggleRow('Repeat header on page break', repeatHeader,
                    onRepeatHeaderChanged),
              ],
            ),
          ),

          const SizedBox(height: 12),

          // ── Info note ─────────────────────────────────────────────────────
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
                Icon(Icons.info_outline,
                    size: 14, color: Color(0xFF6366F1)),
                SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'These settings are stored on the template now. '
                    'Automatic table reformatting will use them in a later step.',
                    style: TextStyle(
                      fontSize: 11,
                      color: Color(0xFF8B949E),
                    ),
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
