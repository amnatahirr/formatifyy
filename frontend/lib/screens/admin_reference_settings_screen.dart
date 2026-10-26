// lib/screens/admin_reference_settings_screen.dart
//
// Admin UI panel for configuring the Reference Formatting Rules of a template.
// This screen is embedded inside TemplateConfigurationScreen (the "Templates"
// tab in AdminDashboard) — just call:
//
//   Navigator.push(context, MaterialPageRoute(
//     builder: (_) => AdminReferenceSettingsScreen(templateId: t['id']),
//   ));
//
// or mount it as a sub-section of your existing template editor.

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';

import '../widgets/tr.dart';
class AdminReferenceSettingsScreen extends StatefulWidget {
  final int templateId;
  final int userId;

  const AdminReferenceSettingsScreen({
    Key? key,
    required this.templateId,
    required this.userId,
  }) : super(key: key);

  @override
  State<AdminReferenceSettingsScreen> createState() =>
      _AdminReferenceSettingsScreenState();
}

class _AdminReferenceSettingsScreenState
    extends State<AdminReferenceSettingsScreen> {
  // ── State ──────────────────────────────────────────────────────────────────
  bool _loading = true;
  bool _saving = false;
  String? _error;
  String? _successMessage;

  // Rule fields (mirrors ReferenceFormattingRule on the backend)
  String _style = 'APA';
  String _fontName = 'Times New Roman';
  double _fontSize = 12.0;
  double _lineSpacing = 1.5;
  double _hangingIndent = 0.5;
  double _spaceBefore = 0.0;
  double _spaceAfter = 6.0;
  bool _bold = false;
  bool _italic = false;
  String _color = '#000000';
  bool _sortAlphabetically = true;
  bool _removeDuplicates = true;
  bool _makeUrlsClickable = true;
  bool _markIncomplete = true;
  String _numberingStyle = 'numeric'; // default

  // Controllers
  final _fontSizeCtrl = TextEditingController();
  final _lineSpacingCtrl = TextEditingController();
  final _hangingCtrl = TextEditingController();
  final _spaceBeforeCtrl = TextEditingController();
  final _spaceAfterCtrl = TextEditingController();

  // ── Lifecycle ──────────────────────────────────────────────────────────────
  @override
  void initState() {
    super.initState();
    _loadRules();
  }

  @override
  void dispose() {
    _fontSizeCtrl.dispose();
    _lineSpacingCtrl.dispose();
    _hangingCtrl.dispose();
    _spaceBeforeCtrl.dispose();
    _spaceAfterCtrl.dispose();
    super.dispose();
  }

  // ── Network ───────────────────────────────────────────────────────────────
  Future<void> _loadRules() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final base = ApiConfig.getBaseUrl();
      print('📡 Loading reference rules from: $base/references/rules/${widget.templateId}');
      
      final res = await http.get(
        Uri.parse('$base/references/rules/${widget.templateId}'),
        headers: {'Content-Type': 'application/json'},
      ).timeout(const Duration(seconds: 10));

      print('📥 Load response status: ${res.statusCode}');
      
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        final r = data['reference_rules'] as Map<String, dynamic>? ?? {};
        print('📦 Loaded reference rules: $r');
        _applyRules(r);
      } else {
        _error = 'Failed to load rules: ${res.body}';
        print('❌ Failed to load rules: ${res.body}');
      }
    } catch (e) {
      _error = 'Error: $e';
      print('❌ Error loading rules: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  void _applyRules(Map<String, dynamic> r) {
    print('🔧 Applying rules: $r');
    
    _style = r['style'] ?? 'APA';
    _fontName = r['font_name'] ?? 'Times New Roman';
    _fontSize = (r['font_size'] as num?)?.toDouble() ?? 12.0;
    _lineSpacing = (r['line_spacing'] as num?)?.toDouble() ?? 1.5;
    _hangingIndent = (r['hanging_indent'] as num?)?.toDouble() ?? 0.5;
    _spaceBefore = (r['space_before'] as num?)?.toDouble() ?? 0.0;
    _spaceAfter = (r['space_after'] as num?)?.toDouble() ?? 6.0;
    _bold = r['bold'] ?? false;
    _italic = r['italic'] ?? false;
    _color = r['color'] ?? '#000000';
    _sortAlphabetically = r['sort_alphabetically'] ?? true;
    _removeDuplicates = r['remove_duplicates'] ?? true;
    _makeUrlsClickable = r['make_urls_clickable'] ?? true;
    _markIncomplete = r['mark_incomplete'] ?? true;
    _numberingStyle = r['numbering_style'] ?? 'numeric';

    print('✅ Applied values - Bold: $_bold, Italic: $_italic, Style: $_style');

    _fontSizeCtrl.text = _fontSize.toString();
    _lineSpacingCtrl.text = _lineSpacing.toString();
    _hangingCtrl.text = _hangingIndent.toString();
    _spaceBeforeCtrl.text = _spaceBefore.toString();
    _spaceAfterCtrl.text = _spaceAfter.toString();

  }

  Future<void> _saveRules() async {
    setState(() {
      _saving = true;
      _error = null;
      _successMessage = null;
    });

    try {
      final base = ApiConfig.getBaseUrl();
      final uri = Uri.parse(
        '$base/references/rules/${widget.templateId}?user_id=${widget.userId}',
      );
      
      // Get current values from controllers
      final fontSize = double.tryParse(_fontSizeCtrl.text) ?? _fontSize;
      final lineSpacing = double.tryParse(_lineSpacingCtrl.text) ?? _lineSpacing;
      final hangingIndent = double.tryParse(_hangingCtrl.text) ?? _hangingIndent;
      final spaceBefore = double.tryParse(_spaceBeforeCtrl.text) ?? _spaceBefore;
      final spaceAfter = double.tryParse(_spaceAfterCtrl.text) ?? _spaceAfter;
      
      final payload = {
        'style': _style,
        'font_name': _fontName,
        'font_size': fontSize,
        'line_spacing': lineSpacing,
        'hanging_indent': hangingIndent,
        'space_before': spaceBefore,
        'space_after': spaceAfter,
        'bold': _bold,
        'italic': _italic,
        'color': _color,
        'sort_alphabetically': _sortAlphabetically,
        'remove_duplicates': _removeDuplicates,
        'make_urls_clickable': _makeUrlsClickable,
        'mark_incomplete': _markIncomplete,
        'numbering_style': _numberingStyle,
      };

      final body = jsonEncode(payload);

      // DEBUG: Print what we're sending
      print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
      print('💾 SAVING REFERENCE RULES');
      print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
      print('📋 Template ID: ${widget.templateId}');
      print('👤 User ID: ${widget.userId}');
      print('🔗 URL: $uri');
      print('🎨 Style: $_style');
      print('📝 Font: $_fontName');
      print('📏 Font Size: $fontSize');
      print('💪 Bold: $_bold');
      print('🎭 Italic: $_italic');
      print('📦 Full payload: $payload');
      print('📤 JSON body: $body');
      print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

      final res = await http.put(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: body,
      ).timeout(const Duration(seconds: 15));

      print('📥 Response status: ${res.statusCode}');
      print('📥 Response body: ${res.body}');

      if (res.statusCode == 200) {
        _successMessage = 'Reference rules saved successfully!';
        print('✅ Save successful!');
        
        // Show success and then return
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Tr('Reference rules saved successfully!'),
            backgroundColor: Colors.green,
            duration: Duration(seconds: 2),
          ),
        );
        
        // Return to previous screen with success
        Navigator.pop(context, payload);
      } else {
        _error = 'Save failed: ${res.body}';
        print('❌ Save failed: ${res.body}');
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Save failed: ${res.body}'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } catch (e) {
      print('❌ Error saving: $e');
      _error = 'Error saving: $e';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error saving: $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  // ── Build ──────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    // DEBUG: Print current state on each build
    print('🏗️ Building with bold: $_bold, italic: $_italic, style: $_style');
    
    if (_loading) {
      return const Scaffold(
        backgroundColor: Color(0xFF0F1419),
        body: Center(child: CircularProgressIndicator(color: Color(0xFF6366F1))),
      );
    }

    return Scaffold(
      backgroundColor: const Color(0xFF0F1419),
      appBar: AppBar(
        backgroundColor: const Color(0xFF141B27),
        title: const Tr('Reference Formatting Rules',
          style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w600),
        ),
        iconTheme: const IconThemeData(color: Colors.white),
        actions: [
          _saving
              ? const Padding(
                  padding: EdgeInsets.all(14),
                  child: SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  ),
                )
              : TextButton.icon(
                  onPressed: () {
                    print('🔘 Save button pressed!');
                    print('   Current bold value: $_bold');
                    print('   Current italic value: $_italic');
                    _saveRules();
                  },
                  icon: const Icon(Icons.save, color: Color(0xFF6366F1)),
                  label: const Tr('Save', style: TextStyle(color: Color(0xFF6366F1))),
                ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (_error != null) _statusBanner(_error!, isError: true),
            if (_successMessage != null) _statusBanner(_successMessage!, isError: false),

            _sectionTitle('Citation Style'),
            _styleSelector(),

            const SizedBox(height: 24),
            _sectionTitle('Font & Typography'),
            _typographyCard(),

            const SizedBox(height: 24),
            _sectionTitle('Spacing & Indentation'),
            _spacingCard(),

            const SizedBox(height: 24),
            _sectionTitle('Behaviour'),
            _behaviourCard(),

            const SizedBox(height: 40),
            _sectionTitle('Numbering Style'),
            _numberingSelector(),
          ],
        ),
      ),
    );
  }

  // ── Section builders ───────────────────────────────────────────────────────

  Widget _sectionTitle(String title) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Text(
          title,
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w700,
            color: Color(0xFF6366F1),
            letterSpacing: 0.8,
          ),
        ),
      );

  Widget _styleSelector() {
    return _card(
      child: Row(
        children: ['APA', 'IEEE', 'MLA'].map((s) {
          final selected = _style == s;
          return Expanded(
            child: GestureDetector(
              onTap: () {
                print('🎨 Changing style to: $s');
                setState(() => _style = s);
              },
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                margin: const EdgeInsets.symmetric(horizontal: 4),
                padding: const EdgeInsets.symmetric(vertical: 14),
                decoration: BoxDecoration(
                  color: selected
                      ? const Color(0xFF6366F1)
                      : const Color(0xFF0F1419),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: selected
                        ? const Color(0xFF6366F1)
                        : const Color(0xFF2D3748),
                  ),
                ),
                child: Text(
                  s,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: selected ? Colors.white : Colors.white60,
                  ),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _typographyCard() {
    return _card(
      child: Column(
        children: [
          _dropdownRow(
            label: 'Font',
            value: _fontName,
            items: const [
              'Times New Roman',
              'Arial',
              'Calibri',
              'Georgia',
              'Garamond'
            ],
            onChanged: (v) {
              print('🔤 Changing font to: $v');
              setState(() => _fontName = v!);
            },
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(child: _numField('Font Size (pt)', _fontSizeCtrl)),
              const SizedBox(width: 16),
              _toggleRow('Bold', _bold, (v) {
                print('💪 Setting bold to: $v');
                setState(() => _bold = v);
              }),
              const SizedBox(width: 8),
              _toggleRow('Italic', _italic, (v) {
                print('🎭 Setting italic to: $v');
                setState(() => _italic = v);
              }),
            ],
          ),
        ],
      ),
    );
  }

  Widget _spacingCard() {
    return _card(
      child: Column(
        children: [
          Row(children: [
            Expanded(child: _numField('Line Spacing', _lineSpacingCtrl)),
            const SizedBox(width: 16),
            Expanded(child: _numField('Hanging Indent (in)', _hangingCtrl)),
          ]),
          const SizedBox(height: 16),
          Row(children: [
            Expanded(child: _numField('Space Before (pt)', _spaceBeforeCtrl)),
            const SizedBox(width: 16),
            Expanded(child: _numField('Space After (pt)', _spaceAfterCtrl)),
          ]),
        ],
      ),
    );
  }

  Widget _behaviourCard() {
    return _card(
      child: Column(
        children: [
          _switchRow(
            'Sort Alphabetically',
            'Order references by first author last name',
            _sortAlphabetically,
            (v) {
              print('🔄 Sort alphabetically: $v');
              setState(() => _sortAlphabetically = v);
            },
          ),
          const Divider(color: Color(0xFF2D3748), height: 24),
          _switchRow(
            'Remove Duplicates',
            'Automatically deduplicate identical references',
            _removeDuplicates,
            (v) {
              print('🔁 Remove duplicates: $v');
              setState(() => _removeDuplicates = v);
            },
          ),
          const Divider(color: Color(0xFF2D3748), height: 24),
          _switchRow(
            'Clickable URLs / DOIs',
            'Turn hyperlinks into clickable Word links',
            _makeUrlsClickable,
            (v) {
              print('🔗 Clickable URLs: $v');
              setState(() => _makeUrlsClickable = v);
            },
          ),
          const Divider(color: Color(0xFF2D3748), height: 24),
          _switchRow(
            'Mark Incomplete References',
            'Tag references missing author / year / title',
            _markIncomplete,
            (v) {
              print('⚠️ Mark incomplete: $v');
              setState(() => _markIncomplete = v);
            },
          ),
        ],
      ),
    );
  }

  // ── Reusable widgets ───────────────────────────────────────────────────────

  Widget _card({required Widget child}) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: const Color(0xFF1A1F2E),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFF2D3748)),
        ),
        child: child,
      );

  Widget _statusBanner(String msg, {required bool isError}) => Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: (isError ? const Color(0xFFEF4444) : const Color(0xFF10B981))
              .withOpacity(0.15),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isError ? const Color(0xFFEF4444) : const Color(0xFF10B981),
          ),
        ),
        child: Text(
          msg,
          style: TextStyle(
            color: isError ? const Color(0xFFEF4444) : const Color(0xFF10B981),
            fontSize: 13,
          ),
        ),
      );
  Widget _numberingSelector() {
  return _card(
    child: Row(
      children: [
        _numberOption('None', 'none'),
        _numberOption('1. 2. 3.', 'numeric'),
        _numberOption('[1] [2] [3]', 'bracket'),
      ],
    ),
  );
}

