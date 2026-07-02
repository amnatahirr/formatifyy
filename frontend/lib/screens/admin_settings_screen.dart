import 'package:flutter/material.dart';

class AdminSettingsScreen extends StatefulWidget {
  const AdminSettingsScreen({Key? key}) : super(key: key);

  @override
  State<AdminSettingsScreen> createState() => _AdminSettingsScreenState();
}

class _AdminSettingsScreenState extends State<AdminSettingsScreen> {
  bool _emailNotifications = true;
  bool _systemNotifications = true;
  bool _maintenanceMode = false;
  String _apiRateLimit = '10000';

  @override
  Widget build(BuildContext context) {
    return Container(
      color: const Color(0xFF0F1419),
      padding: const EdgeInsets.all(32),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Settings',
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Manage system configuration and preferences',
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.white.withOpacity(0.6),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 32),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    children: [
                      _buildSettingsCard(
                        title: 'General Settings',
                        children: [
                          _buildSettingItem(
                            'System Name',
                            'FORMATIFY Admin Panel',
                          ),
                          _buildSettingItem('Version', '1.0.0'),
                          _buildSettingItem('Environment', 'Production'),
                        ],
                      ),
                      const SizedBox(height: 24),
                      _buildSettingsCard(
                        title: 'Notification Settings',
                        children: [
                          _buildToggleSetting(
                            'Email Notifications',
                            'Receive system emails',
                            _emailNotifications,
                            (value) =>
                                setState(() => _emailNotifications = value),
                          ),
                          const SizedBox(height: 16),
                          _buildToggleSetting(
                            'System Notifications',
                            'In-app notifications',
                            _systemNotifications,
                            (value) =>
                                setState(() => _systemNotifications = value),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 24),
                Expanded(
                  child: Column(
                    children: [
                      _buildSettingsCard(
                        title: 'API Configuration',
                        children: [
                          _buildTextSetting('API Rate Limit', _apiRateLimit),
                          const SizedBox(height: 16),
                          _buildTextSetting('API Timeout', '30 seconds'),
                          const SizedBox(height: 16),
                          _buildTextSetting('Max File Size', '100 MB'),
                        ],
                      ),
                      const SizedBox(height: 24),
                      _buildSettingsCard(
                        title: 'Maintenance',
                        children: [
                          _buildToggleSetting(
                            'Maintenance Mode',
                            'Disable access for users',
                            _maintenanceMode,
                            (value) => setState(() => _maintenanceMode = value),
                          ),
                          const SizedBox(height: 16),
                          ElevatedButton(
                            onPressed: () {},
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF1A1F2E),
                              foregroundColor: Colors.white,
                              side: const BorderSide(color: Color(0xFF2D3748)),
                            ),
                            child: const Text('Clear Cache'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSettingsCard({
    required String title,
    required List<Widget> children,
  }) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F2E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF2D3748)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 16),
          ...children,
        ],
      ),
    );
  }

  Widget _buildSettingItem(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 13,
              color: Colors.white,
              fontWeight: FontWeight.w500,
            ),
          ),
          Text(
            value,
            style: TextStyle(
              fontSize: 13,
              color: Colors.white.withOpacity(0.6),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildToggleSetting(
    String title,
    String subtitle,
    bool value,
    Function(bool) onChanged,
  ) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w500,
                color: Colors.white,
              ),
            ),
            Text(
              subtitle,
              style: TextStyle(
                fontSize: 11,
                color: Colors.white.withOpacity(0.5),
              ),
            ),
          ],
        ),
        Switch(
          value: value,
          activeColor: const Color(0xFF3B82F6),
          onChanged: onChanged,
        ),
      ],
    );
  }

  Widget _buildTextSetting(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: Colors.white70,
          ),
        ),
        const SizedBox(height: 8),
        TextField(
          readOnly: true,
          style: const TextStyle(color: Colors.white),
          decoration: InputDecoration(
            filled: true,
            fillColor: const Color(0xFF0F1419),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(6),
              borderSide: const BorderSide(color: Color(0xFF2D3748)),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(6),
              borderSide: const BorderSide(color: Color(0xFF2D3748)),
            ),
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 12,
              vertical: 10,
            ),
            hintText: value,
            hintStyle: TextStyle(color: Colors.white.withOpacity(0.5)),
          ),
        ),
      ],
    );
  }
}
