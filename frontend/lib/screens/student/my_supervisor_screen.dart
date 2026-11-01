import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../providers/fyp_provider.dart';
import '../../theme/app_theme.dart';

import '../../widgets/tr.dart';
/// Shows the student's latest assignment_requests status (email-matched).
class MySupervisorScreen extends StatefulWidget {
  /// Opens the Choose Supervisor tab (e.g. after rejection).
  final VoidCallback? onChooseSupervisor;

  const MySupervisorScreen({super.key, this.onChooseSupervisor});

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

  Widget _pendingCard(Map<String, dynamic> data) {
    return _statusShell(
      accent: const Color(0xFFF59E0B),
      title: 'Request pending',
      subtitle:
          'Waiting for ${(data['project_title'] ?? data['group_name'] ?? 'your group').toString()} to be reviewed.',
      child: Text(
        'Group: ${data['group_name'] ?? '—'}\n'
        'Project: ${data['project_title'] ?? '—'}',
        style: TextStyle(color: _p.textSecondary, height: 1.5),
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
        ],
      ),
    );
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
