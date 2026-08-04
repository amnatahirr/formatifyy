import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../config/dev_user_config.dart';
import '../../services/super_admin_api_service.dart';
import '../../utils/responsive.dart';
import '../../theme/app_theme.dart';
import '../../widgets/admin/admin_ui.dart';

/// Platform Super Admin — manage organizations (multi-tenancy).
/// Access with [DevUserConfig.superAdminKey] matching backend SUPER_ADMIN_KEY.
class SuperAdminScreen extends StatefulWidget {
  const SuperAdminScreen({super.key});

  @override
  State<SuperAdminScreen> createState() => _SuperAdminScreenState();
}

class _SuperAdminNavItem {
  final int id;
  final String label;
  final String shortLabel;
  final IconData icon;

  const _SuperAdminNavItem({
    required this.id,
    required this.label,
    required this.shortLabel,
    required this.icon,
  });
}

class _SuperAdminScreenState extends State<SuperAdminScreen> {
  final SuperAdminApiService _api = SuperAdminApiService();
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  final _keyController = TextEditingController(text: DevUserConfig.superAdminKey);

  static const _navItems = <_SuperAdminNavItem>[
    _SuperAdminNavItem(
      id: 0,
      label: 'Overview',
      shortLabel: 'Home',
      icon: Icons.dashboard_outlined,
    ),
    _SuperAdminNavItem(
      id: 1,
      label: 'Organizations',
      shortLabel: 'Orgs',
      icon: Icons.apartment_outlined,
    ),
    _SuperAdminNavItem(
      id: 2,
      label: 'Admins',
      shortLabel: 'Admins',
      icon: Icons.people_outline,
    ),
    _SuperAdminNavItem(
      id: 3,
      label: 'Billing',
      shortLabel: 'Billing',
      icon: Icons.receipt_long_outlined,
    ),
    _SuperAdminNavItem(
      id: 4,
      label: 'Activity',
      shortLabel: 'Activity',
      icon: Icons.history,
    ),
    _SuperAdminNavItem(
      id: 5,
      label: 'Settings',
      shortLabel: 'More',
      icon: Icons.settings_outlined,
    ),
  ];

  static const _mobilePrimaryIds = <int>[0, 1, 2, 5];

  int _selectedId = 1; // Organizations — existing screen
  List<Map<String, dynamic>> _orgs = const [];
  List<Map<String, dynamic>> _admins = const [];
  Map<String, dynamic>? _platformStats;
  bool _unlocked = false;
  bool _loading = false;
  String? _error;
  String _orgSearch = '';

  String get _selectedLabel {
    for (final item in _navItems) {
      if (item.id == _selectedId) return item.label;
    }
    return 'Super Admin';
  }

  List<_SuperAdminNavItem> get _mobilePrimaryItems {
    return _mobilePrimaryIds
        .map((id) {
          for (final item in _navItems) {
            if (item.id == id) return item;
          }
          return null;
        })
        .whereType<_SuperAdminNavItem>()
        .toList();
  }

