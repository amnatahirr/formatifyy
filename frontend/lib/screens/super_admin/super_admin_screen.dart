import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../config/dev_user_config.dart';
import '../../services/super_admin_api_service.dart';
import '../../utils/responsive.dart';
import '../../theme/app_theme.dart';
import '../../widgets/admin/admin_ui.dart';

import '../../widgets/tr.dart';

/// Platform Super Admin — manage organizations (multi-tenancy).
/// Access with [DevUserConfig.superAdminKey] matching backend SUPER_ADMIN_KEY.
///
/// All dashboard data (overview, growth, billing, activity, catalogs) is loaded
/// from `GET /api/super-admin/stats` via [SuperAdminApiService.platformStats].
class SuperAdminScreen extends StatefulWidget {
  const SuperAdminScreen({super.key});

  @override
  State<SuperAdminScreen> createState() => _SuperAdminScreenState();
}

class _SuperAdminNavItem {
  final int id;
  final String label;
  final String shortLabel;
  final String subtitle;
  final IconData icon;

  const _SuperAdminNavItem({
    required this.id,
    required this.label,
    required this.shortLabel,
    required this.subtitle,
    required this.icon,
  });
}

// ---------------------------------------------------------------------------
// Small parsing helpers for server JSON.
// ---------------------------------------------------------------------------

Map<String, dynamic> _saMap(dynamic v) =>
    v is Map ? Map<String, dynamic>.from(v) : <String, dynamic>{};

List<Map<String, dynamic>> _saList(dynamic v) => v is List
    ? v.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList()
    : <Map<String, dynamic>>[];

int _saInt(dynamic v) => v is num ? v.toInt() : int.tryParse('${v ?? ''}') ?? 0;

String _saMoney(num n) {
  final s = n.round().toString();
  final buf = StringBuffer();
  for (var i = 0; i < s.length; i++) {
    if (i > 0 && (s.length - i) % 3 == 0) buf.write(',');
    buf.write(s[i]);
  }
  return '\$${buf.toString()}';
}

const _saMonthNames = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

