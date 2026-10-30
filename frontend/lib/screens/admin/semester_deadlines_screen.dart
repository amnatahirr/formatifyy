import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/admin_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/admin_api_service.dart';
import '../../theme/app_theme.dart';
import '../../widgets/admin/admin_ui.dart';

import '../../widgets/tr.dart';

/// Admin UI for global Semester 6 / 7 / 8 FYP submission deadlines.
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

  static const _semesters = [6, 7, 8];

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
    final setCount = _semesters.where((s) {
      final r = _rowFor(s);
      return r != null && r.deadlineDate.isNotEmpty;
    }).length;

    final body = _loading
        ? const Center(child: CircularProgressIndicator(color: AdminColors.primary))
        : _error != null
            ? AdminErrorView(message: _error!, onRetry: _load)
            : RefreshIndicator(
                color: AdminColors.primary,
                onRefresh: _load,
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(24),
                  children: [
                    _InfoBanner(setCount: setCount, total: _semesters.length),
                    const SizedBox(height: 22),
                    LayoutBuilder(
                      builder: (context, c) {
                        const gap = 16.0;
                        final cols = c.maxWidth >= 840 ? _semesters.length : 1;
                        final w = (c.maxWidth - gap * (cols - 1)) / cols;
                        return Wrap(
                          spacing: gap,
                          runSpacing: gap,
                          children: [
                            for (final s in _semesters)
                              SizedBox(width: w, child: _semesterTile(s)),
                          ],
                        );
                      },
                    ),
                  ],
                ),
              );

    if (widget.embedded) {
      return body;
    }

    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        title: const Tr('Semester Deadlines'),
        backgroundColor: AdminColors.surface,
      ),
      body: AppPalette.dark.ambientGlowBackdrop(child: body),
    );
  }

  /// Returns (label, color) describing how close the deadline is.
  _Status _statusFor(SemesterDeadlineModel? row) {
    final date = row == null ? null : DateTime.tryParse(row.deadlineDate);
    if (date == null) {
      return _Status('Not set', Colors.white54, Icons.event_busy_rounded);
    }
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final due = DateTime(date.year, date.month, date.day);
    final days = due.difference(today).inDays;
    if (days < 0) {
      return _Status('Closed · ${-days}d ago', AdminColors.danger,
          Icons.lock_clock_rounded);
    }
    if (days == 0) {
      return _Status('Due today', AdminColors.warning, Icons.schedule_rounded);
    }
    if (days <= 7) {
      return _Status('$days day${days == 1 ? '' : 's'} left',
          AdminColors.warning, Icons.schedule_rounded);
    }
    return _Status('$days days left', AdminColors.success,
        Icons.check_circle_outline_rounded);
  }

  Widget _semesterTile(int semester) {
    final row = _rowFor(semester);
    final hasDate = row != null && row.deadlineDate.isNotEmpty;
    final label = hasDate ? _displayDate(row.deadlineDate) : 'Not set';
    final status = _statusFor(row);
    final accent = hasDate ? status.color : AdminColors.primary;

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AdminColors.card,
            Color.alphaBlend(accent.withOpacity(0.08), AdminColors.card),
          ],
        ),
        border: Border.all(color: accent.withOpacity(hasDate ? 0.35 : 0.15)),
        boxShadow: [
          BoxShadow(
            color: accent.withOpacity(0.08),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 50,
                height: 50,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(15),
                  gradient: const LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [AdminColors.primary, AdminColors.accent],
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: AdminColors.primary.withOpacity(0.35),
                      blurRadius: 12,
                      offset: const Offset(0, 5),
                    ),
                  ],
                ),
                child: Text(
                  '$semester',
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w800,
                    fontSize: 20,
                  ),
                ),
              ),
              const Spacer(),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: status.color.withOpacity(0.14),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: status.color.withOpacity(0.4)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(status.icon, size: 14, color: status.color),
                    const SizedBox(width: 6),
                    Text(
                      status.label,
                      style: TextStyle(
                        color: status.color,
                        fontWeight: FontWeight.w700,
                        fontSize: 11.5,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Text(
            'Semester $semester',
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w800,
              fontSize: 18,
            ),
          ),
          const SizedBox(height: 14),
          Text(
            'SUBMISSION DEADLINE',
            style: TextStyle(
              fontSize: 10.5,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.2,
              color: Colors.white.withOpacity(0.4),
            ),
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              Icon(
                Icons.event_rounded,
                size: 18,
                color: hasDate ? accent : Colors.white.withOpacity(0.35),
              ),
              const SizedBox(width: 8),
              Text(
                label,
                style: TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                  color: hasDate ? Colors.white : Colors.white.withOpacity(0.45),
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          SizedBox(
            width: double.infinity,
            child: hasDate
                ? OutlinedButton.icon(
                    onPressed: () => _pickAndSave(semester),
                    icon: const Icon(Icons.edit_calendar_rounded, size: 18),
                    label: const Text('Update'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.white,
                      side: BorderSide(color: Colors.white.withOpacity(0.18)),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      textStyle: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                  )
                : ElevatedButton.icon(
                    onPressed: () => _pickAndSave(semester),
                    icon: const Icon(Icons.calendar_today_outlined, size: 16),
                    label: const Text('Set date'),
                    style: ElevatedButton.styleFrom(
                      elevation: 0,
                      backgroundColor: AdminColors.primary,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      textStyle: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}

class _Status {
  final String label;
  final Color color;
  final IconData icon;

  _Status(this.label, this.color, this.icon);
}

class _InfoBanner extends StatelessWidget {
  final int setCount;
  final int total;

  const _InfoBanner({required this.setCount, required this.total});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        color: AdminColors.primary.withOpacity(0.08),
        border: Border.all(color: AdminColors.primary.withOpacity(0.25)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: AdminColors.primary.withOpacity(0.18),
              borderRadius: BorderRadius.circular(11),
            ),
            child: const Icon(
              Icons.info_outline_rounded,
              size: 20,
              color: AdminColors.primary,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              'Global FYP submission deadlines (one per semester). '
              'Students are blocked from submitting after the date passes.',
              style: TextStyle(
                color: Colors.white.withOpacity(0.75),
                fontSize: 13.5,
                height: 1.45,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.06),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              '$setCount / $total set',
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
                fontSize: 12.5,
              ),
            ),
          ),
        ],
      ),
    );
  }
}