  void _selectNav(_SuperAdminNavItem item, {bool closeDrawer = false}) {
    setState(() => _selectedId = item.id);
    if (closeDrawer) {
      Navigator.of(context).maybePop();
    }
  }

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
      final admins = await _api.listAdmins();
      if (!mounted) return;
      setState(() {
        _orgs = orgs;
        _platformStats = stats;
        _admins = admins;
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
      final admins = await _api.listAdmins();
      if (!mounted) return;
      setState(() {
        _orgs = orgs;
        _platformStats = stats;
        _admins = admins;
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

    final compact = isCompact(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setLocal) => AlertDialog(
          backgroundColor: AdminColors.surface,
          insetPadding: EdgeInsets.symmetric(
            horizontal: compact ? 16 : 40,
            vertical: compact ? 24 : 40,
          ),
          title: const Text('Create Organization'),
          content: SizedBox(
            width: compact ? double.maxFinite : 460,
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
                    decoration: const InputDecoration(
                      labelText: 'Org Code (e.g. NUST-ISB)',
                    ),
                  ),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<String>(
                    value: plan,
                    decoration: const InputDecoration(labelText: 'Plan'),
                    items: const [
                      DropdownMenuItem(
                        value: 'university',
                        child: Text('university'),
                      ),
                      DropdownMenuItem(
                        value: 'enterprise',
                        child: Text('enterprise (company)'),
                      ),
                      DropdownMenuItem(
                        value: 'starter',
                        child: Text('starter'),
                      ),
                    ],
                    onChanged: (v) => setLocal(() {
                      plan = v ?? 'university';
                      if (plan == 'enterprise' || plan == 'starter') {
                        hasFyp = false;
                      } else {
                        hasFyp = true;
                      }
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
                      decoration: const InputDecoration(
                        labelText: 'Admin Password',
                      ),
                    ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: Text(compact ? 'Create' : 'Create Organization + Admin'),
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

    if (!mounted) return;
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => PopScope(
        canPop: false,
        child: AlertDialog(
          backgroundColor: AdminColors.surface,
          content: Row(
            children: [
              const SizedBox(
                width: 28,
                height: 28,
                child: CircularProgressIndicator(
                  strokeWidth: 3,
                  color: AdminColors.primary,
                ),
              ),
              const SizedBox(width: 18),
              Expanded(
                child: Text(
                  'Creating organization and sending login credentials to $adminEmail…',
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.85),
                    fontSize: 13,
                    height: 1.4,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );

    try {
      final result = await _api.createOrganization({
        'name': nameCtrl.text.trim(),
        'code': codeCtrl.text.trim(),
        // Only the university plan is a university tenant; starter + enterprise are company.
        'type': plan == 'university' ? 'university' : 'company',
        'plan': plan,
        'modules': modules,
        'admin_name': adminNameCtrl.text.trim(),
        'admin_email': adminEmail,
        if (!autoPassword && adminPassCtrl.text.trim().isNotEmpty)
          'admin_password': adminPassCtrl.text.trim(),
      });
      if (mounted) Navigator.of(context, rootNavigator: true).pop();
      await _refresh();
      if (!mounted) return;
      await _showCreatedCredentialsDialog(result);
    } catch (e) {
      if (mounted) Navigator.of(context, rootNavigator: true).pop();
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    }
  }

  Future<void> _showCreatedCredentialsDialog(Map<String, dynamic> result) async {
    final org = Map<String, dynamic>.from(result['organization'] as Map? ?? {});
    final admin = result['admin'] is Map
        ? Map<String, dynamic>.from(result['admin'] as Map)
        : null;
    final code = (result['org_code'] ?? org['code'] ?? '').toString();
    final emailInfo = result['credentials_email'] is Map
        ? Map<String, dynamic>.from(result['credentials_email'] as Map)
        : (admin != null && admin['credentials_email'] is Map
            ? Map<String, dynamic>.from(admin['credentials_email'] as Map)
            : null);
    final emailSent = emailInfo?['sent'] == true;
    final emailMessage = (emailInfo?['message'] ?? result['message'] ?? '').toString();

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
                emailSent
                    ? 'Login credentials were emailed to the org admin. You can still copy them below if needed:'
                    : 'Credentials email could not be sent automatically. Share these with the Org Admin:',
                style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 13, height: 1.4),
              ),
              if (emailMessage.isNotEmpty) ...[
                const SizedBox(height: 10),
                Text(
                  emailMessage,
                  style: TextStyle(
                    color: emailSent
                        ? const Color(0xFF4ADE80)
                        : const Color(0xFFFBBF24),
                    fontSize: 12,
                    height: 1.35,
                  ),
                ),
              ],
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

  /// Update plan/type only — never overwrite modules (core/fyp are independent).
  Future<bool> _changeOrgPlan(Map<String, dynamic> org) async {
    final id = org['id'] as int;
    var plan = (org['plan'] ?? 'university').toString();
    if (plan != 'university' && plan != 'enterprise' && plan != 'starter') {
      plan = 'university';
    }

    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setLocal) => AlertDialog(
          backgroundColor: AdminColors.surface,
          title: Text('Change plan — ${org['code']}'),
          content: DropdownButtonFormField<String>(
            value: plan,
            decoration: const InputDecoration(labelText: 'Plan'),
            items: const [
              DropdownMenuItem(value: 'university', child: Text('university')),
              DropdownMenuItem(value: 'enterprise', child: Text('enterprise (company)')),
              DropdownMenuItem(value: 'starter', child: Text('starter')),
            ],
            onChanged: (v) => setLocal(() => plan = v ?? 'university'),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
    if (ok != true) return false;

    try {
      await _api.updateOrganization(id, {
        'plan': plan,
        'type': plan == 'university' ? 'university' : 'company',
      });
      await _refresh();
      if (mounted) {
        showAdminSnackBar(context, 'Plan updated to $plan.');
      }
      return true;
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
      return false;
    }
  }

  /// Edit core/fyp modules independently of plan (company may have FYP, university may be core-only).
  Future<bool> _changeOrgModules(Map<String, dynamic> org) async {
    final id = org['id'] as int;
    final current = <String>{};
    final rawList = org['modules_list'];
    if (rawList is List) {
      current.addAll(rawList.map((e) => e.toString().trim().toLowerCase()));
    } else {
      current.addAll(
        (org['modules'] ?? 'core')
            .toString()
            .split(',')
            .map((e) => e.trim().toLowerCase())
            .where((e) => e.isNotEmpty),
      );
    }
    var hasCore = current.contains('core') || current.isEmpty;
    var hasFyp = current.contains('fyp');

    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setLocal) => AlertDialog(
          backgroundColor: AdminColors.surface,
          title: Text('Edit modules — ${org['code']}'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CheckboxListTile(
                value: hasCore,
                onChanged: (v) => setLocal(() => hasCore = v ?? true),
                title: const Text('core module'),
                dense: true,
                contentPadding: EdgeInsets.zero,
              ),
              CheckboxListTile(
                value: hasFyp,
                onChanged: (v) => setLocal(() => hasFyp = v ?? false),
                title: const Text('fyp module'),
                dense: true,
                contentPadding: EdgeInsets.zero,
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
    if (ok != true) return false;

    final modules = <String>[
      if (hasCore) 'core',
      if (hasFyp) 'fyp',
    ];
    if (modules.isEmpty) modules.add('core');

    try {
      await _api.updateOrganization(id, {'modules': modules});
      await _refresh();
      if (mounted) {
        showAdminSnackBar(context, 'Modules updated: ${modules.join(', ')}.');
      }
      return true;
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
      return false;
    }
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
              Text(
                '${org['code']} · ${org['plan']} · ${(org['modules'] ?? 'core')}',
                style: TextStyle(color: Colors.white.withOpacity(0.55)),
              ),
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
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AdminColors.primary,
                    side: BorderSide(color: AdminColors.primary.withOpacity(0.7)),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                  onPressed: () async {
                    final changed = await _changeOrgPlan(org);
                    if (changed == true && ctx.mounted) Navigator.pop(ctx);
                  },
                  icon: const Icon(Icons.swap_horiz_rounded, size: 18),
                  label: const Text('Change plan'),
                ),
              ),
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AdminColors.primary,
                    side: BorderSide(color: AdminColors.primary.withOpacity(0.7)),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                  onPressed: () async {
                    final changed = await _changeOrgModules(org);
                    if (changed == true && ctx.mounted) Navigator.pop(ctx);
                  },
                  icon: const Icon(Icons.extension_rounded, size: 18),
                  label: const Text('Edit modules'),
                ),
              ),
              const SizedBox(height: 10),
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
    if (!_unlocked) {
      return Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: AdminColors.surface,
          title: const Text('Super Admin'),
        ),
        body: AppPalette.dark.ambientGlowBackdrop(child: _buildGate()),
      );
    }

    final compact = isCompact(context);

    return Scaffold(
      key: _scaffoldKey,
      backgroundColor: Colors.transparent,
      drawer: compact ? _buildDrawer() : null,
      floatingActionButton: compact && _selectedId == 1
          ? FloatingActionButton(
              onPressed: _showCreateDialog,
              backgroundColor: AdminColors.primary,
              child: const Icon(Icons.add, color: Colors.white),
            )
          : null,
      body: AppPalette.dark.ambientGlowBackdrop(
        child: compact
            ? SafeArea(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _buildTopBar(compact: true),
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
                        child: _buildContent(),
                      ),
                    ),
                  ],
                ),
              )
            : Row(
                children: [
                  _buildSidebar(),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        _buildTopBar(compact: false),
                        Expanded(
                          child: Padding(
                            padding: const EdgeInsets.all(26),
                            child: _buildContent(),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
      ),
      bottomNavigationBar: compact ? _buildMobileBottomNav() : null,
    );
  }

  Widget _buildDrawer() {
    return Drawer(
      backgroundColor: AdminColors.surface,
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
              child: Row(
                children: [
                  Container(
                    width: 26,
                    height: 26,
                    decoration: BoxDecoration(
                      color: AdminColors.primary,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.shield_outlined,
                      size: 14,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(width: 9),
                  const Text(
                    'Super Admin',
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                      fontSize: 14.5,
                    ),
                  ),
                ],
              ),
            ),
            Divider(height: 1, color: AdminColors.border.withOpacity(0.55)),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 14),
                children: _navItems
                    .map((item) => _buildNavItem(item, closeDrawer: true))
                    .toList(),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
              child: OutlinedButton.icon(
                onPressed: () {
                  Navigator.of(context).maybePop();
                  Navigator.of(context).maybePop();
                },
                icon: const Icon(Icons.arrow_back_rounded, size: 18),
                label: const Text('Back to login'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white70,
                  side: BorderSide(color: AdminColors.border.withOpacity(0.8)),
                  minimumSize: const Size(double.infinity, 44),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSidebar() {
    return Container(
      width: 224,
      padding: const EdgeInsets.symmetric(vertical: 22, horizontal: 14),
      decoration: BoxDecoration(
        color: AdminColors.surface,
        border: Border(right: BorderSide(color: AdminColors.border)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Row(
              children: [
                Container(
                  width: 26,
                  height: 26,
                  decoration: BoxDecoration(
                    color: AdminColors.primary,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.shield_outlined, size: 14, color: Colors.white),
                ),
                const SizedBox(width: 9),
                const Text(
                  'Super Admin',
                  style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 14.5),
                ),
              ],
            ),
          ),
          const SizedBox(height: 26),
          ..._navItems.map(_buildNavItem),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
            decoration: BoxDecoration(
              border: Border(top: BorderSide(color: AdminColors.border.withOpacity(0.55))),
            ),
            child: Row(
              children: [
                Container(
                  width: 6,
                  height: 6,
                  decoration: const BoxDecoration(color: AdminColors.success, shape: BoxShape.circle),
                ),
                const SizedBox(width: 6),
                Text(
                  'Platform operational',
                  style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.4)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNavItem(_SuperAdminNavItem item, {bool closeDrawer = false}) {
    final isSelected = _selectedId == item.id;
    return Padding(
      padding: const EdgeInsets.only(bottom: 2),
      child: Material(
        color: isSelected
            ? AdminColors.primary.withOpacity(0.14)
            : Colors.transparent,
        borderRadius: BorderRadius.circular(9),
        child: InkWell(
          borderRadius: BorderRadius.circular(9),
          onTap: () => _selectNav(item, closeDrawer: closeDrawer),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
            child: Row(
              children: [
                Icon(
                  item.icon,
                  size: 16,
                  color: isSelected
                      ? AdminColors.primary
                      : Colors.white.withOpacity(0.35),
                ),
                const SizedBox(width: 10),
                Text(
                  item.label,
                  style: TextStyle(
                    fontSize: 13,
                    color: isSelected
                        ? Colors.white
                        : Colors.white.withOpacity(0.55),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildMobileBottomNav() {
    final items = _mobilePrimaryItems;
    final selectedNav = items.indexWhere((item) => item.id == _selectedId);
    final showMoreSelected = selectedNav < 0;

    return Container(
      decoration: BoxDecoration(
        color: AdminColors.surface,
        border: Border(top: BorderSide(color: AdminColors.border)),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 64,
          child: Row(
            children: [
              for (final item in items)
                Expanded(
                  child: InkWell(
                    onTap: () => _selectNav(item),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          item.icon,
                          size: 22,
                          color: item.id == _selectedId
                              ? AdminColors.primary
                              : Colors.white.withOpacity(0.35),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          item.shortLabel,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: item.id == _selectedId
                                ? FontWeight.w600
                                : FontWeight.w400,
                            color: item.id == _selectedId
                                ? AdminColors.primary
                                : Colors.white.withOpacity(0.45),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              Expanded(
                child: InkWell(
                  onTap: () => _scaffoldKey.currentState?.openDrawer(),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.menu_rounded,
                        size: 22,
                        color: showMoreSelected
                            ? AdminColors.primary
                            : Colors.white.withOpacity(0.35),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Menu',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: showMoreSelected
                              ? FontWeight.w600
                              : FontWeight.w400,
                          color: showMoreSelected
                              ? AdminColors.primary
                              : Colors.white.withOpacity(0.45),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTopBar({required bool compact}) {
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 8 : 26,
        vertical: compact ? 10 : 16,
      ),
      decoration: BoxDecoration(
        color: AdminColors.surface,
        border: Border(bottom: BorderSide(color: AdminColors.border)),
      ),
      child: Row(
        children: [
          if (compact)
            IconButton(
              onPressed: () => _scaffoldKey.currentState?.openDrawer(),
              icon: const Icon(Icons.menu_rounded, color: Colors.white),
              tooltip: 'Menu',
            ),
          Expanded(
            child: Text(
              _selectedLabel,
              style: TextStyle(
                fontSize: compact ? 16 : 17,
                fontWeight: FontWeight.w600,
                color: Colors.white,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (_selectedId == 1 && !compact) ...[
            SizedBox(
              width: 220,
              height: 36,
              child: TextField(
                style: const TextStyle(color: Colors.white, fontSize: 13),
                onChanged: (v) => setState(() => _orgSearch = v),
                decoration: InputDecoration(
                  hintText: 'Search organizations',
                  hintStyle: TextStyle(
                    color: Colors.white.withOpacity(0.35),
                    fontSize: 13,
                  ),
                  prefixIcon: Icon(
                    Icons.search,
                    size: 16,
                    color: Colors.white.withOpacity(0.35),
                  ),
                  filled: true,
                  fillColor: AdminColors.card,
                  contentPadding: const EdgeInsets.symmetric(vertical: 0),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(9),
                    borderSide: const BorderSide(color: AdminColors.border),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(9),
                    borderSide: const BorderSide(color: AdminColors.primary),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 10),
          ],
          if (_selectedId == 1 && compact)
            IconButton(
              onPressed: () => _showMobileSearchSheet(),
              icon: Icon(
                Icons.search,
                size: 20,
                color: Colors.white.withOpacity(0.7),
              ),
              tooltip: 'Search',
            ),
          if (_selectedId == 0 || _selectedId == 1 || _selectedId == 2)
            IconButton(
              onPressed: _loading ? null : _refresh,
              icon: Icon(
                Icons.refresh,
                size: 18,
                color: Colors.white.withOpacity(0.55),
              ),
              tooltip: 'Refresh',
            ),
          if (_selectedId == 1 && !compact) ...[
            const SizedBox(width: 8),
            ElevatedButton.icon(
              onPressed: _showCreateDialog,
              icon: const Icon(Icons.add, size: 16),
              label: const Text('Add Organization'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AdminColors.primary,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(9),
                ),
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 12,
                ),
              ),
            ),
          ],
          IconButton(
            onPressed: () => Navigator.of(context).maybePop(),
            icon: Icon(
              Icons.arrow_back_rounded,
              size: 18,
              color: Colors.white.withOpacity(0.55),
            ),
            tooltip: 'Back',
          ),
        ],
      ),
    );
  }

  Future<void> _showMobileSearchSheet() async {
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: AdminColors.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return Padding(
          padding: EdgeInsets.fromLTRB(
            16,
            16,
            16,
            16 + MediaQuery.of(ctx).viewInsets.bottom,
          ),
          child: TextField(
            autofocus: true,
            style: const TextStyle(color: Colors.white, fontSize: 15),
            onChanged: (v) => setState(() => _orgSearch = v),
            decoration: InputDecoration(
              hintText: 'Search organizations',
              hintStyle: TextStyle(color: Colors.white.withOpacity(0.35)),
              prefixIcon: Icon(
                Icons.search,
                color: Colors.white.withOpacity(0.35),
              ),
              filled: true,
              fillColor: AdminColors.card,
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: AdminColors.border),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: AdminColors.primary),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildContent() {
    switch (_selectedId) {
      case 0:
        return _buildOverview();
      case 1:
        return _buildOrganizationsList();
      case 2:
        return _buildAdminsList();
      case 3:
        return _buildBillingPlaceholder();
      case 4:
        return _buildActivityPlaceholder();
      case 5:
        return _buildSettingsPlaceholder();
      default:
        return const SizedBox();
    }
  }

  Widget _buildOverview() {
    final stats = _platformStats;
    if (_loading && stats == null) {
      return const Center(child: CircularProgressIndicator(color: AdminColors.primary));
    }
    if (stats == null) {
      return AdminErrorView(
        message: _error ?? 'Platform stats unavailable.',
        onRetry: _refresh,
      );
    }

    final totalOrgs = stats['total_orgs'] ?? 0;
    final activeOrgs = stats['active_orgs'] ?? 0;
    final totalDocs = stats['total_documents'] ?? 0;

    return RefreshIndicator(
      onRefresh: _refresh,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            LayoutBuilder(
              builder: (context, constraints) {
                final wide = constraints.maxWidth >= 900;
                final cards = [
                  _SaCompactStat(
                    icon: Icons.apartment_outlined,
                    label: 'Organizations',
                    value: '$totalOrgs',
                    sub: '$activeOrgs active',
                    accent: AdminColors.primary,
                  ),
                  _SaCompactStat(
                    icon: Icons.check_circle_outline,
                    label: 'Active',
                    value: '$activeOrgs',
                    sub: 'across platform',
                    accent: AdminColors.success,
                  ),
                  _SaCompactStat(
                    icon: Icons.description_outlined,
                    label: 'Documents',
                    value: '$totalDocs',
                    sub: 'across platform',
                    accent: AdminColors.warning,
                  ),
                ];
                if (wide) {
                  return Row(
                    children: [
                      for (var i = 0; i < cards.length; i++) ...[
                        if (i > 0) const SizedBox(width: 14),
                        Expanded(child: cards[i]),
                      ],
                    ],
                  );
                }
                return Column(
                  children: [
                    for (var i = 0; i < cards.length; i++) ...[
                      if (i > 0) const SizedBox(height: 14),
                      cards[i],
                    ],
                  ],
                );
              },
            ),
            const SizedBox(height: 14),
            LayoutBuilder(
              builder: (context, constraints) {
                final stacked = constraints.maxWidth < 900;
                final growth = _saPanel(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Organization growth',
                        style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: Colors.white),
                      ),
                      const SizedBox(height: 18),
                      // MOCK DATA — replace with real historical org counts when available.
                      const SuperAdminMockGrowthChart(
                        counts: _mockGrowthCounts,
                        labels: _mockGrowthLabels,
                      ),
                    ],
                  ),
                );

                // Same mock entries as the Activity screen (excerpt of first 4).
                final activity = _saPanel(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Recent activity',
                        style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: Colors.white),
                      ),
                      const SizedBox(height: 16),
                      ..._mockActivity.take(4).map((a) {
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 14),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                margin: const EdgeInsets.only(top: 6),
                                width: 6,
                                height: 6,
                                decoration: const BoxDecoration(
                                  color: AdminColors.primary,
                                  shape: BoxShape.circle,
                                ),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      a.text,
                                      style: const TextStyle(
                                        fontSize: 12.5,
                                        color: Colors.white,
                                        height: 1.4,
                                      ),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      a.time,
                                      style: TextStyle(
                                        fontSize: 11,
                                        color: Colors.white.withOpacity(0.35),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        );
                      }),
                    ],
                  ),
                );
                if (stacked) {
                  return Column(children: [growth, const SizedBox(height: 14), activity]);
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(flex: 2, child: growth),
                    const SizedBox(width: 14),
                    Expanded(child: activity),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAdminsList() {
    if (_loading && _admins.isEmpty) {
      return const Center(child: CircularProgressIndicator(color: AdminColors.primary));
    }
    if (_error != null && _admins.isEmpty) {
      return AdminErrorView(message: _error!, onRetry: _refresh);
    }

    if (_admins.isEmpty) {
      return RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          children: const [
            SizedBox(height: 80),
            AdminEmptyView(message: 'No organization admins yet.'),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView(
        children: [
          if (isCompact(context))
            ..._admins.map((admin) {
              final name = admin['name']?.toString() ?? '';
              final email = admin['email']?.toString() ?? '';
              final role = admin['role']?.toString() ?? 'admin';
              final orgName = admin['org_name']?.toString() ?? '';
              final orgCode = admin['org_code']?.toString() ?? '';
              final orgLabel = orgCode.isEmpty ? orgName : orgCode;
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _saPanel(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(
                            Icons.person_outline,
                            size: 16,
                            color: Colors.white.withOpacity(0.45),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              name.isEmpty ? '—' : name,
                              style: const TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w600,
                                color: Colors.white,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          _SaPill.accent(role),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        email.isEmpty ? '—' : email,
                        style: TextStyle(
                          fontSize: 12.5,
                          color: Colors.white.withOpacity(0.55),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        orgLabel.isEmpty ? '—' : orgLabel,
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.white.withOpacity(0.4),
                          fontFamily: 'monospace',
                        ),
                      ),
                    ],
                  ),
                ),
              );
            })
          else
            _saPanel(
              padding: EdgeInsets.zero,
              child: Column(
                children: [
                  _saRowHeader(const ['NAME', 'EMAIL', 'ORG', 'ROLE']),
                  ..._admins.map((admin) {
                    final name = admin['name']?.toString() ?? '';
                    final email = admin['email']?.toString() ?? '';
                    final role = admin['role']?.toString() ?? 'admin';
                    final orgName = admin['org_name']?.toString() ?? '';
                    final orgCode = admin['org_code']?.toString() ?? '';
                    final orgLabel = orgCode.isEmpty ? orgName : orgCode;
                    return _saDataRow([
                      Row(
                        children: [
                          Icon(
                            Icons.person_outline,
                            size: 13,
                            color: Colors.white.withOpacity(0.35),
                          ),
                          const SizedBox(width: 8),
                          Flexible(
                            child: Text(
                              name.isEmpty ? '—' : name,
                              style: const TextStyle(
                                fontSize: 13,
                                color: Colors.white,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                      Text(
                        email.isEmpty ? '—' : email,
                        style: TextStyle(
                          fontSize: 12.5,
                          color: Colors.white.withOpacity(0.55),
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                      Text(
                        orgLabel.isEmpty ? '—' : orgLabel,
                        style: TextStyle(
                          fontSize: 12.5,
                          color: Colors.white.withOpacity(0.55),
                          fontFamily: 'monospace',
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: _SaPill.accent(role),
                      ),
                    ]);
                  }),
                ],
              ),
            ),
        ],
      ),
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

  Widget _buildOrganizationsList() {
    final stats = _platformStats;
    final query = _orgSearch.trim().toLowerCase();
    final filtered = query.isEmpty
        ? _orgs
        : _orgs.where((org) {
            final name = (org['name'] ?? '').toString().toLowerCase();
            final code = (org['code'] ?? '').toString().toLowerCase();
            return name.contains(query) || code.contains(query);
          }).toList();

    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView(
        children: [
          if (stats != null) ...[
            _saPanel(
              child: Text(
                'Orgs ${stats['total_orgs']} · Active ${stats['active_orgs']} · '
                'Docs ${stats['total_documents']}',
                style: TextStyle(color: Colors.white.withOpacity(0.85), height: 1.4, fontSize: 13),
              ),
            ),
            const SizedBox(height: 14),
          ],
          if (_loading && _orgs.isEmpty)
            const Padding(
              padding: EdgeInsets.only(top: 48),
              child: Center(child: CircularProgressIndicator(color: AdminColors.primary)),
            )
          else if (_orgs.isEmpty)
            const AdminEmptyView(message: 'No organizations yet.')
          else if (filtered.isEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 48),
              child: Center(
                child: Text(
                  'No organizations match "$_orgSearch".',
                  style: TextStyle(color: Colors.white.withOpacity(0.4)),
                ),
              ),
            )
          else
            ...filtered.map((org) {
              final active = org['is_active'] == true;
              final used = int.tryParse('${org['documents_used']}') ?? 0;
              final limit = int.tryParse('${org['documents_limit']}') ?? 0;
              final plan = (org['plan'] ?? '').toString();
              final modules = _modulesForOrg(org);
              final planLabel = plan.isEmpty
                  ? '—'
                  : '${plan[0].toUpperCase()}${plan.substring(1)}';

              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _saPanel(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                  child: LayoutBuilder(
                    builder: (context, constraints) {
                      final narrow = constraints.maxWidth < 520;
                      final leading = Row(
                        children: [
                          _SaQuotaRing(used: used, limit: limit),
                          const SizedBox(width: 14),
                          Expanded(
                            child: InkWell(
                              onTap: () => _openOrgDetail(org),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Flexible(
                                        child: Text(
                                          org['name']?.toString() ?? '',
                                          style: const TextStyle(
                                            fontSize: 14.5,
                                            fontWeight: FontWeight.w600,
                                            color: Colors.white,
                                          ),
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ),
                                      const SizedBox(width: 6),
                                      Icon(
                                        Icons.chevron_right,
                                        size: 15,
                                        color: Colors.white.withOpacity(0.35),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 6),
                                  Wrap(
                                    spacing: 8,
                                    runSpacing: 6,
                                    crossAxisAlignment: WrapCrossAlignment.center,
                                    children: [
                                      Text(
                                        org['code']?.toString() ?? '',
                                        style: TextStyle(
                                          fontSize: 11.5,
                                          color: Colors.white.withOpacity(0.55),
                                          fontFamily: 'monospace',
                                        ),
                                      ),
                                      _SaPill.accent(planLabel),
                                      ...modules.map((m) => _SaPill(m)),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      );

                      final trailing = Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Docs $used/$limit',
                            style: TextStyle(
                              fontSize: 11.5,
                              color: Colors.white.withOpacity(0.4),
                              fontFamily: 'monospace',
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
                                if (mounted) {
                                  showAdminSnackBar(
                                    context,
                                    e.toString(),
                                    isError: true,
                                  );
                                }
                              }
                            },
                          ),
                        ],
                      );

                      if (narrow) {
                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            leading,
                            const SizedBox(height: 10),
                            trailing,
                          ],
                        );
                      }

                      return Row(
                        children: [
                          Expanded(child: leading),
                          const SizedBox(width: 12),
                          Text(
                            'Docs $used/$limit',
                            style: TextStyle(
                              fontSize: 11.5,
                              color: Colors.white.withOpacity(0.4),
                              fontFamily: 'monospace',
                            ),
                          ),
                          const SizedBox(width: 12),
                          Switch(
                            value: active,
                            activeColor: AdminColors.primary,
                            onChanged: (_) async {
                              try {
                                await _api.toggleOrganization(org['id'] as int);
                                await _refresh();
                              } catch (e) {
                                if (mounted) {
                                  showAdminSnackBar(
                                    context,
                                    e.toString(),
                                    isError: true,
                                  );
                                }
                              }
                            },
                          ),
                        ],
                      );
                    },
                  ),
                ),
              );
            }),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // MOCK DATA — replace when real endpoint / pricing fields exist.
  // Billing prices are invented; org rows come from the real `_orgs` list.
  // Activity entries are static fake audit lines (no API).
  // Settings catalog prices are invented; module/plan keys are real.
  // ---------------------------------------------------------------------------

  static const _mockPlanPricesUsd = <String, int>{
    'enterprise': 99,
    'university': 150,
    'starter': 48,
  };

  static const _mockPlanLabels = <String, String>{
    'enterprise': 'Enterprise (Company)',
    'university': 'University',
    'starter': 'Starter',
  };

  static const _mockModuleCatalog = <({String key, String label, int price, String desc})>[
    (key: 'core', label: 'Core Module', price: 99, desc: 'Base platform access, document workflows, reporting.'),
    (key: 'fyp', label: 'FYP Module', price: 51, desc: 'Final-year project tracking, supervisor allocation, defenses.'),
  ];

  static const _mockActivity = <({String text, String time, String kind})>[
    (text: 'Fast was created on plan university', time: '27 May, 09:14', kind: 'org'),
    (text: 'Tkxel was reactivated after suspension', time: '22 May, 17:02', kind: 'toggle'),
    (text: 'Admin invite sent to sara.malik@tkxel.com', time: '18 Apr, 11:40', kind: 'admin'),
    (text: 'fyp module enabled for COMSATS University Islamabad', time: '3 Mar, 14:21', kind: 'module'),
    (text: 'DEVSINC was created on plan enterprise', time: '2 Mar, 08:55', kind: 'org'),
  ];

  // MOCK DATA — replace with real historical org counts when available.
  // Used by Overview growth chart (Jan–Jun).
  static const _mockGrowthCounts = [1, 1, 2, 2, 3, 4];
  static const _mockGrowthLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];

  int _mockMonthlyPriceForPlan(String plan) {
    final key = plan.trim().toLowerCase();
    return _mockPlanPricesUsd[key] ?? 99;
  }

  Widget _buildBillingPlaceholder() {
    // MOCK DATA — replace when real monthly_price_usd (or plan catalog) exists.
    final planKeys = ['university', 'enterprise', 'starter'];
    final total = _orgs.fold<int>(
      0,
      (sum, org) => sum + _mockMonthlyPriceForPlan((org['plan'] ?? '').toString()),
    );

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              for (final key in planKeys) ...[
                Expanded(
                  child: _saPanel(
                    child: Builder(
                      builder: (_) {
                        final planOrgs = _orgs
                            .where((o) => (o['plan'] ?? '').toString().toLowerCase() == key)
                            .toList();
                        final planTotal = planOrgs.fold<int>(
                          0,
                          (s, o) => s + _mockMonthlyPriceForPlan(key),
                        );
                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _mockPlanLabels[key] ?? key,
                              style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.55)),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              '\$$planTotal/mo',
                              style: const TextStyle(
                                fontSize: 22,
                                fontWeight: FontWeight.w600,
                                color: Colors.white,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${planOrgs.length} organizations',
                              style: TextStyle(fontSize: 11.5, color: Colors.white.withOpacity(0.35)),
                            ),
                          ],
                        );
                      },
                    ),
                  ),
                ),
                const SizedBox(width: 14),
              ],
              Expanded(
                child: Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    color: AdminColors.primary.withOpacity(0.12),
                    border: Border.all(color: AdminColors.primary),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Platform total',
                        style: TextStyle(fontSize: 12, color: AdminColors.primary.withOpacity(0.9)),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '\$$total/mo',
                        style: const TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'estimated recurring',
                        style: TextStyle(fontSize: 11.5, color: AdminColors.primary.withOpacity(0.75)),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _saPanel(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                _saRowHeader(const ['ORGANIZATION', 'PLAN', 'MODULES', 'MONTHLY']),
                if (_orgs.isEmpty)
                  Padding(
                    padding: const EdgeInsets.all(18),
                    child: Text(
                      'No organizations yet.',
                      style: TextStyle(fontSize: 12.5, color: Colors.white.withOpacity(0.4)),
                    ),
                  )
                else
                  ..._orgs.map((org) {
                    final plan = (org['plan'] ?? '').toString().toLowerCase();
                    final modules = _modulesForOrg(org);
                    final price = _mockMonthlyPriceForPlan(plan);
                    return _saDataRow([
                      Text(
                        org['name']?.toString() ?? '—',
                        style: const TextStyle(fontSize: 13, color: Colors.white),
                        overflow: TextOverflow.ellipsis,
                      ),
                      Text(
                        plan.isEmpty ? '—' : plan,
                        style: TextStyle(fontSize: 12.5, color: Colors.white.withOpacity(0.55)),
                      ),
                      Wrap(
                        spacing: 5,
                        runSpacing: 4,
                        children: modules.map((m) => _SaPill(m)).toList(),
                      ),
                      Text(
                        '\$$price',
                        style: const TextStyle(
                          fontSize: 13,
                          color: Colors.white,
                          fontFamily: 'monospace',
                        ),
                      ),
                    ]);
                  }),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActivityPlaceholder() {
    // MOCK DATA — replace when GET /super-admin/activity exists.
    const icons = <String, IconData>{
      'org': Icons.apartment_outlined,
      'toggle': Icons.block,
      'admin': Icons.vpn_key_outlined,
      'module': Icons.settings_outlined,
    };

    return _saPanel(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        children: _mockActivity.map((a) {
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: AdminColors.card,
                    borderRadius: BorderRadius.circular(9),
                  ),
                  child: Icon(
                    icons[a.kind] ?? Icons.history,
                    size: 14,
                    color: Colors.white.withOpacity(0.45),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(a.text, style: const TextStyle(fontSize: 13, color: Colors.white)),
                      const SizedBox(height: 3),
                      Text(
                        a.time,
                        style: TextStyle(fontSize: 11.5, color: Colors.white.withOpacity(0.35)),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildSettingsPlaceholder() {
    // MOCK DATA — replace when server-backed module/plan catalogs exist.
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: _saPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Module catalog',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Colors.white),
                ),
                const SizedBox(height: 14),
                ..._mockModuleCatalog.map((e) {
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(e.label, style: const TextStyle(fontSize: 13, color: Colors.white)),
                              Text(
                                e.desc,
                                style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.35)),
                              ),
                            ],
                          ),
                        ),
                        Text(
                          '\$${e.price}/mo',
                          style: TextStyle(
                            fontSize: 12.5,
                            color: Colors.white.withOpacity(0.55),
                            fontFamily: 'monospace',
                          ),
                        ),
                      ],
                    ),
                  );
                }),
              ],
            ),
          ),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: _saPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Plans',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Colors.white),
                ),
                const SizedBox(height: 14),
                ..._mockPlanLabels.entries.map((p) {
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Row(
                      children: [
                        Expanded(
                          child: Text(p.value, style: const TextStyle(fontSize: 13, color: Colors.white)),
                        ),
                        Text(
                          '\$${_mockPlanPricesUsd[p.key]}/mo',
                          style: TextStyle(
                            fontSize: 12.5,
                            color: Colors.white.withOpacity(0.55),
                            fontFamily: 'monospace',
                          ),
                        ),
                        const SizedBox(width: 8),
                        Icon(Icons.chevron_right, size: 14, color: Colors.white.withOpacity(0.35)),
                      ],
                    ),
                  );
                }),
              ],
            ),
          ),
        ),
      ],
    );
  }

  List<String> _modulesForOrg(Map<String, dynamic> org) {
    final list = org['modules_list'];
    if (list is List && list.isNotEmpty) {
      return list.map((e) => e.toString()).where((e) => e.isNotEmpty).toList();
    }
    return (org['modules'] ?? 'core')
        .toString()
        .split(',')
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toList();
  }
}

// ---------------------------------------------------------------------------
// Local Super Admin chrome helpers (AdminColors only — no RefColors).
// ---------------------------------------------------------------------------

Widget _saPanel({required Widget child, EdgeInsets? padding}) => Container(
      padding: padding ?? const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AdminColors.surface,
        border: Border.all(color: AdminColors.border),
        borderRadius: BorderRadius.circular(14),
      ),
      child: child,
    );

Widget _saRowHeader(List<String> cols) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AdminColors.border)),
      ),
      child: Row(
        children: cols
            .map(
              (c) => Expanded(
                child: Text(
                  c,
                  style: TextStyle(
                    fontSize: 11,
                    color: Colors.white.withOpacity(0.35),
                    fontFamily: 'monospace',
                  ),
                ),
              ),
            )
            .toList(),
      ),
    );

Widget _saDataRow(List<Widget> cells) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 13),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: AdminColors.border.withOpacity(0.55))),
      ),
      child: Row(children: cells.map((c) => Expanded(child: c)).toList()),
    );

class _SaPill extends StatelessWidget {
  final String text;
  final Color? bg;
  final Color? fg;
  final Color? bd;

  const _SaPill(this.text, {this.bg, this.fg, this.bd});

  factory _SaPill.accent(String text) => _SaPill(
        text,
        bg: AdminColors.primary.withOpacity(0.14),
        fg: const Color(0xFFA5B4FC),
        bd: AdminColors.primary,
      );

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: bg ?? AdminColors.card,
        border: Border.all(color: (bd ?? AdminColors.border).withOpacity(0.4)),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 11.5,
          color: fg ?? Colors.white.withOpacity(0.55),
          fontFamily: 'monospace',
        ),
      ),
    );
  }
}

class _SaCompactStat extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final String? sub;
  final Color accent;

  const _SaCompactStat({
    required this.icon,
    required this.label,
    required this.value,
    this.sub,
    required this.accent,
  });

  @override
  Widget build(BuildContext context) {
    return _saPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 28,
                height: 28,
                decoration: BoxDecoration(
                  color: accent.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, size: 15, color: accent),
              ),
              const SizedBox(width: 8),
              Text(label, style: TextStyle(fontSize: 12.5, color: Colors.white.withOpacity(0.55))),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            value,
            style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w600, color: Colors.white),
          ),
          if (sub != null) ...[
            const SizedBox(height: 4),
            Text(sub!, style: TextStyle(fontSize: 11.5, color: Colors.white.withOpacity(0.35))),
          ],
        ],
      ),
    );
  }
}

class _SaQuotaRing extends StatelessWidget {
  final int used;
  final int limit;
  final double size;

