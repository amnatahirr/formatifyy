import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import '../config/api_config.dart';
import '../providers/auth_provider.dart';
import '../providers/template_provider.dart';

import 'tr.dart';
class TemplateFormWidget extends StatefulWidget {
  final int universityId;
  final Function()? onTemplateCreated;

  const TemplateFormWidget({
    Key? key,
    required this.universityId,
    this.onTemplateCreated,
  }) : super(key: key);

  @override
  State<TemplateFormWidget> createState() => _TemplateFormWidgetState();
}

class _TemplateFormWidgetState extends State<TemplateFormWidget> {
  late String baseUrl;
  final _formKey = GlobalKey<FormState>();
  bool _isLoading = false;
  String? _errorMessage;

  // Predefined font options
  final List<String> _fontOptions = [
    'Times New Roman',
    'Arial',
    'Calibri',
    'Georgia',
    'Courier New',
    'Garamond',
    'Verdana',
  ];

  // Page size options (MS Word standards)
  final List<String> _pageSizeOptions = [
    'Letter', // 8.5" x 11"
    'Legal', // 8.5" x 14"
    'A4', // 210mm x 297mm
    'A3', // 297mm x 420mm
    'Tabloid', // 11" x 17"
  ];

  // Line spacing options
  final List<String> _lineSpacingOptions = [
    '1.0',
    '1.15',
    '1.5',
    '2.0',
    '2.5',
    '3.0',
  ];

  // Form fields
  late TextEditingController _nameController;
  late TextEditingController _sectionsController;

  // Formatting rules
  late TextEditingController _heading1FontController;
  late TextEditingController _heading1SizeController;
  late TextEditingController _heading1ColorController;
  late TextEditingController _heading2FontController;
  late TextEditingController _heading2SizeController;
  late TextEditingController _heading2ColorController;
  late TextEditingController _heading3FontController;
  late TextEditingController _heading3SizeController;
  late TextEditingController _heading3ColorController;
  late TextEditingController _bodyFontController;
  late TextEditingController _bodySizeController;
  late TextEditingController _bodyColorController;
  late TextEditingController _marginTopController;
  late TextEditingController _marginBottomController;
  late TextEditingController _marginLeftController;
  late TextEditingController _marginRightController;
  late TextEditingController _firstLineIndentController;
  late TextEditingController _bulletIndentController;

  // Bullet and List controllers
  late TextEditingController _bulletFontController;
  late TextEditingController _bulletSizeController;
  late TextEditingController _bulletColorController;
  String _bulletType = 'bullet'; // bullet, dash, asterisk

  late TextEditingController _numberedFontController;
  late TextEditingController _numberedSizeController;
  late TextEditingController _numberedColorController;
  String _numberedStyle = '1,2,3'; // 1,2,3, A,B,C, a,b,c, i,ii,iii

  // Line spacing and paragraph spacing controllers for each element
  late TextEditingController _heading1LineSpacingController;
  late TextEditingController _heading1SpaceBeforeController;
  late TextEditingController _heading1SpaceAfterController;

  late TextEditingController _heading2LineSpacingController;
  late TextEditingController _heading2SpaceBeforeController;
  late TextEditingController _heading2SpaceAfterController;

  late TextEditingController _heading3LineSpacingController;
  late TextEditingController _heading3SpaceBeforeController;
  late TextEditingController _heading3SpaceAfterController;

  late TextEditingController _bodyLineSpacingController;
  late TextEditingController _bodySpaceBeforeController;
  late TextEditingController _bodySpaceAfterController;

  late TextEditingController _bulletLineSpacingController;
  late TextEditingController _bulletSpaceBeforeController;
  late TextEditingController _bulletSpaceAfterController;

  late TextEditingController _numberedLineSpacingController;
  late TextEditingController _numberedSpaceBeforeController;
  late TextEditingController _numberedSpaceAfterController;

  // Page size selector
  String _pageSize = 'A4';

  bool _heading1Bold = true;
  bool _heading1Italic = false;
  bool _heading1Underline = false;
  bool _heading2Bold = true;
  bool _heading2Italic = false;
  bool _heading2Underline = false;
  bool _heading3Bold = true;
  bool _heading3Italic = false;
  bool _heading3Underline = false;
  bool _bodyJustified = false;
  bool _lineNumberEnabled = false;

