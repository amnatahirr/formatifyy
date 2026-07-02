import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';
import '../providers/qr_service.dart';
import '../widgets/qr_dialog.dart';
class ExportDialog extends StatefulWidget {
  final Function(String format, {bool applyBullets, bool autoDetect}) onExport;
  final Function()? onQRCode;
  final Function()? onScanQRDownload;
  final bool isLoading;

  const ExportDialog({
    Key? key,
    required this.onExport,
    this.onQRCode,
    this.onScanQRDownload,
    this.isLoading = false,
  }) : super(key: key);

  @override
  State<ExportDialog> createState() => _ExportDialogState();
}

class _ExportDialogState extends State<ExportDialog> {
  String _selectedFormat = 'docx';
  bool _applyBulletFormatting = true;
  bool _autoDetectBullets = true;

  final List<Map<String, dynamic>> _exportFormats = [
    {
      'format': 'docx',
      'label': 'Word Document',
      'extension': '.docx',
      'description': 'Microsoft Word format with full formatting',
      'icon': Icons.description,
      'color': Color(0xFF2563EB),
    },
    {
      'format': 'pdf',
      'label': 'PDF Document',
      'extension': '.pdf',
      'description': 'Universal PDF format',
      'icon': Icons.picture_as_pdf,
      'color': Color(0xFFDC2626),
    },
    {
      'format': 'txt',
      'label': 'Plain Text',
      'extension': '.txt',
      'description': 'Simple text file without formatting',
      'icon': Icons.text_fields,
      'color': Color(0xFF64748B),
    },
  ];

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: const Color(0xFF161B22),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      child: Container(
        width: 500,
        padding: const EdgeInsets.all(32),
        decoration: BoxDecoration(
          color: const Color(0xFF161B22),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: Colors.white.withOpacity(0.1),
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Export Document',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Choose your preferred export format',
                      style: TextStyle(
                        fontSize: 13,
                        color: Colors.white.withOpacity(0.6),
                      ),
                    ),
                  ],
                ),
                GestureDetector(
                  onTap: () => Navigator.of(context).pop(),
                  child: Icon(
                    Icons.close,
                    color: Colors.white.withOpacity(0.5),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),
            // Format Options
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _exportFormats.length,
              separatorBuilder: (context, index) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final format = _exportFormats[index];
                final isSelected = _selectedFormat == format['format'];

                return GestureDetector(
                  onTap: () {
                    setState(() {
                      _selectedFormat = format['format'];
                    });
                  },
                  child: Container(
                    decoration: BoxDecoration(
                      color: isSelected
                          ? format['color'].withOpacity(0.15)
                          : const Color(0xFF0D1117),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: isSelected
                            ? format['color']
                            : Colors.white.withOpacity(0.1),
                        width: isSelected ? 2 : 1,
                      ),
                    ),
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: format['color'].withOpacity(0.2),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Icon(
                            format['icon'],
                            color: format['color'],
                            size: 20,
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Text(
                                    format['label'],
                                    style: const TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w600,
                                      color: Colors.white,
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    format['extension'],
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.white.withOpacity(0.5),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 4),
                              Text(
                                format['description'],
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.white.withOpacity(0.6),
                                ),
                              ),
                            ],
                          ),
                        ),
                        if (isSelected)
                          Icon(
                            Icons.check_circle,
                            color: format['color'],
                            size: 20,
                          ),
                      ],
                    ),
                  ),
                );
              },
            ),
            const SizedBox(height: 28),
            // Bullet Formatting Options (DOCX only)
            if (_selectedFormat == 'docx')
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Bullet Formatting',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    decoration: BoxDecoration(
                      color: const Color(0xFF0D1117),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: Colors.white.withOpacity(0.1),
                      ),
                    ),
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      children: [
                        SwitchListTile(
                          dense: true,
                          title: const Text(
                            'Apply Bullet Formatting',
                            style: TextStyle(
                              fontSize: 13,
                              color: Colors.white,
                            ),
                          ),
                          subtitle: Text(
                            'Format lists with bullets from template',
                            style: TextStyle(
                              fontSize: 11,
                              color: Colors.white.withOpacity(0.6),
                            ),
                          ),
                          value: _applyBulletFormatting,
                          onChanged: (value) {
                            setState(() {
                              _applyBulletFormatting = value;
                            });
                          },
                          activeColor: const Color(0xFF10B981),
                        ),
                        if (_applyBulletFormatting) ...[
                          const SizedBox(height: 8),
                          Divider(
                            color: Colors.white.withOpacity(0.1),
                          ),
                          const SizedBox(height: 8),
                          SwitchListTile(
                            dense: true,
                            title: const Text(
                              'Auto-Detect List Content',
                              style: TextStyle(
                                fontSize: 13,
                                color: Colors.white,
                              ),
                            ),
                            subtitle: Text(
                              'Automatically detect and format list items',
                              style: TextStyle(
                                fontSize: 11,
                                color: Colors.white.withOpacity(0.6),
                              ),
                            ),
                            value: _autoDetectBullets,
                            onChanged: (value) {
                              setState(() {
                                _autoDetectBullets = value;
                              });
                            },
                            activeColor: const Color(0xFF10B981),
                          ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),
                ],
              ),
            // QR Download Options
            if (widget.onQRCode != null || widget.onScanQRDownload != null)
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Download to Phone',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                     if (widget.onQRCode != null)
  Expanded(
    child: SizedBox(
      height: 40,
      child: ElevatedButton.icon(
        onPressed: widget.isLoading
            ? null
            : () async {
                try {
                  // Directly call the parent async function that shows the QR
                  await widget.onQRCode!();
                } catch (e) {
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text("Failed to generate QR: $e"),
                        backgroundColor: const Color(0xFFEF4444),
                      ),
                    );
                  }
                }
              },
        icon: const Icon(Icons.qr_code_2, size: 16),
        label: const Text('Generate QR Code'),
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF10B981),
        ),
      ),
    ),
  ),

                      if (widget.onQRCode != null && widget.onScanQRDownload != null)
                        const SizedBox(width: 12),
                      if (widget.onScanQRDownload != null)
                        Expanded(
                          child: SizedBox(
                            height: 40,
                            child: ElevatedButton.icon(
                              onPressed: widget.isLoading ? null : widget.onScanQRDownload,
                              icon: const Icon(Icons.qr_code_scanner, size: 16),
                              label: const Text('Scan & Download'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: const Color(0xFF6366F1),
                                disabledBackgroundColor:
                                    const Color(0xFF6366F1).withOpacity(0.5),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(6),
                                ),
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 20),
                ],
              ),
            // Action Buttons
            Row(
              children: [
                SizedBox(
                  height: 40,
                  child: ElevatedButton(
                    onPressed: () => Navigator.of(context).pop(),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.transparent,
                      side: BorderSide(
                        color: Colors.white.withOpacity(0.2),
                      ),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(6),
                      ),
                    ),
                    child: const Text(
                      'Cancel',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                SizedBox(
                  height: 40,
                  child: ElevatedButton.icon(
                    onPressed: widget.isLoading
                        ? null
                        : () {
                            widget.onExport(
                              _selectedFormat,
                              applyBullets: _applyBulletFormatting,
                              autoDetect: _autoDetectBullets,
                            );
                            Navigator.of(context).pop();
                          },
                    icon: widget.isLoading
                        ? const SizedBox(
                            height: 16,
                            width: 16,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor: AlwaysStoppedAnimation<Color>(
                                  Colors.white),
                            ),
                          )
                        : const Icon(Icons.download, size: 16),
                    label: Text(
                      widget.isLoading ? 'Exporting...' : 'Export',
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF3B82F6),
                      disabledBackgroundColor:
                          const Color(0xFF3B82F6).withOpacity(0.5),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(6),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
