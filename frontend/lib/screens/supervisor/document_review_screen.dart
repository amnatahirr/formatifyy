import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../widgets/admin/admin_ui.dart';

/// Yellow for unresolved comments, gray for resolved-only paragraphs.
const Color _unresolvedHighlight = Color(0xFFFFF3C4);
const Color _resolvedHighlight = Color(0xFF9CA3AF);

class DocumentReviewScreen extends StatefulWidget {
  final int groupId;
  final int documentId;
  final String? documentTitle;

  const DocumentReviewScreen({
    super.key,
    required this.groupId,
    required this.documentId,
    this.documentTitle,
  });

  @override
  State<DocumentReviewScreen> createState() => _DocumentReviewScreenState();
}

class _DocumentReviewScreenState extends State<DocumentReviewScreen> {
  final SupervisorApiService _api = SupervisorApiService();
  DocumentReviewModel? _review;
  String? _error;
  bool _loading = true;
  bool _busy = false;
  bool _downloading = false;

  @override
  void initState() {
    super.initState();
    _loadReview();
  }

  Future<void> _loadReview() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final review = await _api.fetchDocumentReview(
        userId: userId,
        groupId: widget.groupId,
        documentId: widget.documentId,
      );
      if (mounted) setState(() => _review = review);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _downloadFile() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _downloading = true);
    try {
      final path = await _api.downloadGroupDocument(
        userId: userId,
        groupId: widget.groupId,
        documentId: widget.documentId,
        preferredFilename: _review?.document.filename,
      );
      if (!mounted) return;
      showAdminSnackBar(context, 'Saved to $path');
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _downloading = false);
    }
  }

  Future<void> _addComment(DocumentParagraphModel paragraph) async {
    final controller = TextEditingController();
    String? errorText;
    final comment = await showDialog<String>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              backgroundColor: AdminColors.surface,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              title: const Text('Add Comment'),
              content: SizedBox(
                width: 440,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'This comment will be linked to the selected paragraph and the student will be notified.',
                      style: TextStyle(color: Colors.white.withOpacity(0.7), height: 1.4),
                    ),
                    const SizedBox(height: 14),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AdminColors.card,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: AdminColors.border),
                      ),
                      child: Text(
                        paragraph.text,
                        maxLines: 4,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(color: Colors.white.withOpacity(0.75), height: 1.4, fontSize: 13),
                      ),
                    ),
                    const SizedBox(height: 14),
                    TextField(
                      controller: controller,
                      maxLines: 4,
                      autofocus: true,
                      decoration: InputDecoration(
                        labelText: 'Comment',
                        hintText: 'Write feedback for the student…',
                        errorText: errorText,
                        filled: true,
                        fillColor: AdminColors.card,
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext),
                  child: const Text('Cancel'),
                ),
                ElevatedButton(
                  onPressed: () {
                    final text = controller.text.trim();
                    if (text.isEmpty) {
                      setDialogState(() => errorText = 'Enter a comment');
                      return;
                    }
                    Navigator.pop(dialogContext, text);
                  },
                  child: const Text('Add Comment'),
                ),
              ],
            );
          },
        );
      },
    );
    controller.dispose();
    if (comment == null || comment.trim().isEmpty) return;

    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _busy = true);
    try {
      final review = await _api.addParagraphComment(
        userId: userId,
        groupId: widget.groupId,
        documentId: widget.documentId,
        paragraphId: paragraph.id,
        commentText: comment.trim(),
      );
      if (!mounted) return;
      setState(() => _review = review);
      showAdminSnackBar(context, 'Comment added. Student notified.');
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _resolveComments(DocumentParagraphModel paragraph) async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _busy = true);
    try {
      final review = await _api.resolveParagraphComments(
        userId: userId,
        groupId: widget.groupId,
        documentId: widget.documentId,
        paragraphId: paragraph.id,
      );
      if (!mounted) return;
      setState(() => _review = review);
      showAdminSnackBar(context, 'Comments marked as resolved.');
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _onParagraphLongPress(DocumentParagraphModel paragraph) async {
    if (_busy) return;
    final action = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) {
        return Container(
          margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          decoration: BoxDecoration(
            color: AdminColors.surface,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: AdminColors.border.withOpacity(0.8)),
          ),
          child: SafeArea(
            top: false,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const SizedBox(height: 10),
                Container(
                  width: 42,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.22),
                    borderRadius: BorderRadius.circular(99),
                  ),
                ),
                ListTile(
                  leading: const Icon(Icons.add_comment_outlined, color: AdminColors.primary),
                  title: const Text('Add Comment', style: TextStyle(color: Colors.white)),
                  onTap: () => Navigator.pop(sheetContext, 'comment'),
                ),
                if (paragraph.hasUnresolvedComments)
                  ListTile(
                    leading: const Icon(Icons.check_circle_outline, color: AdminColors.success),
                    title: const Text('Mark Resolved', style: TextStyle(color: Colors.white)),
                    subtitle: Text(
                      'Turns this paragraph gray',
                      style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 12),
                    ),
                    onTap: () => Navigator.pop(sheetContext, 'resolve'),
                  ),
                ListTile(
                  leading: Icon(Icons.close_rounded, color: Colors.white.withOpacity(0.6)),
                  title: Text('Cancel', style: TextStyle(color: Colors.white.withOpacity(0.75))),
                  onTap: () => Navigator.pop(sheetContext),
                ),
                const SizedBox(height: 8),
              ],
            ),
          ),
        );
      },
    );

    if (action == 'comment') {
      await _addComment(paragraph);
    } else if (action == 'resolve') {
      await _resolveComments(paragraph);
    }
  }

  @override
  Widget build(BuildContext context) {
    final title = _review?.document.title.isNotEmpty == true
        ? _review!.document.title
        : (widget.documentTitle ?? 'Document Review');

    return Scaffold(
      backgroundColor: AdminColors.background,
      body: Column(
        children: [
          Container(
            height: 72,
            decoration: BoxDecoration(
              color: AdminColors.surface,
              border: Border(bottom: BorderSide(color: AdminColors.border.withOpacity(0.5))),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                IconButton(
                  tooltip: 'Back',
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.arrow_back_rounded, color: Colors.white),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Colors.white),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      Text(
                        'Long-press a paragraph to add a comment',
                        style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.5)),
                      ),
                    ],
                  ),
                ),
                if (_busy || _downloading)
                  const Padding(
                    padding: EdgeInsets.only(right: 8),
                    child: SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2, color: AdminColors.primary),
                    ),
                  ),
                IconButton(
                  tooltip: 'Download file',
                  onPressed: (_busy || _downloading) ? null : _downloadFile,
                  icon: const Icon(Icons.download_rounded, color: Colors.white),
                ),
              ],
            ),
          ),
          Expanded(child: _buildBody()),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const AdminPage(child: AdminLoadingView());
    }
    if (_error != null) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _loadReview));
    }
    final review = _review;
    if (review == null) {
      return const AdminPage(child: AdminEmptyView(message: 'Document review data is unavailable.'));
    }

    return AdminPage(
      onRefresh: _loadReview,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageHeader(
            title: review.document.title,
            subtitle: review.groupTitle.isEmpty
                ? 'Review submission paragraph by paragraph'
                : '${review.groupTitle} · ${review.document.statusLabel}',
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 8,
            children: [
              _LegendChip(color: _unresolvedHighlight, label: 'Unresolved comment'),
              _LegendChip(color: _resolvedHighlight.withOpacity(0.55), label: 'Resolved comment'),
              _LegendChip(color: AdminColors.card, label: 'No comment', bordered: true),
            ],
          ),
          const SizedBox(height: 20),
          if (review.paragraphs.isEmpty)
            const AdminEmptyView(message: 'This document has no paragraphs to review yet.')
          else
            ...review.paragraphs.map(
              (paragraph) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _ParagraphCard(
                  paragraph: paragraph,
                  onLongPress: () => _onParagraphLongPress(paragraph),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _LegendChip extends StatelessWidget {
  final Color color;
  final String label;
  final bool bordered;

  const _LegendChip({
    required this.color,
    required this.label,
    this.bordered = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(bordered ? 1 : 0.9),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: bordered ? AdminColors.border : color.withOpacity(0.8)),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: bordered ? Colors.white.withOpacity(0.7) : const Color(0xFF1F2937),
        ),
      ),
    );
  }
}

