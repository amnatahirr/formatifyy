import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../providers/collaboration_provider.dart';

import '../../../widgets/tr.dart';
/// Members tab — roster, roles, and invite-by-email.
class ProjectMembersTab extends StatefulWidget {
  final int projectId;

  const ProjectMembersTab({super.key, required this.projectId});

  @override
  State<ProjectMembersTab> createState() => _ProjectMembersTabState();
}

class _ProjectMembersTabState extends State<ProjectMembersTab> {
  final _email = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _sending = false;

  static final _emailPattern = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  Future<void> _inviteByEmail() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final email = _email.text.trim();
    setState(() => _sending = true);

    final vc = context.read<CollaborationProvider>();
    final result = await vc.inviteMember(widget.projectId, email);
    if (!mounted) return;
    setState(() => _sending = false);

    final ok = result['ok'] == true;
    final message =
        (result['message'] as String?) ?? (ok ? 'Invite email sent' : 'Invite failed');

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: ok ? const Color(0xFF10B981) : const Color(0xFFEF4444),
      ),
    );

    if (ok) {
      _email.clear();
      _formKey.currentState?.reset();
      await vc.loadProject(widget.projectId);
    }
  }

  @override
  Widget build(BuildContext context) {
    final vc = context.watch<CollaborationProvider>();
    final project = vc.currentProject ?? {};
    final members = (project['members'] as List? ?? [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(
          'Members (${members.length})',
          style: const TextStyle(
            color: Colors.white,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 8),
        const Tr('Invite teammates with the Invite button, or add a registered user by email below.',
          style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
        ),
        const SizedBox(height: 16),
        _InviteByEmailCard(
          formKey: _formKey,
          emailController: _email,
          sending: _sending,
          emailPattern: _emailPattern,
          onSubmit: _inviteByEmail,
        ),
        const SizedBox(height: 20),
        if (members.isEmpty)
          const Tr('No members loaded',
            style: TextStyle(color: Color(0xFF94A3B8)),
          )
        else
          ...members.map((m) => _MemberTile(member: m)),
      ],
    );
  }
}

class _InviteByEmailCard extends StatelessWidget {
  final GlobalKey<FormState> formKey;
  final TextEditingController emailController;
  final bool sending;
  final RegExp emailPattern;
  final VoidCallback onSubmit;

  const _InviteByEmailCard({
    required this.formKey,
    required this.emailController,
    required this.sending,
    required this.emailPattern,
    required this.onSubmit,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F2E),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF2D3748)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.mail_outline, size: 18, color: Color(0xFFA5B4FC)),
              SizedBox(width: 8),
              Tr('Invite by email',
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                  fontSize: 14,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          const Tr('We email them the project invite code. They join via Collaboration → Join Project.',
            style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
          ),
          const SizedBox(height: 12),
          Form(
            key: formKey,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: TextFormField(
                    controller: emailController,
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.done,
                    style: const TextStyle(color: Colors.white, fontSize: 14),
                    onFieldSubmitted: (_) {
                      if (!sending) onSubmit();
                    },
                    decoration: const InputDecoration(
                      labelText: 'Email',
                      hintText: 'member@university.edu',
                      hintStyle: TextStyle(color: Color(0xFF64748B)),
                      isDense: true,
                      contentPadding: EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 12,
                      ),
                    ),
                    validator: (value) {
                      final v = value?.trim() ?? '';
                      if (v.isEmpty) return 'Email required';
                      if (!emailPattern.hasMatch(v)) return 'Invalid email';
                      return null;
                    },
                  ),
                ),
                const SizedBox(width: 10),
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: ElevatedButton(
                    onPressed: sending ? null : onSubmit,
                    child: sending
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Tr('Invite'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MemberTile extends StatelessWidget {
  final Map<String, dynamic> member;

  const _MemberTile({required this.member});

  @override
  Widget build(BuildContext context) {
    final name = (member['username'] as String?)?.trim().isNotEmpty == true
        ? member['username'] as String
        : (member['email'] as String? ?? 'User');
    final email = member['email'] as String? ?? '';
    final role = member['role'] as String? ?? 'editor';
    final roleColor = role == 'owner'
        ? const Color(0xFFF59E0B)
        : const Color(0xFF3B82F6);

    return Card(
      color: const Color(0xFF1A1F2E),
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: const Color(0xFF6366F1).withOpacity(0.25),
          child: Text(
            name.isNotEmpty ? name[0].toUpperCase() : '?',
            style: const TextStyle(
              color: Color(0xFFA5B4FC),
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        title: Text(
          name,
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
        subtitle: Text(
          email,
          style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
        ),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: roleColor.withOpacity(0.15),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(
            role,
            style: TextStyle(
              color: roleColor,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ),
    );
  }
}
