// import 'package:flutter/material.dart';
// import 'package:provider/provider.dart';
// import 'dart:convert';
// import 'package:http/http.dart' as http;
// import '../config/api_config.dart';
// import '../providers/auth_provider.dart';
// import '../providers/template_provider.dart';
// import '../widgets/template_config/required_sections_card.dart';
// // Import widget files
// import '../widgets/template_config/template_header.dart';
// import '../widgets/template_config/template_selector.dart';
// import '../widgets/template_config/template_name_field.dart';
// import '../widgets/template_config/document_settings_card.dart';
// import '../widgets/template_config/font_settings_card.dart';
// import '../widgets/template_config/paragraph_style_card.dart';
// import '../widgets/template_config/list_bullet_styles_card.dart';
// import '../widgets/template_config/heading_styles_card.dart';
// import '../widgets/template_config/table_styles_card.dart';    // ← NEW
// import '../widgets/template_config/action_buttons.dart';
// import '../utils/template_mapping_utils.dart';
// import '../screens/admin_reference_settings_screen.dart';

// class TemplateConfigurationScreen extends StatefulWidget {
//   const TemplateConfigurationScreen({super.key});

//   @override
//   State<TemplateConfigurationScreen> createState() =>
//       _TemplateConfigurationScreenState();
// }

// class _TemplateConfigurationScreenState
//     extends State<TemplateConfigurationScreen> {
//   Map<String, dynamic> _referenceRules = {};
//   late String baseUrl;
//   int? _selectedTemplateId;
//   Map<String, dynamic>? _selectedTemplate;
//   bool _isLoading = false;
//   List<RequiredSectionItem> _requiredSections = [];
//   bool _isSaving = false;

//   // ── Existing form controllers ─────────────────────────────────────────────
//   late TextEditingController _templateNameController;
//   late TextEditingController _pageMarginTopController;
//   late TextEditingController _pageMarginBottomController;
//   late TextEditingController _pageMarginLeftController;
//   late TextEditingController _pageMarginRightController;
//   late TextEditingController _heading1SizeController;
//   late TextEditingController _heading1SpaceBeforeController;
//   late TextEditingController _heading1SpaceAfterController;
//   late TextEditingController _heading2SizeController;
//   late TextEditingController _heading2SpaceBeforeController;
//   late TextEditingController _heading2SpaceAfterController;
//   late TextEditingController _heading3SizeController;
//   late TextEditingController _heading3SpaceBeforeController;
//   late TextEditingController _heading3SpaceAfterController;
//   late TextEditingController _heading4SizeController;
//   late TextEditingController _heading4SpaceBeforeController;
//   late TextEditingController _heading4SpaceAfterController;
//   late TextEditingController _bodyFontSizeController;
//   late TextEditingController _lineSpacingController;
//   late TextEditingController _firstLineIndentController;
//   late TextEditingController _bulletIndentController;
//   late TextEditingController _paragraphSpaceBeforeController;
//   late TextEditingController _paragraphSpaceAfterController;

//   // ── NEW: Table style controllers & state ──────────────────────────────────
//   late TextEditingController _tableFontSizeController;
//   late TextEditingController _tableHeaderBgColorController;
//   late TextEditingController _tableBandColorController;
//   late TextEditingController _tableBorderColorController;
//   late TextEditingController _tableBorderSizeController;
//   late TextEditingController _tablePaddingTopController;
//   late TextEditingController _tablePaddingBottomController;
//   late TextEditingController _tablePaddingLeftController;
//   late TextEditingController _tablePaddingRightController;

//   String _tableFontName   = 'Times New Roman';
//   String _tableHeaderAlign = 'Center';
//   String _tableBodyAlign   = 'Left';
//   bool   _tableHeaderBold  = true;
//   bool   _tableBandedRows  = true;
//   bool   _tableBorders     = true;
//   bool   _tableCenterTable = true;
//   bool   _tableAutoFit     = true;
//   bool   _tableRepeatHeader = true;
//   // ─────────────────────────────────────────────────────────────────────────

//   String _pageSize = 'A4';
//   String _primaryFontFamily = 'Times New Roman';
//   String _secondaryFontFamily = 'Same as Primary';
//   String _bulletStyle = 'Filled Circle';
//   String _numberingFormat = '1, 2, 3 (Arabic)';

//   String _heading1Weight = 'Bold';
//   String _heading2Weight = 'Bold';
//   String _heading3Weight = 'Bold';
//   String _heading4Weight = 'Medium';

//   String _heading1Alignment = 'Center';
//   String _heading2Alignment = 'Left';
//   String _heading3Alignment = 'Left';
//   String _heading4Alignment = 'Left';

//   String _heading1Transform = 'UPPERCASE';
//   String _heading2Transform = 'None';
//   String _heading3Transform = 'Normal';
//   String _heading4Transform = 'Normal';

//   bool _enableLigatures = true;
//   bool _justifyText = true;

//   int get _userId => context.read<AuthProvider>().userId ?? 0;

//   @override
//   void initState() {
//     super.initState();
//     baseUrl = ApiConfig.getBaseUrl();
//     _initializeControllers();

//     WidgetsBinding.instance.addPostFrameCallback((_) {
//       _loadTemplates();
//     });
//   }

//   void _initializeControllers() {
//     _templateNameController = TextEditingController();
//     _pageMarginTopController = TextEditingController();
//     _pageMarginBottomController = TextEditingController();
//     _pageMarginLeftController = TextEditingController();
//     _pageMarginRightController = TextEditingController();
//     _heading1SizeController = TextEditingController();
//     _heading1SpaceBeforeController = TextEditingController();
//     _heading1SpaceAfterController = TextEditingController();
//     _heading2SizeController = TextEditingController();
//     _heading2SpaceBeforeController = TextEditingController();
//     _heading2SpaceAfterController = TextEditingController();
//     _heading3SizeController = TextEditingController();
//     _heading3SpaceBeforeController = TextEditingController();
//     _heading3SpaceAfterController = TextEditingController();
//     _heading4SizeController = TextEditingController();
//     _heading4SpaceBeforeController = TextEditingController();
//     _heading4SpaceAfterController = TextEditingController();
//     _bodyFontSizeController = TextEditingController();
//     _lineSpacingController = TextEditingController();
//     _firstLineIndentController = TextEditingController();
//     _bulletIndentController = TextEditingController();
//     _paragraphSpaceBeforeController = TextEditingController();
//     _paragraphSpaceAfterController = TextEditingController();

//     // Table style controllers
//     _tableFontSizeController      = TextEditingController(text: '12');
//     _tableHeaderBgColorController = TextEditingController(text: 'D6E4F0');
//     _tableBandColorController     = TextEditingController(text: 'F2F8FC');
//     _tableBorderColorController   = TextEditingController(text: '000000');
//     _tableBorderSizeController    = TextEditingController(text: '4');
//     _tablePaddingTopController    = TextEditingController(text: '60');
//     _tablePaddingBottomController = TextEditingController(text: '60');
//     _tablePaddingLeftController   = TextEditingController(text: '108');
//     _tablePaddingRightController  = TextEditingController(text: '108');

//     _templateNameController.addListener(() => setState(() {}));
//   }

//   Future<void> _loadTemplates() async {
//     if (!mounted) return;

//     setState(() => _isLoading = true);

//     try {
//       final templateProvider = context.read<TemplateProvider>();
//       await templateProvider.fetchUniversityTemplates(1);

//       if (!mounted) return;

//       setState(() {
//         _selectedTemplateId = null;
//         _selectedTemplate = null;
//         _isLoading = false;
//       });

//       _clearFormFields();
//     } catch (e) {
//       if (!mounted) return;
//       setState(() => _isLoading = false);
//       ScaffoldMessenger.of(context)
//           .showSnackBar(SnackBar(content: Text('Error loading templates: $e')));
//     }
//   }

//   void _clearFormFields() {
//     _templateNameController.clear();
//     _pageMarginTopController.clear();
//     _pageMarginBottomController.clear();
//     _pageMarginLeftController.clear();
//     _pageMarginRightController.clear();
//     _heading1SizeController.clear();
//     _heading1SpaceBeforeController.clear();
//     _heading1SpaceAfterController.clear();
//     _heading2SizeController.clear();
//     _heading2SpaceBeforeController.clear();
//     _heading2SpaceAfterController.clear();
//     _heading3SizeController.clear();
//     _heading3SpaceBeforeController.clear();
//     _heading3SpaceAfterController.clear();
//     _heading4SizeController.clear();
//     _heading4SpaceBeforeController.clear();
//     _heading4SpaceAfterController.clear();
//     _bodyFontSizeController.clear();
//     _lineSpacingController.clear();
//     _firstLineIndentController.clear();
//     _bulletIndentController.clear();
//     _paragraphSpaceBeforeController.clear();
//     _paragraphSpaceAfterController.clear();

//     // Reset table style to defaults
//     _tableFontSizeController.text      = '12';
//     _tableHeaderBgColorController.text = 'D6E4F0';
//     _tableBandColorController.text     = 'F2F8FC';
//     _tableBorderColorController.text   = '000000';
//     _tableBorderSizeController.text    = '4';
//     _tablePaddingTopController.text    = '60';
//     _tablePaddingBottomController.text = '60';
//     _tablePaddingLeftController.text   = '108';
//     _tablePaddingRightController.text  = '108';

//     setState(() {
//       _pageSize = 'A4';
//       _primaryFontFamily = 'Times New Roman';
//       _secondaryFontFamily = 'Same as Primary';
//       _bulletStyle = 'Filled Circle';
//       _numberingFormat = '1, 2, 3 (Arabic)';
//       _heading1Weight = 'Bold';
//       _heading2Weight = 'Bold';
//       _heading3Weight = 'Bold';
//       _heading4Weight = 'Medium';
//       _heading1Alignment = 'Center';
//       _heading2Alignment = 'Left';
//       _heading3Alignment = 'Left';
//       _heading4Alignment = 'Left';
//       _heading1Transform = 'UPPERCASE';
//       _heading2Transform = 'None';
//       _heading3Transform = 'Normal';
//       _heading4Transform = 'Normal';
//       _enableLigatures = true;
//       _justifyText = true;
//       _requiredSections = [];

//       // Table style resets
//       _tableFontName    = 'Times New Roman';
//       _tableHeaderAlign = 'Center';
//       _tableBodyAlign   = 'Left';
//       _tableHeaderBold  = true;
//       _tableBandedRows  = true;
//       _tableBorders     = true;
//       _tableCenterTable = true;
//       _tableAutoFit     = true;
//       _tableRepeatHeader = true;
//     });
//   }

