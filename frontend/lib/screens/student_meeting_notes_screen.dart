import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';

import '../config/api_config.dart';
import '../models/supervisor_models.dart';
import '../providers/auth_provider.dart';
import '../services/student_api_service.dart';

import '../widgets/tr.dart';
/// Read-only meeting notes for the logged-in student (linked via group contact email).
class StudentMeetingNotesScreen extends StatefulWidget {
  const StudentMeetingNotesScreen({super.key});

  @override
  State<StudentMeetingNotesScreen> createState() =>
      _StudentMeetingNotesScreenState();
}

class _StudentMeetingNotesScreenState extends State<StudentMeetingNotesScreen> {
  AppPalette get _p => context.watch<ThemeProvider>().palette;
  final StudentApiService _api = StudentApiService();
  List<MeetingNoteModel> _notes = const [];
  String? _error;
  bool _loading = true;
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

    return RefreshIndicator(
      color: _p.accent,
      backgroundColor: _p.surface,
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(32),
        children: [
          Tr('Meeting notes from your supervisor — read only.',
            style: TextStyle(color: _p.textSecondary, fontSize: 14),
          ),
          const SizedBox(height: 22),
          if (_notes.isEmpty)
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: _p.surface,
                borderRadius: BorderRadius.circular(
                  _p.isDark ? _p.cardRadius : 12,
                ),
                border: Border.all(
                  color: _p.isDark ? _p.borderStrong : _p.border,
                ),
                boxShadow: _p.isDark ? _p.cardShadow : null,
              ),
              child: Tr('No meeting notes yet for your FYP group. When your supervisor adds notes, they will appear here.',
                style: TextStyle(
                  color: _p.textSecondary,
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
                    color: _p.accent.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(
                    Icons.sticky_note_2_outlined,
                    color: _p.accent,
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
                        style: TextStyle(
                          color: _p.textPrimary,
                          fontWeight: FontWeight.w700,
                          fontSize: 15,
                        ),
                      ),
                      if (meta.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Text(
                          meta,
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
            if (note.actionItems.isNotEmpty) ...[
              const SizedBox(height: 14),
              Tr('Action items',
                style: TextStyle(
                  color: _p.textSecondary,
                  fontWeight: FontWeight.w600,
                  fontSize: 12,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                note.actionItems,
                style: TextStyle(
                  color: _p.textSecondary,
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
