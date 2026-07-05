// frontend/lib/providers/table_provider.dart
//
// Manages state for the Tables tab:
//   - Fetches table detection results from GET /api/tables/detect/{id}
//   - Tracks which tables the user has selected for formatting
//   - Tracks the active preset and any toggled custom rules
//   - Calls POST /api/tables/format/{id} to apply formatting
//
// Pattern mirrors document_provider.dart exactly:
//   ChangeNotifier + _isLoading + _errorMessage + debugPrint("[v0] ...")

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Data models
// ─────────────────────────────────────────────────────────────────────────────

class TableIssue {
  final String code;
  final String message;
  final String severity; // "warning" | "error" | "info"

  const TableIssue({
    required this.code,
    required this.message,
    required this.severity,
  });

  factory TableIssue.fromJson(Map<String, dynamic> json) => TableIssue(
        code:     json['code']     as String? ?? '',
        message:  json['message']  as String? ?? '',
        severity: json['severity'] as String? ?? 'info',
      );
}

class TableMeta {
  final int              index;
  final String           label;
  final int              rowCount;
  final int              colCount;
  final bool             hasHeaderRow;
  final List<TableIssue> issues;
  final List<List<String>> previewRows;
  final String           source; // "docx" | "pdf"

  const TableMeta({
    required this.index,
    required this.label,
    required this.rowCount,
    required this.colCount,
    required this.hasHeaderRow,
    required this.issues,
    required this.previewRows,
    required this.source,
  });

  factory TableMeta.fromJson(Map<String, dynamic> json) {
    final rawIssues = json['issues'] as List<dynamic>? ?? [];
    final rawPreview = json['preview_rows'] as List<dynamic>? ?? [];

    return TableMeta(
      index:        (json['index']     as num?)?.toInt() ?? 0,
      label:        json['label']          as String? ?? 'Table',
      rowCount:     (json['row_count'] as num?)?.toInt() ?? 0,
      colCount:     (json['col_count'] as num?)?.toInt() ?? 0,
      hasHeaderRow: json['has_header_row'] as bool?   ?? false,
      source:       json['source']         as String? ?? 'docx',
      issues: rawIssues
          .map((e) => TableIssue.fromJson(e as Map<String, dynamic>))
          .toList(),
      previewRows: rawPreview
          .map((row) => (row as List<dynamic>)
              .map((cell) => cell.toString())
              .toList())
          .toList(),
    );
  }

  int get issueCount => issues.length;
  bool get isClean   => issues.isEmpty;
}

// ─────────────────────────────────────────────────────────────────────────────
// Provider
// ─────────────────────────────────────────────────────────────────────────────

class TableProvider extends ChangeNotifier {
  late final String _baseUrl;

  TableProvider() {
    _baseUrl = ApiConfig.getBaseUrl();
  }

  // ── State ─────────────────────────────────────────────────────────────────

  List<TableMeta>  _tables            = [];
  bool             _isLoading         = false;
  bool             _isFormatting      = false;
  String?          _errorMessage;
  String?          _successMessage;

  // Selection — set of 0-based table indices the user has toggled on
  final Set<int>   _selectedIndices   = {};

  // Active preset name
  String           _activePreset      = 'academic';

  // Custom rule overrides (null value = use preset default)
  Map<String, bool> _customRules = {
    'header_bold':  true,
    'banded_rows':  true,
    'borders':      true,
    'center_table': true,
    'repeat_header':true,
    'auto_fit':     true,
  };

  // ── Getters ───────────────────────────────────────────────────────────────

  List<TableMeta>  get tables           => _tables;
  bool             get isLoading        => _isLoading;
  bool             get isFormatting     => _isFormatting;
  String?          get errorMessage     => _errorMessage;
  String?          get successMessage   => _successMessage;
  Set<int>         get selectedIndices  => _selectedIndices;
  String           get activePreset     => _activePreset;
  Map<String, bool> get customRules     => _customRules;

  bool isSelected(int index)  => _selectedIndices.contains(index);
  bool get hasSelection       => _selectedIndices.isNotEmpty;
  int  get selectedCount      => _selectedIndices.length;

  int get totalIssues =>
      _tables.fold(0, (sum, t) => sum + t.issueCount);

  // ── Table detection ───────────────────────────────────────────────────────

