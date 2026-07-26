import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../widgets/admin/admin_ui.dart';

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
    );
  }

  Widget _buildBody() {
    if (_loading) return const AdminPage(child: AdminLoadingView());
    if (_error != null) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _load));
    }

    return AdminPage(
      onRefresh: _load,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageHeader(
            title: 'Meeting Notes',
            subtitle: _notes.isEmpty
                ? 'No notes yet — add the first meeting log for this group'
                : '${_notes.length} note${_notes.length == 1 ? '' : 's'} · latest at the top · visible to students read-only',
          ),
          const SizedBox(height: 22),
          if (_notes.isEmpty)
            const AdminEmptyView(
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
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      title: const Text('Add Note'),
      content: SizedBox(
        width: 460,
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _dateController,
                decoration: const InputDecoration(
                  labelText: 'Date',
                  hintText: 'YYYY-MM-DD',
                  helperText: 'Auto-filled with today — editable',
                ),
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
                decoration: const InputDecoration(
                  labelText: 'Topic',
                  hintText: 'Meeting topic',
                ),
                validator: (value) =>
                    (value == null || value.trim().isEmpty) ? 'Topic is required' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _actionsController,
                maxLines: 4,
                decoration: const InputDecoration(
                  labelText: 'Action items',
                  hintText: 'List follow-ups for the group…',
                  alignLabelWithHint: true,
                ),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: _onSave,
          child: const Text('Save'),
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
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AdminColors.primary.withOpacity(0.14),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.sticky_note_2_outlined, color: AdminColors.primary, size: 20),
              ),
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
            Text(
              'Action items',
              style: TextStyle(
                color: Colors.white.withOpacity(0.7),
                fontWeight: FontWeight.w600,
                fontSize: 12,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              note.actionItems,
              style: TextStyle(color: Colors.white.withOpacity(0.78), height: 1.45, fontSize: 13),
            ),
          ],
        ],
      ),
    );
  }
}
