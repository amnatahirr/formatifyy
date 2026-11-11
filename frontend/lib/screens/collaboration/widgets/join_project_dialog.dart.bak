import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../config/dev_user_config.dart';
import '../../../providers/auth_provider.dart';
import '../../../providers/collaboration_provider.dart';
import '../../../providers/document_provider.dart';

/// Modal to join a project with an invite code.
class JoinProjectDialog extends StatefulWidget {
  final void Function(int projectId)? onJoined;

  const JoinProjectDialog({super.key, this.onJoined});

  @override
  State<JoinProjectDialog> createState() => _JoinProjectDialogState();
}

class _JoinProjectDialogState extends State<JoinProjectDialog> {
  final _code = TextEditingController();
  bool _submitting = false;

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_code.text.trim().isEmpty) return;
    setState(() => _submitting = true);

    final auth = context.read<AuthProvider>();
    final userId = auth.userId ?? DevUserConfig.backendUserId;
    final vc = context.read<CollaborationProvider>();
    vc.setActiveUserId(userId);

    final ok = await vc.joinProject(_code.text.trim());
    if (!mounted) return;
    setState(() => _submitting = false);

    if (!ok || vc.currentProject == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(vc.error ?? 'Join failed')),
      );
      return;
    }

    await context.read<DocumentProvider>().fetchDocuments(userId);
    if (!mounted) return;
    final projectId = vc.currentProject!['id'] as int;
    Navigator.pop(context);
    widget.onJoined?.call(projectId);
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: const Color(0xFF1A1F2E),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Join Project',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 4),
              const Text(
                'Enter the invite code shared by a project member.',
                style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
              ),
              const SizedBox(height: 20),
              TextField(
                controller: _code,
                decoration: const InputDecoration(
                  labelText: 'Invite code',
                  hintText: 'ABC123XYZ',
                ),
                textCapitalization: TextCapitalization.characters,
              ),
              const SizedBox(height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: _submitting ? null : () => Navigator.pop(context),
                    child: const Text('Cancel'),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton(
                    onPressed: _submitting ? null : _submit,
                    child: _submitting
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Text('Join'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