  Future<void> detectTables(int documentId, int userId) async {
    _isLoading    = true;
    _errorMessage = null;
    _successMessage = null;
    _tables       = [];
    _selectedIndices.clear();
    notifyListeners();

    try {
      final url = '$_baseUrl/tables/detect/$documentId?user_id=$userId';
      debugPrint('[v0] TableProvider.detectTables → $url');

      final response = await http.get(Uri.parse(url));

      if (response.statusCode == 200) {
        final data     = jsonDecode(response.body) as Map<String, dynamic>;
        final rawTables = data['tables'] as List<dynamic>? ?? [];

        _tables = rawTables
            .map((t) => TableMeta.fromJson(t as Map<String, dynamic>))
            .toList();

        debugPrint('[v0] TableProvider: detected ${_tables.length} table(s)');
      } else {
        _errorMessage = 'Failed to detect tables (${response.statusCode})';
        debugPrint('[v0] TableProvider.detectTables failed: ${response.body}');
      }
    } catch (e) {
      _errorMessage = 'Network error: $e';
      debugPrint('[v0] TableProvider.detectTables error: $e');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // ── Selection management ──────────────────────────────────────────────────

  void toggleSelection(int tableIndex) {
    if (_selectedIndices.contains(tableIndex)) {
      _selectedIndices.remove(tableIndex);
    } else {
      _selectedIndices.add(tableIndex);
    }
    _successMessage = null;
    notifyListeners();
  }

  void selectAll() {
    _selectedIndices.addAll(_tables.map((t) => t.index));
    notifyListeners();
  }

  void clearSelection() {
    _selectedIndices.clear();
    notifyListeners();
  }

  // ── Preset management ─────────────────────────────────────────────────────

  void setPreset(String preset) {
    _activePreset   = preset;
    _successMessage = null;

    // Reset custom rules to preset defaults
    switch (preset) {
      case 'academic':
        _customRules = {
          'header_bold':  true,
          'banded_rows':  true,
          'borders':      true,
          'center_table': true,
          'repeat_header':true,
          'auto_fit':     true,
        };
        break;
      case 'professional':
        _customRules = {
          'header_bold':  true,
          'banded_rows':  false,
          'borders':      true,
          'center_table': true,
          'repeat_header':true,
          'auto_fit':     true,
        };
        break;
      case 'minimal':
        _customRules = {
          'header_bold':  false,
          'banded_rows':  false,
          'borders':      true,
          'center_table': false,
          'repeat_header':false,
          'auto_fit':     true,
        };
        break;
    }
    notifyListeners();
  }

  void toggleRule(String key, bool value) {
    _customRules[key]= value;
    _successMessage  = null;
    notifyListeners();
  }

  // ── Apply formatting ──────────────────────────────────────────────────────

  Future<bool> applyFormatting(int documentId, int userId) async {
    if (_selectedIndices.isEmpty) return false;

    _isFormatting   = true;
    _errorMessage   = null;
    _successMessage = null;
    notifyListeners();

    try {
      final url = '$_baseUrl/tables/format/$documentId?user_id=$userId';
      debugPrint('[v0] TableProvider.applyFormatting → $url');
      debugPrint('[v0]   indices=${_selectedIndices.toList()}  preset=$_activePreset');

      // Build custom_rules override — only pass keys where value differs
      // from the preset default (keeps payload small; backend merges with preset)
      final rulesPayload = <String, dynamic>{};
      _customRules.forEach((k, v) => rulesPayload[k] = v);

      final response = await http.post(
        Uri.parse(url),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'selected_indices': _selectedIndices.toList()..sort(),
          'preset':           _activePreset,
          'custom_rules':     rulesPayload,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final count = (data['formatted_tables'] as List?)?.length ?? 0;
        _successMessage = '$count table(s) formatted successfully '
            'with "${_activePreset}" preset.';
        debugPrint('[v0] TableProvider: formatting success — $_successMessage');

        // Re-detect so issue counts update
        await detectTables(documentId, userId);
        return true;
      } else {
        _errorMessage = 'Formatting failed (${response.statusCode}): ${response.body}';
        debugPrint('[v0] TableProvider.applyFormatting failed: ${response.body}');
        return false;
      }
    } catch (e) {
      _errorMessage = 'Network error: $e';
      debugPrint('[v0] TableProvider.applyFormatting error: $e');
      return false;
    } finally {
      _isFormatting = false;
      notifyListeners();
    }
  }

  // ── Utility ───────────────────────────────────────────────────────────────

  void clearMessages() {
    _errorMessage   = null;
    _successMessage = null;
    notifyListeners();
  }

  void reset() {
    _tables           = [];
    _isLoading        = false;
    _isFormatting     = false;
    _errorMessage     = null;
    _successMessage   = null;
    _selectedIndices.clear();
    _activePreset     = 'academic';
    notifyListeners();
  }
}