String _saFormatTime(dynamic raw) {
  final parsed = DateTime.tryParse('${raw ?? ''}');
  if (parsed == null) return '';
  final d = parsed.toLocal();
  final hh = d.hour.toString().padLeft(2, '0');
  final mm = d.minute.toString().padLeft(2, '0');
  return '${d.day} ${_saMonthNames[d.month - 1]} ${d.year}, $hh:$mm';
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
      subtitle: 'Platform-wide metrics',
      icon: Icons.dashboard_rounded,
    ),
    _SuperAdminNavItem(
      id: 1,
      label: 'Organizations',
      shortLabel: 'Orgs',
      subtitle: 'Manage tenant organizations',
      icon: Icons.apartment_rounded,
    ),
    _SuperAdminNavItem(
      id: 2,
      label: 'Admins',
      shortLabel: 'Admins',
      subtitle: 'Organization administrators',
      icon: Icons.people_alt_rounded,
    ),
    _SuperAdminNavItem(
      id: 3,
      label: 'Billing',
      shortLabel: 'Billing',
      subtitle: 'Plans and estimated revenue',
      icon: Icons.receipt_long_rounded,
    ),
    _SuperAdminNavItem(
      id: 4,
      label: 'Activity',
      shortLabel: 'Activity',
      subtitle: 'Recent platform events',
      icon: Icons.history_rounded,
    ),
    _SuperAdminNavItem(
      id: 5,
      label: 'Settings',
      shortLabel: 'More',
      subtitle: 'Module and plan catalogs',
      icon: Icons.settings_rounded,
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

  String get _selectedSubtitle {
    for (final item in _navItems) {
      if (item.id == _selectedId) return item.subtitle;
    }
    return '';
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
          shape: adminDialogShape(),
          insetPadding: EdgeInsets.symmetric(
            horizontal: compact ? 16 : 40,
            vertical: compact ? 24 : 40,
          ),
          title: const Tr('Create Organization'),
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
                        child: Tr('university'),
                      ),
                      DropdownMenuItem(
                        value: 'enterprise',
                        child: Tr('enterprise (company)'),
                      ),
                      DropdownMenuItem(
                        value: 'starter',
                        child: Tr('starter'),
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
                    title: const Tr('core module'),
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                  ),
                  CheckboxListTile(
                    value: hasFyp,
                    onChanged: (v) => setLocal(() => hasFyp = v ?? true),
                    title: const Tr('fyp module'),
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                  ),
                  const SizedBox(height: 12),
                  Tr('First Admin Account',
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
                    title: const Tr('Auto-generate password'),
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
              child: const Tr('Cancel'),
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
          shape: adminDialogShape(),
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
        shape: adminDialogShape(),
        title: const Tr('Organization ready'),
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
            child: const Tr('Copy all'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Tr('Done'),
          ),
        ],
      ),
    );
  }

  Widget _credRow(String label, String value, {bool copyable = false}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.04),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white.withOpacity(0.07)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
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
      ),
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
          shape: adminDialogShape(),
          title: Text('Change plan — ${org['code']}'),
          content: DropdownButtonFormField<String>(
            value: plan,
            decoration: const InputDecoration(labelText: 'Plan'),
            items: const [
              DropdownMenuItem(value: 'university', child: Tr('university')),
              DropdownMenuItem(value: 'enterprise', child: Tr('enterprise (company)')),
              DropdownMenuItem(value: 'starter', child: Tr('starter')),
            ],
            onChanged: (v) => setLocal(() => plan = v ?? 'university'),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Tr('Cancel')),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Tr('Save'),
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
          shape: adminDialogShape(),
          title: Text('Edit modules — ${org['code']}'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CheckboxListTile(
                value: hasCore,
                onChanged: (v) => setLocal(() => hasCore = v ?? true),
                title: const Tr('core module'),
                dense: true,
                contentPadding: EdgeInsets.zero,
              ),
              CheckboxListTile(
                value: hasFyp,
                onChanged: (v) => setLocal(() => hasFyp = v ?? false),
                title: const Tr('fyp module'),
                dense: true,
                contentPadding: EdgeInsets.zero,
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Tr('Cancel')),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Tr('Save'),
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
    final orgName = org['name']?.toString() ?? 'Organization';
    final initial = orgName.trim().isEmpty ? '?' : orgName.trim()[0].toUpperCase();
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: AdminColors.surface,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(22, 14, 22, 28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 42,
                    height: 4,
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.18),
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                Row(
                  children: [
                    Container(
                      width: 52,
                      height: 52,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(16),
                        gradient: const LinearGradient(
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                          colors: [AdminColors.primary, AdminColors.accent],
                        ),
                      ),
                      child: Text(
                        initial,
                        style: const TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w800,
                          color: Colors.white,
                        ),
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            orgName,
                            style: const TextStyle(
                              fontSize: 19,
                              fontWeight: FontWeight.w800,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Wrap(
                            spacing: 8,
                            runSpacing: 6,
                            children: [
                              _SaPill('${org['code']}'),
                              _SaPill.accent('${org['plan']}'),
                              ..._modulesForOrg(org).map((m) => _SaPill(m)),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                Tr('Distribute org code + admin credentials only. API keys stay server-side.',
                  style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 12, height: 1.35),
                ),
                if (stats != null) ...[
                  const SizedBox(height: 18),
                  Row(
                    children: [
                      Expanded(
                        child: _SaMiniStat(
                          label: 'Users',
                          value: '${(stats['stats'] as Map?)?['users'] ?? 0}',
                          icon: Icons.people_alt_rounded,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _SaMiniStat(
                          label: 'Docs',
                          value: '${(stats['stats'] as Map?)?['documents'] ?? 0}',
                          icon: Icons.description_rounded,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _SaMiniStat(
                          label: 'Groups',
                          value: '${(stats['stats'] as Map?)?['groups'] ?? 0}',
                          icon: Icons.groups_rounded,
                        ),
                      ),
                    ],
                  ),
                ],
                const SizedBox(height: 22),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    style: _saOutlinedStyle(AdminColors.primary),
                    onPressed: () async {
                      final changed = await _changeOrgPlan(org);
                      if (changed == true && ctx.mounted) Navigator.pop(ctx);
                    },
                    icon: const Icon(Icons.swap_horiz_rounded, size: 18),
                    label: const Tr('Change plan'),
                  ),
                ),
                const SizedBox(height: 10),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    style: _saOutlinedStyle(AdminColors.primary),
                    onPressed: () async {
                      final changed = await _changeOrgModules(org);
                      if (changed == true && ctx.mounted) Navigator.pop(ctx);
                    },
                    icon: const Icon(Icons.extension_rounded, size: 18),
                    label: const Tr('Edit modules'),
                  ),
                ),
                const SizedBox(height: 10),
                if (id == 1)
                  Tr('Default organization (id=1) cannot be deleted.',
                    style: TextStyle(color: Colors.white.withOpacity(0.45), fontSize: 12),
                  )
                else
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      style: _saOutlinedStyle(AdminColors.danger),
                      onPressed: () async {
                        final confirmed = await showDialog<bool>(
                          context: ctx,
                          builder: (dCtx) => AlertDialog(
                            backgroundColor: AdminColors.surface,
                            shape: adminDialogShape(),
                            title: const Tr('Delete organization?'),
                            content: Text(
                              'Permanently delete "${org['name']}" (${org['code']})?\n'
                              'This cannot be undone.',
                              style: TextStyle(color: Colors.white.withOpacity(0.8), height: 1.4),
                            ),
                            actions: [
                              TextButton(
                                onPressed: () => Navigator.pop(dCtx, false),
                                child: const Tr('Cancel'),
                              ),
                              ElevatedButton(
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: AdminColors.danger,
                                  foregroundColor: Colors.white,
                                ),
                                onPressed: () => Navigator.pop(dCtx, true),
                                child: const Tr('Delete'),
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
                      label: const Tr('Delete organization'),
                    ),
                  ),
              ],
            ),
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
          title: const Tr('Super Admin'),
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

  Color get _sidebarColor =>
      Color.alphaBlend(Colors.black.withOpacity(0.16), AdminColors.surface);

  Widget _buildBrand() {
    return Row(
      children: [
        Container(
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [AdminColors.primary, AdminColors.accent],
            ),
            boxShadow: [
              BoxShadow(
                color: AdminColors.primary.withOpacity(0.4),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: const Icon(Icons.shield_rounded, size: 20, color: Colors.white),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Tr('Super Admin',
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                  fontSize: 15,
                  letterSpacing: 0.2,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                'Platform console',
                style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.45)),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildDrawer() {
    return Drawer(
      backgroundColor: _sidebarColor,
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 22, 20, 18),
              child: _buildBrand(),
            ),
            Divider(height: 1, color: Colors.white.withOpacity(0.07)),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 12),
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
                label: const Tr('Back to login'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white70,
                  side: BorderSide(color: Colors.white.withOpacity(0.14)),
                  minimumSize: const Size(double.infinity, 46),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSidebar() {
    final suspended = _orgs.where((o) => o['is_active'] != true).length;
    final healthy = _error == null;
    final footColor = !healthy
        ? AdminColors.danger
        : (suspended > 0 ? AdminColors.warning : AdminColors.success);
    final footText = !healthy
        ? 'Connection issue'
        : (suspended > 0 ? '$suspended org(s) suspended' : 'All orgs active');

    return Container(
      width: 244,
      padding: const EdgeInsets.symmetric(vertical: 22, horizontal: 14),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            _sidebarColor,
            Color.alphaBlend(Colors.black.withOpacity(0.12), _sidebarColor),
          ],
        ),
        border: Border(right: BorderSide(color: Colors.white.withOpacity(0.07))),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 6),
            child: _buildBrand(),
          ),
          const SizedBox(height: 26),
          Padding(
            padding: const EdgeInsets.fromLTRB(10, 0, 10, 8),
            child: Text(
              'PLATFORM',
              style: TextStyle(
                fontSize: 10.5,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.3,
                color: Colors.white.withOpacity(0.35),
              ),
            ),
          ),
          ..._navItems.map(_buildNavItem),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
            decoration: BoxDecoration(
              color: footColor.withOpacity(0.08),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: footColor.withOpacity(0.25)),
            ),
            child: Row(
              children: [
                Container(
                  width: 7,
                  height: 7,
                  decoration: BoxDecoration(
                    color: footColor,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: footColor.withOpacity(0.6),
                        blurRadius: 6,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: Text(
                    footText,
                    style: TextStyle(
                      fontSize: 11.5,
                      fontWeight: FontWeight.w600,
                      color: Colors.white.withOpacity(0.65),
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
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
      padding: const EdgeInsets.only(bottom: 4),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: () => _selectNav(item, closeDrawer: closeDrawer),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
            decoration: BoxDecoration(
              gradient: isSelected
                  ? LinearGradient(
                      colors: [
                        AdminColors.primary.withOpacity(0.22),
                        AdminColors.primary.withOpacity(0.06),
                      ],
                    )
                  : null,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: isSelected
                    ? AdminColors.primary.withOpacity(0.4)
                    : Colors.transparent,
              ),
            ),
            child: Row(
              children: [
                Container(
                  width: 30,
                  height: 30,
                  decoration: BoxDecoration(
                    color: isSelected
                        ? AdminColors.primary.withOpacity(0.18)
                        : Colors.white.withOpacity(0.04),
                    borderRadius: BorderRadius.circular(9),
                  ),
                  child: Icon(
                    item.icon,
                    size: 17,
                    color: isSelected
                        ? AdminColors.primary
                        : Colors.white.withOpacity(0.55),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    item.label,
                    style: TextStyle(
                      fontSize: 13.5,
                      fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                      color: isSelected
                          ? Colors.white
                          : Colors.white.withOpacity(0.65),
                    ),
                  ),
                ),
                AnimatedContainer(
                  duration: const Duration(milliseconds: 180),
                  width: 4,
                  height: isSelected ? 16 : 0,
                  decoration: BoxDecoration(
                    color: AdminColors.primary,
                    borderRadius: BorderRadius.circular(4),
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

    Widget navButton({
      required IconData icon,
      required String label,
      required bool selected,
      required VoidCallback onTap,
    }) {
      final color = selected ? AdminColors.primary : Colors.white.withOpacity(0.45);
      return InkWell(
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              width: 46,
              height: 28,
              decoration: BoxDecoration(
                color: selected
                    ? AdminColors.primary.withOpacity(0.18)
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(999),
              ),
              child: Icon(icon, size: 21, color: color),
            ),
            const SizedBox(height: 3),
            Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 10,
                fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                color: color,
              ),
            ),
          ],
        ),
      );
    }

    return Container(
      decoration: BoxDecoration(
        color: _sidebarColor,
        border: Border(top: BorderSide(color: Colors.white.withOpacity(0.08))),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.35),
            blurRadius: 20,
            offset: const Offset(0, -6),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 66,
          child: Row(
            children: [
              for (final item in items)
                Expanded(
                  child: navButton(
                    icon: item.icon,
                    label: item.shortLabel,
                    selected: item.id == _selectedId,
                    onTap: () => _selectNav(item),
                  ),
                ),
              Expanded(
                child: navButton(
                  icon: Icons.menu_rounded,
                  label: 'Menu',
                  selected: showMoreSelected,
                  onTap: () => _scaffoldKey.currentState?.openDrawer(),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _topIconButton({
    required IconData icon,
    required String tooltip,
    required VoidCallback? onPressed,
  }) {
    return Tooltip(
      message: tooltip,
      child: InkWell(
        borderRadius: BorderRadius.circular(11),
        onTap: onPressed,
        child: Container(
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.05),
            borderRadius: BorderRadius.circular(11),
            border: Border.all(color: Colors.white.withOpacity(0.09)),
          ),
          child: Icon(
            icon,
            size: 18,
            color: Colors.white.withOpacity(onPressed == null ? 0.25 : 0.7),
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
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Color.alphaBlend(Colors.white.withOpacity(0.02), AdminColors.surface),
            AdminColors.surface,
          ],
        ),
        border: Border(bottom: BorderSide(color: Colors.white.withOpacity(0.07))),
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
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  _selectedLabel,
                  style: TextStyle(
                    fontSize: compact ? 17 : 22,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                if (!compact) ...[
                  const SizedBox(height: 2),
                  Text(
                    _selectedSubtitle,
                    style: TextStyle(
                      fontSize: 12.5,
                      color: Colors.white.withOpacity(0.5),
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ],
            ),
          ),
          if (_selectedId == 1 && !compact) ...[
            SizedBox(
              width: 240,
              height: 40,
              child: TextField(
                style: const TextStyle(color: Colors.white, fontSize: 13),
                cursorColor: AdminColors.primary,
                onChanged: (v) => setState(() => _orgSearch = v),
                decoration: InputDecoration(
                  hintText: 'Search organizations',
                  hintStyle: TextStyle(
                    color: Colors.white.withOpacity(0.35),
                    fontSize: 13,
                  ),
                  prefixIcon: Icon(
                    Icons.search_rounded,
                    size: 18,
                    color: Colors.white.withOpacity(0.4),
                  ),
                  filled: true,
                  fillColor: Colors.white.withOpacity(0.05),
                  contentPadding: const EdgeInsets.symmetric(vertical: 0),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: Colors.white.withOpacity(0.09)),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(
                      color: AdminColors.primary.withOpacity(0.8),
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 10),
          ],
          if (_selectedId == 1 && compact)
            _topIconButton(
              icon: Icons.search_rounded,
              tooltip: 'Search',
              onPressed: _showMobileSearchSheet,
            ),
          const SizedBox(width: 8),
          _topIconButton(
            icon: Icons.refresh_rounded,
            tooltip: 'Refresh',
            onPressed: _loading ? null : _refresh,
          ),
          if (_selectedId == 1 && !compact) ...[
            const SizedBox(width: 10),
            ElevatedButton.icon(
              onPressed: _showCreateDialog,
              icon: const Icon(Icons.add_rounded, size: 18),
              label: const Tr('Add Organization'),
              style: ElevatedButton.styleFrom(
                elevation: 0,
                backgroundColor: AdminColors.primary,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                padding: const EdgeInsets.symmetric(
                  horizontal: 18,
                  vertical: 14,
                ),
                textStyle: const TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                ),
              ),
            ),
          ],
          const SizedBox(width: 8),
          _topIconButton(
            icon: Icons.arrow_back_rounded,
            tooltip: 'Back',
            onPressed: () => Navigator.of(context).maybePop(),
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
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
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
                Icons.search_rounded,
                color: Colors.white.withOpacity(0.4),
              ),
              filled: true,
              fillColor: Colors.white.withOpacity(0.05),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
                borderSide: BorderSide(color: Colors.white.withOpacity(0.09)),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
                borderSide: BorderSide(
                  color: AdminColors.primary.withOpacity(0.8),
                ),
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
        return _buildBilling();
      case 4:
        return _buildActivity();
      case 5:
        return _buildSettings();
      default:
        return const SizedBox();
    }
  }

  /// Shared loading / error / retry wrapper for screens driven by `_platformStats`.
  Widget? _statsGuard() {
    if (_platformStats == null) {
      if (_loading) {
        return const Center(child: CircularProgressIndicator(color: AdminColors.primary));
      }
      return AdminErrorView(
        message: _error ?? 'Platform stats unavailable.',
        onRetry: _refresh,
      );
    }
    return null;
  }

  // ---------------------------------------------------------------------------
  // Overview
  // ---------------------------------------------------------------------------

  Widget _buildOverview() {
    final guard = _statsGuard();
    if (guard != null) return guard;
    final stats = _platformStats!;

    final totalOrgs = _saInt(stats['total_orgs']);
    final activeOrgs = _saInt(stats['active_orgs']);
    final suspended = _saInt(stats['suspended_orgs']);
    final totalDocs = _saInt(stats['total_documents']);
    final totalUsers = _saInt(stats['total_users']);
    final totalAdmins = _saInt(stats['total_admins']);
    final revenue = _saInt(stats['revenue_estimate_usd']);

    final growth = _saMap(stats['growth']);
    final growthCounts = ((growth['counts'] as List?) ?? const []).map(_saInt).toList();
    final growthLabels = ((growth['labels'] as List?) ?? const []).map((e) => '$e').toList();
    final newCounts = ((growth['new_counts'] as List?) ?? const []).map(_saInt).toList();
    final newThisMonth = newCounts.isEmpty ? 0 : newCounts.last;

    final activity = _saList(stats['activity']);
    final byPlan = _saList(_saMap(stats['billing'])['by_plan']);
    final topOrgs = _saList(stats['top_orgs']).take(5).toList();

    return RefreshIndicator(
      onRefresh: _refresh,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            LayoutBuilder(
              builder: (context, c) {
                const gap = 14.0;
                final cols = c.maxWidth >= 1000 ? 4 : 2;
                final w = (c.maxWidth - gap * (cols - 1)) / cols;
                final cards = <Widget>[
                  _SaCompactStat(
                    icon: Icons.apartment_rounded,
                    label: 'Organizations',
                    value: '$totalOrgs',
                    sub: newThisMonth > 0
                        ? '+$newThisMonth this month'
                        : '$activeOrgs active',
                    accent: AdminColors.primary,
                  ),
                  _SaCompactStat(
                    icon: Icons.check_circle_rounded,
                    label: 'Active',
                    value: '$activeOrgs',
                    sub: suspended > 0 ? '$suspended suspended' : 'none suspended',
                    accent: AdminColors.success,
                  ),
                  _SaCompactStat(
                    icon: Icons.people_alt_rounded,
                    label: 'Users',
                    value: '$totalUsers',
                    sub: '$totalAdmins org admins',
                    accent: AdminColors.accent,
                  ),
                  _SaCompactStat(
                    icon: Icons.description_rounded,
                    label: 'Documents',
                    value: '$totalDocs',
                    sub: 'est. ${_saMoney(revenue)}/mo recurring',
                    accent: AdminColors.warning,
                  ),
                ];
                return Wrap(
                  spacing: gap,
                  runSpacing: gap,
                  children: [for (final card in cards) SizedBox(width: w, child: card)],
                );
              },
            ),
            const SizedBox(height: 14),
            LayoutBuilder(
              builder: (context, constraints) {
                final stacked = constraints.maxWidth < 900;
                final growthPanel = _saPanel(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _saTitle(
                        'Organization growth',
                        icon: Icons.show_chart_rounded,
                        trailing: const _SaLiveBadge(label: 'LAST 6 MONTHS'),
                      ),
                      const SizedBox(height: 18),
                      SuperAdminGrowthChart(
                        counts: growthCounts,
                        labels: growthLabels,
                        newCounts: newCounts,
                      ),
                    ],
                  ),
                );

                final activityPanel = _saPanel(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _saTitle(
                        'Recent activity',
                        icon: Icons.history_rounded,
                        trailing: InkWell(
                          borderRadius: BorderRadius.circular(8),
                          onTap: () => setState(() => _selectedId = 4),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            child: Text(
                              'View all',
                              style: TextStyle(
                                fontSize: 11.5,
                                fontWeight: FontWeight.w700,
                                color: AdminColors.primary.withOpacity(0.95),
                              ),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                      if (activity.isEmpty)
                        Text(
                          'No activity recorded yet.',
                          style: TextStyle(
                            fontSize: 12.5,
                            color: Colors.white.withOpacity(0.4),
                          ),
                        )
                      else
                        ...activity.take(5).map((a) {
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 14),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Container(
                                  margin: const EdgeInsets.only(top: 6),
                                  width: 7,
                                  height: 7,
                                  decoration: BoxDecoration(
                                    color: _activityColor('${a['kind']}'),
                                    shape: BoxShape.circle,
                                    boxShadow: [
                                      BoxShadow(
                                        color: _activityColor('${a['kind']}').withOpacity(0.5),
                                        blurRadius: 6,
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        '${a['text']}',
                                        style: const TextStyle(
                                          fontSize: 12.5,
                                          color: Colors.white,
                                          height: 1.4,
                                        ),
                                      ),
                                      const SizedBox(height: 2),
                                      Text(
                                        _saFormatTime(a['created_at']),
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
                  return Column(
                    children: [growthPanel, const SizedBox(height: 14), activityPanel],
                  );
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(flex: 2, child: growthPanel),
                    const SizedBox(width: 14),
                    Expanded(child: activityPanel),
                  ],
                );
              },
            ),
            const SizedBox(height: 14),
            LayoutBuilder(
              builder: (context, constraints) {
                final stacked = constraints.maxWidth < 900;
                final maxPlanOrgs = byPlan.fold<int>(
                  1,
                  (m, p) => _saInt(p['org_count']) > m ? _saInt(p['org_count']) : m,
                );
                final planPanel = _saPanel(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _saTitle('Plan distribution', icon: Icons.pie_chart_rounded),
                      const SizedBox(height: 16),
                      if (byPlan.isEmpty)
                        Text(
                          'No plans yet.',
                          style: TextStyle(fontSize: 12.5, color: Colors.white.withOpacity(0.4)),
                        )
                      else
                        ...byPlan.map((p) {
                          final n = _saInt(p['org_count']);
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 14),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        '${p['label']}',
                                        style: const TextStyle(
                                          fontSize: 12.5,
                                          fontWeight: FontWeight.w600,
                                          color: Colors.white,
                                        ),
                                      ),
                                    ),
                                    Text(
                                      '$n org${n == 1 ? '' : 's'} · ${_saMoney(_saInt(p['monthly_usd']))}/mo',
                                      style: TextStyle(
                                        fontSize: 11.5,
                                        color: Colors.white.withOpacity(0.5),
                                        fontFamily: 'monospace',
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 7),
                                _SaProgressBar(value: n / maxPlanOrgs),
                              ],
                            ),
                          );
                        }),
                    ],
                  ),
                );

                final topPanel = _saPanel(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _saTitle('Top organizations by documents', icon: Icons.leaderboard_rounded),
                      const SizedBox(height: 16),
                      if (topOrgs.isEmpty)
                        Text(
                          'No organizations yet.',
                          style: TextStyle(fontSize: 12.5, color: Colors.white.withOpacity(0.4)),
                        )
                      else
                        ...topOrgs.map((o) {
                          final used = _saInt(o['documents_used']);
                          final limit = _saInt(o['documents_limit']);
                          final pct = limit <= 0 ? 0.0 : (used / limit).clamp(0.0, 1.0);
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 14),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        '${o['name']}',
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(
                                          fontSize: 12.5,
                                          fontWeight: FontWeight.w600,
                                          color: Colors.white,
                                        ),
                                      ),
                                    ),
                                    Text(
                                      limit >= 999999 ? '$used docs' : '$used / $limit',
                                      style: TextStyle(
                                        fontSize: 11.5,
                                        color: Colors.white.withOpacity(0.5),
                                        fontFamily: 'monospace',
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 7),
                                _SaProgressBar(
                                  value: limit >= 999999
                                      ? (totalDocs <= 0 ? 0 : used / totalDocs)
                                      : pct,
                                  warn: limit < 999999 && pct > 0.8,
                                ),
                              ],
                            ),
                          );
                        }),
                    ],
                  ),
                );

                if (stacked) {
                  return Column(children: [planPanel, const SizedBox(height: 14), topPanel]);
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: planPanel),
                    const SizedBox(width: 14),
                    Expanded(child: topPanel),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Admins
  // ---------------------------------------------------------------------------

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

    Widget avatar(String name, {double size = 36}) {
      final initial = name.trim().isEmpty ? '?' : name.trim()[0].toUpperCase();
      return Container(
        width: size,
        height: size,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(size * 0.32),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              AdminColors.primary.withOpacity(0.35),
              AdminColors.accent.withOpacity(0.25),
            ],
          ),
          border: Border.all(color: AdminColors.primary.withOpacity(0.3)),
        ),
        child: Text(
          initial,
          style: TextStyle(
            fontSize: size * 0.42,
            fontWeight: FontWeight.w800,
            color: Colors.white,
          ),
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
                          avatar(name),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              name.isEmpty ? '—' : name,
                              style: const TextStyle(
                                fontSize: 14.5,
                                fontWeight: FontWeight.w700,
                                color: Colors.white,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          _SaPill.accent(role),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        email.isEmpty ? '—' : email,
                        style: TextStyle(
                          fontSize: 12.5,
                          color: Colors.white.withOpacity(0.6),
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
                          avatar(name, size: 30),
                          const SizedBox(width: 10),
                          Flexible(
                            child: Text(
                              name.isEmpty ? '—' : name,
                              style: const TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
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
                          color: Colors.white.withOpacity(0.6),
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                      Text(
                        orgLabel.isEmpty ? '—' : orgLabel,
                        style: TextStyle(
                          fontSize: 12.5,
                          color: Colors.white.withOpacity(0.6),
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
      child: SingleChildScrollView(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 440),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: _saPanel(
              padding: const EdgeInsets.fromLTRB(28, 32, 28, 28),
              accent: AdminColors.primary,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 68,
                    height: 68,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(22),
                      gradient: const LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [AdminColors.primary, AdminColors.accent],
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: AdminColors.primary.withOpacity(0.45),
                          blurRadius: 24,
                          offset: const Offset(0, 10),
                        ),
                      ],
                    ),
                    child: const Icon(
                      Icons.admin_panel_settings_rounded,
                      size: 34,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 22),
                  const Tr('Enter Super Admin key',
                    style: TextStyle(
                      fontSize: 21,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Tr('Must match backend SUPER_ADMIN_KEY',
                    style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 13),
                  ),
                  const SizedBox(height: 24),
                  TextField(
                    controller: _keyController,
                    obscureText: true,
                    onSubmitted: (_) {
                      if (!_loading) _unlock();
                    },
                    decoration: const InputDecoration(
                      labelText: 'X-Super-Admin-Key',
                      prefixIcon: Icon(Icons.key_rounded),
                    ),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 14),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AdminColors.danger.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: AdminColors.danger.withOpacity(0.35)),
                      ),
                      child: Text(
                        _error!,
                        style: const TextStyle(color: AdminColors.danger, fontSize: 12),
                      ),
                    ),
                  ],
                  const SizedBox(height: 22),
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton.icon(
                      onPressed: _loading ? null : _unlock,
                      icon: Icon(
                        _loading ? Icons.hourglass_top_rounded : Icons.lock_open_rounded,
                        size: 18,
                      ),
                      label: Text(_loading ? 'Checking…' : 'Unlock'),
                      style: ElevatedButton.styleFrom(
                        elevation: 0,
                        backgroundColor: AdminColors.primary,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                        textStyle: const TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 14,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Organizations
  // ---------------------------------------------------------------------------

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
            LayoutBuilder(
              builder: (context, c) {
                const gap = 12.0;
                final cols = c.maxWidth >= 640 ? 3 : 1;
                final w = (c.maxWidth - gap * (cols - 1)) / cols;
                Widget chip(IconData icon, String label, String value, Color color) {
                  return SizedBox(
                    width: w,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.035),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: Colors.white.withOpacity(0.07)),
                      ),
                      child: Row(
                        children: [
                          Container(
                            width: 36,
                            height: 36,
                            decoration: BoxDecoration(
                              color: color.withOpacity(0.14),
                              borderRadius: BorderRadius.circular(11),
                            ),
                            child: Icon(icon, size: 18, color: color),
                          ),
                          const SizedBox(width: 12),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                value,
                                style: const TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.w800,
                                  color: Colors.white,
                                  height: 1.1,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                label,
                                style: TextStyle(
                                  fontSize: 11.5,
                                  color: Colors.white.withOpacity(0.5),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  );
                }

                return Wrap(
                  spacing: gap,
                  runSpacing: gap,
                  children: [
                    chip(Icons.apartment_rounded, 'Organizations',
                        '${stats['total_orgs']}', AdminColors.primary),
                    chip(Icons.check_circle_rounded, 'Active',
                        '${stats['active_orgs']}', AdminColors.success),
                    chip(Icons.description_rounded, 'Documents',
                        '${stats['total_documents']}', AdminColors.warning),
                  ],
                );
              },
            ),
            const SizedBox(height: 16),
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

              Future<void> toggle() async {
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
              }

              final statusColor = active ? AdminColors.success : Colors.white54;
              final statusPill = Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.13),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: statusColor.withOpacity(0.35)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 6,
                      height: 6,
                      decoration: BoxDecoration(
                        color: statusColor,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      active ? 'Active' : 'Suspended',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: statusColor,
                      ),
                    ),
                  ],
                ),
              );

              return Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _saPanel(
                  padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
                  accent: active ? AdminColors.primary : null,
                  child: LayoutBuilder(
                    builder: (context, constraints) {
                      final narrow = constraints.maxWidth < 560;
                      final leading = Row(
                        children: [
                          _SaQuotaRing(used: used, limit: limit),
                          const SizedBox(width: 16),
                          Expanded(
                            child: InkWell(
                              borderRadius: BorderRadius.circular(10),
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
                                            fontSize: 15,
                                            fontWeight: FontWeight.w700,
                                            color: Colors.white,
                                          ),
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ),
                                      const SizedBox(width: 6),
                                      Icon(
                                        Icons.chevron_right_rounded,
                                        size: 18,
                                        color: Colors.white.withOpacity(0.35),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 7),
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

                      final docsText = Text(
                        'Docs $used/$limit',
                        style: TextStyle(
                          fontSize: 11.5,
                          color: Colors.white.withOpacity(0.45),
                          fontFamily: 'monospace',
                        ),
                      );

                      final switchWidget = Switch(
                        value: active,
                        activeColor: AdminColors.primary,
                        onChanged: (_) => toggle(),
                      );

                      if (narrow) {
                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            leading,
                            const SizedBox(height: 12),
                            Row(
                              children: [
                                statusPill,
                                const SizedBox(width: 10),
                                docsText,
                                const Spacer(),
                                switchWidget,
                              ],
                            ),
                          ],
                        );
                      }

                      return Row(
                        children: [
                          Expanded(child: leading),
                          const SizedBox(width: 12),
                          docsText,
                          const SizedBox(width: 14),
                          statusPill,
                          const SizedBox(width: 8),
                          switchWidget,
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
  // Billing (real data: GET /stats → billing)
  // ---------------------------------------------------------------------------

  Widget _buildBilling() {
    final guard = _statsGuard();
    if (guard != null) return guard;
    final billing = _saMap(_platformStats!['billing']);
    final byPlan = _saList(billing['by_plan']);
    final rows = _saList(billing['rows']);
    final total = _saInt(billing['total_monthly_usd']);
    final compact = isCompact(context);

    return RefreshIndicator(
      onRefresh: _refresh,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                children: [
                  Icon(Icons.info_outline_rounded,
                      size: 14, color: Colors.white.withOpacity(0.4)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Estimated from plan list prices. Suspended organizations are excluded.',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.white.withOpacity(0.45),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            LayoutBuilder(
              builder: (context, c) {
                const gap = 14.0;
                final cols = c.maxWidth >= 900 ? 4 : 2;
                final w = (c.maxWidth - gap * (cols - 1)) / cols;
                final cards = <Widget>[
                  for (final p in byPlan)
                    SizedBox(
                      width: w,
                      child: _saPanel(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    '${p['label']}',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.white.withOpacity(0.55),
                                    ),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                Text(
                                  '${_saMoney(_saInt(p['price_usd']))}/org',
                                  style: TextStyle(
                                    fontSize: 10.5,
                                    color: Colors.white.withOpacity(0.35),
                                    fontFamily: 'monospace',
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 10),
                            Text(
                              '${_saMoney(_saInt(p['monthly_usd']))}/mo',
                              style: const TextStyle(
                                fontSize: 24,
                                fontWeight: FontWeight.w800,
                                color: Colors.white,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${p['active_count']} active · ${p['org_count']} total',
                              style: TextStyle(
                                fontSize: 11.5,
                                color: Colors.white.withOpacity(0.4),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  SizedBox(
                    width: w,
                    child: Container(
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                          colors: [
                            AdminColors.primary.withOpacity(0.28),
                            AdminColors.accent.withOpacity(0.14),
                          ],
                        ),
                        border: Border.all(color: AdminColors.primary.withOpacity(0.7)),
                        borderRadius: BorderRadius.circular(18),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Tr('Platform total',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.white.withOpacity(0.75),
                            ),
                          ),
                          const SizedBox(height: 10),
                          Text(
                            '${_saMoney(total)}/mo',
                            style: const TextStyle(
                              fontSize: 24,
                              fontWeight: FontWeight.w800,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'est. ${_saMoney(total * 12)}/year',
                            style: TextStyle(
                              fontSize: 11.5,
                              color: Colors.white.withOpacity(0.6),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ];
                return Wrap(spacing: gap, runSpacing: gap, children: cards);
              },
            ),
            const SizedBox(height: 14),
            if (rows.isEmpty)
              _saPanel(
                child: Text(
                  'No organizations yet.',
                  style: TextStyle(fontSize: 12.5, color: Colors.white.withOpacity(0.4)),
                ),
              )
            else if (compact)
              ...rows.map((r) {
                final active = r['is_active'] == true;
                final mods = ((r['modules'] as List?) ?? const []).map((e) => '$e').toList();
                return Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _saPanel(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                '${r['name']}',
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                ),
                              ),
                            ),
                            Text(
                              active ? '${_saMoney(_saInt(r['monthly_usd']))}/mo' : 'Suspended',
                              style: TextStyle(
                                fontSize: 13,
                                fontFamily: 'monospace',
                                color: active ? Colors.white : Colors.white54,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 6,
                          runSpacing: 6,
                          children: [
                            _SaPill.accent('${r['plan_label']}'),
                            ...mods.map((m) => _SaPill(m)),
                          ],
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
                    _saRowHeader(const ['ORGANIZATION', 'PLAN', 'MODULES', 'STATUS', 'MONTHLY']),
                    ...rows.map((r) {
                      final active = r['is_active'] == true;
                      final mods = ((r['modules'] as List?) ?? const []).map((e) => '$e').toList();
                      return _saDataRow([
                        Text(
                          '${r['name']}',
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: _SaPill.accent('${r['plan_label']}'),
                        ),
                        Wrap(
                          spacing: 5,
                          runSpacing: 4,
                          children: mods.map((m) => _SaPill(m)).toList(),
                        ),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: _SaStatusDot(active: active),
                        ),
                        Text(
                          active ? _saMoney(_saInt(r['monthly_usd'])) : '—',
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
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Activity (real data: GET /stats → activity, backed by super_admin_activity)
  // ---------------------------------------------------------------------------

  static const _activityIcons = <String, IconData>{
    'org': Icons.apartment_rounded,
    'toggle': Icons.power_settings_new_rounded,
    'admin': Icons.vpn_key_rounded,
    'module': Icons.extension_rounded,
    'plan': Icons.swap_horiz_rounded,
    'key': Icons.key_rounded,
    'delete': Icons.delete_outline_rounded,
  };

  Color _activityColor(String kind) {
    switch (kind) {
      case 'toggle':
        return AdminColors.warning;
      case 'admin':
        return AdminColors.accent;
      case 'module':
        return AdminColors.success;
      case 'plan':
        return const Color(0xFF60A5FA);
      case 'key':
        return const Color(0xFFC084FC);
      case 'delete':
        return AdminColors.danger;
      default:
        return AdminColors.primary;
    }
  }

  Widget _buildActivity() {
    final guard = _statsGuard();
    if (guard != null) return guard;
    final items = _saList(_platformStats!['activity']);

    return RefreshIndicator(
      onRefresh: _refresh,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: _saPanel(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _saTitle(
                'Audit trail',
                icon: Icons.history_rounded,
                trailing: _SaLiveBadge(label: '${items.length} EVENTS'),
              ),
              const SizedBox(height: 8),
              if (items.isEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 24),
                  child: Text(
                    'No activity recorded yet.',
                    style: TextStyle(fontSize: 13, color: Colors.white.withOpacity(0.4)),
                  ),
                ),
              for (var i = 0; i < items.length; i++)
                Container(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  decoration: BoxDecoration(
                    border: i == items.length - 1
                        ? null
                        : Border(
                            bottom: BorderSide(color: Colors.white.withOpacity(0.06)),
                          ),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 36,
                        height: 36,
                        decoration: BoxDecoration(
                          color: _activityColor('${items[i]['kind']}').withOpacity(0.14),
                          borderRadius: BorderRadius.circular(11),
                        ),
                        child: Icon(
                          _activityIcons['${items[i]['kind']}'] ?? Icons.history_rounded,
                          size: 17,
                          color: _activityColor('${items[i]['kind']}'),
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '${items[i]['text']}',
                              style: const TextStyle(
                                fontSize: 13.5,
                                color: Colors.white,
                                height: 1.35,
                              ),
                            ),
                            const SizedBox(height: 3),
                            Text(
                              _saFormatTime(items[i]['created_at']),
                              style: TextStyle(
                                fontSize: 11.5,
                                color: Colors.white.withOpacity(0.4),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Settings (real data: GET /stats → module_catalog / plan_catalog)
  // ---------------------------------------------------------------------------

  Widget _buildSettings() {
    final guard = _statsGuard();
    if (guard != null) return guard;
    final modulesCatalog = _saList(_platformStats!['module_catalog']);
    final plansCatalog = _saList(_platformStats!['plan_catalog']);

    Widget catalogRow({
      required String title,
      required String desc,
      required String price,
      required int orgCount,
    }) {
      return Container(
        margin: const EdgeInsets.only(top: 8),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.03),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.white.withOpacity(0.06)),
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    desc,
                    style: TextStyle(
                      fontSize: 11.5,
                      color: Colors.white.withOpacity(0.4),
                      height: 1.35,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  price,
                  style: TextStyle(
                    fontSize: 12.5,
                    color: Colors.white.withOpacity(0.75),
                    fontFamily: 'monospace',
                  ),
                ),
                const SizedBox(height: 5),
                _SaPill('$orgCount org${orgCount == 1 ? '' : 's'}'),
              ],
            ),
          ],
        ),
      );
    }

    final modulesPanel = _saPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _saTitle('Module catalog', icon: Icons.extension_rounded),
          const SizedBox(height: 10),
          if (modulesCatalog.isEmpty)
            Text('No modules defined.',
                style: TextStyle(fontSize: 12.5, color: Colors.white.withOpacity(0.4))),
          ...modulesCatalog.map((e) => catalogRow(
                title: '${e['label']}',
                desc: '${e['description']}',
                price: '${_saMoney(_saInt(e['price_usd']))}/mo',
                orgCount: _saInt(e['org_count']),
              )),
        ],
      ),
    );

    final plansPanel = _saPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _saTitle('Plans', icon: Icons.workspace_premium_rounded),
          const SizedBox(height: 10),
          if (plansCatalog.isEmpty)
            Text('No plans defined.',
                style: TextStyle(fontSize: 12.5, color: Colors.white.withOpacity(0.4))),
          ...plansCatalog.map((p) => catalogRow(
                title: '${p['label']}',
                desc: '${p['description']}',
                price: '${_saMoney(_saInt(p['price_usd']))}/mo',
                orgCount: _saInt(p['org_count']),
              )),
        ],
      ),
    );

    return RefreshIndicator(
      onRefresh: _refresh,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                children: [
                  Icon(Icons.info_outline_rounded,
                      size: 14, color: Colors.white.withOpacity(0.4)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Catalogs are defined on the server (PLAN_CATALOG / MODULE_CATALOG). '
                      'Plan prices can be overridden with PLAN_PRICE_* environment variables.',
                      style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.45)),
                    ),
                  ),
                ],
              ),
            ),
            LayoutBuilder(
              builder: (context, c) {
                if (c.maxWidth < 760) {
                  return Column(
                    children: [modulesPanel, const SizedBox(height: 14), plansPanel],
                  );
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: modulesPanel),
                    const SizedBox(width: 14),
                    Expanded(child: plansPanel),
                  ],
                );
              },
            ),
          ],
        ),
      ),
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

ButtonStyle _saOutlinedStyle(Color color) => OutlinedButton.styleFrom(
      foregroundColor: color,
      side: BorderSide(color: color.withOpacity(0.55)),
      padding: const EdgeInsets.symmetric(vertical: 14),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5),
    );

Widget _saPanel({required Widget child, EdgeInsets? padding, Color? accent}) {
  final tint = accent ?? AdminColors.primary;
  return Container(
    padding: padding ?? const EdgeInsets.all(20),
    decoration: BoxDecoration(
      borderRadius: BorderRadius.circular(18),
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          AdminColors.card,
          Color.alphaBlend(tint.withOpacity(accent == null ? 0.03 : 0.08), AdminColors.card),
        ],
      ),
      border: Border.all(
        color: accent == null
            ? Colors.white.withOpacity(0.08)
            : accent.withOpacity(0.25),
      ),
      boxShadow: [
        BoxShadow(
          color: Colors.black.withOpacity(0.18),
          blurRadius: 16,
          offset: const Offset(0, 8),
        ),
      ],
    ),
    child: child,
  );
}

Widget _saTitle(String title, {IconData? icon, Widget? trailing}) => Row(
      children: [
        if (icon != null) ...[
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              color: AdminColors.primary.withOpacity(0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, size: 17, color: AdminColors.primary),
          ),
          const SizedBox(width: 12),
        ],
        Expanded(
          child: Text(
            title,
            style: const TextStyle(
              fontSize: 14.5,
              fontWeight: FontWeight.w700,
              color: Colors.white,
            ),
          ),
        ),
        if (trailing != null) trailing,
      ],
    );

Widget _saRowHeader(List<String> cols) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 13),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.03),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(18)),
        border: Border(bottom: BorderSide(color: Colors.white.withOpacity(0.08))),
      ),
      child: Row(
        children: cols
            .map(
              (c) => Expanded(
                child: Text(
                  c,
                  style: TextStyle(
                    fontSize: 10.5,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.1,
                    color: Colors.white.withOpacity(0.4),
                  ),
                ),
              ),
            )
            .toList(),
      ),
    );

Widget _saDataRow(List<Widget> cells) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: Colors.white.withOpacity(0.05))),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: cells.map((c) => Expanded(child: c)).toList(),
      ),
    );

/// Small badge shown on panels that are backed by live server data.
class _SaLiveBadge extends StatelessWidget {
  final String label;
  const _SaLiveBadge({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: AdminColors.success.withOpacity(0.1),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AdminColors.success.withOpacity(0.35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: const BoxDecoration(
              color: AdminColors.success,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 6),
          Text(
            label,
            style: const TextStyle(
              fontSize: 9.5,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.8,
              color: AdminColors.success,
            ),
          ),
        ],
      ),
    );
  }
}

class _SaStatusDot extends StatelessWidget {
  final bool active;
  const _SaStatusDot({required this.active});

  @override
  Widget build(BuildContext context) {
    final color = active ? AdminColors.success : Colors.white54;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 7,
          height: 7,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 7),
        Text(
          active ? 'Active' : 'Suspended',
          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color),
        ),
      ],
    );
  }
}

