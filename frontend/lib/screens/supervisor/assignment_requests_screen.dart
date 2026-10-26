import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/supervisor_models.dart';
import '../../providers/auth_provider.dart';
import '../../services/supervisor_api_service.dart';
import '../../widgets/admin/admin_ui.dart';

import '../../widgets/tr.dart';
class AssignmentRequestsScreen extends StatefulWidget {
  const AssignmentRequestsScreen({super.key});

  @override
  State<AssignmentRequestsScreen> createState() => _AssignmentRequestsScreenState();
}

class _AssignmentRequestsScreenState extends State<AssignmentRequestsScreen> {
  final SupervisorApiService _api = SupervisorApiService();
  List<AssignmentRequestModel> _requests = const [];
  String? _error;
  bool _loading = true;
  final Set<int> _busyIds = {};
  List<String> _profileMismatchWarnings = const [];

  @override
  void initState() {
    super.initState();
    _loadRequests();
  }

  Future<void> _loadRequests() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final requests = await _api.fetchAssignmentRequests(userId);
      if (mounted) setState(() => _requests = requests);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _accept(AssignmentRequestModel request) async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _busyIds.add(request.id));
    try {
      final result = await _api.acceptAssignmentRequest(userId, request.id);
      if (!mounted) return;
      final rawWarnings = result['profile_mismatch_warnings'];
      final warnings = <String>[];
      if (rawWarnings is List) {
        for (final item in rawWarnings) {
          if (item is Map && item['message'] != null) {
            warnings.add(item['message'].toString());
          } else if (item != null) {
            warnings.add(item.toString());
          }
        }
      }
      setState(() => _profileMismatchWarnings = warnings);
      showAdminSnackBar(context, '${request.groupName} accepted and added to My Groups.');
      await _loadRequests();
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _busyIds.remove(request.id));
    }
  }

  Future<void> _reject(AssignmentRequestModel request) async {
    final reason = await _askRejectionReason(request);
    if (reason == null || reason.trim().isEmpty) return;

    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _busyIds.add(request.id));
    try {
      await _api.rejectAssignmentRequest(userId, request.id, reason: reason.trim());
      if (!mounted) return;
      showAdminSnackBar(context, '${request.groupName} rejected. Student notified.');
      await _loadRequests();
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _busyIds.remove(request.id));
    }
  }

  Future<String?> _askRejectionReason(AssignmentRequestModel request) async {
    final controller = TextEditingController();
    String? errorText;

    final result = await showDialog<String>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              backgroundColor: AdminColors.surface,
              shape: adminDialogShape(),
              title: const Tr('Reject request'),
              content: SizedBox(
                width: 420,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Provide a reason for rejecting ${request.groupName}. The student group will be notified.',
                      style: TextStyle(color: Colors.white.withOpacity(0.7), height: 1.4),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: controller,
                      maxLines: 4,
                      autofocus: true,
                      style: const TextStyle(color: Colors.white),
                      decoration: adminFieldDecoration(
                        label: 'Rejection reason',
                        hint: 'Explain why this request cannot be accepted…',
                      ).copyWith(errorText: errorText),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext),
                  child: const Tr('Cancel'),
                ),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(backgroundColor: AdminColors.danger),
                  onPressed: () {
                    final text = controller.text.trim();
                    if (text.isEmpty) {
                      setDialogState(() => errorText = 'A reason is required');
                      return;
                    }
                    Navigator.pop(dialogContext, text);
                  },
                  child: const Tr('Confirm Reject'),
                ),
              ],
            );
          },
        );
      },
    );

    controller.dispose();
    return result;
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const AdminPage(child: AdminLoadingView(label: 'Loading requests...'));
    }
    if (_error != null) {
      return AdminPage(child: AdminErrorView(message: _error!, onRetry: _loadRequests));
    }

    return AdminPage(
      onRefresh: _loadRequests,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AdminPageMeta(
            text: _requests.isEmpty
                ? 'No pending requests right now'
                : '${_requests.length} pending request${_requests.length == 1 ? '' : 's'} awaiting your decision',
          ),
          if (_profileMismatchWarnings.isNotEmpty) ...[
            const SizedBox(height: 16),
            _ProfileMismatchBanner(
              messages: _profileMismatchWarnings,
              onDismiss: () => setState(() => _profileMismatchWarnings = const []),
            ),
          ],
          const SizedBox(height: 20),
          if (_requests.isEmpty)
            const AdminEmptyView(
              icon: Icons.assignment_ind_outlined,
              title: 'No pending requests',
              message: 'When student groups choose you as supervisor, their requests will appear here.',
            )
          else
            ..._requests.map(
              (request) => Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: _AssignmentRequestCard(
                  request: request,
                  busy: _busyIds.contains(request.id),
                  onAccept: () => _accept(request),
                  onReject: () => _reject(request),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _ProfileMismatchBanner extends StatelessWidget {
  final List<String> messages;
  final VoidCallback onDismiss;

  const _ProfileMismatchBanner({
    required this.messages,
    required this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(14, 12, 8, 12),
      decoration: BoxDecoration(
        color: AdminColors.warning.withOpacity(0.12),
        borderRadius: BorderRadius.circular(adminTileRadius + 2),
        border: Border.all(color: AdminColors.warning.withOpacity(0.45)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(top: 2),
            child: Icon(Icons.info_outline, color: AdminColors.warning, size: 20),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Tr('Profile mismatch notice',
                  style: TextStyle(
                    color: AdminColors.warning,
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 6),
                ...messages.map(
                  (m) => Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text(
                      m,
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.82),
                        fontSize: 12.5,
                        height: 1.4,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            onPressed: onDismiss,
            tooltip: 'Dismiss',
            visualDensity: VisualDensity.compact,
            icon: Icon(Icons.close, size: 18, color: Colors.white.withOpacity(0.55)),
          ),
        ],
      ),
    );
  }
}

class _AssignmentRequestCard extends StatelessWidget {
  final AssignmentRequestModel request;
  final bool busy;
  final VoidCallback onAccept;
  final VoidCallback onReject;

  const _AssignmentRequestCard({
    required this.request,
    required this.busy,
    required this.onAccept,
    required this.onReject,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: adminCardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const AdminIconBadge(icon: Icons.assignment_ind_rounded, size: 22),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      request.groupName,
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Colors.white),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      request.topic.isEmpty ? 'No topic provided' : request.topic,
                      style: TextStyle(fontSize: 13, color: Colors.white.withOpacity(0.7)),
                    ),
                  ],
                ),
              ),
              const AdminPill(
                label: 'Pending',
                color: AdminColors.warning,
                icon: Icons.schedule_rounded,
              ),
            ],
          ),
          const SizedBox(height: 18),
          _metaRow(Icons.apartment_rounded, 'Department', request.departmentLabel),
          const SizedBox(height: 10),
          _metaRow(
            Icons.groups_rounded,
            'Members',
            request.memberNames.isEmpty ? '—' : request.memberNames.join(', '),
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: busy ? null : onReject,
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AdminColors.danger,
                    side: BorderSide(color: AdminColors.danger.withOpacity(0.7)),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(adminTileRadius),
                    ),
                  ),
                  icon: const Icon(Icons.close_rounded, size: 18),
                  label: const Tr('Reject'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: busy ? null : onAccept,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AdminColors.success,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(adminTileRadius),
                    ),
                  ),
                  icon: busy
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Icon(Icons.check_rounded, size: 18),
                  label: Text(busy ? 'Working…' : 'Accept'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _metaRow(IconData icon, String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 16, color: Colors.white.withOpacity(0.45)),
        const SizedBox(width: 8),
        SizedBox(
          width: 92,
          child: Text(
            label,
            style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.45), fontWeight: FontWeight.w600),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(fontSize: 13, color: Colors.white, height: 1.35),
          ),
        ),
      ],
    );
  }
}
