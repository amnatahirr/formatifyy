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

/// Enhanced image issue card with replacement capability
class ImageIssueCardEnhanced extends StatefulWidget {
  final Map<String, dynamic> issue;
  final String imageBaseUrl;
  final int documentId;
  final void Function(Map<String, dynamic> result) onImageReplaced;
  final Function(String) onError; // Error callback

  const ImageIssueCardEnhanced({
    Key? key,
    required this.issue,
    required this.imageBaseUrl,
    required this.documentId,
    required this.onImageReplaced,
    required this.onError,
  }) : super(key: key);

  @override
  State<ImageIssueCardEnhanced> createState() => _ImageIssueCardEnhancedState();
}

class _ImageIssueCardEnhancedState extends State<ImageIssueCardEnhanced> {
  late ImageReplacementService _replacementService;
  bool _isReplacementVisible = false;
  bool _showReplacedBadge = false;

  @override
  void initState() {
    super.initState();
    _replacementService = ImageReplacementService(imageBaseUrl: widget.imageBaseUrl);
  }

  void _showReplacementDialog() {
    final rawPath = widget.issue['image_path'] as String? ?? '';
    final filename = widget.issue['current'] as String? ?? '';

    showDialog(
      context: context,
      builder: (ctx) => ImageReplacementDialog(
        documentId: widget.documentId,
        imageIndex: widget.issue['image_index'] ?? 0,
        currentImagePath: filename,
        service: _replacementService,
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

  @override
  Widget build(BuildContext context) {
    final rawPath = widget.issue['image_path'] as String? ?? '';
    final filename = widget.issue['current'] as String? ?? '';
    final reason = widget.issue['description'] as String? ??
        widget.issue['reason'] as String? ??
        '';
    final confidence = normalizedConfidence(widget.issue['confidence']);
    final pct = (confidence * 100).toInt();

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
                  const Text(
                    'The new image has been validated and is now part of your document.',
                    style: TextStyle(
                      color: _textSec,
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    filename,
                    style: const TextStyle(
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
                  style: const TextStyle(color: _textSec, fontSize: 11),
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
                  const Icon(Icons.broken_image, color: _textSec, size: 28),
                  const SizedBox(height: 6),
                  const Text(
                    'Failed to load image',
                    style: TextStyle(color: _textSec, fontSize: 11),
                  ),
                  const SizedBox(height: 4),
                  SelectableText(
                    imageUrl,
                    style: const TextStyle(
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
                    const Icon(Icons.attach_file, color: _textSec, size: 12),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        filename,
                        style: const TextStyle(
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
                    style: const TextStyle(color: _textSec, fontSize: 11, height: 1.4),
                    maxLines: 4,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 8),
                ],

                // Confidence bar
                Row(
                  children: [
                    const Text(
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

                // Replace button
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    icon: const Icon(Icons.image_search, size: 16),
                    label: const Text('Replace Image'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _blue,
                      foregroundColor: _textPri,
                      padding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                    onPressed: _showReplacementDialog,
                  ),
                ),
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