  @override
  void initState() {
    super.initState();
    baseUrl = ApiConfig.getBaseUrl();

    _nameController = TextEditingController();
    _sectionsController = TextEditingController();

    _heading1FontController = TextEditingController(text: 'Times New Roman');
    _heading1SizeController = TextEditingController(text: '18');
    _heading1ColorController = TextEditingController(text: '#000000');

    _heading2FontController = TextEditingController(text: 'Times New Roman');
    _heading2SizeController = TextEditingController(text: '16');
    _heading2ColorController = TextEditingController(text: '#000000');

    _heading3FontController = TextEditingController(text: 'Times New Roman');
    _heading3SizeController = TextEditingController(text: '14');
    _heading3ColorController = TextEditingController(text: '#000000');

    _bodyFontController = TextEditingController(text: 'Times New Roman');
    _bodySizeController = TextEditingController(text: '12');
    _bodyColorController = TextEditingController(text: '#000000');

    _marginTopController = TextEditingController(text: '1.0');
    _marginBottomController = TextEditingController(text: '1.0');
    _marginLeftController = TextEditingController(text: '1.0');
    _marginRightController = TextEditingController(text: '1.0');
    _firstLineIndentController = TextEditingController(text: '0.5');
    _bulletIndentController = TextEditingController(text: '0.5');

    _bulletFontController = TextEditingController(text: 'Times New Roman');
    _bulletSizeController = TextEditingController(text: '12');
    _bulletColorController = TextEditingController(text: '#000000');

    _numberedFontController = TextEditingController(text: 'Times New Roman');
    _numberedSizeController = TextEditingController(text: '12');
    _numberedColorController = TextEditingController(text: '#000000');

    // Initialize line spacing and paragraph spacing controllers
    _heading1LineSpacingController = TextEditingController(text: '1.0');
    _heading1SpaceBeforeController = TextEditingController(text: '12.0');
    _heading1SpaceAfterController = TextEditingController(text: '6.0');

    _heading2LineSpacingController = TextEditingController(text: '1.0');
    _heading2SpaceBeforeController = TextEditingController(text: '10.0');
    _heading2SpaceAfterController = TextEditingController(text: '5.0');

    _heading3LineSpacingController = TextEditingController(text: '1.0');
    _heading3SpaceBeforeController = TextEditingController(text: '8.0');
    _heading3SpaceAfterController = TextEditingController(text: '4.0');

    _bodyLineSpacingController = TextEditingController(text: '1.0');
    _bodySpaceBeforeController = TextEditingController(text: '0.0');
    _bodySpaceAfterController = TextEditingController(text: '0.0');

    _bulletLineSpacingController = TextEditingController(text: '1.0');
    _bulletSpaceBeforeController = TextEditingController(text: '0.0');
    _bulletSpaceAfterController = TextEditingController(text: '0.0');

    _numberedLineSpacingController = TextEditingController(text: '1.0');
    _numberedSpaceBeforeController = TextEditingController(text: '0.0');
    _numberedSpaceAfterController = TextEditingController(text: '0.0');
  }

  @override
  void dispose() {
    _nameController.dispose();
    _sectionsController.dispose();
    _heading1FontController.dispose();
    _heading1SizeController.dispose();
    _heading1ColorController.dispose();
    _heading2FontController.dispose();
    _heading2SizeController.dispose();
    _heading2ColorController.dispose();
    _heading3FontController.dispose();
    _heading3SizeController.dispose();
    _heading3ColorController.dispose();
    _bodyFontController.dispose();
    _bodySizeController.dispose();
    _bodyColorController.dispose();
    _marginTopController.dispose();
    _marginBottomController.dispose();
    _marginLeftController.dispose();
    _marginRightController.dispose();
    _firstLineIndentController.dispose();
    _bulletIndentController.dispose();
    _bulletFontController.dispose();
    _bulletSizeController.dispose();
    _bulletColorController.dispose();
    _numberedFontController.dispose();
    _numberedSizeController.dispose();
    _numberedColorController.dispose();

    // Dispose line spacing and paragraph spacing controllers
    _heading1LineSpacingController.dispose();
    _heading1SpaceBeforeController.dispose();
    _heading1SpaceAfterController.dispose();
    _heading2LineSpacingController.dispose();
    _heading2SpaceBeforeController.dispose();
    _heading2SpaceAfterController.dispose();
    _heading3LineSpacingController.dispose();
    _heading3SpaceBeforeController.dispose();
    _heading3SpaceAfterController.dispose();
    _bodyLineSpacingController.dispose();
    _bodySpaceBeforeController.dispose();
    _bodySpaceAfterController.dispose();
    _bulletLineSpacingController.dispose();
    _bulletSpaceBeforeController.dispose();
    _bulletSpaceAfterController.dispose();
    _numberedLineSpacingController.dispose();
    _numberedSpaceBeforeController.dispose();
    _numberedSpaceAfterController.dispose();
    super.dispose();
  }

