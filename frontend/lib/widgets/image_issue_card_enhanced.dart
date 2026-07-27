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

/// Enhanced image issue card with replacement / removal capability
class ImageIssueCardEnhanced extends StatefulWidget {
  final Map<String, dynamic> issue;
  final String imageBaseUrl;
  final int documentId;
  final int? userId;
  final void Function(Map<String, dynamic> result) onImageReplaced;
  final void Function(Map<String, dynamic> result)? onImageRemoved;
  final VoidCallback? onIgnore;
  final Function(String) onError;

  const ImageIssueCardEnhanced({
    Key? key,
    required this.issue,
    required this.imageBaseUrl,
    required this.documentId,
    required this.onImageReplaced,
    required this.onError,
    this.userId,
    this.onImageRemoved,
    this.onIgnore,
  }) : super(key: key);

  @override
  State<ImageIssueCardEnhanced> createState() => _ImageIssueCardEnhancedState();
}

class _ImageIssueCardEnhancedState extends State<ImageIssueCardEnhanced> {
  late ImageReplacementService _replacementService;
  bool _isReplacementVisible = false;
  bool _showReplacedBadge = false;
  bool _isRemoving = false;

  @override
  void initState() {
    super.initState();
    _replacementService = ImageReplacementService(imageBaseUrl: widget.imageBaseUrl);
  }

  int get _imageIndex => jsonIntOr(widget.issue['image_index'], 0);

