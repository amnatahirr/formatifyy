import 'package:flutter/material.dart';

import 'tr.dart';
class StylePreviewWidget extends StatelessWidget {
  final Map<String, dynamic> formattingRules;

  const StylePreviewWidget({
    Key? key,
    required this.formattingRules,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        border: Border.all(color: Colors.grey[300]!),
        borderRadius: BorderRadius.circular(8),
        color: Colors.white,
      ),
      padding: const EdgeInsets.all(24),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Tr('Preview',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 24),
            // Heading 1 Preview
            Tr('Heading 1 Example',
              style: _getHeading1Style(),
            ),
            const SizedBox(height: 16),
            // Heading 2 Preview
            Tr('Heading 2 Example',
              style: _getHeading2Style(),
            ),
            const SizedBox(height: 16),
            // Heading 3 Preview
            Tr('Heading 3 Example',
              style: _getHeading3Style(),
            ),
            const SizedBox(height: 16),
            // Body Text Preview
            Tr('This is body text example. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.',
              style: _getBodyStyle(),
            ),
            const SizedBox(height: 24),
            // Margin Preview
            Container(
              decoration: BoxDecoration(
                border: Border.all(color: Colors.blue, width: 2),
                borderRadius: BorderRadius.circular(4),
              ),
              padding: const EdgeInsets.all(16),
              child: Container(
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.red, style: BorderStyle.solid),
                  borderRadius: BorderRadius.circular(2),
                ),
                padding: _getMarginInsets(),
                child: Container(
                  color: Colors.grey[100],
                  padding: const EdgeInsets.all(8),
                  child: const Tr('Content Area',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey,
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Tr('Blue border = Page edges, Red border = Margins',
              style: TextStyle(
                fontSize: 10,
                color: Colors.grey[600],
                fontStyle: FontStyle.italic,
              ),
            ),
          ],
        ),
      ),
    );
  }

  TextStyle _getHeading1Style() {
    return TextStyle(
      fontFamily: _parseFontFamily(formattingRules['heading1_font'] ?? 'Times New Roman'),
      fontSize: double.parse((formattingRules['heading1_size'] ?? 18).toString()),
      fontWeight: (formattingRules['heading1_bold'] ?? true) ? FontWeight.bold : FontWeight.normal,
      fontStyle: (formattingRules['heading1_italic'] ?? false) ? FontStyle.italic : FontStyle.normal,
      decoration: (formattingRules['heading1_underline'] ?? false)
          ? TextDecoration.underline
          : TextDecoration.none,
      color: _parseColor(formattingRules['heading1_color'] ?? '#000000'),
    );
  }

  TextStyle _getHeading2Style() {
    return TextStyle(
      fontFamily: _parseFontFamily(formattingRules['heading2_font'] ?? 'Times New Roman'),
      fontSize: double.parse((formattingRules['heading2_size'] ?? 16).toString()),
      fontWeight: (formattingRules['heading2_bold'] ?? true) ? FontWeight.bold : FontWeight.normal,
      fontStyle: (formattingRules['heading2_italic'] ?? false) ? FontStyle.italic : FontStyle.normal,
      decoration: (formattingRules['heading2_underline'] ?? false)
          ? TextDecoration.underline
          : TextDecoration.none,
      color: _parseColor(formattingRules['heading2_color'] ?? '#000000'),
    );
  }

  TextStyle _getHeading3Style() {
    return TextStyle(
      fontFamily: _parseFontFamily(formattingRules['heading3_font'] ?? 'Times New Roman'),
      fontSize: double.parse((formattingRules['heading3_size'] ?? 14).toString()),
      fontWeight: (formattingRules['heading3_bold'] ?? true) ? FontWeight.bold : FontWeight.normal,
      fontStyle: (formattingRules['heading3_italic'] ?? false) ? FontStyle.italic : FontStyle.normal,
      decoration: (formattingRules['heading3_underline'] ?? false)
          ? TextDecoration.underline
          : TextDecoration.none,
      color: _parseColor(formattingRules['heading3_color'] ?? '#000000'),
    );
  }

  TextStyle _getBodyStyle() {
  final lineSpacing =
      double.parse((formattingRules['line_spacing'] ?? 1.5).toString());

  return TextStyle(
    fontFamily:
        _parseFontFamily(formattingRules['body_font'] ?? 'Times New Roman'),
    fontSize:
        double.parse((formattingRules['body_size'] ?? 12).toString()),
    color: _parseColor(formattingRules['body_color'] ?? '#000000'),
    height: lineSpacing,
  );
}


  EdgeInsets _getMarginInsets() {
    final top = double.parse((formattingRules['margin_top'] ?? 1.0).toString()) * 16;
    final bottom = double.parse((formattingRules['margin_bottom'] ?? 1.0).toString()) * 16;
    final left = double.parse((formattingRules['margin_left'] ?? 1.0).toString()) * 16;
    final right = double.parse((formattingRules['margin_right'] ?? 1.0).toString()) * 16;
    return EdgeInsets.fromLTRB(left, top, right, bottom);
  }

  String _parseFontFamily(dynamic font) {
    if (font == null) return 'Times New Roman';
    final fontStr = font.toString().toLowerCase();
    if (fontStr.contains('arial')) return 'Arial';
    if (fontStr.contains('georgia')) return 'Georgia';
    if (fontStr.contains('courier')) return 'Courier New';
    if (fontStr.contains('verdana')) return 'Verdana';
    if (fontStr.contains('calibri')) return 'Calibri';
    if (fontStr.contains('garamond')) return 'Garamond';
    return 'Times New Roman';
  }

  Color _parseColor(String colorString) {
    try {
      if (colorString.startsWith('#')) {
        return Color(int.parse(colorString.replaceFirst('#', '0xff')));
      }
      return Colors.black;
    } catch (e) {
      return Colors.black;
    }
  }
}
