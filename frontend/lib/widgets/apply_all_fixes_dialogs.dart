import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../theme/app_theme.dart';
import '../models/json_parse.dart';

AppPalette _ap = AppPalette.dark;

Color get _surface => _ap.surface;
Color get _surface2 => _ap.surfaceElevated;
Color get _border => _ap.border;
Color get _textPri => _ap.textPrimary;
Color get _textSec => _ap.textSecondary;
const _green = Color(0xFF10B981);
const _yellow = Color(0xFFF59E0B);
const _red = Color(0xFFEF4444);
const _blue = Color(0xFF4A9EFF);
const _purple = Color(0xFF6366F1);
const _orange = Color(0xFFF97316);

enum ApplyAllOutcomeStatus { done, pending, skipped, failed }

/// One line in the "what will run" / "what was applied" checklists.
class ApplyAllOutcome {
  const ApplyAllOutcome(
    this.label, {
    this.status = ApplyAllOutcomeStatus.done,
    this.detail,
  });

  final String label;
  final ApplyAllOutcomeStatus status;
  final String? detail;
}

/// User's choice from the pre-apply reminder dialog.
class ApplyAllPlan {
  const ApplyAllPlan({
    required this.includeToc,
    required this.includeLot,
    required this.includeLof,
  });

  final bool includeToc;
  final bool includeLot;
  final bool includeLof;
}

// ── Issue helpers ────────────────────────────────────────────────────────────

bool _isEthicsIssue(Map<String, dynamic> issue) {
  final key =
      '${issue['function'] ?? ''} ${issue['category'] ?? ''} ${issue['type'] ?? ''}'
          .toLowerCase();
  return key.contains('ethic');
}

String _imageIssueTitle(Map<String, dynamic> issue) =>
    _isEthicsIssue(issue) ? 'Unethical image' : 'Irrelevant image';

String _imageIssueLabel(Map<String, dynamic> issue) {
  final id = (issue['image_id'] as String? ?? '').trim();
  if (id.isNotEmpty) return id;
  return 'img${jsonIntOr(issue['image_index'], 0)}';
}

String _imageIssueReason(Map<String, dynamic> issue) {
  final reason = (issue['description'] as String? ??
          issue['reason'] as String? ??
          issue['message'] as String? ??
          '')
      .trim();
  return reason.isEmpty ? 'Flagged during image analysis.' : reason;
}

String? _imageIssuePage(Map<String, dynamic> issue) {
  final page = issue['page'] ?? issue['page_number'];
  if (page is num && page > 0) return 'Page ${page.toInt()}';
  return null;
}

// ── Shared small widgets ─────────────────────────────────────────────────────

class _OutcomeRow extends StatelessWidget {
  const _OutcomeRow(this.outcome);

  final ApplyAllOutcome outcome;

  @override
  Widget build(BuildContext context) {
    late final IconData icon;
    late final Color color;
    switch (outcome.status) {
      case ApplyAllOutcomeStatus.done:
        icon = Icons.check_circle;
        color = _green;
        break;
      case ApplyAllOutcomeStatus.pending:
        icon = Icons.play_circle_outline;
        color = _blue;
        break;
      case ApplyAllOutcomeStatus.skipped:
        icon = Icons.remove_circle_outline;
        color = _textSec;
        break;
      case ApplyAllOutcomeStatus.failed:
        icon = Icons.error_outline;
        color = _red;
        break;
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 15, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  outcome.label,
                  style: TextStyle(
                    color: outcome.status == ApplyAllOutcomeStatus.skipped
                        ? _textSec
                        : _textPri,
                    fontSize: 12.5,
                    height: 1.35,
                  ),
                ),
                if (outcome.detail != null && outcome.detail!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(
                      outcome.detail!,
                      style: TextStyle(
                        color: _textSec,
                        fontSize: 11,
                        height: 1.35,
                      ),
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

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.icon, this.title, this.color);

  final IconData icon;
  final String title;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Icon(icon, size: 15, color: color),
          const SizedBox(width: 8),
          Text(
            title,
            style: TextStyle(
              color: color,
              fontSize: 12.5,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.2,
            ),
          ),
        ],
      ),
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner(this.icon, this.text, this.color);

