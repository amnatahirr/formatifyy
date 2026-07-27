import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../models/json_parse.dart';
import '../services/image_replacement_service.dart';
import 'image_replacement_dialog.dart';

AppPalette _ap = AppPalette.dark;

Color get _bg => _ap.scaffold;
Color get _surface => _ap.surface;
Color get _surface2 => _ap.surfaceElevated;
Color get _border => _ap.border;
Color get _textPri => _ap.textPrimary;
Color get _textSec => _ap.textSecondary;
const _green = Color(0xFF10B981);
const _yellow = Color(0xFFFACC15);
const _red = Color(0xFFEF4444);
const _blue = Color(0xFF4A9EFF);

/// Side-by-side original / corrected document preview with issue highlights.
class DocumentPreviewPanel extends StatefulWidget {
  final List<Map<String, dynamic>> blocks;
  final List<Map<String, dynamic>> issues;
  final String imageBaseUrl;
  final int documentId;
  final Map<String, String> appliedFixes;
  final Set<String> ignoredIssueIds;
  final Set<String> resolvedIssueIds;
  final void Function(String issueId, String correctedText) onApplyFix;
  final void Function(String issueId) onIgnoreIssue;
  final void Function(Map<String, dynamic> result, Map<String, dynamic> issue)? onImageReplaced;
  final void Function(Map<String, dynamic> result, Map<String, dynamic> issue)? onImageRemoved;

  const DocumentPreviewPanel({
    super.key,
    required this.blocks,
    required this.issues,
    required this.imageBaseUrl,
    required this.documentId,
    required this.appliedFixes,
    required this.ignoredIssueIds,
    this.resolvedIssueIds = const {},
    required this.onApplyFix,
    required this.onIgnoreIssue,
    this.onImageReplaced,
    this.onImageRemoved,
  });

  @override
  State<DocumentPreviewPanel> createState() => _DocumentPreviewPanelState();
}

class _DocumentPreviewPanelState extends State<DocumentPreviewPanel> {
  String? _selectedBlockKey;
  late ImageReplacementService _replacementService;

  @override
  void initState() {
    super.initState();
    _replacementService = ImageReplacementService(imageBaseUrl: widget.imageBaseUrl);
  }

  String _imageUrl(String rawPath) {
    if (rawPath.isEmpty) return '';
    final clean = rawPath.startsWith('uploads/')
        ? rawPath.substring('uploads/'.length)
        : rawPath;
    return '${widget.imageBaseUrl}/uploads/$clean';
  }

  List<Map<String, dynamic>> _issuesForBlock(Map<String, dynamic> block) {
    final pid = block['paragraph_id'] as String? ?? '';
    final iid = block['image_id'] as String? ?? '';
    return widget.issues.where((issue) {
      if (widget.ignoredIssueIds.contains(issue['issue_id'] as String? ?? '')) {
        return false;
      }
      if (widget.resolvedIssueIds.contains(issue['issue_id'] as String? ?? '')) {
        return false;
      }
      if (pid.isNotEmpty && issue['paragraph_id'] == pid) return true;
      if (iid.isNotEmpty && issue['image_id'] == iid) return true;
      return false;
    }).map((e) => Map<String, dynamic>.from(e)).toList();
  }

  Color _highlightColor(List<Map<String, dynamic>> blockIssues) {
    if (blockIssues.isEmpty) return Colors.transparent;
    final hasMajor = blockIssues.any(
      (i) => (i['severity'] as String? ?? '').toLowerCase() == 'major',
    );
    return hasMajor ? _red.withOpacity(0.22) : _yellow.withOpacity(0.22);
  }

  Color _borderColor(List<Map<String, dynamic>> blockIssues) {
    if (blockIssues.isEmpty) return _border;
    final hasMajor = blockIssues.any(
      (i) => (i['severity'] as String? ?? '').toLowerCase() == 'major',
    );
    return hasMajor ? _red.withOpacity(0.6) : _yellow.withOpacity(0.6);
  }

  String _correctedText(Map<String, dynamic> block, List<Map<String, dynamic>> blockIssues) {
    final pid = block['paragraph_id'] as String? ?? '';
    if (pid.isNotEmpty && widget.appliedFixes.containsKey(pid)) {
      return widget.appliedFixes[pid]!;
    }
    final original = block['text'] as String? ?? '';
    final grammar = blockIssues.firstWhere(
      (i) => (i['function'] as String? ?? '') == 'grammar' && (i['suggestion'] as String? ?? '').isNotEmpty,
      orElse: () => {},
    );
    if (grammar.isNotEmpty) {
      final suggestion = grammar['suggestion'] as String? ?? '';
      final snippet = grammar['original'] as String? ?? grammar['current'] as String? ?? '';
      if (snippet.isNotEmpty && original.contains(snippet)) {
        return original.replaceFirst(snippet, suggestion);
      }
      if (suggestion.isNotEmpty) return suggestion;
    }
    return original;
  }

