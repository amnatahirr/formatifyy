import 'package:flutter/material.dart';
import '../models/json_parse.dart';
import '../services/image_replacement_service.dart';
import 'image_replacement_dialog.dart';

const _bg = Color(0xFF0D1117);
const _surface = Color(0xFF161B22);
const _surface2 = Color(0xFF1C2333);
const _border = Color(0xFF30363D);
const _textPri = Colors.white;
const _textSec = Color(0xFF8B949E);
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
              style: const TextStyle(color: _textPri, fontSize: 14),
            ),
            if ((issue['suggestion'] as String? ?? '').isNotEmpty) ...[
              const SizedBox(height: 12),
              const Text('Suggestion', style: TextStyle(color: _textSec, fontSize: 11)),
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
                isUnethical ? 'Blocked — unethical image' : 'Warning — irrelevant image',
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
                if (isUnethical)
                  Container(
                    color: _surface2,
                    alignment: Alignment.center,
                    child: const Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.block, color: _red, size: 40),
                        SizedBox(height: 8),
                        Text('Image blocked', style: TextStyle(color: _red, fontSize: 12)),
                      ],
                    ),
                  )
                else if (imageUrl.isNotEmpty)
                  Image.network(
                    imageUrl,
                    fit: BoxFit.contain,
                    errorBuilder: (_, __, ___) => const Center(
                      child: Icon(Icons.broken_image, color: _textSec),
                    ),
                  ),
                if (isIrrelevant && !isUnethical)
                  Container(
                    color: _yellow.withOpacity(0.25),
                    alignment: Alignment.center,
                    child: const Icon(Icons.warning_amber_rounded, color: _yellow, size: 36),
                  ),
              ],
            ),
          ),
          if (issue != null && corrected)
            Padding(
              padding: const EdgeInsets.all(10),
              child: ElevatedButton.icon(
                onPressed: () => _showReplaceDialog(block, issue),
                icon: const Icon(Icons.image_search, size: 16),
                label: const Text('Replace Image'),
                style: ElevatedButton.styleFrom(backgroundColor: _blue, foregroundColor: _textPri),
              ),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (widget.blocks.isEmpty) {
      return const Center(
        child: Text('No document content available for preview.', style: TextStyle(color: _textSec)),
      );
    }

    return Container(
      color: _bg,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _buildColumn(title: 'Original', corrected: false, headerColor: _textSec),
          const VerticalDivider(width: 1, color: _border),
          _buildColumn(title: 'Corrected', corrected: true, headerColor: _green),
        ],
      ),
    );
  }
}