  final IconData icon;
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.35)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 15, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                color: color.withOpacity(0.95),
                fontSize: 11.5,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ImageThumb extends StatelessWidget {
  const _ImageThumb({required this.url});

  final String? url;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 54,
      height: 54,
      decoration: BoxDecoration(
        color: _surface2,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: _border),
      ),
      clipBehavior: Clip.antiAlias,
      child: (url == null || url!.isEmpty)
          ? Icon(Icons.image_not_supported_outlined, color: _textSec, size: 18)
          : Image.network(
              url!,
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) =>
                  Icon(Icons.broken_image, color: _textSec, size: 18),
            ),
    );
  }
}

/// Compact card for an image that still needs a manual decision.
class _ImageIssueTile extends StatelessWidget {
  const _ImageIssueTile({
    required this.issue,
    required this.imageUrlBuilder,
    this.onReplace,
    this.onRemove,
    this.busy = false,
  });

  final Map<String, dynamic> issue;
  final String Function(String rawPath) imageUrlBuilder;
  final VoidCallback? onReplace;
  final VoidCallback? onRemove;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    final rawPath = issue['image_path'] as String? ?? '';
    final url = rawPath.isEmpty ? null : imageUrlBuilder(rawPath);
    final ethics = _isEthicsIssue(issue);
    final accent = ethics ? _red : _orange;
    final page = _imageIssuePage(issue);
    final hasActions = onReplace != null || onRemove != null;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: _surface2,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: accent.withOpacity(0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _ImageThumb(url: url),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Flexible(
                          child: Text(
                            '${_imageIssueLabel(issue)} — ${_imageIssueTitle(issue)}',
                            style: TextStyle(
                              color: accent,
                              fontSize: 12.5,
                              fontWeight: FontWeight.w700,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        if (page != null) ...[
                          const SizedBox(width: 8),
                          Text(
                            page,
                            style: TextStyle(color: _textSec, fontSize: 11),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _imageIssueReason(issue),
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: _textSec,
                        fontSize: 11.5,
                        height: 1.35,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (hasActions) ...[
            const SizedBox(height: 10),
            Row(
              children: [
                if (onReplace != null)
                  ElevatedButton.icon(
                    onPressed: busy ? null : onReplace,
                    icon: const Icon(Icons.image_search, size: 14),
                    label: const Text(
                      'Replace Image',
                      style: TextStyle(fontSize: 12),
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _blue,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 14,
                        vertical: 10,
                      ),
                    ),
                  ),
                if (onRemove != null) ...[
                  const SizedBox(width: 8),
                  OutlinedButton.icon(
                    onPressed: busy ? null : onRemove,
                    icon: const Icon(Icons.delete_outline, size: 14),
                    label: const Text(
                      'Remove Image',
                      style: TextStyle(fontSize: 12),
                    ),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: _red,
                      side: BorderSide(color: _red.withOpacity(0.55)),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 14,
                        vertical: 10,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ],
        ],
      ),
    );
  }
}

// ── Pre-apply reminder dialog ────────────────────────────────────────────────

/// Reminds the user about images needing manual review and lets them pick the
/// TOC / LOT / LOF that "Apply All Fixes" should generate.
///
/// Returns `null` when the user cancels.
Future<ApplyAllPlan?> showApplyAllFixesReminderDialog({
  required BuildContext context,
  required List<ApplyAllOutcome> plannedFixes,
  required List<Map<String, dynamic>> imageIssues,
  required Map<String, dynamic> listsStatus,
  required bool includeToc,
  required bool includeLot,
  required bool includeLof,
  required String Function(String rawPath) imageUrlBuilder,
  String? listsError,
}) {
  return showDialog<ApplyAllPlan>(
    context: context,
    barrierDismissible: false,
    builder: (_) => _ApplyAllReminderDialog(
      plannedFixes: plannedFixes,
      imageIssues: imageIssues,
      listsStatus: listsStatus,
      includeToc: includeToc,
      includeLot: includeLot,
      includeLof: includeLof,
      imageUrlBuilder: imageUrlBuilder,
      listsError: listsError,
    ),
  );
}

class _ApplyAllReminderDialog extends StatefulWidget {
  const _ApplyAllReminderDialog({
    required this.plannedFixes,
    required this.imageIssues,
    required this.listsStatus,
    required this.includeToc,
    required this.includeLot,
    required this.includeLof,
    required this.imageUrlBuilder,
    this.listsError,
  });

  final List<ApplyAllOutcome> plannedFixes;
  final List<Map<String, dynamic>> imageIssues;
  final Map<String, dynamic> listsStatus;
  final bool includeToc;
  final bool includeLot;
  final bool includeLof;
  final String Function(String rawPath) imageUrlBuilder;
  final String? listsError;

  @override
  State<_ApplyAllReminderDialog> createState() =>
      _ApplyAllReminderDialogState();
}

class _ApplyAllReminderDialogState extends State<_ApplyAllReminderDialog> {
  late bool _toc;
  late bool _lot;
  late bool _lof;

  int _count(String key) =>
      (widget.listsStatus[key] as num?)?.toInt() ?? 0;

  bool _flag(String key) => widget.listsStatus[key] as bool? ?? false;

  bool get _canToc => _count('heading_count') > 0;
  bool get _canLot => _count('table_count') > 0;
  bool get _canLof => _count('figure_count') > 0;

  /// A list is worth generating when the document can produce it and it is
  /// either missing or present but never populated.
  bool _recommended(bool can, String hasKey, String populatedKey) =>
      can && !(_flag(hasKey) && _flag(populatedKey));

  @override
  void initState() {
    super.initState();
    _toc = widget.includeToc ||
        _recommended(_canToc, 'has_toc', 'toc_populated');
    _lot = widget.includeLot ||
        _recommended(_canLot, 'has_lot', 'lot_populated');
    _lof = widget.includeLof ||
        _recommended(_canLof, 'has_lof', 'lof_populated');
  }

  String? _listStatusNote(bool can, String hasKey, String populatedKey,
      String emptyReason) {
    if (!can) return emptyReason;
    if (_flag(hasKey) && _flag(populatedKey)) {
      return 'Already in the document — regenerating keeps it up to date.';
    }
    if (_flag(hasKey)) return 'Present but empty — needs to be generated.';
    return 'Not in the document yet.';
  }

  @override
  Widget build(BuildContext context) {
    _ap = context.watch<ThemeProvider>().palette;
    final images = widget.imageIssues;

    return Dialog(
      backgroundColor: _surface,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 620, maxHeight: 680),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildHeader(),
            Flexible(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _SectionTitle(
                      Icons.auto_fix_high,
                      'APPLIED AUTOMATICALLY',
                      _purple,
                    ),
                    ...widget.plannedFixes.map((o) => _OutcomeRow(o)),
                    const SizedBox(height: 18),
                    _SectionTitle(Icons.toc, 'DOCUMENT LISTS', _blue),
                    if (widget.listsError != null) ...[
                      _Banner(
                        Icons.error_outline,
                        'Could not scan document lists: ${widget.listsError}. '
                        'You can still generate them later from the Document '
                        'Lists tab.',
                        _red,
                      ),
                      const SizedBox(height: 10),
                    ],
                    Text(
                      'These are only generated when selected. Word fills in '
                      'page numbers when you open the exported file.',
                      style: TextStyle(
                        color: _textSec,
                        fontSize: 11.5,
                        height: 1.4,
                      ),
                    ),
                    const SizedBox(height: 10),
                    _buildListToggle(
                      title: 'Table of Contents',
                      icon: Icons.format_list_bulleted,
                      color: _blue,
                      value: _toc,
                      enabled: _canToc,
                      detail: '${_count('heading_count')} headings detected',
                      note: _listStatusNote(
                        _canToc,
                        'has_toc',
                        'toc_populated',
                        'No headings detected — nothing to build a TOC from.',
                      ),
                      onChanged: (v) => setState(() => _toc = v),
                    ),
                    const SizedBox(height: 8),
                    _buildListToggle(
                      title: 'List of Tables',
                      icon: Icons.table_chart_outlined,
                      color: _purple,
                      value: _lot,
                      enabled: _canLot,
                      detail: '${_count('table_count')} tables detected'
                          '${_count('tables_missing_captions') > 0 ? ' · ${_count('tables_missing_captions')} missing captions' : ''}',
                      note: _listStatusNote(
                        _canLot,
                        'has_lot',
                        'lot_populated',
                        'No tables detected in this document.',
                      ),
                      onChanged: (v) => setState(() => _lot = v),
                    ),
                    const SizedBox(height: 8),
                    _buildListToggle(
                      title: 'List of Figures',
                      icon: Icons.image_outlined,
                      color: _orange,
                      value: _lof,
                      enabled: _canLof,
                      detail: '${_count('figure_count')} figures detected'
                          '${_count('figures_missing_captions') > 0 ? ' · ${_count('figures_missing_captions')} missing captions' : ''}',
                      note: _listStatusNote(
                        _canLof,
                        'has_lof',
                        'lof_populated',
                        'No figures detected in this document.',
                      ),
                      onChanged: (v) => setState(() => _lof = v),
                    ),
                    const SizedBox(height: 18),
                    _SectionTitle(
                      Icons.image_outlined,
                      'IMAGES NEEDING YOUR REVIEW',
                      images.isEmpty ? _green : _yellow,
                    ),
                    if (images.isEmpty)
                      _Banner(
                        Icons.check_circle_outline,
                        'No flagged images. Image alignment and figure '
                        'captions are formatted automatically.',
                        _green,
                      )
                    else ...[
                      _Banner(
                        Icons.warning_amber_rounded,
                        '${images.length} image${images.length == 1 ? '' : 's'} '
                        'cannot be fixed automatically. After the fixes are '
                        'applied you can replace or remove each one.',
                        _yellow,
                      ),
                      const SizedBox(height: 10),
                      ...images.take(4).map(
                            (i) => _ImageIssueTile(
                              issue: i,
                              imageUrlBuilder: widget.imageUrlBuilder,
                            ),
                          ),
                      if (images.length > 4)
                        Text(
                          '+ ${images.length - 4} more flagged image'
                          '${images.length - 4 == 1 ? '' : 's'}',
                          style: TextStyle(color: _textSec, fontSize: 11.5),
                        ),
                    ],
                  ],
                ),
              ),
            ),
            _buildFooter(),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 16, 12, 16),
      decoration: BoxDecoration(
        color: _purple.withOpacity(0.10),
        border: Border(bottom: BorderSide(color: _border)),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
      ),
      child: Row(
        children: [
          const Icon(Icons.auto_fix_high, color: _purple, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Before applying all fixes',
                  style: TextStyle(
                    color: _textPri,
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Text(
                  'Review what runs automatically and what still needs you',
                  style: TextStyle(color: _textSec, fontSize: 11.5),
                ),
              ],
            ),
          ),
          IconButton(
            tooltip: 'Cancel',
            icon: Icon(Icons.close, color: _textSec, size: 18),
            onPressed: () => Navigator.of(context).pop(),
          ),
        ],
      ),
    );
  }

  Widget _buildListToggle({
    required String title,
    required IconData icon,
    required Color color,
    required bool value,
    required bool enabled,
    required String detail,
    required String? note,
    required ValueChanged<bool> onChanged,
  }) {
    return Opacity(
      opacity: enabled ? 1 : 0.55,
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 10, 8, 10),
        decoration: BoxDecoration(
          color: _surface2,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: value && enabled ? color.withOpacity(0.45) : _border,
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 16, color: color),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      color: _textPri,
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    detail,
                    style: TextStyle(color: _textSec, fontSize: 11),
                  ),
                  if (note != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Text(
                        note,
                        style: TextStyle(
                          color: enabled
                              ? _textSec.withOpacity(0.9)
                              : _red.withOpacity(0.85),
                          fontSize: 11,
                          height: 1.35,
                        ),
                      ),
                    ),
                ],
              ),
            ),
            Transform.scale(
              scale: 0.85,
              child: Switch(
                value: value && enabled,
                onChanged: enabled ? onChanged : null,
                activeColor: color,
                inactiveThumbColor: _textSec,
                inactiveTrackColor: _border,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFooter() {
    final selected = [
      if (_toc && _canToc) 'TOC',
      if (_lot && _canLot) 'LOT',
      if (_lof && _canLof) 'LOF',
    ];
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      decoration: BoxDecoration(
        color: _surface,
        border: Border(top: BorderSide(color: _border)),
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(12)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              selected.isEmpty
                  ? 'No document lists selected'
                  : 'Will also generate: ${selected.join(', ')}',
              style: TextStyle(color: _textSec, fontSize: 11.5),
            ),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text('Cancel', style: TextStyle(color: _textSec)),
          ),
          const SizedBox(width: 8),
          ElevatedButton.icon(
            onPressed: () => Navigator.of(context).pop(
              ApplyAllPlan(
                includeToc: _toc && _canToc,
                includeLot: _lot && _canLot,
                includeLof: _lof && _canLof,
              ),
            ),
            icon: const Icon(Icons.auto_fix_high, size: 16),
            label: const Text('Apply All Fixes'),
            style: ElevatedButton.styleFrom(
              backgroundColor: _purple,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(
                horizontal: 18,
                vertical: 12,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Post-apply summary dialog ────────────────────────────────────────────────

/// Shows what "Apply All Fixes" changed and lets the user resolve the images
/// that still need a manual decision without leaving the dialog.
Future<void> showApplyAllFixesSummaryDialog({
  required BuildContext context,
  required List<ApplyAllOutcome> applied,
  required List<ApplyAllOutcome> listOutcomes,
  required List<Map<String, dynamic>> Function() pendingImageIssues,
  required Future<void> Function(Map<String, dynamic> issue) onReplaceImage,
  required Future<void> Function(Map<String, dynamic> issue) onRemoveImage,
  required String Function(String rawPath) imageUrlBuilder,
  required VoidCallback onOpenImagesTab,
  required VoidCallback onOpenListsTab,
}) {
  return showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (_) => _ApplyAllSummaryDialog(
      applied: applied,
      listOutcomes: listOutcomes,
      pendingImageIssues: pendingImageIssues,
      onReplaceImage: onReplaceImage,
      onRemoveImage: onRemoveImage,
      imageUrlBuilder: imageUrlBuilder,
      onOpenImagesTab: onOpenImagesTab,
      onOpenListsTab: onOpenListsTab,
    ),
  );
}

class _ApplyAllSummaryDialog extends StatefulWidget {
  const _ApplyAllSummaryDialog({
    required this.applied,
    required this.listOutcomes,
    required this.pendingImageIssues,
    required this.onReplaceImage,
    required this.onRemoveImage,
    required this.imageUrlBuilder,
    required this.onOpenImagesTab,
    required this.onOpenListsTab,
  });

  final List<ApplyAllOutcome> applied;
  final List<ApplyAllOutcome> listOutcomes;
  final List<Map<String, dynamic>> Function() pendingImageIssues;
  final Future<void> Function(Map<String, dynamic> issue) onReplaceImage;
  final Future<void> Function(Map<String, dynamic> issue) onRemoveImage;
  final String Function(String rawPath) imageUrlBuilder;
  final VoidCallback onOpenImagesTab;
  final VoidCallback onOpenListsTab;

  @override
  State<_ApplyAllSummaryDialog> createState() => _ApplyAllSummaryDialogState();
}

class _ApplyAllSummaryDialogState extends State<_ApplyAllSummaryDialog> {
  String? _busyIssueId;

  String _issueKey(Map<String, dynamic> issue) =>
      (issue['issue_id'] as String? ?? '').isNotEmpty
          ? issue['issue_id'] as String
          : '${issue['function']}_${issue['image_index']}';

  Future<void> _run(
    Map<String, dynamic> issue,
    Future<void> Function(Map<String, dynamic>) action,
  ) async {
    setState(() => _busyIssueId = _issueKey(issue));
    try {
      await action(issue);
    } finally {
      if (mounted) setState(() => _busyIssueId = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    _ap = context.watch<ThemeProvider>().palette;
    final pending = widget.pendingImageIssues();
    final clean = pending.isEmpty;

    return Dialog(
      backgroundColor: _surface,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 620, maxHeight: 680),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildHeader(clean),
            Flexible(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _SectionTitle(Icons.check_circle, 'APPLIED', _green),
                    ...widget.applied.map((o) => _OutcomeRow(o)),
                    const SizedBox(height: 18),
                    _SectionTitle(Icons.toc, 'DOCUMENT LISTS', _blue),
                    ...widget.listOutcomes.map((o) => _OutcomeRow(o)),
                    const SizedBox(height: 4),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton.icon(
                        onPressed: () {
                          Navigator.of(context).pop();
                          widget.onOpenListsTab();
                        },
                        icon: const Icon(Icons.open_in_new, size: 14),
                        label: const Text(
                          'Open Document Lists tab',
                          style: TextStyle(fontSize: 12),
                        ),
                        style: TextButton.styleFrom(foregroundColor: _blue),
                      ),
                    ),
                    const SizedBox(height: 14),
                    _SectionTitle(
                      clean ? Icons.verified_outlined : Icons.warning_amber_rounded,
                      clean ? 'IMAGES' : 'MANUAL ACTION NEEDED',
                      clean ? _green : _yellow,
                    ),
                    if (clean)
                      _Banner(
                        Icons.check_circle_outline,
                        'No flagged images left. Images were centred and figure '
                        'captions were added automatically.',
                        _green,
                      )
                    else ...[
                      _Banner(
                        Icons.warning_amber_rounded,
                        'These images could not be fixed automatically. Replace '
                        'or remove each one so the final document is clean.',
                        _yellow,
                      ),
                      const SizedBox(height: 10),
                      ...pending.map(
                        (issue) => _ImageIssueTile(
                          issue: issue,
                          imageUrlBuilder: widget.imageUrlBuilder,
                          busy: _busyIssueId != null,
                          onReplace: () =>
                              _run(issue, widget.onReplaceImage),
                          onRemove: () => _run(issue, widget.onRemoveImage),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            _buildFooter(clean, pending.length),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader(bool clean) {
    final color = clean ? _green : _yellow;
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 16, 12, 16),
      decoration: BoxDecoration(
        color: color.withOpacity(0.10),
        border: Border(bottom: BorderSide(color: _border)),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
      ),
      child: Row(
        children: [
          Icon(
            clean ? Icons.check_circle : Icons.info_outline,
            color: color,
            size: 20,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'All fixes applied',
                  style: TextStyle(
                    color: _textPri,
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Text(
                  clean
                      ? 'Your document is ready to save or download'
                      : 'A few images still need your decision',
                  style: TextStyle(color: _textSec, fontSize: 11.5),
                ),
              ],
            ),
          ),
          IconButton(
            tooltip: 'Close',
            icon: Icon(Icons.close, color: _textSec, size: 18),
            onPressed: () => Navigator.of(context).pop(),
          ),
        ],
      ),
    );
  }

  Widget _buildFooter(bool clean, int pendingCount) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      decoration: BoxDecoration(
        color: _surface,
        border: Border(top: BorderSide(color: _border)),
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(12)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              clean
                  ? 'Everything that can be automated is done.'
                  : 'Fix all $pendingCount flagged image'
                      '${pendingCount == 1 ? '' : 's'} before downloading the '
                      'final document.',
              style: TextStyle(
                color: clean ? _textSec : _yellow,
                fontSize: 11.5,
                height: 1.35,
              ),
            ),
          ),
          const SizedBox(width: 12),
          if (!clean) ...[
            OutlinedButton.icon(
              onPressed: () {
                Navigator.of(context).pop();
                widget.onOpenImagesTab();
              },
              icon: const Icon(Icons.image_outlined, size: 15),
              label: const Text('Review Images'),
              style: OutlinedButton.styleFrom(
                foregroundColor: _yellow,
                side: BorderSide(color: _yellow.withOpacity(0.55)),
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 12,
                ),
              ),
            ),
            const SizedBox(width: 8),
          ],
          ElevatedButton(
            onPressed: () => Navigator.of(context).pop(),
            style: ElevatedButton.styleFrom(
              backgroundColor: clean ? _green : _purple,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(
                horizontal: 20,
                vertical: 12,
              ),
            ),
            child: const Text('Done'),
          ),
        ],
      ),
    );
  }
}