  void _openFixPanel(Map<String, dynamic> block, List<Map<String, dynamic>> blockIssues) {
    if (blockIssues.isEmpty) return;
    final issue = blockIssues.first;
    final issueId = issue['issue_id'] as String? ?? '';
    final pid = block['paragraph_id'] as String? ?? '';

    showModalBottomSheet(
      context: context,
      backgroundColor: _surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _chip(issue['category'] as String? ?? 'Issue', _blue),
                const SizedBox(width: 8),
                _chip(
                  (issue['severity'] as String? ?? 'minor').toUpperCase(),
                  (issue['severity'] as String? ?? '') == 'major' ? _red : _yellow,
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              issue['description'] as String? ?? issue['reason'] as String? ?? '',
              style: TextStyle(color: _textPri, fontSize: 14),
            ),
            if ((issue['suggestion'] as String? ?? '').isNotEmpty) ...[
              const SizedBox(height: 12),
              Text('Suggestion', style: TextStyle(color: _textSec, fontSize: 11)),
              const SizedBox(height: 4),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: _green.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: _green.withOpacity(0.3)),
                ),
                child: Text(
                  issue['suggestion'] as String,
                  style: const TextStyle(color: _green, fontSize: 13),
                ),
              ),
            ],
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      widget.onIgnoreIssue(issueId);
                      Navigator.pop(ctx);
                    },
                    child: const Text('Ignore'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(backgroundColor: _green),
                    onPressed: () {
                      final corrected = _correctedText(block, blockIssues);
                      if (pid.isNotEmpty) {
                        widget.onApplyFix(issueId, corrected);
                      }
                      Navigator.pop(ctx);
                    },
                    child: const Text('Apply Fix'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _showReplaceDialog(Map<String, dynamic> block, Map<String, dynamic> issue) {
    showDialog(
      context: context,
      builder: (ctx) => ImageReplacementDialog(
        documentId: widget.documentId,
        imageIndex: jsonIntOr(issue['image_index'], jsonIntOr(block['image_index'], 0)),
        currentImagePath: block['image_path'] as String? ?? '',
        service: _replacementService,
        onSuccess: (result) {
          widget.onImageReplaced?.call(result, issue);
        },
        onError: (e) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error: $e'), backgroundColor: _red),
          );
        },
      ),
    );
  }

  Future<void> _confirmAndRemove(Map<String, dynamic> block, Map<String, dynamic> issue) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _surface,
        title: Text('Remove Image?', style: TextStyle(color: _textPri)),
        content: Text(
          'This permanently deletes the image from the document. '
          'A nearby figure caption will also be removed if present.',
          style: TextStyle(color: _textSec, fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text('Cancel', style: TextStyle(color: _textSec)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: _red,
              foregroundColor: Colors.white,
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    try {
      final result = await _replacementService.removeImage(
        documentId: widget.documentId,
        imageIndex: jsonIntOr(issue['image_index'], jsonIntOr(block['image_index'], 0)),
      );
      if (!mounted) return;
      widget.onImageRemoved?.call(result, issue);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Remove failed: $e'), backgroundColor: _red),
      );
    }
  }

  Widget _chip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Text(label, style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w600)),
    );
  }

  Widget _buildColumn({
    required String title,
    required bool corrected,
    required Color headerColor,
  }) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            color: headerColor.withOpacity(0.12),
            child: Text(
              title,
              style: TextStyle(color: headerColor, fontWeight: FontWeight.w700, fontSize: 13),
            ),
          ),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: widget.blocks.length,
              itemBuilder: (ctx, i) {
                final block = Map<String, dynamic>.from(widget.blocks[i] as Map);
                final type = block['type'] as String? ?? 'paragraph';
                final blockIssues = _issuesForBlock(block);
                final blockKey = block['paragraph_id'] as String? ?? block['image_id'] as String? ?? 'b$i';
                final isSelected = _selectedBlockKey == blockKey;

                if (type == 'image') {
                  return _buildImageBlock(block, blockIssues, corrected);
                }

                final text = corrected ? _correctedText(block, blockIssues) : (block['text'] as String? ?? '');
                final highlight = corrected ? _highlightColor(blockIssues) : Colors.transparent;
                final borderColor = blockIssues.isNotEmpty ? _borderColor(blockIssues) : _border;

                return GestureDetector(
                  onTap: blockIssues.isNotEmpty ? () {
                    setState(() => _selectedBlockKey = blockKey);
                    _openFixPanel(block, blockIssues);
                  } : null,
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 6),
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: isSelected ? _surface2 : _surface,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: borderColor, width: blockIssues.isNotEmpty ? 1.5 : 1),
                    ),
                    child: Container(
                      decoration: BoxDecoration(
                        color: highlight,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      padding: const EdgeInsets.all(4),
                      child: Text(
                        text,
                        style: TextStyle(
                          color: type == 'heading' ? _textPri : _textSec,
                          fontSize: type == 'heading' ? 14 : 12,
                          fontWeight: type == 'heading' ? FontWeight.w700 : FontWeight.w400,
                          decoration: corrected && blockIssues.isNotEmpty && widget.appliedFixes.containsKey(block['paragraph_id'])
                              ? TextDecoration.none
                              : null,
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildImageBlock(
    Map<String, dynamic> block,
    List<Map<String, dynamic>> blockIssues,
    bool corrected,
  ) {
    final imagePath = block['image_path'] as String? ?? '';
    final imageUrl = _imageUrl(imagePath);
    final ethics = blockIssues.where((i) => (i['function'] as String? ?? '') == 'image_ethics').toList();
    final irrelevant = blockIssues.where((i) => (i['function'] as String? ?? '') == 'image_relevance').toList();
    final isUnethical = ethics.isNotEmpty;
    final isIrrelevant = irrelevant.isNotEmpty;
    final issue = ethics.isNotEmpty ? ethics.first : (irrelevant.isNotEmpty ? irrelevant.first : null);

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: isUnethical ? _red.withOpacity(0.5) : isIrrelevant ? _yellow.withOpacity(0.5) : _border,
          width: 1.5,
        ),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (isUnethical || isIrrelevant)
            Container(
              color: (isUnethical ? _red : _yellow).withOpacity(0.12),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Text(
                isUnethical
                    ? 'Flagged — unethical image (shown for review)'
                    : 'Warning — irrelevant image',
                style: TextStyle(
                  color: isUnethical ? _red : _yellow,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          SizedBox(
            height: 160,
            child: Stack(
              fit: StackFit.expand,
              children: [
                if (imageUrl.isNotEmpty)
                  Image.network(
                    imageUrl,
                    fit: BoxFit.contain,
                    errorBuilder: (_, __, ___) => Center(
                      child: Icon(Icons.broken_image, color: _textSec),
                    ),
                  )
                else
                  Container(
                    color: _surface2,
                    alignment: Alignment.center,
                    child: Icon(Icons.broken_image, color: _textSec),
                  ),
                if (isUnethical)
                  Positioned(
                    left: 0,
                    right: 0,
                    bottom: 0,
                    child: Container(
                      color: _red.withOpacity(0.85),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 5,
                      ),
                      child: const Text(
                        'Unethical image — visible for review',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  )
                else if (isIrrelevant)
                  Container(
                    color: _yellow.withOpacity(0.25),
                    alignment: Alignment.center,
                    child: const Icon(
                      Icons.warning_amber_rounded,
                      color: _yellow,
                      size: 36,
                    ),
                  ),
              ],
            ),
          ),
          if (issue != null && corrected)
            Padding(
              padding: const EdgeInsets.all(10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ElevatedButton.icon(
                    onPressed: () => _showReplaceDialog(block, issue),
                    icon: const Icon(Icons.image_search, size: 16),
                    label: const Text('Replace Image'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _blue,
                      foregroundColor: _textPri,
                    ),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: () => _confirmAndRemove(block, issue),
                    icon: const Icon(Icons.delete_outline, size: 16),
                    label: const Text('Remove Image'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: _red,
                      side: BorderSide(color: _red.withOpacity(0.55)),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    _ap = context.watch<ThemeProvider>().palette;
    if (widget.blocks.isEmpty) {
      return Center(
        child: Text('No document content available for preview.', style: TextStyle(color: _textSec)),
      );
    }

    return Container(
      color: _bg,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildColumn(title: 'Original', corrected: false, headerColor: _textSec),
          VerticalDivider(width: 1, color: _border),
          _buildColumn(title: 'Corrected', corrected: true, headerColor: _green),
        ],
      ),
    );
  }
}