  Future<void> _createTemplate() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final authProvider = context.read<AuthProvider>();
      final sections = _sectionsController.text
          .split(',')
          .map((s) => s.trim())
          .where((s) => s.isNotEmpty)
          .toList();

      final templateData = {
        'name': _nameController.text,
        'required_sections': sections,
        'formatting_rules': {
          'heading1_font': _heading1FontController.text,
          'heading1_size': int.parse(_heading1SizeController.text),
          'heading1_bold': _heading1Bold,
          'heading1_italic': _heading1Italic,
          'heading1_underline': _heading1Underline,
          'heading1_color': _heading1ColorController.text,
          'heading1_line_spacing': double.parse(
            _heading1LineSpacingController.text,
          ),
          'heading1_space_before': double.parse(
            _heading1SpaceBeforeController.text,
          ),
          'heading1_space_after': double.parse(
            _heading1SpaceAfterController.text,
          ),
          'heading2_font': _heading2FontController.text,
          'heading2_size': int.parse(_heading2SizeController.text),
          'heading2_bold': _heading2Bold,
          'heading2_italic': _heading2Italic,
          'heading2_underline': _heading2Underline,
          'heading2_color': _heading2ColorController.text,
          'heading2_line_spacing': double.parse(
            _heading2LineSpacingController.text,
          ),
          'heading2_space_before': double.parse(
            _heading2SpaceBeforeController.text,
          ),
          'heading2_space_after': double.parse(
            _heading2SpaceAfterController.text,
          ),
          'heading3_font': _heading3FontController.text,
          'heading3_size': int.parse(_heading3SizeController.text),
          'heading3_bold': _heading3Bold,
          'heading3_italic': _heading3Italic,
          'heading3_underline': _heading3Underline,
          'heading3_color': _heading3ColorController.text,
          'heading3_line_spacing': double.parse(
            _heading3LineSpacingController.text,
          ),
          'heading3_space_before': double.parse(
            _heading3SpaceBeforeController.text,
          ),
          'heading3_space_after': double.parse(
            _heading3SpaceAfterController.text,
          ),
          'body_font': _bodyFontController.text,
          'body_size': int.parse(_bodySizeController.text),
          'body_color': _bodyColorController.text,
          'body_justified': _bodyJustified,
          'body_line_spacing': double.parse(_bodyLineSpacingController.text),
          'body_space_before': double.parse(_bodySpaceBeforeController.text),
          'body_space_after': double.parse(_bodySpaceAfterController.text),
          'bullet_font': _bulletFontController.text,
          'bullet_size': int.parse(_bulletSizeController.text),
          'bullet_color': _bulletColorController.text,
          'bullet_type': _bulletType,
          'bullet_line_spacing': double.parse(
            _bulletLineSpacingController.text,
          ),
          'bullet_space_before': double.parse(
            _bulletSpaceBeforeController.text,
          ),
          'bullet_space_after': double.parse(_bulletSpaceAfterController.text),
          'numbered_font': _numberedFontController.text,
          'numbered_size': int.parse(_numberedSizeController.text),
          'numbered_color': _numberedColorController.text,
          'numbered_style': _numberedStyle,
          'numbered_line_spacing': double.parse(
            _numberedLineSpacingController.text,
          ),
          'numbered_space_before': double.parse(
            _numberedSpaceBeforeController.text,
          ),
          'numbered_space_after': double.parse(
            _numberedSpaceAfterController.text,
          ),
          'page_size': _pageSize,
          'first_line_indent': double.parse(_firstLineIndentController.text),
          'bullet_indent': double.parse(_bulletIndentController.text),
          'margin_top': double.parse(_marginTopController.text),
          'margin_bottom': double.parse(_marginBottomController.text),
          'margin_left': double.parse(_marginLeftController.text),
          'margin_right': double.parse(_marginRightController.text),
          'line_number_enabled': _lineNumberEnabled,
        },
      };

