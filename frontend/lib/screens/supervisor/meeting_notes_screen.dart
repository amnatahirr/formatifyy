import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../theme/app_theme.dart';
import '../../widgets/admin/admin_ui.dart';

import '../../widgets/tr.dart';
class MeetingNotesScreen extends StatefulWidget {
  final int groupId;
  final String? groupTitle;

  const MeetingNotesScreen({
    super.key,
    required this.groupId,
    this.groupTitle,
  });

  @override
  State<MeetingNotesScreen> createState() => _MeetingNotesScreenState();
}

class _MeetingNotesScreenState extends State<MeetingNotesScreen> {
  final SupervisorApiService _api = SupervisorApiService();
  List<MeetingNoteModel> _notes = const [];
  String? _error;
  bool _loading = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _load();
    });
  }

  Future<void> _load() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final notes = await _api.fetchMeetingNotes(userId, widget.groupId);
      if (mounted) setState(() => _notes = notes);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openAddNote() async {
    final draft = await showDialog<_MeetingNoteDraft>(
      context: context,
      barrierDismissible: !_saving,
      builder: (dialogContext) => const _AddMeetingNoteDialog(),
    );

    if (draft == null || !mounted) return;

    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;

    setState(() => _saving = true);
    try {
      await _api.createMeetingNote(
        userId: userId,
        groupId: widget.groupId,
        meetingDate: draft.meetingDate,
        topic: draft.topic,
        actionItems: draft.actionItems,
      );
      if (!mounted) return;
      showAdminSnackBar(context, 'Meeting note saved. Students can view it read-only.');
      await _load();
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final title = widget.groupTitle?.isNotEmpty == true ? widget.groupTitle! : 'Meeting Notes';

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
                        Tr('Meeting log',
                          style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.5)),
                        ),
                      ],
                    ),
                  ),
                  ElevatedButton.icon(
                    onPressed: _saving || _loading ? null : _openAddNote,
                    icon: _saving
                        ? const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Icon(Icons.note_add_outlined, size: 18),
                    label: Text(_saving ? 'Saving…' : 'Add Note'),
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
      return const AdminPage(child: AdminLoadingView(label: 'Loading notes...'));
    }
    if (_error != null) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _load));
    }

    return AdminPage(
      onRefresh: _load,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageMeta(
            text: _notes.isEmpty
                ? 'No notes yet — add the first meeting log for this group'
                : '${_notes.length} note${_notes.length == 1 ? '' : 's'} · latest at the top · visible to students read-only',
          ),
          const SizedBox(height: 18),
          if (_notes.isEmpty)
            const AdminEmptyView(
              icon: Icons.sticky_note_2_outlined,
              title: 'No meeting notes yet',
              message: 'Use Add Note to record the meeting date, topic, and action items.',
            )
          else
            ..._notes.map(
              (note) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _MeetingNoteCard(note: note),
              ),
            ),
        ],
      ),
    );
  }
}

class _MeetingNoteDraft {
  final String meetingDate;
  final String topic;
  final String actionItems;

  const _MeetingNoteDraft({
    required this.meetingDate,
    required this.topic,
    required this.actionItems,
  });
}

/// Owns its Text controllers so they are never disposed while the dialog
/// route is still animating out (avoids dependents.isEmpty assertion).
class _AddMeetingNoteDialog extends StatefulWidget {
  const _AddMeetingNoteDialog();

  @override
  State<_AddMeetingNoteDialog> createState() => _AddMeetingNoteDialogState();
}

class _AddMeetingNoteDialogState extends State<_AddMeetingNoteDialog> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _dateController;
  late final TextEditingController _topicController;
  late final TextEditingController _actionsController;

  @override
  void initState() {
    super.initState();
    _dateController = TextEditingController(
      text: DateTime.now().toIso8601String().substring(0, 10),
    );
    _topicController = TextEditingController();
    _actionsController = TextEditingController();
  }

  @override
  void dispose() {
    _dateController.dispose();
    _topicController.dispose();
    _actionsController.dispose();
    super.dispose();
  }

  void _onSave() {
    if (_formKey.currentState?.validate() != true) return;
    Navigator.of(context).pop(
      _MeetingNoteDraft(
        meetingDate: _dateController.text.trim(),
        topic: _topicController.text.trim(),
        actionItems: _actionsController.text.trim(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      backgroundColor: AdminColors.surface,
      shape: adminDialogShape(),
      title: const Tr('Add Note'),
      content: SizedBox(
        width: 460,
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _dateController,
                style: const TextStyle(color: Colors.white),
                decoration: adminFieldDecoration(
                  label: 'Date',
                  hint: 'YYYY-MM-DD',
                  prefixIcon: Icons.event_rounded,
                ).copyWith(helperText: 'Auto-filled with today — editable'),
                validator: (value) {
                  final text = (value ?? '').trim();
                  if (text.isEmpty) return 'Date is required';
                  if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(text)) {
                    return 'Use YYYY-MM-DD';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _topicController,
                style: const TextStyle(color: Colors.white),
                decoration: adminFieldDecoration(
                  label: 'Topic',
                  hint: 'Meeting topic',
                  prefixIcon: Icons.title_rounded,
                ),
                validator: (value) =>
                    (value == null || value.trim().isEmpty) ? 'Topic is required' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _actionsController,
                maxLines: 4,
                style: const TextStyle(color: Colors.white),
                decoration: adminFieldDecoration(
                  label: 'Action items',
                  hint: 'List follow-ups for the group…',
                ).copyWith(alignLabelWithHint: true),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Tr('Cancel'),
        ),
        ElevatedButton(
          onPressed: _onSave,
          child: const Tr('Save'),
        ),
      ],
    );
  }
}

class _MeetingNoteCard extends StatelessWidget {
  final MeetingNoteModel note;

  const _MeetingNoteCard({required this.note});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: adminCardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const AdminIconBadge(icon: Icons.sticky_note_2_outlined, size: 20),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      note.topic,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                        fontSize: 15,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      note.meetingDate.isEmpty ? 'No date' : note.meetingDate,
                      style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 12),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (note.actionItems.isNotEmpty) ...[
            const SizedBox(height: 14),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AdminColors.surfaceAlt,
                borderRadius: BorderRadius.circular(adminTileRadius),
                border: Border.all(color: AdminColors.borderStrong),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Tr('ACTION ITEMS',
                    style: TextStyle(
                      color: AdminColors.accent.withOpacity(0.9),
                      fontWeight: FontWeight.w700,
                      fontSize: 10,
                      letterSpacing: 0.9,
                    ),
                  ),
                  const SizedBox(height: 7),
                  Text(
                    note.actionItems,
                    style: TextStyle(color: Colors.white.withOpacity(0.8), height: 1.45, fontSize: 13),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