Widget _numberOption(String label, String value) {
  final selected = _numberingStyle == value;

  return Expanded(
    child: GestureDetector(
      onTap: () {
        setState(() => _numberingStyle = value);
      },
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 4),
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: selected ? const Color(0xFF6366F1) : const Color(0xFF0F1419),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: const Color(0xFF2D3748)),
        ),
        child: Text(
          label,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: selected ? Colors.white : Colors.white60,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    ),
  );
}
  Widget _numField(String label, TextEditingController ctrl) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label,
              style: const TextStyle(fontSize: 12, color: Colors.white70)),
          const SizedBox(height: 6),
          TextField(
            controller: ctrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            style: const TextStyle(color: Colors.white, fontSize: 13),
            decoration: InputDecoration(
              filled: true,
              fillColor: const Color(0xFF0F1419),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
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

  Widget _dropdownRow({
    required String label,
    required String value,
    required List<String> items,
    required ValueChanged<String?> onChanged,
  }) =>
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label,
              style: const TextStyle(fontSize: 12, color: Colors.white70)),
          const SizedBox(height: 6),
          DropdownButtonFormField<String>(
            value: value,
            dropdownColor: const Color(0xFF1A1F2E),
            style: const TextStyle(color: Colors.white, fontSize: 13),
            decoration: InputDecoration(
              filled: true,
              fillColor: const Color(0xFF0F1419),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(6),
                borderSide: const BorderSide(color: Color(0xFF2D3748)),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(6),
                borderSide: const BorderSide(color: Color(0xFF2D3748)),
              ),
            ),
            items: items
                .map((e) => DropdownMenuItem(value: e, child: Text(e)))
                .toList(),
            onChanged: onChanged,
          ),
        ],
      );

  Widget _toggleRow(String label, bool value, ValueChanged<bool> onChanged) =>
      Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Checkbox(
            value: value,
            activeColor: const Color(0xFF6366F1),
            onChanged: (v) {
              print('🔄 Toggle $label: ${v ?? false}');
              onChanged(v ?? false);
            },
          ),
          Text(label,
              style: const TextStyle(color: Colors.white, fontSize: 13)),
        ],
      );

  Widget _switchRow(
    String title,
    String subtitle,
    bool value,
    ValueChanged<bool> onChanged,
  ) =>
      Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                      color: Colors.white),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(fontSize: 11, color: Colors.white54),
                ),
              ],
            ),
          ),
          Switch(
            value: value,
            activeColor: const Color(0xFF6366F1),
            onChanged: (v) {
              print('🔄 Switch $title: $v');
              onChanged(v);
            },
          ),
        ],
      );
}