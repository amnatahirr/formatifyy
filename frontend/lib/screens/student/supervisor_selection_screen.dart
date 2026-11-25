import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../providers/fyp_provider.dart';
import '../../theme/app_theme.dart';
import '../../utils/responsive.dart';

import '../../widgets/tr.dart';
/// Student form to request an FYP supervisor (creates assignment_requests row).
class SupervisorSelectionScreen extends StatefulWidget {
  /// Called after a request is submitted successfully (e.g. switch to My Supervisor).
  final VoidCallback? onRequestSubmitted;

  /// Switching from an existing (pending/accepted) supervisor. Requires a reason;
  /// the backend removes the previous supervisor and notifies them.
  final bool changeMode;

  const SupervisorSelectionScreen({
    super.key,
    this.onRequestSubmitted,
    this.changeMode = false,
  });

  @override
  State<SupervisorSelectionScreen> createState() =>
      _SupervisorSelectionScreenState();
}

class _MemberFields {
  final TextEditingController name;
  final TextEditingController email;

  _MemberFields({String name = '', String email = ''})
      : name = TextEditingController(text: name),
        email = TextEditingController(text: email);

  void dispose() {
    name.dispose();
    email.dispose();
  }
}

class _SupervisorSelectionScreenState extends State<SupervisorSelectionScreen> {
  AppPalette get _p => context.watch<ThemeProvider>().palette;
  final _formKey = GlobalKey<FormState>();
  final _groupName = TextEditingController();
  final _projectTitle = TextEditingController();
  final _leaderName = TextEditingController();
  final _leaderEmail = TextEditingController();
  final _members = <_MemberFields>[];
  final _changeReason = TextEditingController();
  String? _changeCategory;

  static const changeCategories = <String>[
    'Research area mismatch',
    'Project topic changed',
    'Supervisor unavailable / on leave',
    'Communication or scheduling issues',
    'Department / co-supervisor advice',
    'Other',
  ];

  /// Mirrors backend _validate_change_reason so students get instant feedback.
  static String? validateChangeReason(String? v) {
    final text = (v ?? '').trim().replaceAll(RegExp(r'\s+'), ' ');
    if (text.length < 30) {
      return 'Explain the reason in at least 30 characters';
    }
    if (text.length > 1000) return 'Max 1000 characters';
    final words = RegExp(r'[A-Za-z؀-ۿ]{2,}')
        .allMatches(text)
        .map((m) => m.group(0)!.toLowerCase())
        .toList();
    if (words.length < 6) return 'Write at least 6 meaningful words';
    if (words.toSet().length < 4) {
      return 'Reason looks repetitive — describe the actual reason';
    }
    if (RegExp(r'(.)\1{4,}').hasMatch(text)) return 'Remove repeated characters';
    final letters = RegExp(r'[A-Za-z؀-ۿ]').allMatches(text).length;
    if (letters < text.length * 0.6) return 'Use words, not symbols or numbers';
    return null;
  }

  int? _departmentId;
  int? _supervisorId;
  int? _cosupervisorId;
  bool _prefilled = false;
  static const _legacySurface = Color(0xFF0D1117);

