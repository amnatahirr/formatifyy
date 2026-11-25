import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../providers/document_provider.dart';
import '../../providers/fyp_provider.dart';
import '../../theme/app_theme.dart';

import '../../widgets/tr.dart';
import 'supervisor_selection_screen.dart';
/// Shows the student's latest assignment_requests status (email-matched).
class MySupervisorScreen extends StatefulWidget {
  /// Opens the Choose Supervisor tab (e.g. after rejection).
  final VoidCallback? onChooseSupervisor;

  /// Quick-access cards (open the same tabs as the sidebar).
  final VoidCallback? onOpenMilestones;
  final VoidCallback? onOpenMeetingNotes;
  final VoidCallback? onOpenPlagiarism;
  final VoidCallback? onOpenStatusTracker;

  const MySupervisorScreen({
    super.key,
    this.onChooseSupervisor,
    this.onOpenMilestones,
    this.onOpenMeetingNotes,
    this.onOpenPlagiarism,
    this.onOpenStatusTracker,
  });

  @override
  State<MySupervisorScreen> createState() => _MySupervisorScreenState();
}

class _MySupervisorScreenState extends State<MySupervisorScreen> {
  AppPalette get _p => context.watch<ThemeProvider>().palette;
  String? _error;
  bool _loading = true;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _load();
    });
  }

  Future<void> _load() async {
    final auth = context.read<AuthProvider>();
    final userId = auth.userId;
    final email = (auth.userEmail ?? auth.email ?? '').trim();
    if (userId == null) {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = 'Please sign in again to view supervisor status.';
        });
      }
      return;
    }
    if (email.isEmpty) {
      setState(() {
        _loading = false;
        _error = 'Your account has no email — cannot look up supervisor status.';
      });
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await context.read<FypProvider>().fetchAssignmentStatus(
            userId: userId,
            email: email,
          );
      if (!mounted) return;
      if (data == null) {
        setState(() {
          _error = context.read<FypProvider>().errorMessage ?? 'Failed to load status';
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Center(child: CircularProgressIndicator(color: _p.accent));
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _error!,
                style: TextStyle(color: _p.textSecondary),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              TextButton(onPressed: _load, child: const Tr('Retry')),
            ],
          ),
        ),
      );
    }

    final statusMap = context.watch<FypProvider>().assignmentStatus;
    final found = statusMap?['found'] == true;
    final status = (statusMap?['status'] ?? '').toString().toLowerCase();

    return RefreshIndicator(
      color: _p.accent,
      backgroundColor: _p.surface,
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(32),
        children: [
          _quickAccessCards(),
          const SizedBox(height: 26),
          Tr('Your FYP supervisor assignment status.',
            style: TextStyle(color: _p.textSecondary, fontSize: 14),
          ),
          const SizedBox(height: 22),
          if (!found || status.isEmpty)
            _emptyCard()
          else if (status == 'pending')
            _pendingCard(statusMap!)
          else if (status == 'rejected')
            _rejectedCard(statusMap!)
          else if (status == 'accepted')
            _acceptedCard(statusMap!)
          else
            _genericCard(statusMap!),
        ],
      ),
    );
  }

  // ─── Quick access cards (Milestones / Meeting Notes / Plagiarism / Status) ───

  Widget _quickAccessCards() {
    final items = <_QuickItem>[
      if (widget.onOpenMilestones != null)
        _QuickItem(
          'Milestones',
          'View your FYP milestone checklist',
          Icons.checklist_outlined,
          const Color(0xFF6366F1),
          widget.onOpenMilestones!,
        ),
      if (widget.onOpenMeetingNotes != null)
        _QuickItem(
          'Meeting Notes',
          'Read-only notes from your supervisor',
          Icons.sticky_note_2_outlined,
          const Color(0xFF06B6D4),
          widget.onOpenMeetingNotes!,
        ),
      if (widget.onOpenPlagiarism != null)
        _QuickItem(
          'Plagiarism Report',
          'Score and matched sources',
          Icons.policy_outlined,
          const Color(0xFFEC4899),
          widget.onOpenPlagiarism!,
        ),
      if (widget.onOpenStatusTracker != null)
        _QuickItem(
          'Status Tracker',
          'Submission review status and decisions',
          Icons.track_changes_outlined,
          const Color(0xFF10B981),
          widget.onOpenStatusTracker!,
        ),
    ];
    if (items.isEmpty) return const SizedBox.shrink();

    return LayoutBuilder(
      builder: (context, c) {
        const gap = 14.0;
        final cols = c.maxWidth >= 1100 ? 4 : (c.maxWidth >= 560 ? 2 : 1);
        final w = (c.maxWidth - gap * (cols - 1)) / cols;
        return Wrap(
          spacing: gap,
          runSpacing: gap,
          children: items
              .map((f) => SizedBox(width: w, child: _quickCard(f)))
              .toList(),
        );
      },
    );
  }

  Widget _quickCard(_QuickItem f) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: InkWell(
        onTap: f.onTap,
        borderRadius: BorderRadius.circular(_p.isDark ? _p.cardRadius : 12),
        child: Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: _p.surface,
            borderRadius: BorderRadius.circular(_p.isDark ? _p.cardRadius : 12),
            border: Border.all(color: _p.isDark ? _p.borderStrong : _p.border),
            boxShadow: _p.isDark ? _p.cardShadow : null,
          ),
          child: Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: f.color.withOpacity(0.14),
                  borderRadius: BorderRadius.circular(11),
                ),
                child: Icon(f.icon, color: f.color, size: 21),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Tr(
                      f.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w600,
                        color: _p.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Tr(
                      f.subtitle,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 11,
                        color: _p.textSecondary,
                        height: 1.3,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_rounded, color: _p.textMuted, size: 18),
            ],
          ),
        ),
      ),
    );
  }

  Widget _emptyCard() {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: _p.surface,
        borderRadius: BorderRadius.circular(_p.isDark ? _p.cardRadius : 12),
        border: Border.all(color: _p.isDark ? _p.borderStrong : _p.border),
        boxShadow: _p.isDark ? _p.cardShadow : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Tr('No supervisor request yet.',
            style: TextStyle(color: _p.textSecondary, height: 1.45),
          ),
          const SizedBox(height: 14),
          ElevatedButton.icon(
            onPressed: widget.onChooseSupervisor,
            icon: const Icon(Icons.school_outlined, size: 18),
            label: const Tr('Choose Supervisor'),
            style: ElevatedButton.styleFrom(
              backgroundColor: _p.accent,
              foregroundColor: Colors.white,
            ),
          ),
        ],
      ),
    );
  }

  bool _canChange(Map<String, dynamic> data) =>
      data['can_change_supervisor'] == true;

  Future<void> _openChangeSupervisor() async {
    final p = context.read<ThemeProvider>().palette;
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (routeCtx) => Scaffold(
          backgroundColor: p.scaffold,
          appBar: AppBar(
            backgroundColor: p.surface,
            foregroundColor: p.textPrimary,
            elevation: 0,
            title: const Tr('Change Supervisor'),
          ),
          body: SupervisorSelectionScreen(
            changeMode: true,
            onRequestSubmitted: () => Navigator.of(routeCtx).pop(true),
          ),
        ),
      ),
    );
    if (changed == true && mounted) await _load();
  }

  Widget _changeSupervisorButton() {
    return OutlinedButton.icon(
      onPressed: _openChangeSupervisor,
      icon: const Icon(Icons.swap_horiz_rounded, size: 18),
      label: const Tr('Change Supervisor'),
      style: OutlinedButton.styleFrom(
        foregroundColor: const Color(0xFFF59E0B),
        side: const BorderSide(color: Color(0xFFF59E0B)),
      ),
    );
  }

  Widget _memberOnlyNote() {
    return Tr(
      'Only your group leader can change the supervisor.',
      style: TextStyle(color: _p.textMuted, fontSize: 12),
    );
  }

  Widget _pendingCard(Map<String, dynamic> data) {
    final supName = (data['supervisor_name'] ?? '').toString().trim();
    return _statusShell(
      accent: const Color(0xFFF59E0B),
      title: 'Request pending',
      subtitle:
          'Waiting for ${(data['project_title'] ?? data['group_name'] ?? 'your group').toString()} to be reviewed.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Group: ${data['group_name'] ?? '—'}\n'
            'Project: ${data['project_title'] ?? '—'}'
            '${supName.isNotEmpty ? '\nRequested supervisor: $supName' : ''}',
            style: TextStyle(color: _p.textSecondary, height: 1.5),
          ),
          const SizedBox(height: 16),
          if (_canChange(data)) _changeSupervisorButton() else _memberOnlyNote(),
        ],
      ),
    );
  }

  Widget _rejectedCard(Map<String, dynamic> data) {
    final reason = (data['rejection_reason'] ?? '').toString().trim();
    return _statusShell(
      accent: const Color(0xFFEF4444),
      title: 'Request rejected',
      subtitle: 'You can submit a new request to another supervisor.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            reason.isEmpty ? 'No rejection reason provided.' : reason,
            style: TextStyle(color: _p.textSecondary, height: 1.45),
          ),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: widget.onChooseSupervisor,
            icon: const Icon(Icons.refresh, size: 18),
            label: const Tr('Choose another supervisor'),
            style: ElevatedButton.styleFrom(
              backgroundColor: _p.accent,
              foregroundColor: Colors.white,
            ),
          ),
        ],
      ),
    );
  }

  Widget _acceptedCard(Map<String, dynamic> data) {
    final supervisor = Map<String, dynamic>.from(
      (data['supervisor'] as Map?) ?? const {},
    );
    final group = Map<String, dynamic>.from(
      (data['group'] as Map?) ?? const {},
    );
    final groupId = data['fyp_group_id'] ?? group['id'];

    return _statusShell(
      accent: const Color(0xFF10B981),
      title: 'Supervisor assigned',
      subtitle: 'Your FYP group is active.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _infoRow('Supervisor', supervisor['name']?.toString() ?? '—'),
          _infoRow('Email', supervisor['email']?.toString() ?? '—'),
          _infoRow(
            'Department',
            [
              supervisor['department_name'],
              supervisor['department_code'],
            ].where((e) => (e ?? '').toString().isNotEmpty).join(' · ').ifEmpty('—'),
          ),
          _infoRow('Group', group['title']?.toString() ?? data['group_name']?.toString() ?? '—'),
          _infoRow(
            'Project',
            group['project_title']?.toString() ?? data['project_title']?.toString() ?? '—',
          ),
          _infoRow('Group ID', groupId?.toString() ?? '—'),
          const SizedBox(height: 8),
          Wrap(
            spacing: 12,
            runSpacing: 10,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              ElevatedButton.icon(
                onPressed: () => _openSendReportDialog(groupId),
                icon: const Icon(Icons.send_rounded, size: 18),
                label: const Tr('Send Report to Supervisor'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: _p.accent,
                  foregroundColor: Colors.white,
                ),
              ),
              if (_canChange(data))
                _changeSupervisorButton()
              else
                _memberOnlyNote(),
            ],
          ),
        ],
      ),
    );
  }

  // ─── Send Report to Supervisor (reuses DocumentProvider.submitFinalSubmission) ───

  void _snack(String msg, {bool error = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor:
            error ? const Color(0xFFEF4444) : const Color(0xFF10B981),
      ),
    );
  }

  String _reportStatusLabel(String status) {
    switch (status.toLowerCase()) {
      case 'completed':
      case 'formatted':
        return 'Completed';
      case 'processing':
        return 'In Progress';
      case 'uploaded':
      case 'pending':
        return 'Ready to Analyze';
      case 'draft':
        return 'Draft';
      default:
        return 'Formatted';
    }
  }

  Color _reportStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'completed':
      case 'formatted':
        return const Color(0xFF10B981);
      case 'processing':
        return const Color(0xFFEAB308);
      case 'uploaded':
      case 'pending':
        return const Color(0xFF6366F1);
      case 'draft':
        return const Color(0xFFEF4444);
      default:
        return const Color(0xFF10B981);
    }
  }

  String _reportTimeAgo(dynamic value) {
    if (value == null) return 'just now';
    var s = value.toString().trim();
    if (!s.endsWith('Z') && !s.contains('+')) s += 'Z';
    final parsed = DateTime.tryParse(s)?.toLocal();
    if (parsed == null) return 'just now';
    final d = DateTime.now().difference(parsed);
    if (d.isNegative || d.inSeconds < 30) return 'just now';
    if (d.inDays >= 7) {
      final w = (d.inDays / 7).floor();
      return '$w week${w > 1 ? 's' : ''} ago';
    }
    if (d.inDays > 0) return '${d.inDays} day${d.inDays > 1 ? 's' : ''} ago';
    if (d.inHours > 0) {
      return '${d.inHours} hour${d.inHours > 1 ? 's' : ''} ago';
    }
    if (d.inMinutes > 0) {
      return '${d.inMinutes} minute${d.inMinutes > 1 ? 's' : ''} ago';
    }
    return 'less than a minute ago';
  }

  Widget _reportChip(String text, Color color, {IconData? icon}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.13),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 11, color: color),
            const SizedBox(width: 4),
          ],
          Text(
            text,
            style: TextStyle(
              fontSize: 10.5,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _openSendReportDialog(dynamic rawGroupId) async {
    final auth = context.read<AuthProvider>();
    final docs = context.read<DocumentProvider>();
    final p = context.read<ThemeProvider>().palette;

    final userId = auth.userId;
    final email = (auth.userEmail ?? auth.email ?? '').trim();
    final groupId = int.tryParse('${rawGroupId ?? ''}');

    if (userId == null || email.isEmpty) {
      _snack('Please sign in again to send', error: true);
      return;
    }
    if (groupId == null) {
      _snack('No accepted supervisor group found yet.', error: true);
      return;
    }

    // Refresh My Reports list (not awaited; dialog rebuilds when it arrives).
    docs.fetchDocuments(userId);

    final picked = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (ctx) {
        int? selectedId;
        return StatefulBuilder(
          builder: (ctx, setLocal) => AnimatedBuilder(
            animation: docs,
            builder: (ctx, _) {
              final list = docs.documents;
              Widget body;
              if (docs.isLoading && list.isEmpty) {
                body = Center(
                  child: CircularProgressIndicator(color: p.accent),
                );
              } else if (list.isEmpty) {
                body = Center(
                  child: Text(
                    'No reports found. Upload a document from New Report first.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: p.textSecondary),
                  ),
                );
              } else {
                body = ListView.separated(
                  itemCount: list.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 10),
                  itemBuilder: (_, i) {
                    final doc = list[i];
                    final id = doc['id'];
                    final selected =
                        id != null && selectedId != null && '$id' == '$selectedId';
                    final status = (doc['status'] ?? 'draft').toString();
                    final sColor = _reportStatusColor(status);
                    final formatted = doc['has_formatted'] == true;
                    return InkWell(
                      borderRadius: BorderRadius.circular(12),
                      onTap: id == null
                          ? null
                          : () => setLocal(() {
                                selectedId = id is int ? id : int.tryParse('$id');
                              }),
                      child: Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: selected ? p.accentSoft : p.surfaceAlt,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: selected ? p.accent : p.border,
                            width: selected ? 1.5 : 1,
                          ),
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(
                              selected
                                  ? Icons.radio_button_checked
                                  : Icons.radio_button_unchecked,
                              size: 20,
                              color: selected ? p.accent : p.textMuted,
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    (doc['filename'] ?? 'Untitled').toString(),
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      color: p.textPrimary,
                                      fontSize: 13.5,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  const SizedBox(height: 3),
                                  Text(
                                    '${doc['template_name'] ?? 'No template'} · Modified ${_reportTimeAgo(doc['created_at'])}',
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      color: p.textSecondary,
                                      fontSize: 11.5,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Wrap(
                                    spacing: 6,
                                    runSpacing: 6,
                                    children: [
                                      _reportChip(
                                        _reportStatusLabel(status),
                                        sColor,
                                      ),
                                      if (formatted)
                                        _reportChip(
                                          'Formatted saved',
                                          const Color(0xFF10B981),
                                          icon: Icons.check_circle,
                                        ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                );
              }

              return AlertDialog(
                backgroundColor: p.surface,
                title: Text(
                  'Send Report to Supervisor',
                  style: TextStyle(color: p.textPrimary, fontSize: 18),
                ),
                content: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 520),
                  child: SizedBox(
                    width: double.maxFinite,
                    height: 400,
                    child: body,
                  ),
                ),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.pop(ctx),
                    child: const Tr('Cancel'),
                  ),
                  ElevatedButton.icon(
                    onPressed: selectedId == null
                        ? null
                        : () {
                            final doc = list.firstWhere(
                              (d) => '${d['id']}' == '$selectedId',
                            );
                            Navigator.pop(
                              ctx,
                              Map<String, dynamic>.from(doc),
                            );
                          },
                    icon: const Icon(Icons.send_rounded, size: 16),
                    label: const Tr('Send'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF10B981),
                      foregroundColor: Colors.white,
                    ),
                  ),
                ],
              );
            },
          ),
        );
      },
    );

    if (picked == null || !mounted) return;
    await _submitReport(picked, groupId, userId, email);
  }

  Future<void> _submitReport(
    Map<String, dynamic> doc,
    int groupId,
    int userId,
    String email,
  ) async {
    final docs = context.read<DocumentProvider>();
    final rawId = doc['id'];
    final docId = rawId is int ? rawId : int.tryParse('$rawId');
    if (docId == null) {
      _snack('Invalid document', error: true);
      return;
    }

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(
        child: CircularProgressIndicator(color: Color(0xFF10B981)),
      ),
    );

    final result = await docs.submitFinalSubmission(
      userId: userId,
      groupId: groupId,
      title: (doc['filename'] ?? 'Report').toString(),
      filename: (doc['filename'] ?? 'document.docx').toString(),
      studentContactEmail: email,
      sourceDocumentId: docId,
      analysisReport: docs.analysisReportFor(docId),
    );

    if (!mounted) return;
    Navigator.of(context, rootNavigator: true).pop(); // close loader

    if (result != null) {
      _snack('Sent to supervisor for review');
    } else {
      _snack(docs.errorMessage ?? 'Failed to send', error: true);
    }
  }

  Widget _genericCard(Map<String, dynamic> data) {
    return _statusShell(
      accent: _p.accent,
      title: 'Status: ${data['status']}',
      subtitle: data['group_name']?.toString() ?? '',
      child: const SizedBox.shrink(),
    );
  }

  Widget _statusShell({
    required Color accent,
    required String title,
    required String subtitle,
    required Widget child,
  }) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: _p.surface,
        borderRadius: BorderRadius.circular(_p.isDark ? _p.cardRadius : 12),
        border: Border.all(color: _p.isDark ? _p.borderStrong : _p.border),
        boxShadow: _p.isDark ? _p.cardShadow : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: accent.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.verified_user_outlined, color: accent, size: 22),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: TextStyle(
                        color: _p.textPrimary,
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    if (subtitle.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        subtitle,
                        style: TextStyle(
                          color: _p.textSecondary,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          child,
        ],
      ),
    );
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(
              label,
              style: TextStyle(color: _p.textMuted, fontSize: 12),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(color: _p.textPrimary, fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
}

extension on String {
  String ifEmpty(String fallback) => isEmpty ? fallback : this;
}

class _QuickItem {
  final String title, subtitle;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;
  const _QuickItem(this.title, this.subtitle, this.icon, this.color, this.onTap);
}
