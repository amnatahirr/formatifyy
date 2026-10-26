import 'package:flutter/material.dart';

import 'admin/admin_ui.dart';

import 'tr.dart';
/// Confirmation before starting template-free analysis (non-student roles).
Future<bool> confirmAnalyzeWithoutTemplate(BuildContext context) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      backgroundColor: AdminColors.surface,
      title: const Tr('Analyzing without a template'),
      content: Text(
        'Results will use general academic formatting guidelines '
        '(headings, fonts, spacing, margins, citations), not your '
        'organization\'s template rules. You can still review findings '
        'before any export.',
        style: TextStyle(
          color: Colors.white.withOpacity(0.8),
          height: 1.4,
          fontSize: 13,
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx, false),
          child: const Tr('Cancel'),
        ),
        ElevatedButton(
          onPressed: () => Navigator.pop(ctx, true),
          style: ElevatedButton.styleFrom(
            backgroundColor: AdminColors.primary,
            foregroundColor: Colors.white,
          ),
          child: const Tr('Continue'),
        ),
      ],
    ),
  );
  return ok == true;
}

/// Pre-export summary for freeform AI-guided export.
/// Checkpoint UI only — caller decides whether to actually export.
Future<bool> showFreeformExportSummaryDialog(
  BuildContext context, {
  required List<Map<String, dynamic>> appliedFixes,
  required List<Map<String, dynamic>> manualNotes,
}) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      backgroundColor: AdminColors.surface,
      title: const Tr('Export AI-guided fixes'),
      content: SizedBox(
        width: 480,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: AdminColors.primary.withOpacity(0.14),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: AdminColors.primary.withOpacity(0.35)),
                ),
                child: const Tr('AI-guided · no template',
                  style: TextStyle(
                    color: Color(0xFFA5B4FC),
                    fontSize: 11.5,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              const SizedBox(height: 14),
              Text(
                'The following safe fixes will be applied to a copy of your document. '
                'Nothing is written until you confirm.',
                style: TextStyle(
                  color: Colors.white.withOpacity(0.75),
                  fontSize: 13,
                  height: 1.4,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'Will be applied (${appliedFixes.length})',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                ),
              ),
              const SizedBox(height: 8),
              if (appliedFixes.isEmpty)
                Tr('No auto-applicable fixes.',
                  style: TextStyle(color: Colors.white.withOpacity(0.45), fontSize: 12.5),
                )
              else
                ...appliedFixes.map((f) {
                  final action = (f['fix_action'] ?? f['suggestion'] ?? '').toString();
                  final pid = (f['paragraph_id'] ?? '').toString();
                  final level = f['heading_level'];
                  final detail = level != null && level != 0 && level != '0'
                      ? '$action (H$level)'
                      : action;
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.check_circle_outline, size: 16, color: AdminColors.success),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            pid.isEmpty ? detail : '$detail · $pid',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.85),
                              fontSize: 12.5,
                              height: 1.35,
                            ),
                          ),
                        ),
                      ],
                    ),
                  );
                }),
              if (manualNotes.isNotEmpty) ...[
                const SizedBox(height: 14),
                Text(
                  'Suggested but not auto-applied (${manualNotes.length})',
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 8),
                ...manualNotes.map((n) {
                  final note = (n['note'] ?? '').toString();
                  final pid = (n['paragraph_id'] ?? '').toString();
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(Icons.info_outline, size: 16, color: Colors.white.withOpacity(0.45)),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            pid.isEmpty ? note : '$note · $pid',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.55),
                              fontSize: 12.5,
                              height: 1.35,
                            ),
                          ),
                        ),
                      ],
                    ),
                  );
                }),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(ctx, false),
          child: const Tr('Cancel'),
        ),
        ElevatedButton(
          onPressed: appliedFixes.isEmpty ? null : () => Navigator.pop(ctx, true),
          style: ElevatedButton.styleFrom(
            backgroundColor: AdminColors.primary,
            foregroundColor: Colors.white,
          ),
          child: const Tr('Confirm export'),
        ),
      ],
    ),
  );
  return ok == true;
}
