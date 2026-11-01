import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../theme/app_theme.dart';
import '../../utils/responsive.dart';
import '../../widgets/admin/admin_ui.dart';
import 'document_review_screen.dart';

import '../../widgets/tr.dart';
class SubmissionDetailScreen extends StatefulWidget {
  final int submissionId;
  final String? titleHint;

  const SubmissionDetailScreen({
    super.key,
    required this.submissionId,
    this.titleHint,
  });

  @override
  State<SubmissionDetailScreen> createState() => _SubmissionDetailScreenState();
}

class _SubmissionDetailScreenState extends State<SubmissionDetailScreen> {
  final SupervisorApiService _api = SupervisorApiService();
  FinalSubmissionModel? _submission;
  String? _error;
  bool _loading = true;
  bool _busy = false;
  bool _downloading = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await _api.fetchSubmissionDetail(userId, widget.submissionId);
      if (mounted) setState(() => _submission = data);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<String?> _askNote({
    required String title,
    required String confirmLabel,
    required Color confirmColor,
    bool required = true,
  }) async {
    final controller = TextEditingController();
    String? errorText;
    final result = await showDialog<String>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              backgroundColor: AdminColors.surface,
              shape: adminDialogShape(),
              title: Text(title),
              content: SizedBox(
                width: 420,
                child: TextField(
                  controller: controller,
                  maxLines: 4,
                  autofocus: true,
                  style: const TextStyle(color: Colors.white),
                  decoration: adminFieldDecoration(
                    label: required ? 'Reason / note' : 'Optional note',
                  ).copyWith(errorText: errorText),
                ),
              ),
              actions: [
                TextButton(onPressed: () => Navigator.pop(dialogContext), child: const Tr('Cancel')),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(backgroundColor: confirmColor),
                  onPressed: () {
                    final text = controller.text.trim();
                    if (required && text.isEmpty) {
                      setDialogState(() => errorText = 'This field is required');
                      return;
                    }
                    Navigator.pop(dialogContext, text);
                  },
                  child: Text(confirmLabel),
                ),
              ],
            );
          },
        );
      },
    );
    controller.dispose();
    return result;
  }

  Future<void> _approve() async {
    final note = await _askNote(
      title: 'Approve submission',
      confirmLabel: 'Approve',
      confirmColor: AdminColors.success,
      required: false,
    );
    if (note == null) return;
    await _runAction(() => _api.approveSubmission(
          context.read<AuthProvider>().userId!,
          widget.submissionId,
          note: note,
        ));
  }

  Future<void> _requestRevision() async {
    final note = await _askNote(
      title: 'Request revision',
      confirmLabel: 'Request Revision',
      confirmColor: AdminColors.warning,
    );
    if (note == null || note.trim().isEmpty) return;
    await _runAction(() => _api.requestSubmissionRevision(
          context.read<AuthProvider>().userId!,
          widget.submissionId,
          note: note.trim(),
        ));
  }

  Future<void> _reject() async {
    final reason = await _askNote(
      title: 'Reject submission',
      confirmLabel: 'Reject',
      confirmColor: AdminColors.danger,
    );
    if (reason == null || reason.trim().isEmpty) return;
    await _runAction(() => _api.rejectSubmission(
          context.read<AuthProvider>().userId!,
          widget.submissionId,
          reason: reason.trim(),
        ));
  }

  Future<void> _runAction(Future<FinalSubmissionModel> Function() action) async {
    setState(() => _busy = true);
    try {
      final updated = await action();
      if (!mounted) return;
      setState(() => _submission = updated);
      showAdminSnackBar(context, 'Decision saved. Student notified.');
      Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _downloadFile() async {
    final item = _submission;
    final userId = context.read<AuthProvider>().userId;
    if (item == null || userId == null) return;
    setState(() => _downloading = true);
    try {
      final path = await _api.downloadSubmissionFile(
        userId: userId,
        submissionId: item.id,
        preferredFilename: item.filename.isNotEmpty ? item.filename : null,
      );
      if (!mounted) return;
      showAdminSnackBar(context, 'Saved to $path');
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _downloading = false);
    }
  }

  Future<void> _openPreviewAndComment() async {
    final item = _submission;
    final groupDocId = item?.groupDocumentId;
    if (item == null || groupDocId == null) {
      showAdminSnackBar(
        context,
        'In-app preview is not available for this submission yet.',
        isError: true,
      );
      return;
    }
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DocumentReviewScreen(
          groupId: item.groupId,
          documentId: groupDocId,
          documentTitle: item.title,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final title = _submission?.title.isNotEmpty == true
        ? _submission!.title
        : (widget.titleHint ?? 'Submission Review');

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: AppPalette.dark.innerGlowBackdrop(
        child: Column(
          children: [
            Container(
              height: 72,
              decoration: BoxDecoration(
                color: AdminColors.surface,
                border: Border(bottom: BorderSide(color: AdminColors.borderStrong)),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  IconButton(
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
                          style: const TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                            letterSpacing: -0.2,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 2),
                        Tr('Final submission review',
                          style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.5)),
                        ),
                      ],
                    ),
                  ),
                  if (_busy)
                    const Padding(
                      padding: EdgeInsets.only(right: 12),
                      child: SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: AdminColors.primary),
                      ),
                    ),
                ],
              ),
            ),
            Expanded(child: _buildBody()),
          ],
        ),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const AdminPage(child: AdminLoadingView(label: 'Loading submission...'));
    }
    if (_error != null) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _load));
    }
    final item = _submission;
    if (item == null) {
      return const AdminPage(
        child: AdminEmptyView(
          icon: Icons.search_off_rounded,
          title: 'Submission not found',
          message: 'This submission may have been withdrawn or removed.',
        ),
      );
    }

    final summary = item.analysisSummary;
    final canDecide = item.status.toLowerCase() == 'pending';
    final metaParts = [
      if (item.groupTitle.isNotEmpty) item.groupTitle,
      if (item.filename.isNotEmpty) item.filename,
    ];

    return AdminPage(
      onRefresh: _load,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageMeta(
            text: metaParts.isEmpty
                ? 'Final submission review'
                : metaParts.join(' · '),
          ),
          const SizedBox(height: 16),
          AdminSectionCard(
            title: 'Document',
            icon: Icons.description_outlined,
            trailing: AdminPill(
              label: item.statusLabel,
              color: item.status.toLowerCase() == 'pending'
                  ? AdminColors.warning
                  : AdminColors.success,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(item.title, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                const SizedBox(height: 6),
                Text(
                  item.filename.isEmpty ? 'No filename provided' : item.filename,
                  style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 13),
                ),
                if (item.submittedAt.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text('Submitted: ${item.submittedAt}', style: TextStyle(color: Colors.white.withOpacity(0.45), fontSize: 12)),
                ],
                const SizedBox(height: 14),
                Tr('Download the file, or preview paragraphs in-app and add comments for the student to resolve.',
                  style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 12, height: 1.4),
                ),
                const SizedBox(height: 14),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    ElevatedButton.icon(
                      onPressed: (_busy || _downloading) ? null : _downloadFile,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AdminColors.primary,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      ),
                      icon: _downloading
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          : const Icon(Icons.download_rounded, size: 18),
                      label: Text(_downloading ? 'Downloading…' : 'Download'),
                    ),
                    OutlinedButton.icon(
                      onPressed: (_busy || !item.canPreviewInApp) ? null : _openPreviewAndComment,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.white,
                        side: BorderSide(color: Colors.white.withOpacity(0.35)),
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      ),
                      icon: const Icon(Icons.rate_review_outlined, size: 18),
                      label: const Tr('Preview & Comment'),
                    ),
                  ],
                ),
                if (!item.canPreviewInApp) ...[
                  const SizedBox(height: 10),
                  Tr('Preview & comments need a linked review document. Ask the student to re-submit if this is an older submission.',
                    style: TextStyle(color: AdminColors.warning.withOpacity(0.9), fontSize: 12, height: 1.35),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 16),
          AdminSectionCard(
            title: 'AI Analysis Report',
            icon: Icons.auto_awesome_rounded,
            accent: AdminColors.accent,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Tr('Same Formatify analysis shape used on the student analyze screen (grammar + plagiarism).',
                  style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 12, height: 1.4),
                ),
                const SizedBox(height: 14),
                adminResponsiveGrid(
                  itemCount: 4,
                  itemBuilder: (context, index) {
                    final cards = [
                      AdminStatCard(
                        title: 'Grammar Issues',
                        value: '${summary.grammarIssues}',
                        icon: Icons.spellcheck_rounded,
                      ),
                      AdminStatCard(
                        title: 'Plagiarism Risk',
                        value: '${summary.plagiarismScore.toStringAsFixed(0)}%',
                        icon: Icons.policy_outlined,
                        accent: AdminColors.warning,
                      ),
                      AdminStatCard(
                        title: 'Plagiarism Flags',
                        value: '${summary.plagiarismIssues}',
                        icon: Icons.find_in_page_outlined,
                        accent: AdminColors.danger,
                      ),
                      AdminStatCard(
                        title: 'Compliance',
                        value: '${summary.complianceScore.toStringAsFixed(0)}%',
                        icon: Icons.verified_outlined,
                        accent: AdminColors.success,
                      ),
                    ];
                    return cards[index];
                  },
                ),
                const SizedBox(height: 22),
                const AdminSectionLabel(label: 'Grammar findings'),
                const SizedBox(height: 12),
                if (item.grammarIssues.isEmpty)
                  Tr('No grammar issues reported.', style: TextStyle(color: Colors.white.withOpacity(0.55)))
                else
                  ...item.grammarIssues.map((issue) => _IssueTile(issue: issue, accent: AdminColors.primary)),
                const SizedBox(height: 20),
                const AdminSectionLabel(label: 'Plagiarism findings'),
                const SizedBox(height: 12),
                if (item.plagiarismIssues.isEmpty)
                  Tr('No plagiarism issues reported.', style: TextStyle(color: Colors.white.withOpacity(0.55)))
                else
                  ...item.plagiarismIssues.map((issue) => _IssueTile(issue: issue, accent: AdminColors.warning)),
              ],
            ),
          ),
          const SizedBox(height: 24),
          if (canDecide)
            _DecisionActions(
              busy: _busy,
              stacked: isCompact(context),
              onApprove: _approve,
              onRevision: _requestRevision,
              onReject: _reject,
            )
          else
            AdminSectionCard(
              title: 'Decision',
              icon: Icons.gavel_rounded,
              accent: AdminColors.success,
              child: Text(
                'Status: ${item.statusLabel}'
                '${item.decisionNote.isEmpty ? '' : '\nNote: ${item.decisionNote}'}',
                style: TextStyle(color: Colors.white.withOpacity(0.8), height: 1.45),
              ),
            ),
        ],
      ),
    );
  }
}

