import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../../../providers/collaboration_provider.dart';

import '../../../widgets/tr.dart';
/// Invite menu: share code or invite by email.
class InviteMenuDialog extends StatefulWidget {
  final int projectId;
  final String inviteCode;
  /// Called after a successful email invite (members list should refresh).
  final VoidCallback? onInvited;

  const InviteMenuDialog({
    super.key,
    required this.projectId,
    required this.inviteCode,
    this.onInvited,
  });

  @override
  State<InviteMenuDialog> createState() => _InviteMenuDialogState();
}

class _InviteMenuDialogState extends State<InviteMenuDialog> {
  bool _byEmail = false;
  final _email = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  bool _sending = false;
  String? _inlineError;

  static final _emailPattern = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

  @override
  void dispose() {
    _email.dispose();
    super.dispose();
  }

  Future<void> _sendInvite() async {
    setState(() => _inlineError = null);
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
      await vc.loadProject(widget.projectId);
      widget.onInvited?.call();
      if (mounted) Navigator.pop(context);
    } else {
      setState(() => _inlineError = message);
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
              const Tr('Invite',
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
                    label: const Tr('Invite with code'),
                    selected: !_byEmail,
                    onSelected: (_) => setState(() {
                      _byEmail = false;
                      _inlineError = null;
                    }),
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
                    label: const Tr('Invite by email'),
                    selected: _byEmail,
                    onSelected: (_) => setState(() {
                      _byEmail = true;
                      _inlineError = null;
                    }),
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
                const Tr('Share this invite code',
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
                                const SnackBar(content: Tr('Invite code copied')),
                              );
                            },
                      icon: const Icon(Icons.copy, size: 18, color: Color(0xFF94A3B8)),
                    ),
                  ],
                ),
              ] else ...[
                const Tr('We\'ll email them this project\'s invite code. They join via Collaboration → Join Project (sign up first if needed).',
                  style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                ),
                const SizedBox(height: 12),
                Form(
                  key: _formKey,
                  child: TextFormField(
                    controller: _email,
                    autofocus: true,
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.done,
                    style: const TextStyle(color: Colors.white),
                    onFieldSubmitted: (_) {
                      if (!_sending) _sendInvite();
                    },
                    decoration: InputDecoration(
                      labelText: 'Email address',
                      hintText: 'member@university.edu',
                      hintStyle: const TextStyle(color: Color(0xFF64748B)),
                      prefixIcon: const Icon(
                        Icons.email_outlined,
                        color: Color(0xFF94A3B8),
                        size: 20,
                      ),
                      errorText: _inlineError,
                    ),
                    validator: (value) {
                      final v = value?.trim() ?? '';
                      if (v.isEmpty) return 'Enter an email address';
                      if (!_emailPattern.hasMatch(v)) {
                        return 'Enter a valid email address';
                      }
                      return null;
                    },
                  ),
                ),
                const SizedBox(height: 16),
                Align(
                  alignment: Alignment.centerRight,
                  child: ElevatedButton.icon(
                    onPressed: _sending ? null : _sendInvite,
                    icon: _sending
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.person_add_alt_1, size: 18),
                    label: Text(_sending ? 'Sending…' : 'Send invite'),
                  ),
                ),
              ],
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  onPressed: _sending ? null : () => Navigator.pop(context),
                  child: const Tr('Close'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