class _ParagraphCard extends StatelessWidget {
  final DocumentParagraphModel paragraph;
  final VoidCallback onLongPress;

  const _ParagraphCard({
    required this.paragraph,
    required this.onLongPress,
  });

  Color get _background {
    switch (paragraph.highlight) {
      case 'unresolved':
        return _unresolvedHighlight;
      case 'resolved':
        return _resolvedHighlight.withOpacity(0.45);
      default:
        return AdminColors.card;
    }
  }

  Color get _textColor {
    switch (paragraph.highlight) {
      case 'unresolved':
        return const Color(0xFF1F2937);
      case 'resolved':
        return const Color(0xFF111827);
      default:
        return Colors.white.withOpacity(0.88);
    }
  }

  @override
  Widget build(BuildContext context) {
    final unresolved = paragraph.comments.where((c) => !c.isResolved).toList();
    final resolved = paragraph.comments.where((c) => c.isResolved).toList();

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onLongPress: onLongPress,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: _background,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: paragraph.highlight == 'unresolved'
                  ? AdminColors.warning.withOpacity(0.7)
                  : paragraph.highlight == 'resolved'
                      ? Colors.white.withOpacity(0.15)
                      : AdminColors.border,
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.12),
                blurRadius: 12,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    'Paragraph ${paragraph.sortOrder}',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: paragraph.highlight == 'none'
                          ? Colors.white.withOpacity(0.45)
                          : const Color(0xFF4B5563),
                    ),
                  ),
                  const Spacer(),
                  Icon(
                    Icons.touch_app_outlined,
                    size: 14,
                    color: paragraph.highlight == 'none'
                        ? Colors.white.withOpacity(0.35)
                        : const Color(0xFF6B7280),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                paragraph.text,
                style: TextStyle(
                  fontSize: 14,
                  height: 1.55,
                  color: _textColor,
                  fontWeight: FontWeight.w500,
                ),
              ),
              if (unresolved.isNotEmpty) ...[
                const SizedBox(height: 12),
                ...unresolved.map(
                  (comment) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Text(
                      'Comment: ${comment.commentText}',
                      style: const TextStyle(
                        fontSize: 12,
                        height: 1.35,
                        color: Color(0xFF92400E),
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
              ],
              if (resolved.isNotEmpty && unresolved.isEmpty) ...[
                const SizedBox(height: 10),
                Text(
                  '${resolved.length} resolved comment${resolved.length == 1 ? '' : 's'}',
                  style: const TextStyle(
                    fontSize: 11,
                    color: Color(0xFF374151),
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
