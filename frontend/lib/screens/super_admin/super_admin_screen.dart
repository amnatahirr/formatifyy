import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../config/dev_user_config.dart';
import '../../services/super_admin_api_service.dart';
import '../../widgets/admin/admin_ui.dart';

/// Platform Super Admin — manage organizations (multi-tenancy).
/// Access with [DevUserConfig.superAdminKey] matching backend SUPER_ADMIN_KEY.
class SuperAdminScreen extends StatefulWidget {
  const SuperAdminScreen({super.key});

  @override
  State<SuperAdminScreen> createState() => _SuperAdminScreenState();
}

class _SuperAdminScreenState extends State<SuperAdminScreen> {
  final SuperAdminApiService _api = SuperAdminApiService();
  final _keyController = TextEditingController(text: DevUserConfig.superAdminKey);

  List<Map<String, dynamic>> _orgs = const [];
  Map<String, dynamic>? _platformStats;
  bool _unlocked = false;
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _keyController.dispose();
    super.dispose();
  }

  Future<void> _unlock() async {
    DevUserConfig.superAdminKey = _keyController.text.trim();
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final orgs = await _api.listOrganizations();
      final stats = await _api.platformStats();
      if (!mounted) return;
      setState(() {
        _orgs = orgs;
        _platformStats = stats;
        _unlocked = true;
      });
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _refresh() async {
    setState(() => _loading = true);
    try {
      final orgs = await _api.listOrganizations();
      final stats = await _api.platformStats();
      if (!mounted) return;
      setState(() {
        _orgs = orgs;
        _platformStats = stats;
        _error = null;
      });
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _showCreateDialog() async {
    final nameCtrl = TextEditingController();
    final codeCtrl = TextEditingController();
    final adminNameCtrl = TextEditingController();
    final adminEmailCtrl = TextEditingController();
    final adminPassCtrl = TextEditingController();
    var plan = 'university';
    var hasCore = true;
    var hasFyp = true;
    var autoPassword = true;

    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setLocal) => AlertDialog(
          backgroundColor: AdminColors.surface,
          title: const Text('Create Organization'),
          content: SizedBox(
            width: 460,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  TextField(
                    controller: nameCtrl,
                    decoration: const InputDecoration(labelText: 'Org Name'),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: codeCtrl,
                    textCapitalization: TextCapitalization.characters,
                    decoration: const InputDecoration(labelText: 'Org Code (e.g. NUST-ISB)'),
                  ),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<String>(
                    value: plan,
                    decoration: const InputDecoration(labelText: 'Plan'),
                    items: const [
                      DropdownMenuItem(value: 'university', child: Text('university')),
                      DropdownMenuItem(value: 'enterprise', child: Text('enterprise (company)')),
                      DropdownMenuItem(value: 'starter', child: Text('starter')),
                    ],
                    onChanged: (v) => setLocal(() {
                      plan = v ?? 'university';
                      if (plan == 'enterprise') hasFyp = false;
                    }),
                  ),
                  CheckboxListTile(
                    value: hasCore,
                    onChanged: (v) => setLocal(() => hasCore = v ?? true),
                    title: const Text('core module'),
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                  ),
                  CheckboxListTile(
                    value: hasFyp,
                    onChanged: (v) => setLocal(() => hasFyp = v ?? true),
                    title: const Text('fyp module'),
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'First Admin Account',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.85),
                      fontWeight: FontWeight.w700,
                      fontSize: 13,
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: adminNameCtrl,
                    decoration: const InputDecoration(labelText: 'Admin Name'),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: adminEmailCtrl,
                    keyboardType: TextInputType.emailAddress,
                    decoration: const InputDecoration(labelText: 'Admin Email'),
                  ),
                  const SizedBox(height: 10),
                  CheckboxListTile(
                    value: autoPassword,
                    onChanged: (v) => setLocal(() => autoPassword = v ?? true),
                    title: const Text('Auto-generate password'),
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                  ),
                  if (!autoPassword)
                    TextField(
                      controller: adminPassCtrl,
                      obscureText: true,
                      decoration: const InputDecoration(labelText: 'Admin Password'),
                    ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Create Organization + Admin'),
            ),
          ],
        ),
      ),
    );

    if (ok != true) return;
    final modules = <String>[
      if (hasCore) 'core',
      if (hasFyp) 'fyp',
    ];
    if (modules.isEmpty) modules.add('core');

    final adminEmail = adminEmailCtrl.text.trim();
    if (adminEmail.isEmpty) {
      if (mounted) {
        showAdminSnackBar(context, 'Admin email is required to onboard the org.', isError: true);
      }
      return;
    }

    try {
      final result = await _api.createOrganization({
        'name': nameCtrl.text.trim(),
        'code': codeCtrl.text.trim(),
        'type': plan == 'enterprise' ? 'company' : 'university',
        'plan': plan,
        'modules': modules,
        'admin_name': adminNameCtrl.text.trim(),
        'admin_email': adminEmail,
        if (!autoPassword && adminPassCtrl.text.trim().isNotEmpty)
          'admin_password': adminPassCtrl.text.trim(),
      });
      await _refresh();
      if (!mounted) return;
      await _showCreatedCredentialsDialog(result);
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    }
  }

  Future<void> _showCreatedCredentialsDialog(Map<String, dynamic> result) async {
    final org = Map<String, dynamic>.from(result['organization'] as Map? ?? {});
    final admin = result['admin'] is Map
        ? Map<String, dynamic>.from(result['admin'] as Map)
        : null;
    final code = (result['org_code'] ?? org['code'] ?? '').toString();

    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        backgroundColor: AdminColors.surface,
        title: const Text('Organization ready'),
        content: SizedBox(
          width: 460,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Share only these with the Org Admin (never share internal API keys):',
                style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 13, height: 1.4),
              ),
              const SizedBox(height: 16),
              _credRow('Org Code', code, copyable: true),
              if (admin != null) ...[
                const SizedBox(height: 8),
                _credRow('Admin Email', (admin['email'] ?? '').toString(), copyable: true),
                const SizedBox(height: 8),
                _credRow('Admin Password', (admin['password'] ?? '').toString(), copyable: true),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              final buf = StringBuffer()
                ..writeln('Org: ${org['name']} ($code)')
                ..writeln('Org Code: $code');
              if (admin != null) {
                buf.writeln('Admin: ${admin['email']} / ${admin['password']}');
              }
              Clipboard.setData(ClipboardData(text: buf.toString()));
              showAdminSnackBar(context, 'Credentials copied.');
            },
            child: const Text('Copy all'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Done'),
          ),
        ],
      ),
    );
  }

  Widget _credRow(String label, String value, {bool copyable = false}) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 110,
          child: Text(label, style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 12)),
        ),
        Expanded(
          child: SelectableText(
            value.isEmpty ? '—' : value,
            style: const TextStyle(color: Colors.white, fontFamily: 'monospace', fontSize: 12),
          ),
        ),
        if (copyable && value.isNotEmpty)
          IconButton(
            tooltip: 'Copy',
            onPressed: () {
              Clipboard.setData(ClipboardData(text: value));
              showAdminSnackBar(context, '$label copied.');
            },
            icon: const Icon(Icons.copy_rounded, size: 18, color: AdminColors.primary),
          ),
      ],
    );
  }

  Future<void> _openOrgDetail(Map<String, dynamic> org) async {
    final id = org['id'] as int;
    Map<String, dynamic>? stats;
    try {
      stats = await _api.organizationStats(id);
    } catch (_) {}

    if (!mounted) return;
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: AdminColors.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(org['name']?.toString() ?? 'Organization',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Colors.white)),
              const SizedBox(height: 6),
              Text('${org['code']} · ${org['plan']}',
                  style: TextStyle(color: Colors.white.withOpacity(0.55))),
              const SizedBox(height: 12),
              Text(
                'Distribute org code + admin credentials only. API keys stay server-side.',
                style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 12, height: 1.35),
              ),
              if (stats != null) ...[
                const SizedBox(height: 16),
                Text('Usage', style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 12)),
                const SizedBox(height: 8),
                Text(
                  'Users ${(stats['stats'] as Map?)?['users'] ?? 0} · '
                  'Docs ${(stats['stats'] as Map?)?['documents'] ?? 0} · '
                  'Groups ${(stats['stats'] as Map?)?['groups'] ?? 0}',
                  style: const TextStyle(color: Colors.white),
                ),
              ],
              const SizedBox(height: 20),
              if (id == 1)
                Text(
                  'Default organization (id=1) cannot be deleted.',
                  style: TextStyle(color: Colors.white.withOpacity(0.45), fontSize: 12),
                )
              else
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AdminColors.danger,
                      side: BorderSide(color: AdminColors.danger.withOpacity(0.7)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    onPressed: () async {
                      final confirmed = await showDialog<bool>(
                        context: ctx,
                        builder: (dCtx) => AlertDialog(
                          backgroundColor: AdminColors.surface,
                          title: const Text('Delete organization?'),
                          content: Text(
                            'Permanently delete "${org['name']}" (${org['code']})?\n'
                            'This cannot be undone.',
                            style: TextStyle(color: Colors.white.withOpacity(0.8), height: 1.4),
                          ),
                          actions: [
                            TextButton(
                              onPressed: () => Navigator.pop(dCtx, false),
                              child: const Text('Cancel'),
                            ),
                            ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: AdminColors.danger,
                                foregroundColor: Colors.white,
                              ),
                              onPressed: () => Navigator.pop(dCtx, true),
                              child: const Text('Delete'),
                            ),
                          ],
                        ),
                      );
                      if (confirmed != true) return;
                      try {
                        await _api.deleteOrganization(id);
                        if (ctx.mounted) Navigator.pop(ctx);
                        await _refresh();
                        if (mounted) {
                          showAdminSnackBar(context, 'Organization deleted.');
                        }
                      } catch (e) {
                        if (mounted) {
                          showAdminSnackBar(context, e.toString(), isError: true);
                        }
                      }
                    },
                    icon: const Icon(Icons.delete_outline_rounded),
                    label: const Text('Delete organization'),
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AdminColors.background,
      appBar: AppBar(
        backgroundColor: AdminColors.surface,
        title: const Text('Super Admin'),
        actions: [
          if (_unlocked)
            IconButton(onPressed: _loading ? null : _refresh, icon: const Icon(Icons.refresh_rounded)),
        ],
      ),
      floatingActionButton: _unlocked
          ? FloatingActionButton.extended(
              onPressed: _showCreateDialog,
              icon: const Icon(Icons.add),
              label: const Text('Add Organization'),
            )
          : null,
      body: !_unlocked ? _buildGate() : _buildList(),
    );
  }

  Widget _buildGate() {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.admin_panel_settings_rounded, size: 48, color: AdminColors.primary),
              const SizedBox(height: 16),
              const Text(
                'Enter Super Admin key',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Colors.white),
              ),
              const SizedBox(height: 8),
              Text(
                'Must match backend SUPER_ADMIN_KEY',
                style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 13),
              ),
              const SizedBox(height: 20),
              TextField(
                controller: _keyController,
                obscureText: true,
                decoration: const InputDecoration(labelText: 'X-Super-Admin-Key'),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: AdminColors.danger, fontSize: 12)),
              ],
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _loading ? null : _unlock,
                  child: Text(_loading ? 'Checking…' : 'Unlock'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildList() {
    final stats = _platformStats;
    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (stats != null)
            AdminSectionCard(
              title: 'Platform',
              child: Text(
                'Orgs ${stats['total_orgs']} · Active ${stats['active_orgs']} · '
                'Docs ${stats['total_documents']} · Est. \$${stats['revenue_estimate_usd']}/mo',
                style: TextStyle(color: Colors.white.withOpacity(0.85), height: 1.4),
              ),
            ),
          const SizedBox(height: 16),
          if (_loading && _orgs.isEmpty)
            const Center(child: CircularProgressIndicator(color: AdminColors.primary))
          else if (_orgs.isEmpty)
            const AdminEmptyView(message: 'No organizations yet.')
          else
            ..._orgs.map((org) {
              final active = org['is_active'] == true;
              final modules = (org['modules'] ?? '').toString();
              return Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: InkWell(
                  onTap: () => _openOrgDetail(org),
                  borderRadius: BorderRadius.circular(14),
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: adminCardDecoration(),
                    child: Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                org['name']?.toString() ?? '',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w700,
                                  fontSize: 15,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${org['code']} · ${org['plan']} · $modules',
                                style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 12),
                              ),
                              const SizedBox(height: 6),
                              Text(
                                'Docs ${org['documents_used']}/${org['documents_limit']}',
                                style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 12),
                              ),
                            ],
                          ),
                        ),
                        Switch(
                          value: active,
                          activeColor: AdminColors.primary,
                          onChanged: (_) async {
                            try {
                              await _api.toggleOrganization(org['id'] as int);
                              await _refresh();
                            } catch (e) {
                              if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
                            }
                          },
                        ),
                      ],
                    ),
                  ),
                ),
              );
            }),
        ],
      ),
    );
  }
}