class _DecisionActions extends StatelessWidget {
  final bool busy;
  final bool stacked;
  final VoidCallback onApprove;
  final VoidCallback onRevision;
  final VoidCallback onReject;

  const _DecisionActions({
    required this.busy,
    required this.stacked,
    required this.onApprove,
    required this.onRevision,
    required this.onReject,
  });

  @override
  Widget build(BuildContext context) {
    final approve = ElevatedButton.icon(
      onPressed: busy ? null : onApprove,
      style: ElevatedButton.styleFrom(
        backgroundColor: AdminColors.success,
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(vertical: 14),
      ),
      icon: const Icon(Icons.check_rounded, size: 18),
      label: const Tr('Approve'),
    );
    final revision = ElevatedButton.icon(
      onPressed: busy ? null : onRevision,
      style: ElevatedButton.styleFrom(
        backgroundColor: AdminColors.warning,
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(vertical: 14),
      ),
      icon: const Icon(Icons.edit_note_rounded, size: 18),
      label: const Tr('Request Revision'),
    );
    final reject = OutlinedButton.icon(
      onPressed: busy ? null : onReject,
      style: OutlinedButton.styleFrom(
        foregroundColor: AdminColors.danger,
        side: BorderSide(color: AdminColors.danger.withOpacity(0.75)),
        padding: const EdgeInsets.symmetric(vertical: 14),
      ),
      icon: const Icon(Icons.close_rounded, size: 18),
      label: const Tr('Reject'),
    );

    if (stacked) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          approve,
          const SizedBox(height: 10),
          revision,
          const SizedBox(height: 10),
          reject,
        ],
      );
    }

    return Row(
      children: [
        Expanded(child: approve),
        const SizedBox(width: 10),
        Expanded(child: revision),
        const SizedBox(width: 10),
        Expanded(child: reject),
      ],
    );
  }
}

class _IssueTile extends StatelessWidget {
  final AnalysisIssueModel issue;
  final Color accent;

  const _IssueTile({required this.issue, required this.accent});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AdminColors.surfaceAlt,
        borderRadius: BorderRadius.circular(adminTileRadius),
        border: Border.all(color: accent.withOpacity(0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              AdminPill(label: issue.severity.toUpperCase(), color: accent),
              if (issue.similarity != null) ...[
                const SizedBox(width: 8),
                Text(
                  'Similarity ${(issue.similarity! > 1 ? issue.similarity! : issue.similarity! * 100).toStringAsFixed(0)}%',
                  style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 11),
                ),
              ],
            ],
          ),
          if (issue.reason.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(issue.reason, style: const TextStyle(color: Colors.white, fontSize: 13, height: 1.4)),
          ],
          if (issue.original.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text('Original: ${issue.original}', style: TextStyle(color: Colors.white.withOpacity(0.65), fontSize: 12)),
          ],
          if (issue.suggestion.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text('Suggestion: ${issue.suggestion}', style: TextStyle(color: Colors.white.withOpacity(0.65), fontSize: 12)),
          ],
        ],
      ),
    );
  }
}