//   void _fillDefaultValues() {
//     _pageMarginTopController.text = '25';
//     _pageMarginBottomController.text = '25';
//     _pageMarginLeftController.text = '30';
//     _pageMarginRightController.text = '20';
//     _heading1SizeController.text = '18';
//     _heading1SpaceBeforeController.text = '12';
//     _heading1SpaceAfterController.text = '6';
//     _heading2SizeController.text = '16';
//     _heading2SpaceBeforeController.text = '10';
//     _heading2SpaceAfterController.text = '5';
//     _heading3SizeController.text = '14';
//     _heading3SpaceBeforeController.text = '8';
//     _heading3SpaceAfterController.text = '4';
//     _heading4SizeController.text = '12';
//     _heading4SpaceBeforeController.text = '6';
//     _heading4SpaceAfterController.text = '3';
//     _bodyFontSizeController.text = '12';
//     _lineSpacingController.text = '2.0';
//     _firstLineIndentController.text = '0.5';
//     _bulletIndentController.text = '0.5';
//     _paragraphSpaceBeforeController.text = '0';
//     _paragraphSpaceAfterController.text = '0';
//   }

//   Future<void> _loadTemplateDetails() async {
//     if (_selectedTemplateId == null) return;

//     try {
//       setState(() => _isLoading = true);

//       final response = await http.get(
//         Uri.parse('$baseUrl/templates/$_selectedTemplateId'),
//       );

//       if (response.statusCode == 200) {
//         final template = jsonDecode(response.body);

//         final rules = template['formatting_rules'] ?? {};
//         final rawSections =
//             (template['required_sections'] as List<dynamic>?) ?? [];
//         _requiredSections = rawSections.map((s) {
//           if (s is Map<String, dynamic>) return RequiredSectionItem.fromJson(s);
//           return RequiredSectionItem(name: s.toString());
//         }).toList();

//         // Load table style from template if present
//         final tableStyle =
//             rules['table_style'] as Map<String, dynamic>? ?? {};

//         setState(() {
//           _selectedTemplate = template;

//           _templateNameController.text = template['name'] ?? '';

//           _pageMarginTopController.text =
//               (rules['margin_top'] ?? 25).toString();
//           _pageMarginBottomController.text =
//               (rules['margin_bottom'] ?? 25).toString();
//           _pageMarginLeftController.text =
//               (rules['margin_left'] ?? 30).toString();
//           _pageMarginRightController.text =
//               (rules['margin_right'] ?? 20).toString();

//           _heading1SizeController.text =
//               (rules['heading1_size'] ?? 18).toString();
//           _heading1SpaceBeforeController.text =
//               (rules['heading1_space_before'] ?? 12.0).toString();
//           _heading1SpaceAfterController.text =
//               (rules['heading1_space_after'] ?? 6.0).toString();
//           _heading1Weight =
//               (rules['heading1_bold'] == true) ? 'Bold' : 'Normal';

//           _heading2SizeController.text =
//               (rules['heading2_size'] ?? 16).toString();
//           _heading2SpaceBeforeController.text =
//               (rules['heading2_space_before'] ?? 10.0).toString();
//           _heading2SpaceAfterController.text =
//               (rules['heading2_space_after'] ?? 5.0).toString();
//           _heading2Weight =
//               (rules['heading2_bold'] == true) ? 'Bold' : 'Normal';

//           _heading3SizeController.text =
//               (rules['heading3_size'] ?? 14).toString();
//           _heading3SpaceBeforeController.text =
//               (rules['heading3_space_before'] ?? 8.0).toString();
//           _heading3SpaceAfterController.text =
//               (rules['heading3_space_after'] ?? 4.0).toString();
//           _heading3Weight =
//               (rules['heading3_bold'] == true) ? 'Bold' : 'Normal';

//           _heading4SizeController.text =
//               (rules['heading4_size'] ?? 12).toString();
//           _heading4SpaceBeforeController.text =
//               (rules['heading4_space_before'] ?? 6.0).toString();
//           _heading4SpaceAfterController.text =
//               (rules['heading4_space_after'] ?? 3.0).toString();
//           _heading4Weight =
//               (rules['heading4_bold'] == true) ? 'Bold' : 'Normal';

//           _bodyFontSizeController.text =
//               (rules['body_size'] ?? 12).toString();
//           _lineSpacingController.text =
//               (rules['body_line_spacing'] ?? 2.0).toString();
//           _firstLineIndentController.text =
//               (rules['first_line_indent'] ?? 0.5).toString();
//           _bulletIndentController.text =
//               (rules['bullet_indent'] ?? 0.5).toString();

//           _paragraphSpaceBeforeController.text =
//               (rules['body_space_before'] ?? 0.0).toString();
//           _paragraphSpaceAfterController.text =
//               (rules['body_space_after'] ?? 0.0).toString();

//           _primaryFontFamily = rules['heading1_font'] ?? 'Times New Roman';
//           _pageSize = rules['page_size'] ?? 'A4';

//           _bulletStyle = TemplateMappingUtils.mapBulletTypeToDisplay(
//               rules['bullet_type'] ?? 'bullet');
//           _numberingFormat = TemplateMappingUtils.mapNumberedStyleToDisplay(
//               rules['numbered_style'] ?? '1,2,3');

//           _justifyText = rules['body_justified'] ?? true;

//           // ── Load table style ──────────────────────────────────────────────
//           _tableFontName    = tableStyle['font_name']    ?? 'Times New Roman';
//           _tableHeaderAlign = _capitalise(tableStyle['header_align'] ?? 'center');
//           _tableBodyAlign   = _capitalise(tableStyle['body_align']   ?? 'left');
//           _tableHeaderBold  = tableStyle['header_bold']   ?? true;
//           _tableBandedRows  = tableStyle['banded_rows']   ?? true;
//           _tableBorders     = tableStyle['borders']       ?? true;
//           _tableCenterTable = tableStyle['center_table']  ?? true;
//           _tableAutoFit     = tableStyle['auto_fit']      ?? true;
//           _tableRepeatHeader = tableStyle['repeat_header'] ?? true;

//           _tableFontSizeController.text =
//               (tableStyle['font_size'] ?? 12).toString();
//           _tableHeaderBgColorController.text =
//               (tableStyle['header_bg'] ?? 'D6E4F0').toString().replaceAll('#', '');
//           _tableBandColorController.text =
//               (tableStyle['band_color'] ?? 'F2F8FC').toString().replaceAll('#', '');
//           _tableBorderColorController.text =
//               (tableStyle['border_color'] ?? '000000').toString().replaceAll('#', '');
//           _tableBorderSizeController.text =
//               (tableStyle['border_size'] ?? 4).toString();
//           _tablePaddingTopController.text =
//               (tableStyle['cell_padding_top'] ?? 60).toString();
//           _tablePaddingBottomController.text =
//               (tableStyle['cell_padding_bot'] ?? 60).toString();
//           _tablePaddingLeftController.text =
//               (tableStyle['cell_padding_lft'] ?? 108).toString();
//           _tablePaddingRightController.text =
//               (tableStyle['cell_padding_rgt'] ?? 108).toString();

//           _isLoading = false;
//         });
//       }
//     } catch (e) {
//       setState(() => _isLoading = false);
//       if (mounted) {
//         ScaffoldMessenger.of(context)
//             .showSnackBar(SnackBar(content: Text('Error loading template: $e')));
//       }
//     }
//   }

//   // ── Capitalise first letter for dropdown values loaded from DB ────────────
//   String _capitalise(String s) =>
//       s.isEmpty ? s : s[0].toUpperCase() + s.substring(1).toLowerCase();

//   Future<void> _createTemplate() async {
//     if (_templateNameController.text.trim().isEmpty) {
//       ScaffoldMessenger.of(context).showSnackBar(
//           const SnackBar(content: Text('Please enter a template name')));
//       return;
//     }

//     if (_pageMarginTopController.text.isEmpty ||
//         _pageMarginBottomController.text.isEmpty ||
//         _pageMarginLeftController.text.isEmpty ||
//         _pageMarginRightController.text.isEmpty ||
//         _bodyFontSizeController.text.isEmpty ||
//         _lineSpacingController.text.isEmpty) {
//       ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
//           content: Text('Please fill in required margin and font fields')));
//       return;
//     }

//     setState(() => _isSaving = true);

//     try {
//       final authProvider = context.read<AuthProvider>();
//       final lineSpacing = double.parse(
//           _lineSpacingController.text.isEmpty
//               ? '2.0'
//               : _lineSpacingController.text);

//       final templateData = _buildTemplateData(lineSpacing);

//       final response = await http.post(
//         Uri.parse(
//             '$baseUrl/admin/templates?user_id=${authProvider.userId}&university_id=1'),
//         headers: {'Content-Type': 'application/json'},
//         body: jsonEncode(templateData),
//       );

//       if (response.statusCode == 200 || response.statusCode == 201) {
//         if (mounted) {
//           ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
//               content: Text('Template created successfully!'),
//               backgroundColor: Colors.green));
//         }
//         await _loadTemplates();
//         _clearFormFields();
//         setState(() => _selectedTemplateId = null);
//       } else {
//         if (mounted) {
//           ScaffoldMessenger.of(context).showSnackBar(SnackBar(
//               content: Text('Error: ${response.body}'),
//               backgroundColor: Colors.red));
//         }
//       }
//     } catch (e) {
//       if (mounted) {
//         ScaffoldMessenger.of(context).showSnackBar(
//             SnackBar(content: Text('Error creating template: $e')));
//       }
//     } finally {
//       setState(() => _isSaving = false);
//     }
//   }

//   Future<void> _saveTemplate() async {
//     if (_selectedTemplateId == null) {
//       ScaffoldMessenger.of(context).showSnackBar(
//           const SnackBar(content: Text('No template selected to save')));
//       return;
//     }

//     setState(() => _isSaving = true);

//     try {
//       final authProvider = context.read<AuthProvider>();
//       final lineSpacing = double.parse(
//           _lineSpacingController.text.isEmpty
//               ? '2.0'
//               : _lineSpacingController.text);

//       final templateData = _buildTemplateData(lineSpacing);

//       final response = await http.put(
//         Uri.parse(
//             '$baseUrl/admin/templates/$_selectedTemplateId?user_id=${authProvider.userId}'),
//         headers: {'Content-Type': 'application/json'},
//         body: jsonEncode(templateData),
//       );

//       if (response.statusCode == 200) {
//         if (mounted) {
//           ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
//               content: Text('Template saved successfully!'),
//               backgroundColor: Colors.green));
//         }
//         final templateProvider = context.read<TemplateProvider>();
//         await templateProvider.fetchUniversityTemplates(1);
//       } else {
//         if (mounted) {
//           ScaffoldMessenger.of(context).showSnackBar(SnackBar(
//               content: Text('Error: ${response.body}'),
//               backgroundColor: Colors.red));
//         }
//       }
//     } catch (e) {
//       if (mounted) {
//         ScaffoldMessenger.of(context)
//             .showSnackBar(SnackBar(content: Text('Error saving template: $e')));
//       }
//     } finally {
//       setState(() => _isSaving = false);
//     }
//   }

//   // ── Helpers ───────────────────────────────────────────────────────────────

//   double _safeDouble(String value, double def) =>
//       value.isEmpty ? def : (double.tryParse(value) ?? def);

