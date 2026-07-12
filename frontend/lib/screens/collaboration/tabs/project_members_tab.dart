import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../providers/collaboration_provider.dart';

/// Members tab — roster and roles (invite lives in the top Invite button).
class ProjectMembersTab extends StatelessWidget {
  final int projectId;

  const ProjectMembersTab({super.key, required this.projectId});

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
        const Text(
          'Use the Invite button above to share a code or invite by email.',
          style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
        ),
        const SizedBox(height: 16),
        if (members.isEmpty)
          const Text(
            'No members loaded',
            style: TextStyle(color: Color(0xFF94A3B8)),
          )
        else
          ...members.map((m) => _MemberTile(member: m)),
      ],
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