class _SaProgressBar extends StatelessWidget {
  final double value;
  final bool warn;
  const _SaProgressBar({required this.value, this.warn = false});

  @override
  Widget build(BuildContext context) {
    final v = value.isNaN ? 0.0 : value.clamp(0.0, 1.0);
    final color = warn ? AdminColors.warning : AdminColors.primary;
    return ClipRRect(
      borderRadius: BorderRadius.circular(999),
      child: Stack(
        children: [
          Container(height: 6, color: Colors.white.withOpacity(0.07)),
          FractionallySizedBox(
            widthFactor: v == 0 ? 0.01 : v,
            child: Container(
              height: 6,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [color.withOpacity(0.65), color],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SaPill extends StatelessWidget {
  final String text;
  final Color? bg;
  final Color? fg;
  final Color? bd;

  const _SaPill(this.text, {this.bg, this.fg, this.bd});

  factory _SaPill.accent(String text) => _SaPill(
        text,
        bg: AdminColors.primary.withOpacity(0.16),
        fg: const Color(0xFFC7D2FE),
        bd: AdminColors.primary,
      );

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3.5),
      decoration: BoxDecoration(
        color: bg ?? Colors.white.withOpacity(0.05),
        border: Border.all(
          color: (bd ?? Colors.white).withOpacity(bd == null ? 0.1 : 0.45),
        ),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: fg ?? Colors.white.withOpacity(0.6),
          fontFamily: 'monospace',
        ),
      ),
    );
  }
}

class _SaMiniStat extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;

  const _SaMiniStat({
    required this.label,
    required this.value,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.04),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withOpacity(0.07)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 16, color: AdminColors.primary),
          const SizedBox(height: 10),
          Text(
            value,
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w800,
              color: Colors.white,
              height: 1.0,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: TextStyle(fontSize: 11.5, color: Colors.white.withOpacity(0.5)),
          ),
        ],
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
      accent: accent,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: accent.withOpacity(0.16),
                  borderRadius: BorderRadius.circular(11),
                ),
                child: Icon(icon, size: 18, color: accent),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  label,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w500,
                    color: Colors.white.withOpacity(0.6),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            value,
            style: const TextStyle(
              fontSize: 30,
              fontWeight: FontWeight.w800,
              color: Colors.white,
              height: 1.0,
            ),
          ),
          if (sub != null) ...[
            const SizedBox(height: 6),
            Text(
              sub!,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: 11.5, color: Colors.white.withOpacity(0.4)),
            ),
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

  const _SaQuotaRing({required this.used, required this.limit, this.size = 46});

  @override
  Widget build(BuildContext context) {
    final pct = limit <= 0 ? 0.0 : (used / limit).clamp(0.0, 1.0);
    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          CustomPaint(size: Size(size, size), painter: _SaRingPainter(pct)),
          Text(
            '${(pct * 100).round()}%',
            style: TextStyle(
              fontSize: size * 0.24,
              fontWeight: FontWeight.w800,
              color: Colors.white.withOpacity(0.85),
            ),
          ),
        ],
      ),
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
      ..color = Colors.white.withOpacity(0.08)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 4;
    final fill = Paint()
      ..color = pct > 0.8 ? AdminColors.warning : AdminColors.primary
      ..style = PaintingStyle.stroke
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round;
    canvas.drawCircle(center, radius, track);
    canvas.drawArc(Rect.fromCircle(center: center, radius: radius), -1.5708, 6.2832 * pct, false, fill);
  }

  @override
  bool shouldRepaint(covariant _SaRingPainter old) => old.pct != pct;
}