//   int _safeInt(String value, int def) =>
//       value.isEmpty ? def : (int.tryParse(value) ?? def);

//   /// Build the table_style sub-object from current UI state.
//   Map<String, dynamic> _buildTableStyleData() {
//     return {
//       'font_name':        _tableFontName,
//       'font_size':        _safeInt(_tableFontSizeController.text, 12),
//       'header_bold':      _tableHeaderBold,
//       'header_bg':        _tableHeaderBgColorController.text.replaceAll('#', ''),
//       'header_align':     _tableHeaderAlign.toLowerCase(),
//       'body_align':       _tableBodyAlign.toLowerCase(),
//       'banded_rows':      _tableBandedRows,
//       'band_color':       _tableBandColorController.text.replaceAll('#', ''),
//       'borders':          _tableBorders,
//       'border_color':     _tableBorderColorController.text.replaceAll('#', ''),
//       'border_size':      _safeInt(_tableBorderSizeController.text, 4),
//       'cell_padding_top': _safeInt(_tablePaddingTopController.text, 60),
//       'cell_padding_bot': _safeInt(_tablePaddingBottomController.text, 60),
//       'cell_padding_lft': _safeInt(_tablePaddingLeftController.text, 108),
//       'cell_padding_rgt': _safeInt(_tablePaddingRightController.text, 108),
//       'center_table':     _tableCenterTable,
//       'auto_fit':         _tableAutoFit,
//       'repeat_header':    _tableRepeatHeader,
//     };
//   }

//   Map<String, dynamic> _buildTemplateData(double lineSpacing) {
//     print('Selected template: $_selectedTemplate');

//     // Preserve existing reference_rules
//     Map<String, dynamic> existingRefRules = {};
//     if (_selectedTemplate != null) {
//       if (_selectedTemplate!.containsKey('formatting_rules')) {
//         final fr = _selectedTemplate!['formatting_rules'] as Map<String, dynamic>?;
//         if (fr != null && fr.containsKey('reference_rules')) {
//           existingRefRules = fr['reference_rules'] as Map<String, dynamic>? ?? {};
//         }
//       }
//       if (_selectedTemplate!.containsKey('reference_rules')) {
//         existingRefRules =
//             _selectedTemplate!['reference_rules'] as Map<String, dynamic>? ?? {};
//       }
//     }

//     final formattingRules = <String, dynamic>{
//       // Heading 1
//       'heading1_font': _primaryFontFamily,
//       'heading1_size': _safeInt(_heading1SizeController.text, 18),
//       'heading1_bold': _heading1Weight.contains('Bold'),
//       'heading1_italic': false,
//       'heading1_underline': false,
//       'heading1_color': '#000000',
//       'heading1_line_spacing': 1.5,
//       'heading1_space_before':
//           _safeDouble(_heading1SpaceBeforeController.text, 12.0),
//       'heading1_space_after':
//           _safeDouble(_heading1SpaceAfterController.text, 6.0),
//       // Heading 2
//       'heading2_font': _primaryFontFamily,
//       'heading2_size': _safeInt(_heading2SizeController.text, 16),
//       'heading2_bold': _heading2Weight.contains('Bold'),
//       'heading2_italic': false,
//       'heading2_underline': false,
//       'heading2_color': '#000000',
//       'heading2_line_spacing': 1.5,
//       'heading2_space_before':
//           _safeDouble(_heading2SpaceBeforeController.text, 10.0),
//       'heading2_space_after':
//           _safeDouble(_heading2SpaceAfterController.text, 5.0),
//       // Heading 3
//       'heading3_font': _primaryFontFamily,
//       'heading3_size': _safeInt(_heading3SizeController.text, 14),
//       'heading3_bold': _heading3Weight.contains('Bold'),
//       'heading3_italic': false,
//       'heading3_underline': false,
//       'heading3_color': '#000000',
//       'heading3_line_spacing': 1.5,
//       'heading3_space_before':
//           _safeDouble(_heading3SpaceBeforeController.text, 8.0),
//       'heading3_space_after':
//           _safeDouble(_heading3SpaceAfterController.text, 4.0),
//       // Heading 4
//       'heading4_font': _primaryFontFamily,
//       'heading4_size': _safeInt(_heading4SizeController.text, 12),
//       'heading4_bold': _heading4Weight.contains('Bold'),
//       'heading4_italic': false,
//       'heading4_underline': false,
//       'heading4_color': '#000000',
//       'heading4_line_spacing': 1.5,
//       'heading4_space_before':
//           _safeDouble(_heading4SpaceBeforeController.text, 6.0),
//       'heading4_space_after':
//           _safeDouble(_heading4SpaceAfterController.text, 3.0),
//       // Body
//       'body_font': _primaryFontFamily,
//       'body_size': _safeInt(_bodyFontSizeController.text, 12),
//       'body_color': '#000000',
//       'body_line_spacing': lineSpacing,
//       'body_space_before':
//           _safeDouble(_paragraphSpaceBeforeController.text, 0.0),
//       'body_space_after':
//           _safeDouble(_paragraphSpaceAfterController.text, 0.0),
//       'body_justified': _justifyText,
//       // Bullets
//       'bullet_font': _primaryFontFamily,
//       'bullet_size': _safeInt(_bodyFontSizeController.text, 12),
//       'bullet_color': '#000000',
//       'bullet_line_spacing': lineSpacing,
//       'bullet_indent': _safeDouble(_bulletIndentController.text, 0.5),
//       'bullet_space_before': 0.0,
//       'bullet_space_after': 0.0,
//       'bullet_type':
//           TemplateMappingUtils.mapBulletTypeToDb(_bulletStyle),
//       // Numbered
//       'numbered_font': _primaryFontFamily,
//       'numbered_size': _safeInt(_bodyFontSizeController.text, 12),
//       'numbered_color': '#000000',
//       'numbered_line_spacing': lineSpacing,
//       'numbered_indent': _safeDouble(_bulletIndentController.text, 0.5),
//       'numbered_space_before': 0.0,
//       'numbered_space_after': 0.0,
//       'numbered_style':
//           TemplateMappingUtils.mapNumberedStyleToDb(_numberingFormat),
//       // Page
//       'page_size': _pageSize,
//       'margin_top': _safeDouble(_pageMarginTopController.text, 25.0),
//       'margin_bottom': _safeDouble(_pageMarginBottomController.text, 25.0),
//       'margin_left': _safeDouble(_pageMarginLeftController.text, 30.0),
//       'margin_right': _safeDouble(_pageMarginRightController.text, 20.0),
//       'line_number_enabled': false,
//       'first_line_indent': _safeDouble(_firstLineIndentController.text, 0.5),

//       // ── Table style (NEW) ─────────────────────────────────────────────────
//       'table_style': _buildTableStyleData(),
//     };

//     // Reference rules — prefer updated UI rules, fall back to existing DB values
//     if (_referenceRules.isNotEmpty) {
//       formattingRules['reference_rules'] = _referenceRules;
//     } else if (existingRefRules.isNotEmpty) {
//       formattingRules['reference_rules'] = existingRefRules;
//     }

//     return {
//       'name': _templateNameController.text.trim(),
//       'required_sections': _requiredSections
//           .asMap()
//           .entries
//           .map((e) => e.value.toJson(e.key + 1))
//           .toList(),
//       'formatting_rules': formattingRules,
//     };
//   }

//   @override
//   void dispose() {
//     _templateNameController.dispose();
//     _pageMarginTopController.dispose();
//     _pageMarginBottomController.dispose();
//     _pageMarginLeftController.dispose();
//     _pageMarginRightController.dispose();
//     _heading1SizeController.dispose();
//     _heading1SpaceBeforeController.dispose();
//     _heading1SpaceAfterController.dispose();
//     _heading2SizeController.dispose();
//     _heading2SpaceBeforeController.dispose();
//     _heading2SpaceAfterController.dispose();
//     _heading3SizeController.dispose();
//     _heading3SpaceBeforeController.dispose();
//     _heading3SpaceAfterController.dispose();
//     _heading4SizeController.dispose();
//     _heading4SpaceBeforeController.dispose();
//     _heading4SpaceAfterController.dispose();
//     _bodyFontSizeController.dispose();
//     _lineSpacingController.dispose();
//     _firstLineIndentController.dispose();
//     _bulletIndentController.dispose();
//     _paragraphSpaceBeforeController.dispose();
//     _paragraphSpaceAfterController.dispose();
//     // Table controllers
//     _tableFontSizeController.dispose();
//     _tableHeaderBgColorController.dispose();
//     _tableBandColorController.dispose();
//     _tableBorderColorController.dispose();
//     _tableBorderSizeController.dispose();
//     _tablePaddingTopController.dispose();
//     _tablePaddingBottomController.dispose();
//     _tablePaddingLeftController.dispose();
//     _tablePaddingRightController.dispose();
//     super.dispose();
//   }

//   // ── Reference Rules button ────────────────────────────────────────────────

//   Widget _buildReferenceRulesButton() {
//     if (_selectedTemplateId == null) return const SizedBox.shrink();

//     return Container(
//       width: double.infinity,
//       padding: const EdgeInsets.all(20),
//       decoration: BoxDecoration(
//         color: const Color(0xFF1A1F2E),
//         borderRadius: BorderRadius.circular(12),
//         border: Border.all(color: const Color(0xFF6366F1).withOpacity(0.35)),
//       ),
//       child: Column(
//         crossAxisAlignment: CrossAxisAlignment.start,
//         children: [
//           Row(children: [
//             Container(
//               padding: const EdgeInsets.all(7),
//               decoration: BoxDecoration(
//                 color: const Color(0xFF6366F1).withOpacity(0.15),
//                 borderRadius: BorderRadius.circular(7),
//               ),
//               child: const Icon(Icons.format_list_numbered,
//                   color: Color(0xFF6366F1), size: 18),
//             ),
//             const SizedBox(width: 12),
//             const Column(
//               crossAxisAlignment: CrossAxisAlignment.start,
//               children: [
//                 Text(
//                   'Reference Formatting Rules',
//                   style: TextStyle(
//                     fontSize: 14,
//                     fontWeight: FontWeight.w700,
//                     color: Colors.white,
//                   ),
//                 ),
//                 Text(
//                   'Set citation style, font, spacing and behaviour for the References section',
//                   style: TextStyle(fontSize: 11, color: Color(0xFF8B949E)),
//                 ),
//               ],
//             ),
//           ]),
//           const SizedBox(height: 16),
//           SizedBox(
//             width: double.infinity,
//             child: OutlinedButton.icon(
//               onPressed: () async {
//                 final result = await Navigator.push(
//                   context,
//                   MaterialPageRoute(
//                     builder: (_) => AdminReferenceSettingsScreen(
//                       templateId: _selectedTemplateId!,
//                       userId: _userId,
//                     ),
//                   ),
//                 );
//                 if (result != null && result is Map<String, dynamic>) {
//                   setState(() => _referenceRules = result);
//                 }
//               },
//               icon: const Icon(Icons.tune, size: 16, color: Color(0xFF6366F1)),
//               label: const Text(
//                 'Configure Reference Rules',
//                 style: TextStyle(
//                   fontSize: 13,
//                   fontWeight: FontWeight.w600,
//                   color: Color(0xFF6366F1),
//                 ),
//               ),
//               style: OutlinedButton.styleFrom(
//                 side: const BorderSide(color: Color(0xFF6366F1)),
//                 padding: const EdgeInsets.symmetric(vertical: 14),
//                 shape: RoundedRectangleBorder(
//                   borderRadius: BorderRadius.circular(8),
//                 ),
//               ),
//             ),
//           ),
//         ],
//       ),
//     );
//   }

