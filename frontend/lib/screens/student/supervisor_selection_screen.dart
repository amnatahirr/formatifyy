import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../providers/fyp_provider.dart';

/// Student form to request an FYP supervisor (creates assignment_requests row).
class SupervisorSelectionScreen extends StatefulWidget {
  const SupervisorSelectionScreen({super.key});

  @override
  State<SupervisorSelectionScreen> createState() =>
      _SupervisorSelectionScreenState();
}

class _SupervisorSelectionScreenState extends State<SupervisorSelectionScreen> {
  final _formKey = GlobalKey<FormState>();
  final _groupName = TextEditingController();
  final _projectTitle = TextEditingController();
  final _leaderName = TextEditingController();
  final _leaderEmail = TextEditingController();
  final _memberControllers = <TextEditingController>[];

  int? _departmentId;
  int? _supervisorId;
  bool _prefilled = false;

  static const _card = Color(0xFF161B22);
  static const _border = Color(0x22FFFFFF);
  static const _accent = Color(0xFF3B82F6);
  static const _surface = Color(0xFF0D1117);

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
    for (final c in _memberControllers) {
      c.dispose();
    }
    super.dispose();
  }

  void _addMemberField({String initial = ''}) {
    setState(() {
      final c = TextEditingController(text: initial);
      _memberControllers.add(c);
    });
  }

  void _removeMemberField(int index) {
    setState(() {
      _memberControllers[index].dispose();
      _memberControllers.removeAt(index);
    });
  }

  InputDecoration _dec(String label, {String? hint}) {
    return InputDecoration(
      labelText: label,
      hintText: hint,
      filled: true,
      fillColor: _surface,
      labelStyle: TextStyle(color: Colors.white.withOpacity(0.65)),
      hintStyle: TextStyle(color: Colors.white.withOpacity(0.35)),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: _border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: _accent),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: Color(0xFFEF4444)),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: Color(0xFFEF4444)),
      ),
    );
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    if (_supervisorId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Select a supervisor'),
          backgroundColor: Color(0xFFEF4444),
        ),
      );
      return;
    }

    final auth = context.read<AuthProvider>();
    final userId = auth.userId;
    if (userId == null) return;

    final members = _memberControllers
        .map((c) => c.text.trim())
        .where((s) => s.isNotEmpty)
        .toList();

    final fyp = context.read<FypProvider>();
    final result = await fyp.createAssignmentRequest(
      userId: userId,
      supervisorId: _supervisorId!,
      groupName: _groupName.text.trim(),
      projectTitle: _projectTitle.text.trim(),
      studentLeaderName: _leaderName.text.trim(),
      studentLeaderEmail: _leaderEmail.text.trim(),
      memberNames: members,
      departmentId: _departmentId,
    );

    if (!mounted) return;
    if (result != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Request sent — waiting for supervisor approval'),
          backgroundColor: Color(0xFF10B981),
        ),
      );
      _groupName.clear();
      _projectTitle.clear();
      setState(() {
        _supervisorId = null;
        for (final c in _memberControllers) {
          c.dispose();
        }
        _memberControllers.clear();
      });
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
      default:
        return const Color(0xFFF59E0B);
    }
  }

  @override
  Widget build(BuildContext context) {
    final fyp = context.watch<FypProvider>();
    final filteredSupervisors = fyp.supervisorsForDepartment(_departmentId);

    if (fyp.isLoading && fyp.supervisors.isEmpty) {
      return const Center(child: CircularProgressIndicator(color: _accent));
    }

    return RefreshIndicator(
      color: _accent,
      backgroundColor: _card,
      onRefresh: _bootstrap,
      child: ListView(
        padding: const EdgeInsets.all(32),
        children: [
          Text(
            'Request an FYP supervisor for your group. Your request stays pending until they accept.',
            style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 14),
          ),
          const SizedBox(height: 22),
          Container(
            padding: const EdgeInsets.all(22),
            decoration: BoxDecoration(
              color: _card,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: _border),
            ),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Group details',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _groupName,
                    style: const TextStyle(color: Colors.white),
                    decoration: _dec('Group name'),
                    validator: (v) =>
                        (v == null || v.trim().isEmpty) ? 'Required' : null,
                  ),
                  const SizedBox(height: 14),
                  TextFormField(
                    controller: _projectTitle,
                    style: const TextStyle(color: Colors.white),
                    decoration: _dec('Project title / topic'),
                    validator: (v) =>
                        (v == null || v.trim().isEmpty) ? 'Required' : null,
                  ),
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      Expanded(
                        child: TextFormField(
                          controller: _leaderName,
                          style: const TextStyle(color: Colors.white),
                          decoration: _dec('Student leader name'),
                          validator: (v) => (v == null || v.trim().isEmpty)
                              ? 'Required'
                              : null,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: TextFormField(
                          controller: _leaderEmail,
                          readOnly: true,
                          style: TextStyle(color: Colors.white.withOpacity(0.85)),
                          decoration: _dec(
                            'Student leader email',
                            hint: 'From your account',
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 22),
                  Row(
                    children: [
                      const Text(
                        'Member names',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const Spacer(),
                      TextButton.icon(
                        onPressed: () => _addMemberField(),
                        icon: const Icon(Icons.person_add_alt_1, size: 18),
                        label: const Text('Add member'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  if (_memberControllers.isEmpty)
                    Text(
                      'Optional — add other group members. Leader is included automatically.',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.5),
                        fontSize: 12,
                      ),
                    ),
                  ...List.generate(_memberControllers.length, (i) {
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Row(
                        children: [
                          Expanded(
                            child: TextFormField(
                              controller: _memberControllers[i],
                              style: const TextStyle(color: Colors.white),
                              decoration: _dec('Member ${i + 1}'),
                            ),
                          ),
                          IconButton(
                            onPressed: () => _removeMemberField(i),
                            icon: const Icon(Icons.close, color: Color(0xFF94A3B8)),
                          ),
                        ],
                      ),
                    );
                  }),
                  const SizedBox(height: 18),
                  DropdownButtonFormField<int>(
                    value: _departmentId,
                    dropdownColor: _card,
                    style: const TextStyle(color: Colors.white),
                    decoration: _dec('Department'),
                    items: [
                      const DropdownMenuItem<int>(
                        value: null,
                        child: Text('All departments'),
                      ),
                      ...fyp.departments.map(
                        (d) => DropdownMenuItem<int>(
                          value: d['id'] as int?,
                          child: Text(
                            '${d['name'] ?? ''}${d['code'] != null ? ' (${d['code']})' : ''}',
                          ),
                        ),
                      ),
                    ],
                    onChanged: (v) {
                      setState(() {
                        _departmentId = v;
                        // Clear supervisor if no longer in filtered list
                        if (_supervisorId != null &&
                            !fyp
                                .supervisorsForDepartment(v)
                                .any((s) => s['id'] == _supervisorId)) {
                          _supervisorId = null;
                        }
                      });
                    },
                  ),
                  const SizedBox(height: 14),
                  DropdownButtonFormField<int>(
                    value: _supervisorId,
                    dropdownColor: _card,
                    style: const TextStyle(color: Colors.white),
                    decoration: _dec('Supervisor'),
                    items: filteredSupervisors.map((s) {
                      final id = s['id'] as int;
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
                    onChanged: (v) => setState(() => _supervisorId = v),
                  ),
                  if (filteredSupervisors.isEmpty) ...[
                    const SizedBox(height: 8),
                    Text(
                      'No active supervisors for this department.',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.5),
                        fontSize: 12,
                      ),
                    ),
                  ],
                  const SizedBox(height: 22),
                  Align(
                    alignment: Alignment.centerRight,
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
                          : const Icon(Icons.send, size: 18),
                      label: Text(
                        fyp.isSubmitting ? 'Submitting…' : 'Send request',
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _accent,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(
                          horizontal: 22,
                          vertical: 14,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 28),
          const Text(
            'Your requests',
            style: TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 12),
          if (fyp.requests.isEmpty)
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: _card,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: _border),
              ),
              child: Text(
                'No assignment requests yet.',
                style: TextStyle(color: Colors.white.withOpacity(0.6)),
              ),
            )
          else
            ...fyp.requests.map((r) {
              final status = (r['status'] ?? 'pending').toString();
              final color = _statusColor(status);
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: _card,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: _border),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              (r['group_name'] ?? 'Group').toString(),
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${r['project_title'] ?? ''} · ${r['supervisor_name'] ?? 'Supervisor'}',
                              style: TextStyle(
                                color: Colors.white.withOpacity(0.55),
                                fontSize: 12,
                              ),
                            ),
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