/// Organization growth chart (cumulative org count per month) driven by the
/// `growth` series returned from `GET /api/super-admin/stats`.
class SuperAdminGrowthChart extends StatelessWidget {
  final List<int> counts;
  final List<String> labels;

  /// Optional: organizations created in each month (shown as "+n" under the bar).
  final List<int> newCounts;

  const SuperAdminGrowthChart({
    super.key,
    required this.counts,
    required this.labels,
    this.newCounts = const [],
  });

  @override
  Widget build(BuildContext context) {
    if (counts.isEmpty || counts.length != labels.length) {
      return SizedBox(
        height: 130,
        child: Center(
          child: Text(
            'Not enough data yet.',
            style: TextStyle(fontSize: 12.5, color: Colors.white.withOpacity(0.4)),
          ),
        ),
      );
    }
    final maxG = counts.reduce((a, b) => a > b ? a : b);
    final denom = maxG <= 0 ? 1 : maxG;
    return SizedBox(
      key: const Key('sa_growth_chart'),
      height: 150,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: List.generate(counts.length, (i) {
          final isLast = i == counts.length - 1;
          final barHeight = (counts[i] / denom) * 78 + 8;
          final added = i < newCounts.length ? newCounts[i] : 0;
          return Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 6),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Text(
                    '${counts[i]}',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: isLast
                          ? Colors.white
                          : Colors.white.withOpacity(0.45),
                    ),
                  ),
                  const SizedBox(height: 5),
                  Container(
                    key: Key('sa_growth_bar_$i'),
                    height: barHeight,
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.bottomCenter,
                        end: Alignment.topCenter,
                        colors: isLast
                            ? [AdminColors.primary.withOpacity(0.6), AdminColors.primary]
                            : [
                                Colors.white.withOpacity(0.05),
                                Colors.white.withOpacity(0.12),
                              ],
                      ),
                      borderRadius: const BorderRadius.vertical(
                        top: Radius.circular(8),
                        bottom: Radius.circular(4),
                      ),
                      boxShadow: isLast
                          ? [
                              BoxShadow(
                                color: AdminColors.primary.withOpacity(0.35),
                                blurRadius: 12,
                              ),
                            ]
                          : null,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    labels[i],
                    style: TextStyle(
                      fontSize: 10.5,
                      color: Colors.white.withOpacity(0.4),
                    ),
                  ),
                  SizedBox(
                    height: 14,
                    child: added > 0
                        ? Text(
                            '+$added',
                            style: const TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w700,
                              color: AdminColors.success,
                            ),
                          )
                        : null,
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