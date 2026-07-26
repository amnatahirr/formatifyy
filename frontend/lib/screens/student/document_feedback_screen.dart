import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/student_api_service.dart';

/// Student view of supervisor paragraph comments — reply + mark resolved.
class DocumentFeedbackScreen extends StatefulWidget {
  final int groupId;
  final int documentId;
  final int? focusCommentId;

  const DocumentFeedbackScreen({
    super.key,
    required this.groupId,
    required this.documentId,
    this.focusCommentId,
  });

  @override
  State<DocumentFeedbackScreen> createState() => _DocumentFeedbackScreenState();
}

class _DocumentFeedbackScreenState extends State<DocumentFeedbackScreen> {
  final StudentApiService _api = StudentApiService();
  final Map<int, TextEditingController> _replyControllers = {};
  final ScrollController _scrollController = ScrollController();
  final Map<int, GlobalKey> _commentKeys = {};

  DocumentReviewModel? _review;
  bool _loading = true;
  String? _error;
  int? _busyCommentId;
  bool _didFocusComment = false;

  static const _card = Color(0xFF161B22);
  static const _border = Color(0x22FFFFFF);
  static const _accent = Color(0xFF3B82F6);
  static const _unresolved = Color(0xFFFFF3C4);
  static const _resolved = Color(0xFF9CA3AF);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _load();
    });
  }

  @override
  void dispose() {
    for (final c in _replyControllers.values) {
      c.dispose();
    }
    _scrollController.dispose();
    super.dispose();
  }

  TextEditingController _controllerFor(int commentId) {
    return _replyControllers.putIfAbsent(commentId, TextEditingController.new);
  }

  GlobalKey _keyFor(int commentId) {
    return _commentKeys.putIfAbsent(commentId, GlobalKey.new);
  }

  Future<void> _load() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) {
      setState(() {
        _loading = false;
        _error = 'Please sign in again.';
      });
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final review = await _api.fetchDocumentComments(
        userId: userId,
        groupId: widget.groupId,
        documentId: widget.documentId,
      );
      if (!mounted) return;
      setState(() {
        _review = review;
        _loading = false;
      });
      _scheduleFocusComment();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString().replaceFirst(RegExp(r'^Exception:\s*'), '');
        _loading = false;
      });
    }
  }

  void _scheduleFocusComment() {
    final focusId = widget.focusCommentId;
    if (focusId == null || _didFocusComment) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || _didFocusComment) return;
      final key = _commentKeys[focusId];
      final ctx = key?.currentContext;
      if (ctx != null) {
        _didFocusComment = true;
        Scrollable.ensureVisible(
          ctx,
          duration: const Duration(milliseconds: 350),
          alignment: 0.2,
          curve: Curves.easeOutCubic,
        );
      }
    });
  }

  Future<void> _resolve(DocumentCommentModel comment) async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _busyCommentId = comment.id);
    try {
      await _api.resolveComment(userId: userId, commentId: comment.id);
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Comment marked as resolved.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Resolve failed: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _busyCommentId = null);
    }
  }

  Future<void> _reply(DocumentCommentModel comment) async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    final text = _controllerFor(comment.id).text.trim();
    if (text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Enter a reply first.')),
      );
      return;
    }

    setState(() => _busyCommentId = comment.id);
    try {
      await _api.replyToComment(
        userId: userId,
        commentId: comment.id,
        replyText: text,
      );
      _controllerFor(comment.id).clear();
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Reply sent.')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Reply failed: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _busyCommentId = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: _card,
        foregroundColor: Colors.white,
        title: Text(
          _review?.document.title.isNotEmpty == true
              ? _review!.document.title
              : 'Document feedback',
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
        ),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(
        child: CircularProgressIndicator(color: _accent, strokeWidth: 2),
      );
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _error!,
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white.withOpacity(0.7)),
              ),
              const SizedBox(height: 12),
              TextButton(onPressed: _load, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }

    final review = _review;
    if (review == null || review.paragraphs.isEmpty) {
      return Center(
        child: Text(
          'No paragraphs yet for this document.',
          style: TextStyle(color: Colors.white.withOpacity(0.55)),
        ),
      );
    }

    final hasAnyComments =
        review.paragraphs.any((p) => p.comments.isNotEmpty);
    final unresolvedCount = review.paragraphs.fold<int>(
      0,
      (sum, p) =>
          sum +
          p.comments
              .where((c) => !c.isResolved && c.parentCommentId == null)
              .length,
    );

    return RefreshIndicator(
      color: _accent,
      backgroundColor: _card,
      onRefresh: _load,
      child: ListView(
        controller: _scrollController,
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
        children: [
          Text(
            review.groupTitle.isNotEmpty
                ? review.groupTitle
                : 'Supervisor feedback',
            style: TextStyle(
              color: Colors.white.withOpacity(0.55),
              fontSize: 13,
            ),
          ),
          if (unresolvedCount > 0) ...[
            const SizedBox(height: 10),
            Text(
              '$unresolvedCount open supervisor comment${unresolvedCount == 1 ? '' : 's'} — reply or mark resolved below.',
              style: const TextStyle(
                color: Color(0xFFFBBF24),
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
          if (!hasAnyComments) ...[
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: _card,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: _border),
              ),
              child: Text(
                'No comments on this document yet.',
                style: TextStyle(color: Colors.white.withOpacity(0.65)),
              ),
            ),
          ],
          const SizedBox(height: 16),
          ...review.paragraphs.map(_paragraphCard),
        ],
      ),
    );
  }

  Widget _paragraphCard(DocumentParagraphModel paragraph) {
    final highlight = paragraph.highlight;
    final bg = switch (highlight) {
      'unresolved' => _unresolved.withOpacity(0.92),
      'resolved' => _resolved.withOpacity(0.35),
      _ => _card,
    };
    final textColor =
        highlight == 'unresolved' ? const Color(0xFF1F2937) : Colors.white;

    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: highlight == 'unresolved'
                ? const Color(0xFFF59E0B).withOpacity(0.5)
                : _border,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              paragraph.text,
              style: TextStyle(
                color: textColor.withOpacity(0.9),
                height: 1.45,
                fontSize: 14,
              ),
            ),
            if (paragraph.comments.isNotEmpty) ...[
              const SizedBox(height: 12),
              ...paragraph.comments.map(
                (c) => _commentBlock(c, darkText: highlight == 'unresolved'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _commentBlock(DocumentCommentModel comment, {required bool darkText}) {
    final muted = darkText
        ? const Color(0xFF4B5563)
        : Colors.white.withOpacity(0.55);
    final strong = darkText ? const Color(0xFF111827) : Colors.white;
    final isReply = comment.parentCommentId != null;
    final busy = _busyCommentId == comment.id;
    final isFocused = widget.focusCommentId == comment.id;

    return Padding(
      key: _keyFor(comment.id),
      padding: EdgeInsets.only(left: isReply ? 12 : 0, bottom: 12, top: 4),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: darkText
              ? Colors.white.withOpacity(0.55)
              : Colors.black.withOpacity(0.25),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isFocused
                ? _accent
                : comment.isResolved
                    ? Colors.white24
                    : const Color(0xFFF59E0B).withOpacity(0.45),
            width: isFocused ? 2 : 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              isReply ? 'Your reply' : 'Supervisor comment',
              style: TextStyle(
                color: muted,
                fontSize: 11,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              comment.commentText,
              style: TextStyle(
                color: strong,
                fontSize: 13,
                height: 1.4,
                fontWeight: FontWeight.w500,
              ),
            ),
            if (comment.createdAt.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                comment.createdAt.length >= 16
                    ? comment.createdAt.substring(0, 16)
                    : comment.createdAt,
                style: TextStyle(color: muted, fontSize: 11),
              ),
            ],
            if (!comment.isResolved && !isReply) ...[
              const SizedBox(height: 10),
              TextField(
                controller: _controllerFor(comment.id),
                enabled: !busy,
                style: TextStyle(color: strong, fontSize: 13),
                decoration: InputDecoration(
                  isDense: true,
                  hintText: 'Write a short reply…',
                  hintStyle: TextStyle(color: muted),
                  filled: true,
                  fillColor: darkText
                      ? Colors.white.withOpacity(0.7)
                      : Colors.white.withOpacity(0.06),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: BorderSide.none,
                  ),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 10,
                  ),
                ),
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _reply(comment),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: busy ? null : () => _reply(comment),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: _accent,
                        side: const BorderSide(color: _accent),
                      ),
                      child: busy
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('Reply'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: busy ? null : () => _resolve(comment),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF10B981),
                        foregroundColor: Colors.white,
                      ),
                      child: const Text('Mark Resolved'),
                    ),
                  ),
                ],
              ),
            ] else if (comment.isResolved && !isReply) ...[
              const SizedBox(height: 8),
              Text(
                'Resolved',
                style: TextStyle(
                  color: const Color(0xFF10B981),
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
