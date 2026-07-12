import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../../../providers/collaboration_provider.dart';

/// Invite menu: share code or invite by email.
class InviteMenuDialog extends StatefulWidget {
  final int projectId;
  final String inviteCode;

  const InviteMenuDialog({
    super.key,
    required this.projectId,
    required this.inviteCode,
  });

  @override
  State<InviteMenuDialog> createState() => _InviteMenuDialogState();
}

class _InviteMenuDialogState extends State<InviteMenuDialog> {
  bool _byEmail = false;
  final _email = TextEditingController();
  bool _sending = false;

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  Future<void> _sendInvite() async {
    final email = _email.text.trim();
    if (email.isEmpty) return;
    setState(() => _sending = true);
    final vc = context.read<CollaborationProvider>();
    final ok = await vc.inviteMember(widget.projectId, email);
    if (!mounted) return;
    setState(() => _sending = false);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(ok ? 'Invite sent to $email' : 'Invite failed'),
        backgroundColor: ok ? const Color(0xFF10B981) : const Color(0xFFEF4444),
      ),
    );
    if (ok) {
      _email.clear();
      await vc.loadProject(widget.projectId);
      if (mounted) Navigator.pop(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: const Color(0xFF1A1F2E),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Invite',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  ChoiceChip(
                    label: const Text('Invite with code'),
                    selected: !_byEmail,
                    onSelected: (_) => setState(() => _byEmail = false),
                    selectedColor: const Color(0xFF6366F1).withOpacity(0.3),
                    labelStyle: TextStyle(
                      color: !_byEmail ? Colors.white : const Color(0xFF94A3B8),
                      fontSize: 12,
                    ),
                    backgroundColor: const Color(0xFF0F1419),
                    side: BorderSide(
                      color: !_byEmail
                          ? const Color(0xFF6366F1)
                          : const Color(0xFF2D3748),
                    ),
                  ),
                  const SizedBox(width: 8),
                  ChoiceChip(
                    label: const Text('Invite by email'),
                    selected: _byEmail,
                    onSelected: (_) => setState(() => _byEmail = true),
                    selectedColor: const Color(0xFF6366F1).withOpacity(0.3),
                    labelStyle: TextStyle(
                      color: _byEmail ? Colors.white : const Color(0xFF94A3B8),
                      fontSize: 12,
                    ),
                    backgroundColor: const Color(0xFF0F1419),
                    side: BorderSide(
                      color: _byEmail
                          ? const Color(0xFF6366F1)
                          : const Color(0xFF2D3748),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              if (!_byEmail) ...[
                const Text(
                  'Share this invite code',
                  style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: SelectableText(
                        widget.inviteCode.isEmpty ? '—' : widget.inviteCode,
                        style: const TextStyle(
                          color: Color(0xFF6366F1),
                          fontWeight: FontWeight.w700,
                          fontSize: 20,
                          letterSpacing: 1.2,
                        ),
                      ),
                    ),
                    IconButton(
                      tooltip: 'Copy',
                      onPressed: widget.inviteCode.isEmpty
                          ? null
                          : () async {
                              await Clipboard.setData(
                                ClipboardData(text: widget.inviteCode),
                              );
                              if (!context.mounted) return;
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Invite code copied')),
                              );
                            },
                      icon: const Icon(Icons.copy, size: 18, color: Color(0xFF94A3B8)),
                    ),
                  ],
                ),
              ] else ...[
                TextField(
                  controller: _email,
                  decoration: const InputDecoration(
                    labelText: 'Enter email',
                    hintText: 'member@university.edu',
                  ),
                ),
                const SizedBox(height: 16),
                Align(
                  alignment: Alignment.centerRight,
                  child: ElevatedButton(
                    onPressed: _sending ? null : _sendInvite,
                    child: _sending
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Text('Invite'),
                  ),
                ),
              ],
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Close'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