//   @override
//   Widget build(BuildContext context) {
//     return SingleChildScrollView(
//       child: Container(
//         color: const Color(0xFF0F1419),
//         padding: const EdgeInsets.all(32),
//         child: Column(
//           crossAxisAlignment: CrossAxisAlignment.start,
//           children: [
//             TemplateHeader(selectedTemplate: _selectedTemplate),
//             const SizedBox(height: 32),
//             TemplateSelector(
//               selectedTemplateId: _selectedTemplateId,
//               onTemplateChanged: (value) {
//                 setState(() => _selectedTemplateId = value);
//                 if (value != null) {
//                   _loadTemplateDetails();
//                 } else {
//                   _clearFormFields();
//                   setState(() => _selectedTemplate = null);
//                 }
//               },
//             ),
//             const SizedBox(height: 32),
//             TemplateNameField(controller: _templateNameController),
//             const SizedBox(height: 24),
//             Row(
//               crossAxisAlignment: CrossAxisAlignment.start,
//               children: [
//                 Expanded(
//                   child: Column(
//                     children: [
//                       DocumentSettingsCard(
//                         pageSize: _pageSize,
//                         onPageSizeChanged: (value) =>
//                             setState(() => _pageSize = value),
//                         pageMarginTopController: _pageMarginTopController,
//                         pageMarginBottomController: _pageMarginBottomController,
//                         pageMarginLeftController: _pageMarginLeftController,
//                         pageMarginRightController: _pageMarginRightController,
//                         lineSpacingController: _lineSpacingController,
//                       ),
//                       const SizedBox(height: 24),
//                       ParagraphStyleCard(
//                         firstLineIndentController: _firstLineIndentController,
//                         spaceBeforeController: _paragraphSpaceBeforeController,
//                         spaceAfterController: _paragraphSpaceAfterController,
//                       ),
//                     ],
//                   ),
//                 ),
//                 const SizedBox(width: 24),
//                 Expanded(
//                   child: Column(
//                     children: [
//                       FontSettingsCard(
//                         primaryFontFamily: _primaryFontFamily,
//                         onFontFamilyChanged: (value) =>
//                             setState(() => _primaryFontFamily = value),
//                         bodyFontSizeController: _bodyFontSizeController,
//                         justifyText: _justifyText,
//                         onJustifyTextChanged: (value) =>
//                             setState(() => _justifyText = value),
//                       ),
//                       const SizedBox(height: 24),
//                       ListBulletStylesCard(
//                         bulletStyle: _bulletStyle,
//                         onBulletStyleChanged: (value) =>
//                             setState(() => _bulletStyle = value),
//                         numberingFormat: _numberingFormat,
//                         onNumberingFormatChanged: (value) =>
//                             setState(() => _numberingFormat = value),
//                         bulletIndentController: _bulletIndentController,
//                       ),
//                     ],
//                   ),
//                 ),
//               ],
//             ),
//             const SizedBox(height: 32),
//             HeadingStylesCard(
//               heading1SizeController: _heading1SizeController,
//               heading1SpaceBeforeController: _heading1SpaceBeforeController,
//               heading1SpaceAfterController: _heading1SpaceAfterController,
//               heading1Weight: _heading1Weight,
//               heading1Alignment: _heading1Alignment,
//               heading1Transform: _heading1Transform,
//               onHeading1WeightChanged: (v) =>
//                   setState(() => _heading1Weight = v),
//               onHeading1AlignmentChanged: (v) =>
//                   setState(() => _heading1Alignment = v),
//               onHeading1TransformChanged: (v) =>
//                   setState(() => _heading1Transform = v),
//               heading2SizeController: _heading2SizeController,
//               heading2SpaceBeforeController: _heading2SpaceBeforeController,
//               heading2SpaceAfterController: _heading2SpaceAfterController,
//               heading2Weight: _heading2Weight,
//               heading2Alignment: _heading2Alignment,
//               heading2Transform: _heading2Transform,
//               onHeading2WeightChanged: (v) =>
//                   setState(() => _heading2Weight = v),
//               onHeading2AlignmentChanged: (v) =>
//                   setState(() => _heading2Alignment = v),
//               onHeading2TransformChanged: (v) =>
//                   setState(() => _heading2Transform = v),
//               heading3SizeController: _heading3SizeController,
//               heading3SpaceBeforeController: _heading3SpaceBeforeController,
//               heading3SpaceAfterController: _heading3SpaceAfterController,
//               heading3Weight: _heading3Weight,
//               heading3Alignment: _heading3Alignment,
//               heading3Transform: _heading3Transform,
//               onHeading3WeightChanged: (v) =>
//                   setState(() => _heading3Weight = v),
//               onHeading3AlignmentChanged: (v) =>
//                   setState(() => _heading3Alignment = v),
//               onHeading3TransformChanged: (v) =>
//                   setState(() => _heading3Transform = v),
//               heading4SizeController: _heading4SizeController,
//               heading4SpaceBeforeController: _heading4SpaceBeforeController,
//               heading4SpaceAfterController: _heading4SpaceAfterController,
//               heading4Weight: _heading4Weight,
//               heading4Alignment: _heading4Alignment,
//               heading4Transform: _heading4Transform,
//               onHeading4WeightChanged: (v) =>
//                   setState(() => _heading4Weight = v),
//               onHeading4AlignmentChanged: (v) =>
//                   setState(() => _heading4Alignment = v),
//               onHeading4TransformChanged: (v) =>
//                   setState(() => _heading4Transform = v),
//             ),
//             const SizedBox(height: 32),

//             // ── Table Styles Card (NEW) ────────────────────────────────────
//             TableStylesCard(
//               fontSizeController:       _tableFontSizeController,
//               fontName:                 _tableFontName,
//               onFontNameChanged:        (v) => setState(() => _tableFontName = v),
//               headerBold:               _tableHeaderBold,
//               onHeaderBoldChanged:      (v) => setState(() => _tableHeaderBold = v),
//               headerAlign:              _tableHeaderAlign,
//               onHeaderAlignChanged:     (v) => setState(() => _tableHeaderAlign = v),
//               headerBgColorController:  _tableHeaderBgColorController,
//               bodyAlign:                _tableBodyAlign,
//               onBodyAlignChanged:       (v) => setState(() => _tableBodyAlign = v),
//               bandedRows:               _tableBandedRows,
//               onBandedRowsChanged:      (v) => setState(() => _tableBandedRows = v),
//               bandColorController:      _tableBandColorController,
//               borders:                  _tableBorders,
//               onBordersChanged:         (v) => setState(() => _tableBorders = v),
//               borderColorController:    _tableBorderColorController,
//               borderSizeController:     _tableBorderSizeController,
//               paddingTopController:     _tablePaddingTopController,
//               paddingBottomController:  _tablePaddingBottomController,
//               paddingLeftController:    _tablePaddingLeftController,
//               paddingRightController:   _tablePaddingRightController,
//               centerTable:              _tableCenterTable,
//               onCenterTableChanged:     (v) => setState(() => _tableCenterTable = v),
//               autoFit:                  _tableAutoFit,
//               onAutoFitChanged:         (v) => setState(() => _tableAutoFit = v),
//               repeatHeader:             _tableRepeatHeader,
//               onRepeatHeaderChanged:    (v) => setState(() => _tableRepeatHeader = v),
//             ),

//             const SizedBox(height: 32),
//             RequiredSectionsCard(
//               sections: _requiredSections,
//               onSectionsChanged: (updated) =>
//                   setState(() => _requiredSections = updated),
//             ),
//             const SizedBox(height: 32),

//             _buildReferenceRulesButton(),
//             if (_selectedTemplateId != null) const SizedBox(height: 32),

//             ActionButtons(
//               selectedTemplateId: _selectedTemplateId,
//               isSaving: _isSaving,
//               canSubmit: _templateNameController.text.trim().isNotEmpty,
//               onCreateTemplate: _createTemplate,
//               onSaveTemplate: _saveTemplate,
//               onClearSelection: () {
//                 setState(() {
//                   _selectedTemplateId = null;
//                   _selectedTemplate = null;
//                 });
//                 _clearFormFields();
//               },
//             ),
//           ],
//         ),
//       ),
//     );
//   }
// }

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';
import '../providers/auth_provider.dart';
import '../providers/template_provider.dart';
import '../widgets/template_config/required_sections_card.dart';
// Import widget files
import '../widgets/template_config/template_header.dart';
import '../widgets/template_config/template_selector.dart';
import '../widgets/template_config/template_name_field.dart';
import '../widgets/template_config/document_settings_card.dart';
import '../widgets/template_config/font_settings_card.dart';
import '../widgets/template_config/paragraph_style_card.dart';
import '../widgets/template_config/list_bullet_styles_card.dart';
import '../widgets/template_config/heading_styles_card.dart';
import '../widgets/template_config/table_styles_card.dart';    // ← NEW
import '../widgets/template_config/action_buttons.dart';
import '../widgets/template_config/upload_template_document_button.dart';
import '../utils/template_mapping_utils.dart';
import '../screens/admin_reference_settings_screen.dart';
import '../widgets/admin/admin_ui.dart';

class TemplateConfigurationScreen extends StatefulWidget {
  final int? departmentId;
  final bool standalone;

  const TemplateConfigurationScreen({
    super.key,
    this.departmentId,
    this.standalone = false,
  });

  @override
  State<TemplateConfigurationScreen> createState() =>
      _TemplateConfigurationScreenState();
}

