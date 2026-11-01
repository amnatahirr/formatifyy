import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

import 'tr.dart';
class QRDialog extends StatelessWidget {
  final String qrUrl;

  const QRDialog({super.key, required this.qrUrl});

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Tr("Scan to Download"),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          QrImageView(
            data: qrUrl,
            size: 220,
          ),
          const SizedBox(height: 10),
          const Tr("Scan with phone camera\nValid for 5 minutes",
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