  void _showReplacementDialog() {
    final filename = widget.issue['current'] as String? ?? '';

    showDialog(
      context: context,
      builder: (ctx) => ImageReplacementDialog(
        documentId: widget.documentId,
        imageIndex: _imageIndex,
        currentImagePath: filename,
        service: _replacementService,
        userId: widget.userId,
        onSuccess: (result) {
          setState(() => _showReplacedBadge = true);
          widget.onImageReplaced(result);
        },
        onError: (error) {
          widget.onError(error);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Error: $error'),
              backgroundColor: _red,
              duration: const Duration(seconds: 3),
            ),
          );
        },
      ),
    );
  }

  Future<void> _confirmAndRemove() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _surface,
        title: Text('Remove Image?', style: TextStyle(color: _textPri)),
        content: Text(
          'This permanently deletes the image from the document'
          '${widget.issue['image_id'] != null ? ' (${widget.issue['image_id']})' : ''}'
          '. A nearby figure caption will also be removed if present.',
          style: TextStyle(color: _textSec, fontSize: 13, height: 1.4),
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

    setState(() => _isRemoving = true);
    try {
      final result = await _replacementService.removeImage(
        documentId: widget.documentId,
        imageIndex: _imageIndex,
        userId: widget.userId,
      );
      if (!mounted) return;
      if (widget.onImageRemoved != null) {
        widget.onImageRemoved!(result);
      } else {
        // Fallback: treat as resolved via replace handler path
        widget.onImageReplaced({...result, 'cleared': true});
      }
    } catch (e) {
      widget.onError(e.toString());
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Remove failed: $e'),
            backgroundColor: _red,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isRemoving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    _ap = context.watch<ThemeProvider>().palette;
    final rawPath = widget.issue['image_path'] as String? ?? '';
    final filename = widget.issue['current'] as String? ?? '';
    final reason = widget.issue['description'] as String? ??
        widget.issue['reason'] as String? ??
        '';
    final confidence = normalizedConfidence(widget.issue['confidence']);
    final pct = (confidence * 100).toInt();
    final textBefore =
        ((widget.issue['text_before'] as String?) ?? '').trim();
    final textAfter = ((widget.issue['text_after'] as String?) ?? '').trim();
    final hasNearbyContext = textBefore.isNotEmpty || textAfter.isNotEmpty;

    // Build image URL
    final cleanPath = rawPath.startsWith('uploads/')
        ? rawPath.substring('uploads/'.length)
        : rawPath;
   final hostBase = widget.imageBaseUrl;
    final imageUrl = '$hostBase/uploads/$cleanPath';

    // If image was replaced, show success state
    if (_showReplacedBadge) {
      return Container(
        margin: const EdgeInsets.only(bottom: 16),
        decoration: BoxDecoration(
          color: _surface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: _green.withOpacity(0.35), width: 1.5),
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Green success header
            Container(
              color: _green.withOpacity(0.12),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: Row(
                children: [
                  const Icon(Icons.check_circle, color: _green, size: 16),
                  const SizedBox(width: 8),
                  const Text(
                    '✓  Image Replaced & Validated',
                    style: TextStyle(
                      color: _green,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const Spacer(),
                  _Tag('RESOLVED', _green),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'The new image has been validated and is now part of your document.',
                    style: TextStyle(
                      color: _textSec,
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    filename,
                    style: TextStyle(
                      color: _textSec,
                      fontSize: 10,
                      fontFamily: 'monospace',
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }

    // Normal error state with replace button
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: _red.withOpacity(0.35), width: 1.5),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Red header bar
          Container(
            color: _red.withOpacity(0.12),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Row(
              children: [
                const Icon(Icons.image_not_supported, color: _red, size: 16),
                const SizedBox(width: 8),
                const Text(
                  '❌  Irrelevant Image Detected',
                  style: TextStyle(
                    color: _red,
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                _Tag('CRITICAL', _red),
                const SizedBox(width: 8),
                Text(
                  '$pct% confidence',
                  style: TextStyle(color: _textSec, fontSize: 11),
                ),
              ],
            ),
          ),

          // Image preview
          Image.network(
            imageUrl,
            height: 200,
            fit: BoxFit.contain,
            loadingBuilder: (ctx, child, progress) {
              if (progress == null) return child;
              return SizedBox(
                height: 200,
                child: Center(
                  child: CircularProgressIndicator(
                    value: progress.expectedTotalBytes != null
                        ? progress.cumulativeBytesLoaded /
                              progress.expectedTotalBytes!
                        : null,
                    color: _blue,
                    strokeWidth: 2,
                  ),
                ),
              );
            },
            errorBuilder: (_, error, __) => Container(
              height: 100,
              color: _surface2,
              alignment: Alignment.center,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.broken_image, color: _textSec, size: 28),
                  const SizedBox(height: 6),
                  Text(
                    'Failed to load image',
                    style: TextStyle(color: _textSec, fontSize: 11),
                  ),
                  const SizedBox(height: 4),
                  SelectableText(
                    imageUrl,
                    style: TextStyle(
                      color: _textSec,
                      fontSize: 9,
                      fontFamily: 'monospace',
                    ),
                  ),
                ],
              ),
            ),
          ),

          // Footer with filename, confidence bar, and replace button
          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.attach_file, color: _textSec, size: 12),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        filename,
                        style: TextStyle(
                          color: _textSec,
                          fontSize: 11,
                          fontFamily: 'monospace',
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),

                if (reason.isNotEmpty) ...[
                  Text(
                    reason,
                    style: TextStyle(color: _textSec, fontSize: 11, height: 1.4),
                    maxLines: 5,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 8),
                ],

                if (hasNearbyContext) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: _surface2,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: _border),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Checked against nearby text',
                          style: TextStyle(
                            color: _textPri,
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        if (textBefore.isNotEmpty) ...[
                          const SizedBox(height: 6),
                          Text(
                            'Before: $textBefore',
                            style: TextStyle(
                              color: _textSec,
                              fontSize: 10,
                              height: 1.35,
                            ),
                            maxLines: 3,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                        if (textAfter.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Text(
                            'After: $textAfter',
                            style: TextStyle(
                              color: _textSec,
                              fontSize: 10,
                              height: 1.35,
                            ),
                            maxLines: 3,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(height: 8),
                ],

                // Confidence bar
                Row(
                  children: [
                    Text(
                      'Irrelevance confidence: ',
                      style: TextStyle(color: _textSec, fontSize: 11),
                    ),
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: confidence,
                          minHeight: 5,
                          backgroundColor: _border,
                          valueColor: AlwaysStoppedAnimation(
                            confidence > 0.85 ? _red : _yellow,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '$pct%',
                      style: TextStyle(
                        color: confidence > 0.85 ? _red : _yellow,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),

                // Suggestion banner
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: _yellow.withOpacity(0.1),
                    border: Border.all(
                      color: _yellow.withOpacity(0.3),
                      width: 1,
                    ),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.info, color: _yellow, size: 16),
                      const SizedBox(width: 8),
                      const Expanded(
                        child: Text(
                          'Replace this image with one relevant to the section content.',
                          style: TextStyle(
                            color: _yellow,
                            fontSize: 11,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),

                // Actions: Replace / Remove / Ignore
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    icon: const Icon(Icons.image_search, size: 16),
                    label: const Text('Replace Image'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _blue,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                    onPressed: _isRemoving ? null : _showReplacementDialog,
                  ),
                ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    icon: _isRemoving
                        ? const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.delete_outline, size: 16),
                    label: Text(_isRemoving ? 'Removing…' : 'Remove Image'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: _red,
                      side: BorderSide(color: _red.withOpacity(0.55)),
                      padding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                    onPressed: _isRemoving ? null : _confirmAndRemove,
                  ),
                ),
                if (widget.onIgnore != null) ...[
                  const SizedBox(height: 8),
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton(
                      onPressed: _isRemoving ? null : widget.onIgnore,
                      child: const Text('Ignore'),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// Tag widget for status display
class _Tag extends StatelessWidget {
  final String text;
  final Color color;

  const _Tag(this.text, this.color);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        border: Border.all(color: color.withOpacity(0.4), width: 0.5),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 10,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.3,
        ),
      ),
    );
  }
}
