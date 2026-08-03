import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../config/dev_user_config.dart';
import '../models/admin_models.dart';
import '../providers/auth_provider.dart';
import '../services/admin_api_service.dart';
import '../widgets/admin/admin_ui.dart';

class AdminSettingsScreen extends StatefulWidget {
  const AdminSettingsScreen({super.key});

  @override
  State<AdminSettingsScreen> createState() => _AdminSettingsScreenState();
}

class _AdminSettingsScreenState extends State<AdminSettingsScreen> {
  final AdminApiService _api = AdminApiService();
  bool _loading = true;
  bool _saving = false;
  String? _error;
  AdminSettingsModel? _settings;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final settings = await _api.fetchSettings(userId);
      if (mounted) setState(() => _settings = settings);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _saveSettings(AdminSettingsModel updated) async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() => _saving = true);
    try {
      final saved = await _api.updateSettings(userId, updated.toJson());
      if (mounted) {
        setState(() => _settings = saved);
        showAdminSnackBar(context, 'Settings saved successfully.');
      }
    } catch (e) {
      if (mounted) showAdminSnackBar(context, e.toString(), isError: true);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AdminPage(
      onRefresh: _loadSettings,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_saving)
            const Padding(
              padding: EdgeInsets.only(bottom: 16),
              child: Align(
                alignment: Alignment.centerRight,
                child: SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
            ),
          if (_loading)
            const AdminLoadingView()
          else if (_error != null)
            AdminErrorView(message: _error!, onRetry: _loadSettings)
          else if (_settings == null)
            const AdminEmptyView(message: 'Settings could not be loaded from the server.')
          else
            LayoutBuilder(
              builder: (context, constraints) {
                final stacked = constraints.maxWidth < 980;
                final left = Column(
                  children: [
                    _settingsCard(
                      title: 'General Settings',
                      children: [
                        _infoRow('System Name', _settings!.systemName),
                        _infoRow('Version', _settings!.version),
                        _infoRow('Environment', _settings!.environment),
                      ],
                    ),
                    const SizedBox(height: 18),
                    _settingsCard(
                      title: 'Notification Settings',
                      children: [
                        _toggleRow(
                          'Email Notifications',
                          'Receive system emails',
                          _settings!.emailNotifications,
                          (value) => _saveSettings(_settings!.copyWith(emailNotifications: value)),
                        ),
                        const SizedBox(height: 14),
                        _toggleRow(
                          'System Notifications',
                          'In-app notifications',
                          _settings!.systemNotifications,
                          (value) => _saveSettings(_settings!.copyWith(systemNotifications: value)),
                        ),
                      ],
                    ),
                  ],
                );
                final right = Column(
                  children: [
                    _settingsCard(
                      title: 'API Configuration',
                      children: [
                        _infoRow('API Rate Limit', '${_settings!.apiRateLimit}'),
                        _infoRow('API Timeout', '${_settings!.apiTimeoutSeconds} seconds'),
                        _infoRow('Max File Size', '${_settings!.maxFileSizeMb} MB'),
                      ],
                    ),
                    const SizedBox(height: 18),
                    _settingsCard(
                      title: 'Maintenance',
                      children: [
                        _toggleRow(
                          'Maintenance Mode',
                          DevUserConfig.hasFypModule
                              ? 'Disable access for students'
                              : 'Disable access for members',
                          _settings!.maintenanceMode,
                          (value) => _saveSettings(_settings!.copyWith(maintenanceMode: value)),
                        ),
                      ],
                    ),
                  ],
                );
                if (stacked) return Column(children: [left, const SizedBox(height: 18), right]);
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: left),
                    const SizedBox(width: 18),
                    Expanded(child: right),
                  ],
                );
              },
            ),
        ],
      ),
    );
  }

  Widget _settingsCard({required String title, required List<Widget> children}) {
    return AdminSectionCard(title: title, child: Column(children: children));
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500)),
          Text(value, style: TextStyle(color: Colors.white.withOpacity(0.65))),
        ],
      ),
    );
  }

  Widget _toggleRow(String title, String subtitle, bool value, ValueChanged<bool> onChanged) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500)),
              Text(subtitle, style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 12)),
            ],
          ),
        ),
        Switch(
          value: value,
          activeColor: AdminColors.primary,
          onChanged: _saving ? null : onChanged,
        ),
      ],
    );
  }
}

extension on AdminSettingsModel {
  AdminSettingsModel copyWith({
    bool? emailNotifications,
    bool? systemNotifications,
    bool? maintenanceMode,
  }) {
    return AdminSettingsModel(
      systemName: systemName,
      version: version,
      environment: environment,
      emailNotifications: emailNotifications ?? this.emailNotifications,
      systemNotifications: systemNotifications ?? this.systemNotifications,
      maintenanceMode: maintenanceMode ?? this.maintenanceMode,
      apiRateLimit: apiRateLimit,
      apiTimeoutSeconds: apiTimeoutSeconds,
      maxFileSizeMb: maxFileSizeMb,
    );
  }
}
