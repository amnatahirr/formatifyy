import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/api_config.dart';
import '../models/supervisor_models.dart';
import '../providers/auth_provider.dart';
import '../services/student_api_service.dart';

/// Read-only meeting notes for the logged-in student (linked via group contact email).
class StudentMeetingNotesScreen extends StatefulWidget {
  const StudentMeetingNotesScreen({super.key});

  @override
  State<StudentMeetingNotesScreen> createState() =>
      _StudentMeetingNotesScreenState();
}

class _StudentMeetingNotesScreenState extends State<StudentMeetingNotesScreen> {
  final StudentApiService _api = StudentApiService();
  List<MeetingNoteModel> _notes = const [];
  String? _error;
  bool _loading = true;

  static const _card = Color(0xFF161B22);
  static const _border = Color(0x22FFFFFF);
  static const _accent = Color(0xFF3B82F6);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    if (!mounted) return;
    final userId = context.read<AuthProvider>().userId;
    setState(() {
      _loading = true;
      _error = null;
    });

    if (userId == null) {
      setState(() {
        _loading = false;
        _error = 'Please sign in again to view meeting notes.';
      });
      return;
    }

    try {
      // Uses ApiConfig.getBaseUrl() via StudentApiService (same as DocumentProvider).
      debugPrint(
        '[MeetingNotes] GET ${ApiConfig.getBaseUrl()}/student/meeting-notes',
      );
      final notes = await _api.fetchMeetingNotes(userId);
      if (mounted) {
        setState(() {
          _notes = notes;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => _error = e.toString());
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator(color: _accent));
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
                style: TextStyle(color: Colors.white.withOpacity(0.75)),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              TextButton(onPressed: _load, child: const Text('Retry')),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      color: _accent,
      backgroundColor: _card,
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(32),
        children: [
          Text(
            'Meeting notes from your supervisor — read only.',
            style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 14),
          ),
          const SizedBox(height: 22),
          if (_notes.isEmpty)
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: _card,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: _border),
              ),
              child: Text(
                'No meeting notes yet for your FYP group. When your supervisor adds notes, they will appear here.',
                style: TextStyle(
                  color: Colors.white.withOpacity(0.65),
                  height: 1.45,
                ),
              ),
            )
          else
            ..._notes.map(_noteCard),
        ],
      ),
    );
  }

  Widget _noteCard(MeetingNoteModel note) {
    final meta = [
      if (note.meetingDate.isNotEmpty) note.meetingDate,
      if (note.groupTitle.isNotEmpty) note.groupTitle,
      if (note.supervisorName.isNotEmpty) note.supervisorName,
    ].join(' · ');

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: _card,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: _border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: _accent.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(
                    Icons.sticky_note_2_outlined,
                    color: _accent,
                    size: 20,
                  ),
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
                      if (meta.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Text(
                          meta,
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.5),
                            fontSize: 12,
                          ),
                        ),
                      ],
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
                style: TextStyle(
                  color: Colors.white.withOpacity(0.78),
                  height: 1.45,
                  fontSize: 13,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