class _TemplateConfigurationScreenState
    extends State<TemplateConfigurationScreen> {
  Map<String, dynamic> _referenceRules = {};
  late String baseUrl;
  int? _selectedTemplateId;
  Map<String, dynamic>? _selectedTemplate;
  bool _isLoading = false;
  List<RequiredSectionItem> _requiredSections = [];
  bool _isSaving = false;

  // ── Existing form controllers ─────────────────────────────────────────────
  late TextEditingController _templateNameController;
  late TextEditingController _pageMarginTopController;
  late TextEditingController _pageMarginBottomController;
  late TextEditingController _pageMarginLeftController;
  late TextEditingController _pageMarginRightController;
  late TextEditingController _heading1SizeController;
  late TextEditingController _heading1SpaceBeforeController;
  late TextEditingController _heading1SpaceAfterController;
  late TextEditingController _heading2SizeController;
  late TextEditingController _heading2SpaceBeforeController;
  late TextEditingController _heading2SpaceAfterController;
  late TextEditingController _heading3SizeController;
  late TextEditingController _heading3SpaceBeforeController;
  late TextEditingController _heading3SpaceAfterController;
  late TextEditingController _heading4SizeController;
  late TextEditingController _heading4SpaceBeforeController;
  late TextEditingController _heading4SpaceAfterController;
  late TextEditingController _bodyFontSizeController;
  late TextEditingController _lineSpacingController;
  late TextEditingController _firstLineIndentController;
  late TextEditingController _bulletIndentController;
  late TextEditingController _paragraphSpaceBeforeController;
  late TextEditingController _paragraphSpaceAfterController;

  // ── NEW: Table style controllers & state ──────────────────────────────────
  late TextEditingController _tableFontSizeController;
  late TextEditingController _tableHeaderBgColorController;
  late TextEditingController _tableBandColorController;
  late TextEditingController _tableBorderColorController;
  late TextEditingController _tableBorderSizeController;
  late TextEditingController _tablePaddingTopController;
  late TextEditingController _tablePaddingBottomController;
  late TextEditingController _tablePaddingLeftController;
  late TextEditingController _tablePaddingRightController;

  String _tableFontName   = 'Times New Roman';
  String _tableHeaderAlign = 'Center';
  String _tableBodyAlign   = 'Left';
  bool   _tableHeaderBold  = true;
  bool   _tableBandedRows  = true;
  bool   _tableBorders     = true;
  bool   _tableCenterTable = true;
  bool   _tableAutoFit     = true;
  bool   _tableRepeatHeader = true;
  // ─────────────────────────────────────────────────────────────────────────

  String _pageSize = 'A4';
  String _spacingUnit = 'mm';
  String _primaryFontFamily = 'Times New Roman';
  String _secondaryFontFamily = 'Same as Primary';
  String _bulletStyle = 'Filled Circle';
  String _numberingFormat = '1, 2, 3 (Arabic)';
  String _headingNumberingStyle = 'None';

  String _heading1Weight = 'Bold';
  String _heading2Weight = 'Bold';
  String _heading3Weight = 'Bold';
  String _heading4Weight = 'Medium';
  bool _heading1Italic = false;
  bool _heading2Italic = false;
  bool _heading3Italic = false;
  bool _heading4Italic = false;

  String _heading1Alignment = 'Center';
  String _heading2Alignment = 'Left';
  String _heading3Alignment = 'Left';
  String _heading4Alignment = 'Left';

  String _heading1Transform = 'UPPERCASE';
  String _heading2Transform = 'None';
  String _heading3Transform = 'Normal';
  String _heading4Transform = 'Normal';

  bool _enableLigatures = true;
  bool _justifyText = true;

  int get _userId => context.read<AuthProvider>().userId ?? 0;

  @override
  void initState() {
    super.initState();
    baseUrl = ApiConfig.getBaseUrl();
    _initializeControllers();

    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadTemplates();
    });
  }

  void _initializeControllers() {
    _templateNameController = TextEditingController();
    _pageMarginTopController = TextEditingController();
    _pageMarginBottomController = TextEditingController();
    _pageMarginLeftController = TextEditingController();
    _pageMarginRightController = TextEditingController();
    _heading1SizeController = TextEditingController();
    _heading1SpaceBeforeController = TextEditingController();
    _heading1SpaceAfterController = TextEditingController();
    _heading2SizeController = TextEditingController();
    _heading2SpaceBeforeController = TextEditingController();
    _heading2SpaceAfterController = TextEditingController();
    _heading3SizeController = TextEditingController();
    _heading3SpaceBeforeController = TextEditingController();
    _heading3SpaceAfterController = TextEditingController();
    _heading4SizeController = TextEditingController();
    _heading4SpaceBeforeController = TextEditingController();
    _heading4SpaceAfterController = TextEditingController();
    _bodyFontSizeController = TextEditingController();
    _lineSpacingController = TextEditingController();
    _firstLineIndentController = TextEditingController();
    _bulletIndentController = TextEditingController();
    _paragraphSpaceBeforeController = TextEditingController();
    _paragraphSpaceAfterController = TextEditingController();

    // Table style controllers
    _tableFontSizeController      = TextEditingController(text: '12');
    _tableHeaderBgColorController = TextEditingController(text: 'D6E4F0');
    _tableBandColorController     = TextEditingController(text: 'F2F8FC');
    _tableBorderColorController   = TextEditingController(text: '000000');
    _tableBorderSizeController    = TextEditingController(text: '4');
    _tablePaddingTopController    = TextEditingController(text: '60');
    _tablePaddingBottomController = TextEditingController(text: '60');
    _tablePaddingLeftController   = TextEditingController(text: '108');
    _tablePaddingRightController  = TextEditingController(text: '108');

    _templateNameController.addListener(() => setState(() {}));
  }

  Future<void> _loadTemplates() async {
    if (!mounted) return;

    setState(() => _isLoading = true);

    try {
      final templateProvider = context.read<TemplateProvider>();
      await templateProvider.fetchUniversityTemplates(1);

      if (!mounted) return;

      setState(() {
        _selectedTemplateId = null;
        _selectedTemplate = null;
        _isLoading = false;
      });

      _clearFormFields();
    } catch (e) {
      if (!mounted) return;
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Error loading templates: $e')));
    }
  }

  void _clearFormFields() {
    _templateNameController.clear();
    _pageMarginTopController.clear();
    _pageMarginBottomController.clear();
    _pageMarginLeftController.clear();
    _pageMarginRightController.clear();
    _heading1SizeController.clear();
    _heading1SpaceBeforeController.clear();
    _heading1SpaceAfterController.clear();
    _heading2SizeController.clear();
    _heading2SpaceBeforeController.clear();
    _heading2SpaceAfterController.clear();
    _heading3SizeController.clear();
    _heading3SpaceBeforeController.clear();
    _heading3SpaceAfterController.clear();
    _heading4SizeController.clear();
    _heading4SpaceBeforeController.clear();
    _heading4SpaceAfterController.clear();
    _bodyFontSizeController.clear();
    _lineSpacingController.clear();
    _firstLineIndentController.clear();
    _bulletIndentController.clear();
    _paragraphSpaceBeforeController.clear();
    _paragraphSpaceAfterController.clear();

    // Reset table style to defaults
    _tableFontSizeController.text      = '12';
    _tableHeaderBgColorController.text = 'D6E4F0';
    _tableBandColorController.text     = 'F2F8FC';
    _tableBorderColorController.text   = '000000';
    _tableBorderSizeController.text    = '4';
    _tablePaddingTopController.text    = '60';
    _tablePaddingBottomController.text = '60';
    _tablePaddingLeftController.text   = '108';
    _tablePaddingRightController.text  = '108';

    setState(() {
      _pageSize = 'A4';
      _spacingUnit = 'mm';
      _primaryFontFamily = 'Times New Roman';
      _secondaryFontFamily = 'Same as Primary';
      _bulletStyle = 'Filled Circle';
      _numberingFormat = '1, 2, 3 (Arabic)';
      _headingNumberingStyle = 'None';
      _heading1Weight = 'Bold';
      _heading2Weight = 'Bold';
      _heading3Weight = 'Bold';
      _heading4Weight = 'Medium';
      _heading1Italic = false;
      _heading2Italic = false;
      _heading3Italic = false;
      _heading4Italic = false;
      _heading1Alignment = 'Center';
      _heading2Alignment = 'Left';
      _heading3Alignment = 'Left';
      _heading4Alignment = 'Left';
      _heading1Transform = 'UPPERCASE';
      _heading2Transform = 'None';
      _heading3Transform = 'Normal';
      _heading4Transform = 'Normal';
      _enableLigatures = true;
      _justifyText = true;
      _requiredSections = [];

      // Table style resets
      _tableFontName    = 'Times New Roman';
      _tableHeaderAlign = 'Center';
      _tableBodyAlign   = 'Left';
      _tableHeaderBold  = true;
      _tableBandedRows  = true;
      _tableBorders     = true;
      _tableCenterTable = true;
      _tableAutoFit     = true;
      _tableRepeatHeader = true;
    });
  }

  void _fillDefaultValues() {
    _pageMarginTopController.text = '25';
    _pageMarginBottomController.text = '25';
    _pageMarginLeftController.text = '30';
    _pageMarginRightController.text = '20';
    _heading1SizeController.text = '18';
    _heading1SpaceBeforeController.text = '12';
    _heading1SpaceAfterController.text = '6';
    _heading2SizeController.text = '16';
    _heading2SpaceBeforeController.text = '10';
    _heading2SpaceAfterController.text = '5';
    _heading3SizeController.text = '14';
    _heading3SpaceBeforeController.text = '8';
    _heading3SpaceAfterController.text = '4';
    _heading4SizeController.text = '12';
    _heading4SpaceBeforeController.text = '6';
    _heading4SpaceAfterController.text = '3';
    _bodyFontSizeController.text = '12';
    _lineSpacingController.text = '2.0';
    _firstLineIndentController.text = '0.5';
    _bulletIndentController.text = '0.5';
    _paragraphSpaceBeforeController.text = '0';
    _paragraphSpaceAfterController.text = '0';
  }

  Future<void> _loadTemplateDetails() async {
    if (_selectedTemplateId == null) return;

    try {
      setState(() => _isLoading = true);

      final response = await http.get(
        Uri.parse('$baseUrl/templates/$_selectedTemplateId'),
      );

      if (response.statusCode == 200) {
        final template = jsonDecode(response.body);

        final rules = template['formatting_rules'] ?? {};
        final rawSections =
            (template['required_sections'] as List<dynamic>?) ?? [];
        _requiredSections = rawSections.map((s) {
          if (s is Map<String, dynamic>) return RequiredSectionItem.fromJson(s);
          return RequiredSectionItem(name: s.toString());
        }).toList();

        // Load table style from template if present
        final tableStyle =
            rules['table_style'] as Map<String, dynamic>? ?? {};
        
        // DEBUG: Log the table style loaded from API
        print('[DEBUG] Table style loaded from API: $tableStyle');

        setState(() {
          _selectedTemplate = template;

          _templateNameController.text = template['name'] ?? '';

          _pageMarginTopController.text =
              (rules['margin_top'] ?? 25).toString();
          _pageMarginBottomController.text =
              (rules['margin_bottom'] ?? 25).toString();
          _pageMarginLeftController.text =
              (rules['margin_left'] ?? 30).toString();
          _pageMarginRightController.text =
              (rules['margin_right'] ?? 20).toString();

          _heading1SizeController.text =
              (rules['heading1_size'] ?? 18).toString();
          _heading1SpaceBeforeController.text =
              (rules['heading1_space_before'] ?? 12.0).toString();
          _heading1SpaceAfterController.text =
              (rules['heading1_space_after'] ?? 6.0).toString();
          _heading1Weight =
              (rules['heading1_bold'] == true) ? 'Bold' : 'Normal';
          _heading1Italic = rules['heading1_italic'] == true;

          _heading2SizeController.text =
              (rules['heading2_size'] ?? 16).toString();
          _heading2SpaceBeforeController.text =
              (rules['heading2_space_before'] ?? 10.0).toString();
          _heading2SpaceAfterController.text =
              (rules['heading2_space_after'] ?? 5.0).toString();
          _heading2Weight =
              (rules['heading2_bold'] == true) ? 'Bold' : 'Normal';
          _heading2Italic = rules['heading2_italic'] == true;

          _heading3SizeController.text =
              (rules['heading3_size'] ?? 14).toString();
          _heading3SpaceBeforeController.text =
              (rules['heading3_space_before'] ?? 8.0).toString();
          _heading3SpaceAfterController.text =
              (rules['heading3_space_after'] ?? 4.0).toString();
          _heading3Weight =
              (rules['heading3_bold'] == true) ? 'Bold' : 'Normal';
          _heading3Italic = rules['heading3_italic'] == true;

          _heading4SizeController.text =
              (rules['heading4_size'] ?? 12).toString();
          _heading4SpaceBeforeController.text =
              (rules['heading4_space_before'] ?? 6.0).toString();
          _heading4SpaceAfterController.text =
              (rules['heading4_space_after'] ?? 3.0).toString();
          _heading4Weight =
              (rules['heading4_bold'] == true) ? 'Bold' : 'Normal';
          _heading4Italic = rules['heading4_italic'] == true;

          _bodyFontSizeController.text =
              (rules['body_size'] ?? 12).toString();
          _lineSpacingController.text =
              (rules['body_line_spacing'] ?? 2.0).toString();
          _firstLineIndentController.text =
              (rules['first_line_indent'] ?? 0.5).toString();
          _bulletIndentController.text =
              (rules['bullet_indent'] ?? 0.5).toString();

          _paragraphSpaceBeforeController.text =
              (rules['body_space_before'] ?? 0.0).toString();
          _paragraphSpaceAfterController.text =
              (rules['body_space_after'] ?? 0.0).toString();

          _primaryFontFamily = rules['heading1_font'] ?? 'Times New Roman';
          _pageSize = rules['page_size'] ?? 'A4';
          _spacingUnit = rules['spacing_unit'] ?? 'mm';

          _bulletStyle = TemplateMappingUtils.mapBulletTypeToDisplay(
              rules['bullet_type'] ?? 'bullet');
          _numberingFormat = TemplateMappingUtils.mapNumberedStyleToDisplay(
              rules['numbered_style'] ?? '1,2,3');
          _headingNumberingStyle =
              (rules['heading_numbering_style'] ?? 'none') == 'decimal'
                  ? '1, 1.1, 1.1.1'
                  : (rules['heading_numbering_style'] ?? 'none') == 'roman'
                      ? 'I, A, 1'
                      : (rules['heading_numbering_style'] ?? 'none') == 'alpha'
                          ? 'A, 1, a'
                          : 'None';

          _justifyText = rules['body_justified'] ?? true;

          // ── Load table style ──────────────────────────────────────────────
          // CRITICAL FIX: Store the raw values first for state, then populate controllers
          final loadedTableFontName = tableStyle['font_name'] ?? 'Times New Roman';
          final loadedHeaderAlign = _capitalise(tableStyle['header_align'] ?? 'center');
          final loadedBodyAlign = _capitalise(tableStyle['body_align'] ?? 'left');
          
          _tableFontName = loadedTableFontName;
          _tableHeaderAlign = loadedHeaderAlign;
          _tableBodyAlign = loadedBodyAlign;
          _tableHeaderBold = tableStyle['header_bold'] ?? true;
          _tableBandedRows = tableStyle['banded_rows'] ?? true;
          _tableBorders = tableStyle['borders'] ?? true;
          _tableCenterTable = tableStyle['center_table'] ?? true;
          _tableAutoFit = tableStyle['auto_fit'] ?? true;
          _tableRepeatHeader = tableStyle['repeat_header'] ?? true;

          // Populate text controllers
          _tableFontSizeController.text =
              (tableStyle['font_size'] ?? 12).toString();
          _tableHeaderBgColorController.text =
              (tableStyle['header_bg'] ?? 'D6E4F0').toString().replaceAll('#', '');
          _tableBandColorController.text =
              (tableStyle['band_color'] ?? 'F2F8FC').toString().replaceAll('#', '');
          _tableBorderColorController.text =
              (tableStyle['border_color'] ?? '000000').toString().replaceAll('#', '');
          _tableBorderSizeController.text =
              (tableStyle['border_size'] ?? 4).toString();
          _tablePaddingTopController.text =
              (tableStyle['cell_padding_top'] ?? 60).toString();
          _tablePaddingBottomController.text =
              (tableStyle['cell_padding_bot'] ?? 60).toString();
          _tablePaddingLeftController.text =
              (tableStyle['cell_padding_lft'] ?? 108).toString();
          _tablePaddingRightController.text =
              (tableStyle['cell_padding_rgt'] ?? 108).toString();

          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() => _isLoading = false);
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Error loading template: $e')));
      }
    }
  }

  // ── Capitalise first letter for dropdown values loaded from DB ────────────
  String _capitalise(String s) =>
      s.isEmpty ? s : s[0].toUpperCase() + s.substring(1).toLowerCase();

  /// Populate the existing form fields from an extracted draft.
  /// Does not save — admin still uses Create Template / Save Changes as usual.
  void _applyExtractedDraft(Map<String, dynamic> draft) {
    final rules = (draft['formatting_rules'] as Map?)?.cast<String, dynamic>() ??
        <String, dynamic>{};
    final rawSections = (draft['required_sections'] as List<dynamic>?) ?? [];
    final sections = rawSections.map((s) {
      if (s is Map<String, dynamic>) return RequiredSectionItem.fromJson(s);
      if (s is Map) {
        return RequiredSectionItem.fromJson(Map<String, dynamic>.from(s));
      }
      return RequiredSectionItem(name: s.toString());
    }).toList();

    final tableStyle =
        (rules['table_style'] as Map?)?.cast<String, dynamic>() ??
            <String, dynamic>{};

    setState(() {
      // Stay on create path (not edit-selected-template)
      _selectedTemplateId = null;
      _selectedTemplate = null;

      _templateNameController.text = (draft['name'] ?? '').toString();
      _requiredSections = sections;

      _pageMarginTopController.text = (rules['margin_top'] ?? 25).toString();
      _pageMarginBottomController.text =
          (rules['margin_bottom'] ?? 25).toString();
      _pageMarginLeftController.text = (rules['margin_left'] ?? 30).toString();
      _pageMarginRightController.text =
          (rules['margin_right'] ?? 20).toString();

      _heading1SizeController.text = (rules['heading1_size'] ?? 18).toString();
      _heading1SpaceBeforeController.text =
          (rules['heading1_space_before'] ?? 12.0).toString();
      _heading1SpaceAfterController.text =
          (rules['heading1_space_after'] ?? 6.0).toString();
      _heading1Weight = (rules['heading1_bold'] == true) ? 'Bold' : 'Normal';
      _heading1Italic = rules['heading1_italic'] == true;

      _heading2SizeController.text = (rules['heading2_size'] ?? 16).toString();
      _heading2SpaceBeforeController.text =
          (rules['heading2_space_before'] ?? 10.0).toString();
      _heading2SpaceAfterController.text =
          (rules['heading2_space_after'] ?? 5.0).toString();
      _heading2Weight = (rules['heading2_bold'] == true) ? 'Bold' : 'Normal';
      _heading2Italic = rules['heading2_italic'] == true;

      _heading3SizeController.text = (rules['heading3_size'] ?? 14).toString();
      _heading3SpaceBeforeController.text =
          (rules['heading3_space_before'] ?? 8.0).toString();
      _heading3SpaceAfterController.text =
          (rules['heading3_space_after'] ?? 4.0).toString();
      _heading3Weight = (rules['heading3_bold'] == true) ? 'Bold' : 'Normal';
      _heading3Italic = rules['heading3_italic'] == true;

      _heading4SizeController.text = (rules['heading4_size'] ?? 12).toString();
      _heading4SpaceBeforeController.text =
          (rules['heading4_space_before'] ?? 6.0).toString();
      _heading4SpaceAfterController.text =
          (rules['heading4_space_after'] ?? 3.0).toString();
      _heading4Weight = (rules['heading4_bold'] == true) ? 'Bold' : 'Normal';
      _heading4Italic = rules['heading4_italic'] == true;

      _bodyFontSizeController.text = (rules['body_size'] ?? 12).toString();
      _lineSpacingController.text =
          (rules['body_line_spacing'] ?? 2.0).toString();
      _firstLineIndentController.text =
          (rules['first_line_indent'] ?? 0.5).toString();
      _bulletIndentController.text =
          (rules['bullet_indent'] ?? 0.5).toString();
      _paragraphSpaceBeforeController.text =
          (rules['body_space_before'] ?? 0.0).toString();
      _paragraphSpaceAfterController.text =
          (rules['body_space_after'] ?? 0.0).toString();

      _primaryFontFamily = (rules['heading1_font'] ??
              rules['body_font'] ??
              'Times New Roman')
          .toString();
      _pageSize = (rules['page_size'] ?? 'A4').toString();
      _spacingUnit = (rules['spacing_unit'] ?? 'mm').toString();

      _bulletStyle = TemplateMappingUtils.mapBulletTypeToDisplay(
          (rules['bullet_type'] ?? 'bullet').toString());
      _numberingFormat = TemplateMappingUtils.mapNumberedStyleToDisplay(
          (rules['numbered_style'] ?? '1,2,3').toString());
      final hn = (rules['heading_numbering_style'] ?? 'none').toString();
      _headingNumberingStyle = hn == 'decimal'
          ? '1, 1.1, 1.1.1'
          : hn == 'roman'
              ? 'I, A, 1'
              : hn == 'alpha'
                  ? 'A, 1, a'
                  : 'None';

      _justifyText = rules['body_justified'] ?? true;

      if (tableStyle.isNotEmpty) {
        _tableFontName = (tableStyle['font_name'] ?? 'Times New Roman').toString();
        _tableHeaderAlign =
            _capitalise((tableStyle['header_align'] ?? 'center').toString());
        _tableBodyAlign =
            _capitalise((tableStyle['body_align'] ?? 'left').toString());
        _tableHeaderBold = tableStyle['header_bold'] ?? true;
        _tableBandedRows = tableStyle['banded_rows'] ?? true;
        _tableBorders = tableStyle['borders'] ?? true;
        _tableCenterTable = tableStyle['center_table'] ?? true;
        _tableAutoFit = tableStyle['auto_fit'] ?? true;
        _tableRepeatHeader = tableStyle['repeat_header'] ?? true;
        _tableFontSizeController.text =
            (tableStyle['font_size'] ?? 12).toString();
        _tableHeaderBgColorController.text =
            (tableStyle['header_bg'] ?? 'D6E4F0').toString().replaceAll('#', '');
        _tableBandColorController.text =
            (tableStyle['band_color'] ?? 'F2F8FC').toString().replaceAll('#', '');
        _tableBorderColorController.text =
            (tableStyle['border_color'] ?? '000000')
                .toString()
                .replaceAll('#', '');
        _tableBorderSizeController.text =
            (tableStyle['border_size'] ?? 4).toString();
        _tablePaddingTopController.text =
            (tableStyle['cell_padding_top'] ?? 60).toString();
        _tablePaddingBottomController.text =
            (tableStyle['cell_padding_bot'] ?? 60).toString();
        _tablePaddingLeftController.text =
            (tableStyle['cell_padding_lft'] ?? 108).toString();
        _tablePaddingRightController.text =
            (tableStyle['cell_padding_rgt'] ?? 108).toString();
      }
    });
  }

  Future<void> _createTemplate() async {
    if (_templateNameController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Please enter a template name')));
      return;
    }

    if (_pageMarginTopController.text.isEmpty ||
        _pageMarginBottomController.text.isEmpty ||
        _pageMarginLeftController.text.isEmpty ||
        _pageMarginRightController.text.isEmpty ||
        _bodyFontSizeController.text.isEmpty ||
        _lineSpacingController.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Please fill in required margin and font fields')));
      return;
    }

    setState(() => _isSaving = true);

    try {
      final authProvider = context.read<AuthProvider>();
      final lineSpacing = double.parse(
          _lineSpacingController.text.isEmpty
              ? '2.0'
              : _lineSpacingController.text);

      final templateData = _buildTemplateData(lineSpacing);

      final departmentQuery = widget.departmentId != null
          ? '&department_id=${widget.departmentId}'
          : '';
      final response = await http.post(
        Uri.parse(
            '$baseUrl/admin/templates?created_by=${authProvider.userId}&user_id=${authProvider.userId}&university_id=1$departmentQuery'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(templateData),
      );

      if (response.statusCode == 200 || response.statusCode == 201) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
              content: Text('Template created successfully!'),
              backgroundColor: Colors.green));
          if (widget.standalone) {
            Navigator.of(context).pop(true);
            return;
          }
        }
        await _loadTemplates();
        _clearFormFields();
        setState(() => _selectedTemplateId = null);
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
              content: Text('Error: ${response.body}'),
              backgroundColor: Colors.red));
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error creating template: $e')));
      }
    } finally {
      setState(() => _isSaving = false);
    }
  }

  Future<void> _saveTemplate() async {
    if (_selectedTemplateId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No template selected to save')));
      return;
    }

    setState(() => _isSaving = true);

    try {
      final authProvider = context.read<AuthProvider>();
      final lineSpacing = double.parse(
          _lineSpacingController.text.isEmpty
              ? '2.0'
              : _lineSpacingController.text);

      final templateData = _buildTemplateData(lineSpacing);
      
      // DEBUG: Log the table style data being saved
      print('[DEBUG] Table style being saved: ${templateData['formatting_rules']['table_style']}');

      final response = await http.put(
        Uri.parse(
            '$baseUrl/admin/templates/$_selectedTemplateId?user_id=${authProvider.userId}'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(templateData),
      );

      if (response.statusCode == 200) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
              content: Text('Template saved successfully!'),
              backgroundColor: Colors.green));
        }
        // CRITICAL FIX: Reload the template immediately after saving to verify changes
        await _loadTemplateDetails();
        final templateProvider = context.read<TemplateProvider>();
        await templateProvider.fetchUniversityTemplates(1);
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
              content: Text('Error: ${response.body}'),
              backgroundColor: Colors.red));
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Error saving template: $e')));
      }
    } finally {
      setState(() => _isSaving = false);
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  double _safeDouble(String value, double def) =>
      value.isEmpty ? def : (double.tryParse(value) ?? def);

  int _safeInt(String value, int def) =>
      value.isEmpty ? def : (int.tryParse(value) ?? def);

  /// Build the table_style sub-object from current UI state.
  Map<String, dynamic> _buildTableStyleData() {
    return {
      'font_name':        _tableFontName,
      'font_size':        _safeInt(_tableFontSizeController.text, 12),
      'header_bold':      _tableHeaderBold,
      'header_bg':        _tableHeaderBgColorController.text.replaceAll('#', ''),
      'header_align':     _tableHeaderAlign.toLowerCase(),
      'body_align':       _tableBodyAlign.toLowerCase(),
      'banded_rows':      _tableBandedRows,
      'band_color':       _tableBandColorController.text.replaceAll('#', ''),
      'borders':          _tableBorders,
      'border_color':     _tableBorderColorController.text.replaceAll('#', ''),
      'border_size':      _safeInt(_tableBorderSizeController.text, 4),
      'cell_padding_top': _safeInt(_tablePaddingTopController.text, 60),
      'cell_padding_bot': _safeInt(_tablePaddingBottomController.text, 60),
      'cell_padding_lft': _safeInt(_tablePaddingLeftController.text, 108),
      'cell_padding_rgt': _safeInt(_tablePaddingRightController.text, 108),
      'center_table':     _tableCenterTable,
      'auto_fit':         _tableAutoFit,
      'repeat_header':    _tableRepeatHeader,
    };
  }

  Map<String, dynamic> _buildTemplateData(double lineSpacing) {
    print('Selected template: $_selectedTemplate');

    // Preserve existing reference_rules
    Map<String, dynamic> existingRefRules = {};
    if (_selectedTemplate != null) {
      if (_selectedTemplate!.containsKey('formatting_rules')) {
        final fr = _selectedTemplate!['formatting_rules'] as Map<String, dynamic>?;
        if (fr != null && fr.containsKey('reference_rules')) {
          existingRefRules = fr['reference_rules'] as Map<String, dynamic>? ?? {};
        }
      }
      if (_selectedTemplate!.containsKey('reference_rules')) {
        existingRefRules =
            _selectedTemplate!['reference_rules'] as Map<String, dynamic>? ?? {};
      }
    }

    final formattingRules = <String, dynamic>{
      // Heading 1
      'heading1_font': _primaryFontFamily,
      'heading1_size': _safeInt(_heading1SizeController.text, 18),
      'heading1_bold': _heading1Weight.contains('Bold'),
      'heading1_italic': _heading1Italic,
      'heading1_underline': false,
      'heading1_color': '#000000',
      'heading1_line_spacing': 1.5,
      'heading1_space_before':
          _safeDouble(_heading1SpaceBeforeController.text, 12.0),
      'heading1_space_after':
          _safeDouble(_heading1SpaceAfterController.text, 6.0),
      // Heading 2
      'heading2_font': _primaryFontFamily,
      'heading2_size': _safeInt(_heading2SizeController.text, 16),
      'heading2_bold': _heading2Weight.contains('Bold'),
      'heading2_italic': _heading2Italic,
      'heading2_underline': false,
      'heading2_color': '#000000',
      'heading2_line_spacing': 1.5,
      'heading2_space_before':
          _safeDouble(_heading2SpaceBeforeController.text, 10.0),
      'heading2_space_after':
          _safeDouble(_heading2SpaceAfterController.text, 5.0),
      // Heading 3
      'heading3_font': _primaryFontFamily,
      'heading3_size': _safeInt(_heading3SizeController.text, 14),
      'heading3_bold': _heading3Weight.contains('Bold'),
      'heading3_italic': _heading3Italic,
      'heading3_underline': false,
      'heading3_color': '#000000',
      'heading3_line_spacing': 1.5,
      'heading3_space_before':
          _safeDouble(_heading3SpaceBeforeController.text, 8.0),
      'heading3_space_after':
          _safeDouble(_heading3SpaceAfterController.text, 4.0),
      // Heading 4
      'heading4_font': _primaryFontFamily,
      'heading4_size': _safeInt(_heading4SizeController.text, 12),
      'heading4_bold': _heading4Weight.contains('Bold'),
      'heading4_italic': _heading4Italic,
      'heading4_underline': false,
      'heading4_color': '#000000',
      'heading4_line_spacing': 1.5,
      'heading4_space_before':
          _safeDouble(_heading4SpaceBeforeController.text, 6.0),
      'heading4_space_after':
          _safeDouble(_heading4SpaceAfterController.text, 3.0),
      // Body
      'body_font': _primaryFontFamily,
      'body_size': _safeInt(_bodyFontSizeController.text, 12),
      'body_color': '#000000',
      'body_line_spacing': lineSpacing,
      'body_space_before':
          _safeDouble(_paragraphSpaceBeforeController.text, 0.0),
      'body_space_after':
          _safeDouble(_paragraphSpaceAfterController.text, 0.0),
      'body_justified': _justifyText,
      // Bullets
      'bullet_font': _primaryFontFamily,
      'bullet_size': _safeInt(_bodyFontSizeController.text, 12),
      'bullet_color': '#000000',
      'bullet_line_spacing': lineSpacing,
      'bullet_indent': _safeDouble(_bulletIndentController.text, 0.5),
      'bullet_space_before': 0.0,
      'bullet_space_after': 0.0,
      'bullet_type':
          TemplateMappingUtils.mapBulletTypeToDb(_bulletStyle),
      // Numbered
      'numbered_font': _primaryFontFamily,
      'numbered_size': _safeInt(_bodyFontSizeController.text, 12),
      'numbered_color': '#000000',
      'numbered_line_spacing': lineSpacing,
      'numbered_indent': _safeDouble(_bulletIndentController.text, 0.5),
      'numbered_space_before': 0.0,
      'numbered_space_after': 0.0,
      'numbered_style':
          TemplateMappingUtils.mapNumberedStyleToDb(_numberingFormat),
      'heading_numbering_style': _headingNumberingStyle == '1, 1.1, 1.1.1'
          ? 'decimal'
          : _headingNumberingStyle == 'I, A, 1'
              ? 'roman'
              : _headingNumberingStyle == 'A, 1, a'
                  ? 'alpha'
                  : 'none',
      // Page
      'page_size': _pageSize,
      'spacing_unit': _spacingUnit,
      'margin_top': _safeDouble(_pageMarginTopController.text, 25.0),
      'margin_bottom': _safeDouble(_pageMarginBottomController.text, 25.0),
      'margin_left': _safeDouble(_pageMarginLeftController.text, 30.0),
      'margin_right': _safeDouble(_pageMarginRightController.text, 20.0),
      'line_number_enabled': false,
      'first_line_indent': _safeDouble(_firstLineIndentController.text, 0.5),

      // ── Table style (NEW) ─────────────────────────────────────────────────
      'table_style': _buildTableStyleData(),
    };

    // Reference rules — prefer updated UI rules, fall back to existing DB values
    if (_referenceRules.isNotEmpty) {
      formattingRules['reference_rules'] = _referenceRules;
    } else if (existingRefRules.isNotEmpty) {
      formattingRules['reference_rules'] = existingRefRules;
    }

    return {
      'name': _templateNameController.text.trim(),
      'required_sections': _requiredSections
          .asMap()
          .entries
          .map((e) => e.value.toJson(e.key + 1))
          .toList(),
      'formatting_rules': formattingRules,
    };
  }

  @override
  void dispose() {
    _templateNameController.dispose();
    _pageMarginTopController.dispose();
    _pageMarginBottomController.dispose();
    _pageMarginLeftController.dispose();
    _pageMarginRightController.dispose();
    _heading1SizeController.dispose();
    _heading1SpaceBeforeController.dispose();
    _heading1SpaceAfterController.dispose();
    _heading2SizeController.dispose();
    _heading2SpaceBeforeController.dispose();
    _heading2SpaceAfterController.dispose();
    _heading3SizeController.dispose();
    _heading3SpaceBeforeController.dispose();
    _heading3SpaceAfterController.dispose();
    _heading4SizeController.dispose();
    _heading4SpaceBeforeController.dispose();
    _heading4SpaceAfterController.dispose();
    _bodyFontSizeController.dispose();
    _lineSpacingController.dispose();
    _firstLineIndentController.dispose();
    _bulletIndentController.dispose();
    _paragraphSpaceBeforeController.dispose();
    _paragraphSpaceAfterController.dispose();
    // Table controllers
    _tableFontSizeController.dispose();
    _tableHeaderBgColorController.dispose();
    _tableBandColorController.dispose();
    _tableBorderColorController.dispose();
    _tableBorderSizeController.dispose();
    _tablePaddingTopController.dispose();
    _tablePaddingBottomController.dispose();
    _tablePaddingLeftController.dispose();
    _tablePaddingRightController.dispose();
    super.dispose();
  }

  // ── Reference Rules button ────────────────────────────────────────────────

  Widget _buildReferenceRulesButton() {
    if (_selectedTemplateId == null) return const SizedBox.shrink();

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F2E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF6366F1).withOpacity(0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Container(
              padding: const EdgeInsets.all(7),
              decoration: BoxDecoration(
                color: const Color(0xFF6366F1).withOpacity(0.15),
                borderRadius: BorderRadius.circular(7),
              ),
              child: const Icon(Icons.format_list_numbered,
                  color: Color(0xFF6366F1), size: 18),
            ),
            const SizedBox(width: 12),
            const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Reference Formatting Rules',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
                Text(
                  'Set citation style, font, spacing and behaviour for the References section',
                  style: TextStyle(fontSize: 11, color: Color(0xFF8B949E)),
                ),
              ],
            ),
          ]),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: () async {
                final result = await Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => AdminReferenceSettingsScreen(
                      templateId: _selectedTemplateId!,
                      userId: _userId,
                    ),
                  ),
                );
                if (result != null && result is Map<String, dynamic>) {
                  setState(() => _referenceRules = result);
                }
              },
              icon: const Icon(Icons.tune, size: 16, color: Color(0xFF6366F1)),
              label: const Text(
                'Configure Reference Rules',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF6366F1),
                ),
              ),
              style: OutlinedButton.styleFrom(
                side: const BorderSide(color: Color(0xFF6366F1)),
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final form = SingleChildScrollView(
      child: Container(
        color: const Color(0xFF0F1419),
        padding: EdgeInsets.all(widget.standalone ? 24 : 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TemplateHeader(selectedTemplate: _selectedTemplate),
            const SizedBox(height: 32),
            TemplateSelector(
              selectedTemplateId: _selectedTemplateId,
              onTemplateChanged: (value) {
                setState(() => _selectedTemplateId = value);
                if (value != null) {
                  _loadTemplateDetails();
                } else {
                  _clearFormFields();
                  setState(() => _selectedTemplate = null);
                }
              },
            ),
            const SizedBox(height: 32),
            TemplateNameField(controller: _templateNameController),
            const SizedBox(height: 24),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    children: [
                      DocumentSettingsCard(
                        pageSize: _pageSize,
                        spacingUnit: _spacingUnit,
                        onPageSizeChanged: (value) =>
                            setState(() => _pageSize = value),
                        onSpacingUnitChanged: (value) =>
                            setState(() => _spacingUnit = value),
                        pageMarginTopController: _pageMarginTopController,
                        pageMarginBottomController: _pageMarginBottomController,
                        pageMarginLeftController: _pageMarginLeftController,
                        pageMarginRightController: _pageMarginRightController,
                        lineSpacingController: _lineSpacingController,
                      ),
                      const SizedBox(height: 24),
                      ParagraphStyleCard(
                        firstLineIndentController: _firstLineIndentController,
                        spaceBeforeController: _paragraphSpaceBeforeController,
                        spaceAfterController: _paragraphSpaceAfterController,
                        spacingUnit: _spacingUnit,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 24),
                Expanded(
                  child: Column(
                    children: [
                      FontSettingsCard(
                        primaryFontFamily: _primaryFontFamily,
                        onFontFamilyChanged: (value) =>
                            setState(() => _primaryFontFamily = value),
                        bodyFontSizeController: _bodyFontSizeController,
                        justifyText: _justifyText,
                        onJustifyTextChanged: (value) =>
                            setState(() => _justifyText = value),
                      ),
                      const SizedBox(height: 24),
                      ListBulletStylesCard(
                        bulletStyle: _bulletStyle,
                        onBulletStyleChanged: (value) =>
                            setState(() => _bulletStyle = value),
                        numberingFormat: _numberingFormat,
                        onNumberingFormatChanged: (value) =>
                            setState(() => _numberingFormat = value),
                        bulletIndentController: _bulletIndentController,
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 32),
            HeadingStylesCard(
              spacingUnit: _spacingUnit,
              numberingStyle: _headingNumberingStyle,
              onNumberingStyleChanged: (v) =>
                  setState(() => _headingNumberingStyle = v),
              heading1SizeController: _heading1SizeController,
              heading1SpaceBeforeController: _heading1SpaceBeforeController,
              heading1SpaceAfterController: _heading1SpaceAfterController,
              heading1Weight: _heading1Weight,
              heading1Italic: _heading1Italic,
              heading1Alignment: _heading1Alignment,
              heading1Transform: _heading1Transform,
              onHeading1WeightChanged: (v) =>
                  setState(() => _heading1Weight = v),
              onHeading1ItalicChanged: (v) =>
                  setState(() => _heading1Italic = v),
              onHeading1AlignmentChanged: (v) =>
                  setState(() => _heading1Alignment = v),
              onHeading1TransformChanged: (v) =>
                  setState(() => _heading1Transform = v),
              heading2SizeController: _heading2SizeController,
              heading2SpaceBeforeController: _heading2SpaceBeforeController,
              heading2SpaceAfterController: _heading2SpaceAfterController,
              heading2Weight: _heading2Weight,
              heading2Italic: _heading2Italic,
              heading2Alignment: _heading2Alignment,
              heading2Transform: _heading2Transform,
              onHeading2WeightChanged: (v) =>
                  setState(() => _heading2Weight = v),
              onHeading2ItalicChanged: (v) =>
                  setState(() => _heading2Italic = v),
              onHeading2AlignmentChanged: (v) =>
                  setState(() => _heading2Alignment = v),
              onHeading2TransformChanged: (v) =>
                  setState(() => _heading2Transform = v),
              heading3SizeController: _heading3SizeController,
              heading3SpaceBeforeController: _heading3SpaceBeforeController,
              heading3SpaceAfterController: _heading3SpaceAfterController,
              heading3Weight: _heading3Weight,
              heading3Italic: _heading3Italic,
              heading3Alignment: _heading3Alignment,
              heading3Transform: _heading3Transform,
              onHeading3WeightChanged: (v) =>
                  setState(() => _heading3Weight = v),
              onHeading3ItalicChanged: (v) =>
                  setState(() => _heading3Italic = v),
              onHeading3AlignmentChanged: (v) =>
                  setState(() => _heading3Alignment = v),
              onHeading3TransformChanged: (v) =>
                  setState(() => _heading3Transform = v),
            ),
            const SizedBox(height: 32),

            // ── Table Styles Card (NEW) ────────────────────────────────────
            TableStylesCard(
              fontSizeController:       _tableFontSizeController,
              fontName:                 _tableFontName,
              onFontNameChanged:        (v) => setState(() => _tableFontName = v),
              headerBold:               _tableHeaderBold,
              onHeaderBoldChanged:      (v) => setState(() => _tableHeaderBold = v),
              headerAlign:              _tableHeaderAlign,
              onHeaderAlignChanged:     (v) => setState(() => _tableHeaderAlign = v),
              headerBgColorController:  _tableHeaderBgColorController,
              bodyAlign:                _tableBodyAlign,
              onBodyAlignChanged:       (v) => setState(() => _tableBodyAlign = v),
              bandedRows:               _tableBandedRows,
              onBandedRowsChanged:      (v) => setState(() => _tableBandedRows = v),
              bandColorController:      _tableBandColorController,
              borders:                  _tableBorders,
              onBordersChanged:         (v) => setState(() => _tableBorders = v),
              borderColorController:    _tableBorderColorController,
              borderSizeController:     _tableBorderSizeController,
              paddingTopController:     _tablePaddingTopController,
              paddingBottomController:  _tablePaddingBottomController,
              paddingLeftController:    _tablePaddingLeftController,
              paddingRightController:   _tablePaddingRightController,
              centerTable:              _tableCenterTable,
              onCenterTableChanged:     (v) => setState(() => _tableCenterTable = v),
              autoFit:                  _tableAutoFit,
              onAutoFitChanged:         (v) => setState(() => _tableAutoFit = v),
              repeatHeader:             _tableRepeatHeader,
              onRepeatHeaderChanged:    (v) => setState(() => _tableRepeatHeader = v),
            ),

            const SizedBox(height: 32),
            RequiredSectionsCard(
              sections: _requiredSections,
              onSectionsChanged: (updated) =>
                  setState(() => _requiredSections = updated),
            ),
            const SizedBox(height: 32),

            _buildReferenceRulesButton(),
            if (_selectedTemplateId != null) const SizedBox(height: 32),

            Align(
              alignment: Alignment.centerRight,
              child: UploadTemplateDocumentButton(
                enabled: !_isSaving && !_isLoading,
                onDraftReady: _applyExtractedDraft,
              ),
            ),
            const SizedBox(height: 12),
            ActionButtons(
              selectedTemplateId: _selectedTemplateId,
              isSaving: _isSaving,
              canSubmit: _templateNameController.text.trim().isNotEmpty,
              onCreateTemplate: _createTemplate,
              onSaveTemplate: _saveTemplate,
              onClearSelection: () {
                setState(() {
                  _selectedTemplateId = null;
                  _selectedTemplate = null;
                });
                _clearFormFields();
              },
            ),
          ],
        ),
      ),
    );

    if (!widget.standalone) return form;

    return AdminSubPage(
      title: 'Create Template',
      subtitle: widget.departmentId != null
          ? 'Using the full template configuration for this department'
          : 'Using the full template configuration screen',
      onBack: () => Navigator.of(context).pop(false),
      child: form,
    );
  }
}



