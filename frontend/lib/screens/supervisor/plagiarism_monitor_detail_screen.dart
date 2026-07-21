import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../widgets/admin/admin_ui.dart';

class PlagiarismMonitorDetailScreen extends StatefulWidget {
  final int groupId;
  final String? titleHint;

  const PlagiarismMonitorDetailScreen({
    super.key,
    required this.groupId,
    this.titleHint,
  });

  @override
  State<PlagiarismMonitorDetailScreen> createState() => _PlagiarismMonitorDetailScreenState();
}

class _PlagiarismMonitorDetailScreenState extends State<PlagiarismMonitorDetailScreen> {
  final SupervisorApiService _api = SupervisorApiService();
  PlagiarismMonitorGroup? _detail;
  String? _error;
  bool _loading = true;
  bool _flagging = false;

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
      final data = await _api.fetchPlagiarismMonitorDetail(userId, widget.groupId);
      if (mounted) setState(() => _detail = data);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Color _riskColor(String level) {
    switch (level) {
      case 'high':
        return AdminColors.danger;
      case 'some':
        return AdminColors.warning;
      default:
        return AdminColors.success;
    }
  }

  String _riskLabel(String level) {
    switch (level) {
      case 'high':
        return 'High risk';
      case 'some':
        return 'Some risk';
      default:
        return 'Safe';
    }
  }

  Future<void> _flag() async {
    final controller = TextEditingController();
    final note = await showDialog<String>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          backgroundColor: AdminColors.surface,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Text('Flag plagiarism'),
          content: SizedBox(
            width: 420,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Send a warning notification to the student group about plagiarism risk.',
                  style: TextStyle(color: Colors.white.withOpacity(0.7), height: 1.4),
                ),
                const SizedBox(height: 14),
                TextField(
                  controller: controller,
                  maxLines: 3,
                  autofocus: true,
                  decoration: InputDecoration(
                    labelText: 'Optional note',
                    hintText: 'Add guidance for the students…',
                    filled: true,
                    fillColor: AdminColors.card,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(dialogContext), child: const Text('Cancel')),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: AdminColors.danger),
              onPressed: () => Navigator.pop(dialogContext, controller.text.trim()),
              child: const Text('Send Flag'),
            ),
          ],
        );
      },
    );
    controller.dispose();
    if (note == null) return;

    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _flagging = true);
    try {
      final result = await _api.flagPlagiarism(userId, widget.groupId, note: note);
      if (!mounted) return;
      final email = (result['notified_email'] ?? '').toString();
      showAdminSnackBar(
        context,
        email.isEmpty
            ? 'Warning queued (no student email on file).'
            : 'Warning sent to $email.',
      );
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _flagging = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final title = _detail?.title.isNotEmpty == true ? _detail!.title : (widget.titleHint ?? 'Plagiarism Detail');

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
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.arrow_back_rounded, color: Colors.white),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    title,
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Colors.white),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
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
    if (_loading) return const AdminPage(child: AdminLoadingView());
    if (_error != null) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _load));
    }
    final detail = _detail;
    if (detail == null) {
      return const AdminPage(child: AdminEmptyView(message: 'Plagiarism details unavailable.'));
    }

    final color = _riskColor(detail.riskLevel);

    return AdminPage(
      onRefresh: _load,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageHeader(
            title: detail.title,
            subtitle: detail.projectTitle.isEmpty
                ? 'Matched sources from Formatify plagiarism detection'
                : detail.projectTitle,
          ),
          const SizedBox(height: 18),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(18),
            decoration: adminCardDecoration().copyWith(
              border: Border.all(color: color.withOpacity(0.55)),
              color: color.withOpacity(0.1),
            ),
            child: Row(
              children: [
                Container(
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Center(
                    child: Text(
                      '${detail.plagiarismScore.round()}%',
                      style: TextStyle(color: color, fontWeight: FontWeight.w800, fontSize: 18),
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _riskLabel(detail.riskLevel),
                        style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 16),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        '${detail.matchCount} matched source${detail.matchCount == 1 ? '' : 's'}',
                        style: TextStyle(color: Colors.white.withOpacity(0.7)),
                      ),
                      if (detail.memberNames.isNotEmpty) ...[
                        const SizedBox(height: 6),
                        Text(
                          detail.memberNames.join(', '),
                          style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 12),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          AdminSectionCard(
            title: 'Matched sources',
            child: detail.matches.isEmpty
                ? Text(
                    'No matched sources were returned for this group.',
                    style: TextStyle(color: Colors.white.withOpacity(0.6)),
                  )
                : Column(
                    children: detail.matches.map((match) {
                      return Container(
                        width: double.infinity,
                        margin: const EdgeInsets.only(bottom: 10),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: AdminColors.background.withOpacity(0.4),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: AdminColors.border),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    match.source,
                                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
                                  ),
                                ),
                                Text(
                                  '${match.similarity.round()}% similar',
                                  style: const TextStyle(
                                    color: AdminColors.warning,
                                    fontWeight: FontWeight.w700,
                                    fontSize: 12,
                                  ),
                                ),
                              ],
                            ),
                            if (match.sentence.isNotEmpty) ...[
                              const SizedBox(height: 8),
                              Text(
                                match.sentence,
                                style: TextStyle(color: Colors.white.withOpacity(0.7), height: 1.4, fontSize: 13),
                              ),
                            ],
                            if (match.reason.isNotEmpty) ...[
                              const SizedBox(height: 6),
                              Text(
                                match.reason,
                                style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 12, height: 1.35),
                              ),
                            ],
                          ],
                        ),
                      );
                    }).toList(),
                  ),
          ),
          const SizedBox(height: 22),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _flagging ? null : _flag,
              style: ElevatedButton.styleFrom(
                backgroundColor: AdminColors.danger,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              icon: _flagging
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.flag_outlined, size: 18),
              label: Text(_flagging ? 'Sending…' : 'Flag'),
            ),
          ),
        ],
      ),
    );
  }
}