      final response = await http
          .post(
            Uri.parse(
              '$baseUrl/admin/templates?user_id=${authProvider.userId}&university_id=${widget.universityId}',
            ),
            headers: ApiConfig.getHeaders(json: true),
            body: jsonEncode(templateData),
          )
          .timeout(
            Duration(seconds: 10),
            onTimeout: () => throw TimeoutException('Connection timeout'),
          );

      if (response.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Tr('Template created successfully!'),
            backgroundColor: Colors.green,
          ),
        );

        // Reset form
        _nameController.clear();
        _sectionsController.clear();

        // Reload templates
        if (widget.onTemplateCreated != null) {
          widget.onTemplateCreated!();
        }
      } else {
        final errorData = jsonDecode(response.body);
        setState(() {
          _errorMessage = errorData['detail'] ?? 'Failed to create template';
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Error: $e';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (_errorMessage != null)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.red.withOpacity(0.1),
                  border: Border.all(color: Colors.red),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  _errorMessage!,
                  style: const TextStyle(color: Colors.red),
                ),
              ),
            const SizedBox(height: 20),

            // Header
            Tr('Create New Template',
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Tr('Define your formatting rules and document structure',
              style: theme.textTheme.bodySmall?.copyWith(color: Colors.white70),
            ),
            const SizedBox(height: 32),

            // Template Basic Info
            _buildCard(
              title: 'Template Information',
              child: Column(
                children: [
                  TextFormField(
                    controller: _nameController,
                    decoration: _buildInputDecoration(
                      labelText: 'Template Name',
                      hintText: 'e.g., COMSATS Standard Format',
                      icon: Icons.label,
                    ),
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return 'Please enter template name';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _sectionsController,
                    decoration: _buildInputDecoration(
                      labelText: 'Required Sections',
                      hintText:
                          'e.g., Abstract, Introduction, Methodology, Results, Conclusion',
                      icon: Icons.list,
                      helperText: 'Separate sections with commas',
                    ),
                    maxLines: 2,
                    validator: (value) {
                      if (value == null || value.isEmpty) {
                        return 'Please enter required sections';
                      }
                      return null;
                    },
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Heading 1 Styles
            _buildCard(
              title: 'Heading 1 Styles',
              child: Column(
                children: [
                  _buildFontSelector(
                    'Font',
                    _heading1FontController,
                    _fontOptions,
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Size',
                          controller: _heading1SizeController,
                          suffix: const Tr('pt'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildColorPicker(
                          label: 'Color',
                          controller: _heading1ColorController,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  _buildTextFormatOptions(
                    bold: _heading1Bold,
                    italic: _heading1Italic,
                    underline: _heading1Underline,
                    onBoldChanged: (v) => setState(() => _heading1Bold = v),
                    onItalicChanged: (v) => setState(() => _heading1Italic = v),
                    onUnderlineChanged: (v) =>
                        setState(() => _heading1Underline = v),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildDropdownFromList(
                          label: 'Line Spacing',
                          controller: _heading1LineSpacingController,
                          options: _lineSpacingOptions,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Space Before',
                          controller: _heading1SpaceBeforeController,
                          suffix: const Tr('pt'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  _buildStyleRow(
                    label: 'Space After',
                    controller: _heading1SpaceAfterController,
                    suffix: const Tr('pt'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Heading 2 Styles
            _buildCard(
              title: 'Heading 2 Styles',
              child: Column(
                children: [
                  _buildFontSelector(
                    'Font',
                    _heading2FontController,
                    _fontOptions,
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Size',
                          controller: _heading2SizeController,
                          suffix: const Tr('pt'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildColorPicker(
                          label: 'Color',
                          controller: _heading2ColorController,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  _buildTextFormatOptions(
                    bold: _heading2Bold,
                    italic: _heading2Italic,
                    underline: _heading2Underline,
                    onBoldChanged: (v) => setState(() => _heading2Bold = v),
                    onItalicChanged: (v) => setState(() => _heading2Italic = v),
                    onUnderlineChanged: (v) =>
                        setState(() => _heading2Underline = v),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildDropdownFromList(
                          label: 'Line Spacing',
                          controller: _heading2LineSpacingController,
                          options: _lineSpacingOptions,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Space Before',
                          controller: _heading2SpaceBeforeController,
                          suffix: const Tr('pt'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  _buildStyleRow(
                    label: 'Space After',
                    controller: _heading2SpaceAfterController,
                    suffix: const Tr('pt'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Heading 3 Styles
            _buildCard(
              title: 'Heading 3 Styles',
              child: Column(
                children: [
                  _buildFontSelector(
                    'Font',
                    _heading3FontController,
                    _fontOptions,
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Size',
                          controller: _heading3SizeController,
                          suffix: const Tr('pt'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildColorPicker(
                          label: 'Color',
                          controller: _heading3ColorController,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  _buildTextFormatOptions(
                    bold: _heading3Bold,
                    italic: _heading3Italic,
                    underline: _heading3Underline,
                    onBoldChanged: (v) => setState(() => _heading3Bold = v),
                    onItalicChanged: (v) => setState(() => _heading3Italic = v),
                    onUnderlineChanged: (v) =>
                        setState(() => _heading3Underline = v),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildDropdownFromList(
                          label: 'Line Spacing',
                          controller: _heading3LineSpacingController,
                          options: _lineSpacingOptions,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Space Before',
                          controller: _heading3SpaceBeforeController,
                          suffix: const Tr('pt'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  _buildStyleRow(
                    label: 'Space After',
                    controller: _heading3SpaceAfterController,
                    suffix: const Tr('pt'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Body Text Styles
            _buildCard(
              title: 'Body Text Styles',
              child: Column(
                children: [
                  _buildFontSelector('Font', _bodyFontController, _fontOptions),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Size',
                          controller: _bodySizeController,
                          suffix: const Tr('pt'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildColorPicker(
                          label: 'Color',
                          controller: _bodyColorController,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildStyleRow(
                          label: 'First Line Indent',
                          controller: _firstLineIndentController,
                          suffix: const Tr('in'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Bullet Indent',
                          controller: _bulletIndentController,
                          suffix: const Tr('in'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Checkbox(
                        value: _bodyJustified,
                        onChanged: (v) =>
                            setState(() => _bodyJustified = v ?? false),
                      ),
                      const Tr('Justified'),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildDropdownFromList(
                          label: 'Line Spacing',
                          controller: _bodyLineSpacingController,
                          options: _lineSpacingOptions,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Space Before',
                          controller: _bodySpaceBeforeController,
                          suffix: const Tr('pt'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  _buildStyleRow(
                    label: 'Space After',
                    controller: _bodySpaceAfterController,
                    suffix: const Tr('pt'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Bullet List Styles
            _buildCard(
              title: 'Bullet List Styles',
              child: Column(
                children: [
                  _buildFontSelector(
                    'Font',
                    _bulletFontController,
                    _fontOptions,
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Size',
                          controller: _bulletSizeController,
                          suffix: const Tr('pt'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildColorPicker(
                          label: 'Color',
                          controller: _bulletColorController,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    value: _bulletType,
                    decoration: InputDecoration(
                      labelText: 'Bullet Style',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(6),
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 10,
                      ),
                    ),
                    items: const [
                      DropdownMenuItem(
                        value: 'bullet',
                        child: Tr('Bullet (•)'),
                      ),
                      DropdownMenuItem(value: 'dash', child: Tr('Dash (–)')),
                      DropdownMenuItem(
                        value: 'asterisk',
                        child: Tr('Asterisk (*)'),
                      ),
                    ],
                    onChanged: (value) {
                      if (value != null) {
                        setState(() => _bulletType = value);
                      }
                    },
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildDropdownFromList(
                          label: 'Line Spacing',
                          controller: _bulletLineSpacingController,
                          options: _lineSpacingOptions,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Space Before',
                          controller: _bulletSpaceBeforeController,
                          suffix: const Tr('pt'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  _buildStyleRow(
                    label: 'Space After',
                    controller: _bulletSpaceAfterController,
                    suffix: const Tr('pt'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Numbered List Styles
            _buildCard(
              title: 'Numbered List Styles',
              child: Column(
                children: [
                  _buildFontSelector(
                    'Font',
                    _numberedFontController,
                    _fontOptions,
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Size',
                          controller: _numberedSizeController,
                          suffix: const Tr('pt'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildColorPicker(
                          label: 'Color',
                          controller: _numberedColorController,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    value: _numberedStyle,
                    decoration: InputDecoration(
                      labelText: 'Numbering Style',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(6),
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 10,
                      ),
                    ),
                    items: const [
                      DropdownMenuItem(value: '1,2,3', child: Tr('1, 2, 3')),
                      DropdownMenuItem(value: 'A,B,C', child: Tr('A, B, C')),
                      DropdownMenuItem(value: 'a,b,c', child: Tr('a, b, c')),
                      DropdownMenuItem(
                        value: 'i,ii,iii',
                        child: Tr('i, ii, iii'),
                      ),
                    ],
                    onChanged: (value) {
                      if (value != null) {
                        setState(() => _numberedStyle = value);
                      }
                    },
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildDropdownFromList(
                          label: 'Line Spacing',
                          controller: _numberedLineSpacingController,
                          options: _lineSpacingOptions,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Space Before',
                          controller: _numberedSpaceBeforeController,
                          suffix: const Tr('pt'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  _buildStyleRow(
                    label: 'Space After',
                    controller: _numberedSpaceAfterController,
                    suffix: const Tr('pt'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Page Layout
            _buildCard(
              title: 'Page Layout',
              child: Column(
                children: [
                  DropdownButtonFormField<String>(
                    value: _pageSize,
                    decoration: InputDecoration(
                      labelText: 'Paper Size',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(6),
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 10,
                      ),
                      prefixIcon: const Icon(Icons.description),
                    ),
                    items: _pageSizeOptions.map((size) {
                      final sizeInfo = {
                        'Letter': '8.5" × 11"',
                        'Legal': '8.5" × 14"',
                        'A4': '210 × 297mm',
                        'A3': '297 × 420mm',
                        'Tabloid': '11" × 17"',
                      };
                      return DropdownMenuItem(
                        value: size,
                        child: Text('$size - ${sizeInfo[size]}'),
                      );
                    }).toList(),
                    onChanged: (value) {
                      if (value != null) {
                        setState(() => _pageSize = value);
                      }
                    },
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Top Margin',
                          controller: _marginTopController,
                          suffix: const Tr('in'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Bottom Margin',
                          controller: _marginBottomController,
                          suffix: const Tr('in'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Left Margin',
                          controller: _marginLeftController,
                          suffix: const Tr('in'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildStyleRow(
                          label: 'Right Margin',
                          controller: _marginRightController,
                          suffix: const Tr('in'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  _buildStyleRow(
                    label: 'Bullet Indent',
                    controller: _bulletIndentController,
                    suffix: const Tr('in'),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Checkbox(
                        value: _lineNumberEnabled,
                        onChanged: (v) =>
                            setState(() => _lineNumberEnabled = v ?? false),
                      ),
                      const Tr('Enable Line Numbers'),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),

            // Submit button
            SizedBox(
              width: double.infinity,
              height: 50,
              child: ElevatedButton(
                onPressed: _isLoading ? null : _createTemplate,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.deepPurple,
                  foregroundColor: Colors.white,
                  disabledBackgroundColor: Colors.grey,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
                child: _isLoading
                    ? const SizedBox(
                        height: 24,
                        width: 24,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            Colors.white,
                          ),
                        ),
                      )
                    : const Tr('Create Template',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
              ),
            ),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  Widget _buildCard({required String title, required Widget child}) {
    final theme = Theme.of(context);
    return Container(
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF2D3748)),
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: theme.textTheme.titleMedium?.copyWith(
              color: theme.primaryColor,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 16),
          child,
        ],
      ),
    );
  }

  InputDecoration _buildInputDecoration({
    required String labelText,
    required String hintText,
    required IconData icon,
    String? helperText,
  }) {
    return InputDecoration(
      labelText: labelText,
      hintText: hintText,
      helperText: helperText,
      prefixIcon: Icon(icon),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
    );
  }

  Widget _buildStyleRow({
    required String label,
    required TextEditingController controller,
    int flex = 1,
    Widget? suffix,
  }) {
    return Row(
      children: [
        Expanded(
          flex: flex,
          child: TextFormField(
            controller: controller,
            decoration: InputDecoration(
              labelText: label,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(6),
              ),
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 12,
                vertical: 10,
              ),
            ),
            validator: (value) {
              if (value == null || value.isEmpty) {
                return 'Required';
              }
              return null;
            },
          ),
        ),
        if (suffix != null) ...[
          const SizedBox(width: 8),
          Padding(padding: const EdgeInsets.only(top: 8), child: suffix),
        ],
      ],
    );
  }

  Widget _buildFontSelector(
    String label,
    TextEditingController controller,
    List<String> options,
  ) {
    return DropdownButtonFormField<String>(
      value: controller.text,
      decoration: InputDecoration(
        labelText: label,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(6)),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 12,
          vertical: 10,
        ),
      ),
      items: options
          .map((font) => DropdownMenuItem(value: font, child: Text(font)))
          .toList(),
      onChanged: (value) {
        if (value != null) {
          controller.text = value;
        }
      },
    );
  }

  Widget _buildColorPicker({
    required String label,
    required TextEditingController controller,
  }) {
    return TextFormField(
      controller: controller,
      decoration: InputDecoration(
        labelText: label,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(6)),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 12,
          vertical: 10,
        ),
        prefixIcon: GestureDetector(
          onTap: () {
            // Color picker dialog can be implemented here
            showDialog(
              context: context,
              builder: (BuildContext context) {
                return AlertDialog(
                  title: const Tr('Select Color'),
                  content: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children:
                            [
                                  '#000000',
                                  '#1F1F1F',
                                  '#4A4A4A',
                                  '#0066CC',
                                  '#CC0000',
                                  '#008000',
                                  '#663399',
                                ]
                                .map(
                                  (color) => GestureDetector(
                                    onTap: () {
                                      controller.text = color;
                                      Navigator.pop(context);
                                    },
                                    child: Container(
                                      width: 40,
                                      height: 40,
                                      decoration: BoxDecoration(
                                        color: Color(
                                          int.parse(
                                            color.replaceFirst('#', '0xff'),
                                          ),
                                        ),
                                        border: Border.all(
                                          color: controller.text == color
                                              ? Colors.black
                                              : Colors.grey,
                                          width: controller.text == color
                                              ? 2
                                              : 1,
                                        ),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                    ),
                                  ),
                                )
                                .toList(),
                      ),
                    ],
                  ),
                );
              },
            );
          },
          child: Container(
            margin: const EdgeInsets.all(8),
            width: 24,
            height: 24,
            decoration: BoxDecoration(
              color: Color(
                int.parse(controller.text.replaceFirst('#', '0xff')),
              ),
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: Colors.grey),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTextFormatOptions({
    required bool bold,
    required bool italic,
    required bool underline,
    required Function(bool) onBoldChanged,
    required Function(bool) onItalicChanged,
    required Function(bool) onUnderlineChanged,
  }) {
    return Row(
      children: [
        Expanded(
          child: CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            title: const Tr('Bold'),
            value: bold,
            onChanged: (v) => onBoldChanged(v ?? false),
          ),
        ),
        Expanded(
          child: CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            title: const Tr('Italic'),
            value: italic,
            onChanged: (v) => onItalicChanged(v ?? false),
          ),
        ),
        Expanded(
          child: CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            title: const Tr('Underline'),
            value: underline,
            onChanged: (v) => onUnderlineChanged(v ?? false),
          ),
        ),
      ],
    );
  }

  Widget _buildDropdownFromList({
    required String label,
    required TextEditingController controller,
    required List<String> options,
  }) {
    return DropdownButtonFormField<String>(
      value: controller.text,
      decoration: InputDecoration(
        labelText: label,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(6)),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 12,
          vertical: 10,
        ),
      ),
      items: options
          .map((option) => DropdownMenuItem(value: option, child: Text(option)))
          .toList(),
      onChanged: (value) {
        if (value != null) {
          controller.text = value;
        }
      },
    );
  }
}
