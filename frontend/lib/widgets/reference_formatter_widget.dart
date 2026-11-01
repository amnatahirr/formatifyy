// lib/widgets/reference_formatter_widget.dart

import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';

import 'tr.dart';
class ReferenceFormatterWidget extends StatefulWidget {
  final int documentId;
  final int userId;

  const ReferenceFormatterWidget({
    Key? key,
    required this.documentId,
    required this.userId,
  }) : super(key: key);

  @override
  State<ReferenceFormatterWidget> createState() =>
      _ReferenceFormatterWidgetState();
}

class _ReferenceFormatterWidgetState extends State<ReferenceFormatterWidget> {
  bool _loadingPreview = false;
  bool _formatting = false;
  bool _formatted = false;
  bool _hasScanned = false; // ← tracks whether the user has pressed Scan once

  String? _error;

  int _refsFound = 0;
  int _duplicates = 0;
  int _incomplete = 0;
  int _urlsLinked = 0;
  String _message = '';
  List<String> _preview = [];

  // ── API ────────────────────────────────────────────────────────────────────

  Future<void> _loadPreview() async {
    // Guard: don't fire if already in flight
    if (_loadingPreview) return;

    setState(() {
      _loadingPreview = true;
      _error = null;
      _hasScanned = true;
    });

    try {
      final base = ApiConfig.getBaseUrl();
      final url = '$base/references/preview/${widget.documentId}';
      debugPrint('[RefWidget] GET $url');

      final res = await http
          .get(
            Uri.parse(url),
            headers: {'Content-Type': 'application/json'},
          )
          .timeout(const Duration(seconds: 30));

      debugPrint('[RefWidget] status=${res.statusCode}  body=${res.body}');

      if (!mounted) return;

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        setState(() {
          _refsFound = (data['references_found'] as num?)?.toInt() ?? 0;
          _duplicates = (data['duplicates_removed'] as num?)?.toInt() ?? 0;
          _incomplete = (data['incomplete_count'] as num?)?.toInt() ?? 0;
          _urlsLinked = (data['urls_linked'] as num?)?.toInt() ?? 0;
          _message = data['message'] as String? ?? '';
          _preview = List<String>.from(data['preview'] as List? ?? []);

          // Backend returns success=false when no References section found
          if (data['success'] == false) {
            _error = data['message'] as String? ??
                'No References section found in this document.';
          }
        });
      } else {
        // Parse the FastAPI error detail if present
        String detail = res.body;
        try {
          final json = jsonDecode(res.body) as Map<String, dynamic>;
          detail = json['detail'] as String? ?? res.body;
        } catch (_) {}
        setState(() => _error = 'Scan failed (${res.statusCode}): $detail');
      }
    } on Exception catch (e) {
      if (!mounted) return;
      setState(() => _error = 'Network error: $e');
      debugPrint('[RefWidget] Exception: $e');
    } finally {
      if (mounted) setState(() => _loadingPreview = false);
    }
  }

  Future<void> _formatReferences() async {
    if (_formatting) return;
    setState(() {
      _formatting = true;
      _error = null;
    });

    try {
      final base = ApiConfig.getBaseUrl();
      final url =
          '$base/references/format/${widget.documentId}?user_id=${widget.userId}';
      debugPrint('[RefWidget] POST $url');

      final res = await http
          .post(
            Uri.parse(url),
            headers: {'Content-Type': 'application/json'},
          )
          .timeout(const Duration(seconds: 60));

      debugPrint('[RefWidget] format status=${res.statusCode}');

      if (!mounted) return;

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        setState(() {
          _formatted = true;
          _refsFound =
              (data['references_found'] as num?)?.toInt() ?? _refsFound;
          _duplicates =
              (data['duplicates_removed'] as num?)?.toInt() ?? _duplicates;
          _incomplete =
              (data['incomplete_count'] as num?)?.toInt() ?? _incomplete;
          _urlsLinked =
              (data['urls_linked'] as num?)?.toInt() ?? _urlsLinked;
          _message = data['message'] as String? ?? '';
        });
      } else {
        String detail = res.body;
        try {
          final json = jsonDecode(res.body) as Map<String, dynamic>;
          detail = json['detail'] as String? ?? res.body;
        } catch (_) {}
        setState(() => _error = 'Format failed (${res.statusCode}): $detail');
      }
    } on Exception catch (e) {
      if (!mounted) return;
      setState(() => _error = 'Network error: $e');
    } finally {
      if (mounted) setState(() => _formatting = false);
    }
  }

  // ── Build ──────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F2E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF2D3748)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildHeader(),

          // ── Error banner — always shown when _error is set ──────────────
          if (_error != null) _buildErrorBanner(),

          // ── Success banner ───────────────────────────────────────────────
          if (_formatted && _error == null) _buildSuccessBanner(),

          // ── Stats + preview — shown after a successful scan ──────────────
          if (_refsFound > 0) ...[
            _buildStatsRow(),
            const Divider(color: Color(0xFF2D3748), height: 1),
            if (_preview.isNotEmpty) _buildPreviewList(),
          ],

          // ── "No refs found" hint after scan with 0 results ───────────────
          if (_hasScanned && _refsFound == 0 && _error == null)
            _buildNoRefsHint(),

          _buildActionRow(),
        ],
      ),
    );
  }

  // ── Widgets ────────────────────────────────────────────────────────────────

  Widget _buildHeader() => Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: const Color(0xFF6366F1).withOpacity(0.15),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.format_list_numbered,
                  color: Color(0xFF6366F1), size: 20),
            ),
            const SizedBox(width: 12),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Tr('Reference Formatter',
                      style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: Colors.white)),
                  Tr('Auto-format your References section',
                      style:
                          TextStyle(fontSize: 11, color: Colors.white54)),
                ],
              ),
            ),
            // Refresh icon — re-scan at any time
            if (_loadingPreview)
              const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                    strokeWidth: 2, color: Color(0xFF6366F1)),
              )
            else
              IconButton(
                icon: const Icon(Icons.refresh, size: 18, color: Colors.white38),
                tooltip: 'Re-scan',
                onPressed: _loadPreview,
              ),
          ],
        ),
      );

  Widget _buildErrorBanner() => Container(
        margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFFEF4444).withOpacity(0.1),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: const Color(0xFFEF4444).withOpacity(0.4)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.error_outline,
                color: Color(0xFFEF4444), size: 16),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                _error!,
                style: const TextStyle(
                    color: Color(0xFFEF4444), fontSize: 12, height: 1.4),
              ),
            ),
          ],
        ),
      );

  Widget _buildSuccessBanner() => Container(
        margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFF10B981).withOpacity(0.1),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: const Color(0xFF10B981).withOpacity(0.4)),
        ),
        child: Row(
          children: [
            const Icon(Icons.check_circle,
                color: Color(0xFF10B981), size: 16),
            const SizedBox(width: 8),
            Expanded(
              child: Text(_message,
                  style: const TextStyle(
                      color: Color(0xFF10B981), fontSize: 12)),
            ),
          ],
        ),
      );

  Widget _buildNoRefsHint() => Container(
        margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFFF59E0B).withOpacity(0.08),
          borderRadius: BorderRadius.circular(8),
          border:
              Border.all(color: const Color(0xFFF59E0B).withOpacity(0.3)),
        ),
        child: const Row(
          children: [
            Icon(Icons.info_outline,
                color: Color(0xFFF59E0B), size: 16),
            SizedBox(width: 8),
            Expanded(
              child: Text(
                'No "References", "Bibliography" or "Works Cited" heading '
                'was found in this document. Make sure your reference section '
                'has a heading with one of those exact names.',
                style: TextStyle(
                    color: Color(0xFFF59E0B), fontSize: 12, height: 1.4),
              ),
            ),
          ],
        ),
      );

  Widget _buildStatsRow() => Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
        child: Wrap(
          spacing: 10,
          runSpacing: 8,
          children: [
            _chip(Icons.format_quote, '$_refsFound References',
                const Color(0xFF6366F1)),
            if (_duplicates > 0)
              _chip(Icons.copy_outlined,
                  '$_duplicates Duplicates Removed', const Color(0xFFF59E0B)),
            if (_incomplete > 0)
              _chip(Icons.warning_amber_rounded,
                  '$_incomplete Need Review', const Color(0xFFEF4444)),
            if (_urlsLinked > 0)
              _chip(Icons.link, '$_urlsLinked URLs Linked',
                  const Color(0xFF10B981)),
          ],
        ),
      );

  Widget _chip(IconData icon, String label, Color color) => Container(
        padding:
            const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 13, color: color),
            const SizedBox(width: 5),
            Text(label,
                style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: color)),
          ],
        ),
      );

  Widget _buildPreviewList() => ExpansionTile(
        tilePadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 0),
        title: Text('Preview (${_preview.length} references)',
            style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: Colors.white70)),
        iconColor: Colors.white38,
        collapsedIconColor: Colors.white38,
        children: [
          ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 300),
            child: ListView.separated(
              shrinkWrap: true,
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
              itemCount: _preview.length,
              separatorBuilder: (_, __) =>
                  const Divider(color: Color(0xFF2D3748), height: 16),
              itemBuilder: (ctx, i) {
                final isIncomplete =
                    _preview[i].contains('[MANUAL CHECK REQUIRED]');
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      margin:
                          const EdgeInsets.only(top: 5, right: 10),
                      width: 6,
                      height: 6,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: isIncomplete
                            ? const Color(0xFFEF4444)
                            : const Color(0xFF6366F1),
                      ),
                    ),
                    Expanded(
                      child: Text(
                        _preview[i],
                        style: TextStyle(
                          fontSize: 11,
                          color: isIncomplete
                              ? const Color(0xFFEF4444)
                              : Colors.white70,
                          height: 1.5,
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
        ],
      );

  Widget _buildActionRow() => Padding(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
        child: Row(
          children: [
            // ── Scan button — always visible until refs are found ──────────
            if (_refsFound == 0)
              OutlinedButton.icon(
                onPressed: _loadingPreview ? null : _loadPreview,
                icon: _loadingPreview
                    ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Color(0xFF6366F1)))
                    : const Icon(Icons.search,
                        size: 15, color: Color(0xFF6366F1)),
                label: Text(
                  _loadingPreview ? 'Scanning…' : 'Scan References',
                  style: const TextStyle(
                      color: Color(0xFF6366F1), fontSize: 13),
                ),
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: Color(0xFF6366F1)),
                  padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 10),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8)),
                ),
              ),

            // ── Format button — shown after successful scan ────────────────
            if (_refsFound > 0)
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: _formatting ? null : _formatReferences,
                  icon: _formatting
                      ? const SizedBox(
                          width: 15,
                          height: 15,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.white))
                      : Icon(
                          _formatted
                              ? Icons.check_circle_outline
                              : Icons.auto_fix_high,
                          size: 16),
                  label: Text(
                    _formatting
                        ? 'Formatting…'
                        : _formatted
                            ? 'Re-format References'
                            : 'Format References',
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _formatted
                        ? const Color(0xFF10B981)
                        : const Color(0xFF6366F1),
                    foregroundColor: Colors.white,
                    padding:
                        const EdgeInsets.symmetric(vertical: 12),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8)),
                  ),
                ),
              ),
          ],
        ),
      );
}