  const _SaQuotaRing({required this.used, required this.limit, this.size = 40});

  @override
  Widget build(BuildContext context) {
    final pct = limit <= 0 ? 0.0 : (used / limit).clamp(0.0, 1.0);
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(painter: _SaRingPainter(pct)),
    );
  }
}

class _SaRingPainter extends CustomPainter {
  final double pct;
  _SaRingPainter(this.pct);

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = (size.width - 6) / 2;
    final track = Paint()
      ..color = AdminColors.card
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.5;
    final fill = Paint()
      ..color = pct > 0.8 ? AdminColors.warning : AdminColors.primary
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.5
      ..strokeCap = StrokeCap.round;
    canvas.drawCircle(center, radius, track);
    canvas.drawArc(Rect.fromCircle(center: center, radius: radius), -1.5708, 6.2832 * pct, false, fill);
  }

  @override
  bool shouldRepaint(covariant _SaRingPainter old) => old.pct != pct;
}

/// MOCK DATA chart — used by Super Admin Overview.
/// Replace counts/labels with real historical org series when available.
class SuperAdminMockGrowthChart extends StatelessWidget {
  final List<int> counts;
  final List<String> labels;

  const SuperAdminMockGrowthChart({
    super.key,
    required this.counts,
    required this.labels,
  });

  @override
  Widget build(BuildContext context) {
    assert(counts.length == labels.length && counts.isNotEmpty);
    final maxG = counts.reduce((a, b) => a > b ? a : b);
    return SizedBox(
      key: const Key('sa_mock_growth_chart'),
      height: 110,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: List.generate(counts.length, (i) {
          final isLast = i == counts.length - 1;
          final barHeight = (counts[i] / maxG) * 78 + 8;
          return Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 5),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Container(
                    key: Key('sa_mock_growth_bar_$i'),
                    height: barHeight,
                    decoration: BoxDecoration(
                      color: isLast ? AdminColors.primary : AdminColors.card,
                      borderRadius: BorderRadius.circular(6),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    labels[i],
                    style: TextStyle(
                      fontSize: 10.5,
                      color: Colors.white.withOpacity(0.35),
                    ),
                  ),
                ],
              ),
            ),
          );
        }),
      ),
    );
  }
}
