import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/admin_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/admin_api_service.dart';
import '../../theme/app_theme.dart';
import '../../widgets/admin/admin_ui.dart';

/// Admin UI for global Semester 6 / 7 FYP submission deadlines.
class SemesterDeadlinesScreen extends StatefulWidget {
  final bool embedded;

  const SemesterDeadlinesScreen({super.key, this.embedded = false});

  @override
  State<SemesterDeadlinesScreen> createState() =>
      _SemesterDeadlinesScreenState();
}

class _SemesterDeadlinesScreenState extends State<SemesterDeadlinesScreen> {
  final AdminApiService _api = AdminApiService();
  bool _loading = true;
  String? _error;
  List<SemesterDeadlineModel> _rows = const [];

  static const _semesters = [6, 7];

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
      final rows = await _api.fetchSemesterDeadlines(userId);
      if (mounted) setState(() => _rows = rows);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  SemesterDeadlineModel? _rowFor(int semester) {
    for (final r in _rows) {
      if (r.semester == semester) return r;
    }
    return null;
  }

  String _displayDate(String raw) {
    final date = DateTime.tryParse(raw);
    if (date == null) return raw.isEmpty ? 'Not set' : raw;
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    return '${date.day} ${months[date.month - 1]} ${date.year}';
  }

  Future<void> _pickAndSave(int semester) async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;

    final existing = _rowFor(semester);
    final initial = existing != null && existing.deadlineDate.isNotEmpty
        ? DateTime.tryParse(existing.deadlineDate) ?? DateTime.now()
        : DateTime.now();

    final picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(2020),
      lastDate: DateTime(2035),
      helpText: 'Semester $semester deadline',
    );
    if (picked == null || !mounted) return;

    final iso =
        '${picked.year.toString().padLeft(4, '0')}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';

    try {
      if (existing == null) {
        await _api.createSemesterDeadline(
          userId,
          semester: semester,
          deadlineDate: iso,
        );
      } else {
        await _api.updateSemesterDeadline(
          userId,
          existing.id,
          deadlineDate: iso,
        );
      }
      if (!mounted) return;
      showAdminSnackBar(context, 'Semester $semester deadline saved.');
      await _load();
    } catch (e) {
      if (!mounted) return;
      showAdminSnackBar(context, e.toString(), isError: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final body = _loading
        ? const Center(child: CircularProgressIndicator(color: AdminColors.primary))
        : _error != null
            ? AdminErrorView(message: _error!, onRetry: _load)
            : RefreshIndicator(
                color: AdminColors.primary,
                onRefresh: _load,
                child: ListView(
                  padding: const EdgeInsets.all(24),
                  children: [
                    Text(
                      'Global FYP submission deadlines (one per semester). '
                      'Students are blocked from submitting after the date passes.',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.6),
                        fontSize: 13,
                        height: 1.4,
                      ),
                    ),
                    const SizedBox(height: 20),
                    ..._semesters.map(_semesterTile),
                  ],
                ),
              );

    if (widget.embedded) {
      return body;
    }

    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        title: const Text('Semester Deadlines'),
        backgroundColor: AdminColors.surface,
      ),
      body: AppPalette.dark.ambientGlowBackdrop(child: body),
    );
  }

  Widget _semesterTile(int semester) {
    final row = _rowFor(semester);
    final label = row == null ? 'Not set' : _displayDate(row.deadlineDate);

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
        decoration: BoxDecoration(
          color: AdminColors.card,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AdminColors.border.withOpacity(0.6)),
        ),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AdminColors.primary.withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                '$semester',
                style: const TextStyle(
                  color: AdminColors.primary,
                  fontWeight: FontWeight.w800,
                  fontSize: 16,
                ),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Semester $semester',
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 15,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Deadline: $label',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.55),
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
            TextButton.icon(
              onPressed: () => _pickAndSave(semester),
              icon: const Icon(Icons.calendar_today_outlined, size: 16),
              label: Text(row == null ? 'Set date' : 'Update'),
            ),
          ],
        ),
      ),
    );
  }
}
