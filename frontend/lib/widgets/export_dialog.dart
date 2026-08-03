import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';

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
      'color': const Color(0xFF2563EB),
    },
    {
      'format': 'pdf',
      'label': 'PDF Document',
      'extension': '.pdf',
      'description': 'Universal PDF format',
      'icon': Icons.picture_as_pdf,
      'color': const Color(0xFFDC2626),
    },
    {
      'format': 'txt',
      'label': 'Plain Text',
      'extension': '.txt',
      'description': 'Simple text file without formatting',
      'icon': Icons.text_fields,
      'color': const Color(0xFF64748B),
    },
  ];

  @override
  Widget build(BuildContext context) {
    final p = context.watch<ThemeProvider>().palette;
    final media = MediaQuery.of(context);
    final maxDialogWidth = media.size.width < 560 ? media.size.width - 32 : 500.0;
    final maxDialogHeight = media.size.height * 0.88;
    final horizontalPad = media.size.width < 400 ? 16.0 : 28.0;
    final verticalPad = media.size.height < 700 ? 16.0 : 24.0;

    return Dialog(
      backgroundColor: p.surface,
      insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: maxDialogWidth,
          maxHeight: maxDialogHeight,
        ),
        child: Padding(
          padding: EdgeInsets.fromLTRB(
            horizontalPad,
            verticalPad,
            horizontalPad,
            verticalPad,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Header (fixed) ───────────────────────────────────────────
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Export Document',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w700,
                            color: p.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Choose your preferred export format',
                          style: TextStyle(
                            fontSize: 13,
                            color: p.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: Icon(Icons.close, color: p.textMuted),
                    visualDensity: VisualDensity.compact,
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(
                      minWidth: 32,
                      minHeight: 32,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // ── Scrollable body ──────────────────────────────────────────
              Expanded(
                child: SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      ...List.generate(_exportFormats.length * 2 - 1, (i) {
                        if (i.isOdd) return const SizedBox(height: 12);
                        final format = _exportFormats[i ~/ 2];
                        final isSelected = _selectedFormat == format['format'];
                        return _buildFormatOption(p, format, isSelected);
                      }),
                      const SizedBox(height: 20),
                      if (_selectedFormat == 'docx') ...[
                        Text(
                          'Bullet Formatting',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: p.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Container(
                          decoration: BoxDecoration(
                            color: p.surfaceAlt,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: p.border),
                          ),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 4,
                            vertical: 4,
                          ),
                          child: Column(
                            children: [
                              SwitchListTile(
                                dense: true,
                                contentPadding: const EdgeInsets.symmetric(
                                  horizontal: 12,
                                ),
                                title: Text(
                                  'Apply Bullet Formatting',
                                  style: TextStyle(
                                    fontSize: 13,
                                    color: p.textPrimary,
                                  ),
                                ),
                                subtitle: Text(
                                  'Format lists with bullets from template',
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: p.textSecondary,
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
                                Divider(color: p.border, height: 1),
                                SwitchListTile(
                                  dense: true,
                                  contentPadding: const EdgeInsets.symmetric(
                                    horizontal: 12,
                                  ),
                                  title: Text(
                                    'Auto-Detect List Content',
                                    style: TextStyle(
                                      fontSize: 13,
                                      color: p.textPrimary,
                                    ),
                                  ),
                                  subtitle: Text(
                                    'Automatically detect and format list items',
                                    style: TextStyle(
                                      fontSize: 11,
                                      color: p.textSecondary,
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
                      if (widget.onQRCode != null ||
                          widget.onScanQRDownload != null) ...[
                        Text(
                          'Download to Phone',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: p.textPrimary,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 12,
                          runSpacing: 10,
                          children: [
                            if (widget.onQRCode != null)
                              SizedBox(
                                height: 40,
                                child: ElevatedButton.icon(
                                  onPressed: widget.isLoading
                                      ? null
                                      : () async {
                                          try {
                                            await widget.onQRCode!();
                                          } catch (e) {
                                            if (mounted) {
                                              ScaffoldMessenger.of(context)
                                                  .showSnackBar(
                                                SnackBar(
                                                  content: Text(
                                                    'Failed to generate QR: $e',
                                                  ),
                                                  backgroundColor:
                                                      const Color(0xFFEF4444),
                                                ),
                                              );
                                            }
                                          }
                                        },
                                  icon: const Icon(Icons.qr_code_2, size: 16),
                                  label: const Text('Generate QR Code'),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: const Color(0xFF10B981),
                                    foregroundColor: Colors.white,
                                  ),
                                ),
                              ),
                            if (widget.onScanQRDownload != null)
                              SizedBox(
                                height: 40,
                                child: ElevatedButton.icon(
                                  onPressed: widget.isLoading
                                      ? null
                                      : widget.onScanQRDownload,
                                  icon: const Icon(
                                    Icons.qr_code_scanner,
                                    size: 16,
                                  ),
                                  label: const Text('Scan & Download'),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: const Color(0xFF6366F1),
                                    disabledBackgroundColor: const Color(
                                      0xFF6366F1,
                                    ).withOpacity(0.5),
                                    shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                  ),
                                ),
                              ),
                          ],
                        ),
                        const SizedBox(height: 8),
                      ],
                    ],
                  ),
                ),
              ),

              // ── Footer actions (fixed) ───────────────────────────────────
              const SizedBox(height: 16),
              Align(
                alignment: Alignment.centerRight,
                child: Wrap(
                  spacing: 12,
                  runSpacing: 8,
                  alignment: WrapAlignment.end,
                  children: [
                    SizedBox(
                      height: 40,
                      child: OutlinedButton(
                        onPressed: () => Navigator.of(context).pop(),
                        style: OutlinedButton.styleFrom(
                          side: BorderSide(color: p.borderStrong),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(6),
                          ),
                        ),
                        child: Text(
                          'Cancel',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: p.textPrimary,
                          ),
                        ),
                      ),
                    ),
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
                                    Colors.white,
                                  ),
                                ),
                              )
                            : const Icon(Icons.download, size: 16),
                        label: Text(
                          widget.isLoading ? 'Exporting...' : 'Export',
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF3B82F6),
                          foregroundColor: Colors.white,
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
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFormatOption(
    AppPalette p,
    Map<String, dynamic> format,
    bool isSelected,
  ) {
    final Color color = format['color'] as Color;
    return GestureDetector(
      onTap: () {
        setState(() {
          _selectedFormat = format['format'] as String;
        });
      },
      child: Container(
        decoration: BoxDecoration(
          color: isSelected ? color.withOpacity(0.15) : p.surfaceAlt,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isSelected ? color : p.border,
            width: isSelected ? 2 : 1,
          ),
        ),
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: color.withOpacity(0.2),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Icon(
                format['icon'] as IconData,
                color: color,
                size: 20,
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Wrap(
                    crossAxisAlignment: WrapCrossAlignment.center,
                    spacing: 8,
                    children: [
                      Text(
                        format['label'] as String,
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: p.textPrimary,
                        ),
                      ),
                      Text(
                        format['extension'] as String,
                        style: TextStyle(
                          fontSize: 12,
                          color: p.textMuted,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    format['description'] as String,
                    style: TextStyle(
                      fontSize: 12,
                      color: p.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            if (isSelected)
              Icon(
                Icons.check_circle,
                color: color,
                size: 20,
              ),
          ],
        ),
      ),
    );
  }
}