  Color get _inputSurface => _p.isDark ? _p.inputFill : _legacySurface;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _bootstrap());
  }

  Future<void> _bootstrap() async {
    final auth = context.read<AuthProvider>();
    final userId = auth.userId;
    if (!_prefilled) {
      _leaderName.text = auth.currentUser ?? '';
      _leaderEmail.text = auth.userEmail ?? auth.email ?? '';
      if (widget.changeMode) {
        final current = context.read<FypProvider>().assignmentStatus;
        _groupName.text = (current?['group_name'] ?? '').toString();
        _projectTitle.text = (current?['project_title'] ?? '').toString();
      }
      _prefilled = true;
    }
    if (userId == null) return;
    final fyp = context.read<FypProvider>();
    await Future.wait([
      fyp.fetchSupervisors(userId),
      fyp.fetchMyRequests(userId),
    ]);
  }

  @override
  void dispose() {
    _groupName.dispose();
    _projectTitle.dispose();
    _leaderName.dispose();
    _leaderEmail.dispose();
    _changeReason.dispose();
    for (final m in _members) {
      m.dispose();
    }
    super.dispose();
  }

  void _addMember() {
    setState(() => _members.add(_MemberFields()));
  }

  void _removeMember(int index) {
    setState(() {
      _members[index].dispose();
      _members.removeAt(index);
    });
  }

  InputDecoration _dec(String label, {String? hint, Widget? prefixIcon}) {
    return InputDecoration(
      labelText: label,
      hintText: hint,
      prefixIcon: prefixIcon,
      filled: true,
      fillColor: _inputSurface,
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      labelStyle: TextStyle(color: _p.textSecondary, fontSize: 13),
      hintStyle: TextStyle(color: _p.textMuted, fontSize: 13),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide(color: _p.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide(color: _p.accent),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: Color(0xFFEF4444)),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: Color(0xFFEF4444)),
      ),
    );
  }

  String? _emailValidator(String? v, {bool required = false}) {
    final value = (v ?? '').trim();
    if (value.isEmpty) {
      return required ? 'Email required' : null;
    }
    if (!value.contains('@') || !value.contains('.')) {
      return 'Enter a valid email';
    }
    return null;
  }

  List<String> _buildMemberPayload() {
    final out = <String>[];
    for (final m in _members) {
      final name = m.name.text.trim();
      final email = m.email.text.trim();
      if (name.isEmpty && email.isEmpty) continue;
      if (name.isNotEmpty && email.isNotEmpty) {
        out.add('$name <$email>');
      } else if (name.isNotEmpty) {
        out.add(name);
      } else {
        out.add(email);
      }
    }
    return out;
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    if (_supervisorId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Tr('Select a supervisor'),
          backgroundColor: Color(0xFFEF4444),
        ),
      );
      return;
    }

    final auth = context.read<AuthProvider>();
    final userId = auth.userId;
    if (userId == null) return;

    final fyp = context.read<FypProvider>();

    if (widget.changeMode) {
      if (_changeCategory == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Tr('Select a reason category for changing supervisor'),
            backgroundColor: Color(0xFFEF4444),
          ),
        );
        return;
      }
      final current = fyp.assignmentStatus;
      final currentName = (current?['supervisor_name'] ??
              (current?['supervisor'] as Map?)?['name'] ??
              'your current supervisor')
          .toString();
      final accepted =
          (current?['status'] ?? '').toString().toLowerCase() == 'accepted';
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: _p.surface,
          title: Text(
            'Change supervisor?',
            style: TextStyle(color: _p.textPrimary),
          ),
          content: Text(
            accepted
                ? '$currentName will be removed as your supervisor and notified with your reason. '
                    'Your group will leave their My Groups, and the new supervisor must accept your request.'
                : 'Your pending request to $currentName will be withdrawn and they will be notified with your reason.',
            style: TextStyle(color: _p.textSecondary, height: 1.45),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Tr('Cancel'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFEF4444),
                foregroundColor: Colors.white,
              ),
              child: const Tr('Yes, change'),
            ),
          ],
        ),
      );
      if (ok != true || !mounted) return;
    }

    String? cosupervisorName;
    if (_cosupervisorId != null) {
      final match = fyp.supervisors.where((s) => s['id'] == _cosupervisorId);
      if (match.isNotEmpty) {
        cosupervisorName = (match.first['name'] ?? '').toString();
      }
    }

    final result = await fyp.createAssignmentRequest(
      userId: userId,
      supervisorId: _supervisorId!,
      groupName: _groupName.text.trim(),
      projectTitle: _projectTitle.text.trim(),
      studentLeaderName: _leaderName.text.trim(),
      studentLeaderEmail: _leaderEmail.text.trim(),
      memberNames: _buildMemberPayload(),
      departmentId: _departmentId,
      cosupervisorName: cosupervisorName,
      changeReasonCategory: widget.changeMode ? _changeCategory : null,
      changeReason: widget.changeMode ? _changeReason.text.trim() : null,
    );

    if (!mounted) return;
    if (result != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Tr(widget.changeMode
              ? 'Supervisor changed — previous supervisor notified. Waiting for new supervisor approval'
              : 'Request sent — waiting for supervisor approval'),
          backgroundColor: Color(0xFF10B981),
        ),
      );
      _groupName.clear();
      _projectTitle.clear();
      _changeReason.clear();
      setState(() {
        _changeCategory = null;
        _supervisorId = null;
        _cosupervisorId = null;
        for (final m in _members) {
          m.dispose();
        }
        _members.clear();
      });
      widget.onRequestSubmitted?.call();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(fyp.errorMessage ?? 'Submit failed'),
          backgroundColor: const Color(0xFFEF4444),
        ),
      );
    }
  }

  Color _statusColor(String status) {
    switch (status.toLowerCase()) {
      case 'accepted':
        return const Color(0xFF10B981);
      case 'rejected':
        return const Color(0xFFEF4444);
      case 'withdrawn':
        return const Color(0xFF94A3B8);
      case 'discarded':
        return const Color(0xFFEF4444);
      default:
        return const Color(0xFFF59E0B);
    }
  }

  Widget _sectionTitle(String title, {String? subtitle}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: TextStyle(
            color: _p.textPrimary,
            fontSize: 15,
            fontWeight: FontWeight.w700,
          ),
        ),
        if (subtitle != null) ...[
          const SizedBox(height: 4),
          Text(
            subtitle,
            style: TextStyle(
              color: _p.textMuted,
              fontSize: 12,
              height: 1.35,
            ),
          ),
        ],
      ],
    );
  }

  Widget _changeBanner(FypProvider fyp) {
    final current = fyp.assignmentStatus;
    final name = (current?['supervisor_name'] ??
            (current?['supervisor'] as Map?)?['name'] ??
            '')
        .toString();
    final accepted =
        (current?['status'] ?? '').toString().toLowerCase() == 'accepted';
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF59E0B).withOpacity(0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFF59E0B).withOpacity(0.5)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.swap_horiz_rounded, color: Color(0xFFF59E0B)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Current supervisor: ${name.isEmpty ? '—' : name} '
              '(${accepted ? 'assigned' : 'request pending'}).\n'
              'Once you submit, they will be removed automatically and notified with your reason.',
              style: TextStyle(
                color: _p.textPrimary,
                fontSize: 12.5,
                height: 1.45,
              ),
            ),
          ),
        ],
      ),
    );
  }

  List<Widget> _reasonSection() {
    return [
      const SizedBox(height: 22),
      _sectionTitle(
        'Reason for changing supervisor',
        subtitle:
            'Required. Your previous supervisor will see this reason, so be specific and respectful.',
      ),
      const SizedBox(height: 14),
      DropdownButtonFormField<String>(
        value: _changeCategory,
        isExpanded: true,
        dropdownColor: _p.surface,
        style: TextStyle(color: _p.textPrimary, fontSize: 14),
        decoration: _dec('Reason category'),
        items: changeCategories
            .map((c) => DropdownMenuItem<String>(value: c, child: Text(c)))
            .toList(),
        validator: (v) => v == null ? 'Select a reason category' : null,
        onChanged: (v) => setState(() => _changeCategory = v),
      ),
      const SizedBox(height: 12),
      TextFormField(
        controller: _changeReason,
        minLines: 3,
        maxLines: 6,
        maxLength: 1000,
        style: TextStyle(color: _p.textPrimary),
        decoration: _dec(
          'Explain the reason',
          hint:
              'e.g. Our project moved from web development to computer vision, which better matches the new supervisor\'s research area.',
        ),
        validator: validateChangeReason,
      ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final fyp = context.watch<FypProvider>();
    final compact = isCompact(context);
    final currentSupervisorId = widget.changeMode
        ? '${fyp.assignmentStatus?['supervisor_id'] ?? ''}'
        : '';
    final filteredSupervisors = fyp
        .supervisorsForDepartment(_departmentId)
        .where((s) =>
            currentSupervisorId.isEmpty || '${s['id']}' != currentSupervisorId)
        .toList();
    final coOptions = filteredSupervisors
        .where((s) => s['id'] != _supervisorId)
        .toList();

    if (fyp.isLoading && fyp.supervisors.isEmpty) {
      return Center(child: CircularProgressIndicator(color: _p.accent));
    }

    return RefreshIndicator(
      color: _p.accent,
      backgroundColor: _p.surface,
      onRefresh: _bootstrap,
      child: ListView(
        padding: EdgeInsets.fromLTRB(
          compact ? 16 : 32,
          compact ? 12 : 24,
          compact ? 16 : 32,
          compact ? 100 : 40,
        ),
        children: [
          if (widget.changeMode) _changeBanner(fyp),
          Tr(widget.changeMode
              ? 'Choose a new supervisor. Only one supervisor can be active at a time.'
              : 'Request an FYP supervisor for your group. Your request stays pending until they accept.',
            style: TextStyle(
              color: _p.textSecondary,
              fontSize: 13,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 18),
          Container(
            padding: EdgeInsets.all(compact ? 16 : 22),
            decoration: BoxDecoration(
              color: _p.surface,
              borderRadius: BorderRadius.circular(
                _p.isDark ? _p.cardRadius : 16,
              ),
              border: Border.all(
                color: _p.isDark ? _p.borderStrong : _p.border,
              ),
              boxShadow: _p.isDark ? _p.cardShadow : null,
            ),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _sectionTitle(
                    'Project details',
                    subtitle: 'Group identity and project topic',
                  ),
                  const SizedBox(height: 14),
                  TextFormField(
                    controller: _groupName,
                    style: TextStyle(color: _p.textPrimary),
                    decoration: _dec(
                      'Group name',
                      prefixIcon: Icon(
                        Icons.groups_outlined,
                        size: 18,
                        color: _p.textMuted,
                      ),
                    ),
                    validator: (v) =>
                        (v == null || v.trim().isEmpty) ? 'Required' : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _projectTitle,
                    style: TextStyle(color: _p.textPrimary),
                    decoration: _dec(
                      'Project title / topic',
                      prefixIcon: Icon(
                        Icons.topic_outlined,
                        size: 18,
                        color: _p.textMuted,
                      ),
                    ),
                    validator: (v) =>
                        (v == null || v.trim().isEmpty) ? 'Required' : null,
                  ),
                  const SizedBox(height: 22),
                  _sectionTitle(
                    'Group leader',
                    subtitle: 'Email is taken from your signed-in account',
                  ),
                  const SizedBox(height: 14),
                  TextFormField(
                    controller: _leaderName,
                    style: TextStyle(color: _p.textPrimary),
                    decoration: _dec('Leader name'),
                    validator: (v) =>
                        (v == null || v.trim().isEmpty) ? 'Required' : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _leaderEmail,
                    readOnly: true,
                    style: TextStyle(color: _p.textSecondary),
                    decoration: _dec(
                      'Leader email',
                      hint: 'From your account',
                    ),
                  ),
                  const SizedBox(height: 22),
                  Row(
                    children: [
                      Expanded(
                        child: _sectionTitle(
                          'Team members',
                          subtitle: 'Name + email for each member',
                        ),
                      ),
                      TextButton.icon(
                        onPressed: _addMember,
                        icon: const Icon(Icons.person_add_alt_1, size: 18),
                        label: const Tr('Add'),
                        style: TextButton.styleFrom(
                          foregroundColor: _p.accent,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  if (_members.isEmpty)
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: _inputSurface,
                        borderRadius: BorderRadius.circular(
                          _p.isDark ? _p.cardRadius : 12,
                        ),
                        border: Border.all(
                          color: _p.isDark ? _p.borderStrong : _p.border,
                        ),
                      ),
                      child: Tr('Optional — add other members with their university emails. Leader is included automatically.',
                        style: TextStyle(
                          color: _p.textSecondary,
                          fontSize: 12,
                          height: 1.4,
                        ),
                      ),
                    )
                  else
                    ...List.generate(_members.length, (i) {
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: _inputSurface,
                            borderRadius: BorderRadius.circular(
                              _p.isDark ? _p.cardRadius : 12,
                            ),
                            border: Border.all(
                              color: _p.isDark ? _p.borderStrong : _p.border,
                            ),
                          ),
                          child: Column(
                            children: [
                              Row(
                                children: [
                                  Text(
                                    'Member ${i + 1}',
                                    style: TextStyle(
                                      color: _p.textSecondary,
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                  const Spacer(),
                                  IconButton(
                                    onPressed: () => _removeMember(i),
                                    visualDensity: VisualDensity.compact,
                                    icon: const Icon(
                                      Icons.close,
                                      size: 18,
                                      color: Color(0xFF94A3B8),
                                    ),
                                  ),
                                ],
                              ),
                              TextFormField(
                                controller: _members[i].name,
                                style: TextStyle(color: _p.textPrimary),
                                decoration: _dec('Full name'),
                                validator: (v) {
                                  final name = (v ?? '').trim();
                                  final email =
                                      _members[i].email.text.trim();
                                  if (name.isEmpty && email.isNotEmpty) {
                                    return 'Name required with email';
                                  }
                                  return null;
                                },
                              ),
                              const SizedBox(height: 10),
                              TextFormField(
                                controller: _members[i].email,
                                keyboardType: TextInputType.emailAddress,
                                style: TextStyle(color: _p.textPrimary),
                                decoration: _dec(
                                  'University email',
                                  hint: 'name@university.edu',
                                ),
                                validator: (v) {
                                  final email = (v ?? '').trim();
                                  final name =
                                      _members[i].name.text.trim();
                                  if (name.isNotEmpty && email.isEmpty) {
                                    return 'Email required';
                                  }
                                  return _emailValidator(v);
                                },
                              ),
                            ],
                          ),
                        ),
                      );
                    }),
                  const SizedBox(height: 22),
                  _sectionTitle(
                    'Supervision',
                    subtitle: 'Pick department, supervisor, and optional co-supervisor',
                  ),
                  const SizedBox(height: 14),
                  DropdownButtonFormField<int>(
                    value: _departmentId,
                    isExpanded: true,
                    dropdownColor: _p.surface,
                    style: TextStyle(color: _p.textPrimary, fontSize: 14),
                    decoration: _dec('Department'),
                    items: [
                      const DropdownMenuItem<int>(
                        value: null,
                        child: Tr('All departments'),
                      ),
                      ...fyp.departments.map(
                        (d) {
                          final id = d['id'] is int
                              ? d['id'] as int
                              : int.tryParse(d['id']?.toString() ?? '');
                          return DropdownMenuItem<int>(
                            value: id,
                            child: Text(
                              '${d['name'] ?? ''}${d['code'] != null ? ' (${d['code']})' : ''}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          );
                        },
                      ),
                    ],
                    onChanged: (v) {
                      setState(() {
                        _departmentId = v;
                        if (_supervisorId != null &&
                            !fyp
                                .supervisorsForDepartment(v)
                                .any((s) => (s['id'] is int ? s['id'] as int : int.tryParse(s['id']?.toString() ?? '')) == _supervisorId)) {
                          _supervisorId = null;
                        }
                        if (_cosupervisorId != null &&
                            (_cosupervisorId == _supervisorId ||
                                !fyp
                                    .supervisorsForDepartment(v)
                                    .any((s) => (s['id'] is int ? s['id'] as int : int.tryParse(s['id']?.toString() ?? '')) == _cosupervisorId))) {
                          _cosupervisorId = null;
                        }
                      });
                    },
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<int>(
                    value: _supervisorId,
                    isExpanded: true,
                    dropdownColor: _p.surface,
                    style: TextStyle(color: _p.textPrimary, fontSize: 14),
                    decoration: _dec('Supervisor'),
                    items: filteredSupervisors.map((s) {
                      final id = s['id'] is int
                          ? s['id'] as int
                          : (int.tryParse(s['id']?.toString() ?? '') ?? 0);
                      final full = s['is_full'] == true;
                      final slots = s['slots_available'] ?? 0;
                      final dept = s['department_name'] ?? '';
                      return DropdownMenuItem<int>(
                        value: id,
                        enabled: !full,
                        child: Text(
                          '${s['name'] ?? 'Supervisor'}'
                          '${dept.toString().isNotEmpty ? ' — $dept' : ''}'
                          '${full ? ' (full)' : ' ($slots slots)'}',
                          overflow: TextOverflow.ellipsis,
                        ),
                      );
                    }).toList(),
                    validator: (v) => v == null ? 'Select a supervisor' : null,
                    onChanged: (v) {
                      setState(() {
                        _supervisorId = v;
                        if (_cosupervisorId == v) {
                          _cosupervisorId = null;
                        }
                      });
                    },
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<int>(
                    value: _cosupervisorId,
                    isExpanded: true,
                    dropdownColor: _p.surface,
                    style: TextStyle(color: _p.textPrimary, fontSize: 14),
                    decoration: _dec(
                      'Co-supervisor (optional)',
                      hint: 'None',
                    ),
                    items: [
                      const DropdownMenuItem<int>(
                        value: null,
                        child: Tr('None'),
                      ),
                      ...coOptions.map((s) {
                        final id = s['id'] is int
                            ? s['id'] as int
                            : (int.tryParse(s['id']?.toString() ?? '') ?? 0);
                        final dept = s['department_name'] ?? '';
                        return DropdownMenuItem<int>(
                          value: id,
                          child: Text(
                            '${s['name'] ?? 'Supervisor'}'
                            '${dept.toString().isNotEmpty ? ' — $dept' : ''}',
                            overflow: TextOverflow.ellipsis,
                          ),
                        );
                      }),
                    ],
                    onChanged: (v) => setState(() => _cosupervisorId = v),
                  ),
                  if (filteredSupervisors.isEmpty) ...[
                    const SizedBox(height: 8),
                    Tr('No active supervisors for this department.',
                      style: TextStyle(
                        color: _p.textSecondary,
                        fontSize: 12,
                      ),
                    ),
                  ],
                  if (widget.changeMode) ..._reasonSection(),
                  const SizedBox(height: 22),
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton.icon(
                      onPressed: fyp.isSubmitting ? null : _submit,
                      icon: fyp.isSubmitting
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Icon(Icons.send_rounded, size: 18),
                      label: Text(
                        fyp.isSubmitting
                            ? 'Submitting…'
                            : (widget.changeMode
                                ? 'Change supervisor'
                                : 'Send request'),
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _p.accent,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          Tr('Your requests',
            style: TextStyle(
              color: _p.textPrimary,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 12),
          if (fyp.requests.isEmpty)
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: _p.surface,
                borderRadius: BorderRadius.circular(
                  _p.isDark ? _p.cardRadius : 14,
                ),
                border: Border.all(
                  color: _p.isDark ? _p.borderStrong : _p.border,
                ),
                boxShadow: _p.isDark ? _p.cardShadow : null,
              ),
              child: Tr('No assignment requests yet.',
                style: TextStyle(color: _p.textSecondary),
              ),
            )
          else
            ...fyp.requests.map((r) {
              final status = (r['status'] ?? 'pending').toString();
              final color = _statusColor(status);
              final co = (r['cosupervisor_name'] ?? '').toString().trim();
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: _p.surface,
                    borderRadius: BorderRadius.circular(
                      _p.isDark ? _p.cardRadius : 14,
                    ),
                    border: Border.all(
                      color: _p.isDark ? _p.borderStrong : _p.border,
                    ),
                    boxShadow: _p.isDark ? _p.cardShadow : null,
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              (r['group_name'] ?? 'Group').toString(),
                              style: TextStyle(
                                color: _p.textPrimary,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${r['project_title'] ?? ''}',
                              style: TextStyle(
                                color: _p.textSecondary,
                                fontSize: 12,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              'Supervisor: ${r['supervisor_name'] ?? '—'}',
                              style: TextStyle(
                                color: _p.textSecondary,
                                fontSize: 12,
                              ),
                            ),
                            if (co.isNotEmpty)
                              Text(
                                'Co-supervisor: $co',
                                style: TextStyle(
                                  color: _p.textSecondary,
                                  fontSize: 12,
                                ),
                              ),
                            if (status.toLowerCase() == 'withdrawn' &&
                                (r['change_reason'] ?? '')
                                    .toString()
                                    .isNotEmpty) ...[
                              const SizedBox(height: 6),
                              Text(
                                'Changed: ${r['change_reason']}',
                                style: TextStyle(
                                  color: _p.textMuted,
                                  fontSize: 12,
                                ),
                              ),
                            ],
                            if ((r['rejection_reason'] ?? '')
                                .toString()
                                .isNotEmpty) ...[
                              const SizedBox(height: 6),
                              Text(
                                'Reason: ${r['rejection_reason']}',
                                style: const TextStyle(
                                  color: Color(0xFFFCA5A5),
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: color.withOpacity(0.15),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          status.toUpperCase(),
                          style: TextStyle(
                            color: color,
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }),
        ],
      ),
    );
  }
}
