// lib/screens/image_formatter_screen.dart
//
// Drop into: frontend/lib/screens/image_formatter_screen.dart
//
// Shows:
//   • "Format Images" button
//   • Progress indicator while BLIP + formatter runs
//   • Per-image summary cards (original size → display size, caption preview)
//   • Inline manual steps checklist
//   • Download button
//
// Usage from analyze_screen.dart (or anywhere):
//   Navigator.push(context, MaterialPageRoute(
//     builder: (_) => ImageFormatterScreen(
//       documentId: widget.documentId,
//       documentName: widget.documentName,
//     ),
//   ));

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/image_formatter_provider.dart';
import '../providers/auth_provider.dart';
import '../widgets/app_sidebar.dart';

// ── Colour palette (matches your app's existing dark theme) ──────────────────
const _bg      = Color(0xFF0D1117);
const _surface = Color(0xFF161B22);
const _border  = Color(0xFF30363D);
const _textPri = Colors.white;
const _textSec = Color(0xFF8B949E);
const _green   = Color(0xFF10B981);
const _yellow  = Color(0xFFF59E0B);
const _red     = Color(0xFFEF4444);
const _blue    = Color(0xFF4A9EFF);
const _orange  = Color(0xFFF97316);
const _purple  = Color(0xFF6366F1);


class ImageFormatterScreen extends StatelessWidget {
  final int    documentId;
  final String documentName;

  const ImageFormatterScreen({
    Key? key,
    required this.documentId,
    required this.documentName,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => ImageFormatterProvider(),
      child: _ImageFormatterBody(
        documentId:   documentId,
        documentName: documentName,
      ),
    );
  }
}


class _ImageFormatterBody extends StatelessWidget {
  final int    documentId;
  final String documentName;

  const _ImageFormatterBody({
    required this.documentId,
    required this.documentName,
  });

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<ImageFormatterProvider>();
    final auth     = context.read<AuthProvider>();

    return Scaffold(
      backgroundColor: _bg,
      body: Row(children: [
        // ── Sidebar (same as AnalyzeScreen) ────────────────────────────────
        AppSidebar(
          selectedIndex: 2,   // "My Reports" stays highlighted
          onItemSelected: (index) {
            switch (index) {
              case 0:
                final isAdmin = auth.isAdmin;
                final route   = isAdmin ? '/admin-dashboard' : '/student-dashboard';
                Navigator.pushNamedAndRemoveUntil(context, route, (_) => false);
                break;
              case 1:
                Navigator.pushNamedAndRemoveUntil(context, '/new-report', (_) => false);
                break;
              case 3:
                Navigator.pushNamedAndRemoveUntil(context, '/collaboration', (_) => false);
                break;
            }
          },
        ),
        // ── Main content ────────────────────────────────────────────────────
        Expanded(
          child: Column(children: [
            // Top bar
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
              decoration: const BoxDecoration(
                color: _bg,
                border: Border(bottom: BorderSide(color: _border)),
              ),
              child: Row(children: [
                IconButton(
                  icon: const Icon(Icons.arrow_back, color: _textPri),
                  onPressed: () => Navigator.pop(context),
                ),
                const SizedBox(width: 10),
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('FYP Image Formatter',
                      style: TextStyle(color: _textPri, fontSize: 17,
                          fontWeight: FontWeight.w700)),
                  Text(documentName,
                      style: const TextStyle(color: _textSec, fontSize: 12)),
                ]),
                const Spacer(),
                Text('Auto-caption · Centre-align · Table of Figures',
                    style: const TextStyle(color: _textSec, fontSize: 11)),
              ]),
            ),
            // Scrollable content
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [

          // ── Info banner ────────────────────────────────────────────────────
          _InfoBanner(
            icon:  Icons.auto_fix_high,
            color: _blue,
            title: 'FYP Academic Image Formatter',
            body:  'Automatically centres all images, preserves aspect ratios, '
                   'generates BLIP-AI captions (Figure 1: …), keeps images '
                   'and captions together across page breaks, and appends a '
                   'Table of Figures. Output is a new .docx — original untouched.',
          ),
          const SizedBox(height: 24),

          // ── Format button ──────────────────────────────────────────────────
          if (!provider.isLoading && !provider.hasResult)
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () => provider.formatDocumentImages(
                  documentId: documentId,
                  userId: auth.userId!,
                ),
                icon:  const Icon(Icons.auto_fix_high, size: 18),
                label: const Text('Format All Images Now',
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: _blue,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8)),
                ),
              ),
            ),

          // ── Loading ────────────────────────────────────────────────────────
          if (provider.isLoading) ...[
            const Center(child: CircularProgressIndicator(color: _blue)),
            const SizedBox(height: 16),
            const Center(
              child: Text(
                'Generating captions and formatting images…\n'
                'This may take 30–90 seconds.',
                textAlign: TextAlign.center,
                style: TextStyle(color: _textSec, fontSize: 13),
              ),
            ),
          ],

          // ── Error ──────────────────────────────────────────────────────────
          if (provider.error != null)
            _ErrorCard(message: provider.error!),

          // ── Results ───────────────────────────────────────────────────────
          if (provider.hasResult && provider.summary != null)
            _ResultSection(
              summary:    provider.summary!,
              documentId: documentId,
              userId:     auth.userId!,
              provider:   provider,
            ),
        ]),                // Column children list ends
              ),           // SingleChildScrollView
            ),             // Expanded (scroll area)
          ]),              // Column (topbar + content)
        ),                 // Expanded (main content area)
      ]),                  // Row (sidebar + content)
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Results section
// ─────────────────────────────────────────────────────────────────────────────

class _ResultSection extends StatelessWidget {
  final FormatterSummary      summary;
  final int                   documentId;
  final int                   userId;
  final ImageFormatterProvider provider;

  const _ResultSection({
    required this.summary,
    required this.documentId,
    required this.userId,
    required this.provider,
  });

  @override
  Widget build(BuildContext context) {
    final hasImages = summary.totalImages > 0;

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [

      // ── Top summary ────────────────────────────────────────────────────────
      _SummaryBanner(summary: summary),
      const SizedBox(height: 20),

      if (!hasImages) ...[
        const Center(
          child: Text(
            'No images were found in this document.',
            style: TextStyle(color: _textSec, fontSize: 13),
          ),
        ),
        const SizedBox(height: 20),
      ],

      // ── Per-image cards ────────────────────────────────────────────────────
      if (hasImages) ...[
        Text('${summary.totalImages} Image(s) Formatted',
            style: const TextStyle(
                color: _textPri, fontSize: 15, fontWeight: FontWeight.w700)),
        const SizedBox(height: 10),
        ...summary.images.map((img) => _ImageCard(img: img)),
        const SizedBox(height: 24),
      ],

      // ── Manual steps ───────────────────────────────────────────────────────
      if (summary.manualSteps.isNotEmpty) ...[
        _ManualStepsCard(steps: summary.manualSteps),
        const SizedBox(height: 20),
      ],

      // ── Items needing manual attention ─────────────────────────────────────
      if (summary.manualItems.isNotEmpty) ...[
        _ManualItemsCard(items: summary.manualItems),
        const SizedBox(height: 20),
      ],

      // ── Download button ────────────────────────────────────────────────────
      if (summary.downloadUrl != null || summary.outputFilename != null) ...[
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: provider.isDownloading
                ? null
                : () async {
                    final savedPath = await provider.downloadFormattedFile(
                      documentId: documentId,
                      userId:     userId,
                    );
                    if (!context.mounted) return;
                    if (savedPath != null) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Row(children: [
                            const Icon(Icons.check_circle,
                                color: Colors.white, size: 16),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                'Saved to: $savedPath',
                                style: const TextStyle(fontSize: 12),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ]),
                          backgroundColor: _green,
                          duration: const Duration(seconds: 5),
                        ),
                      );
                    } else if (provider.error != null) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text(provider.error!),
                          backgroundColor: _red,
                        ),
                      );
                    }
                  },
            icon: provider.isDownloading
                ? const SizedBox(
                    width: 18, height: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.download, size: 18),
            label: Text(
              provider.isDownloading
                  ? 'Downloading…'
                  : 'Download Formatted Document',
              style: const TextStyle(
                  fontSize: 14, fontWeight: FontWeight.w600),
            ),
            style: ElevatedButton.styleFrom(
              backgroundColor: _green,
              foregroundColor: Colors.white,
              disabledBackgroundColor: _green.withOpacity(0.5),
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8)),
            ),
          ),
        ),
        const SizedBox(height: 12),
      ],

      // ── Format again ───────────────────────────────────────────────────────
      SizedBox(
        width: double.infinity,
        child: OutlinedButton.icon(
          onPressed: () => provider.reset(),
          icon:  const Icon(Icons.refresh, size: 16),
          label: const Text('Format Again'),
          style: OutlinedButton.styleFrom(
            foregroundColor: _textSec,
            side: const BorderSide(color: _border),
            padding: const EdgeInsets.symmetric(vertical: 12),
          ),
        ),
      ),
    ]);
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Sub-widgets
// ─────────────────────────────────────────────────────────────────────────────

class _SummaryBanner extends StatelessWidget {
  final FormatterSummary summary;
  const _SummaryBanner({required this.summary});

  @override
  Widget build(BuildContext context) {
    final color = summary.totalImages > 0 ? _green : _yellow;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color:  color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(children: [
        Icon(summary.totalImages > 0 ? Icons.check_circle_outline : Icons.info_outline,
            color: color, size: 22),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(summary.message,
                style: TextStyle(color: color, fontSize: 13,
                    fontWeight: FontWeight.w600)),
            if (summary.tofAdded)
              const Padding(
                padding: EdgeInsets.only(top: 4),
                child: Text('✓  Table of Figures appended',
                    style: TextStyle(color: _textSec, fontSize: 11)),
              ),
          ]),
        ),
      ]),
    );
  }
}


class _ImageCard extends StatelessWidget {
  final ImageFormatResult img;
  const _ImageCard({required this.img});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _blue.withOpacity(0.25)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        // Figure number + caption
        Row(children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: _blue.withOpacity(0.15),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text('Figure ${img.figNum}',
                style: const TextStyle(color: _blue, fontSize: 11,
                    fontWeight: FontWeight.w700)),
          ),
          if (img.resized) ...[
            const SizedBox(width: 8),
            _Tag('Resized', _orange),
          ],
        ]),
        const SizedBox(height: 8),
        Text(img.caption,
            style: const TextStyle(color: _textPri, fontSize: 12,
                fontStyle: FontStyle.italic)),
        const SizedBox(height: 8),
        // Size info
        Row(children: [
          Expanded(
            child: _SizeInfo(
              label: 'Original',
              w: img.origWidthIn, h: img.origHeightIn,
              color: _textSec,
            ),
          ),
          const Icon(Icons.arrow_forward, color: _textSec, size: 14),
          Expanded(
            child: _SizeInfo(
              label: 'Display',
              w: img.dispWidthIn, h: img.dispHeightIn,
              color: img.resized ? _orange : _green,
            ),
          ),
        ]),
      ]),
    );
  }
}


class _SizeInfo extends StatelessWidget {
  final String label;
  final double w, h;
  final Color  color;
  const _SizeInfo({required this.label, required this.w, required this.h,
      required this.color});

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.center, children: [
    Text(label,
        style: const TextStyle(color: _textSec, fontSize: 10)),
    Text('${w.toStringAsFixed(2)}" × ${h.toStringAsFixed(2)}"',
        style: TextStyle(color: color, fontSize: 11,
            fontWeight: FontWeight.w600)),
  ]);
}


class _ManualStepsCard extends StatelessWidget {
  final List<String> steps;
  const _ManualStepsCard({required this.steps});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _yellow.withOpacity(0.06),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _yellow.withOpacity(0.3)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.build_outlined, color: _yellow, size: 16),
          const SizedBox(width: 8),
          const Text('Manual Steps Required in Word',
              style: TextStyle(color: _yellow, fontSize: 13,
                  fontWeight: FontWeight.w700)),
        ]),
        const SizedBox(height: 10),
        ...steps.asMap().entries.map((e) => Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${e.key + 1}. ',
                style: const TextStyle(color: _yellow, fontSize: 12,
                    fontWeight: FontWeight.w600)),
            Expanded(
              child: Text(e.value,
                  style: const TextStyle(color: _textSec, fontSize: 12,
                      height: 1.4)),
            ),
          ]),
        )),
      ]),
    );
  }
}


class _ManualItemsCard extends StatelessWidget {
  final List<String> items;
  const _ManualItemsCard({required this.items});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _red.withOpacity(0.06),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _red.withOpacity(0.3)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.warning_amber_rounded, color: _red, size: 16),
          const SizedBox(width: 8),
          const Text('Items Needing Manual Attention',
              style: TextStyle(color: _red, fontSize: 13,
                  fontWeight: FontWeight.w700)),
        ]),
        const SizedBox(height: 10),
        ...items.map((item) => Padding(
          padding: const EdgeInsets.only(bottom: 6),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('• ', style: TextStyle(color: _red, fontSize: 12)),
            Expanded(
              child: Text(item,
                  style: const TextStyle(color: _textSec, fontSize: 12,
                      height: 1.4)),
            ),
          ]),
        )),
      ]),
    );
  }
}


class _InfoBanner extends StatelessWidget {
  final IconData icon;
  final Color    color;
  final String   title;
  final String   body;
  const _InfoBanner({
    required this.icon, required this.color,
    required this.title, required this.body,
  });

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: color.withOpacity(0.06),
      borderRadius: BorderRadius.circular(8),
      border: Border.all(color: color.withOpacity(0.2)),
    ),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Icon(icon, color: color, size: 18),
      const SizedBox(width: 10),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title,
            style: TextStyle(color: color, fontSize: 12,
                fontWeight: FontWeight.w600)),
        const SizedBox(height: 4),
        Text(body,
            style: const TextStyle(color: _textSec, fontSize: 11, height: 1.5)),
      ])),
    ]),
  );
}


class _Tag extends StatelessWidget {
  final String label;
  final Color  color;
  const _Tag(this.label, this.color);

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
    decoration: BoxDecoration(
      color: color.withOpacity(0.12),
      borderRadius: BorderRadius.circular(4),
      border: Border.all(color: color.withOpacity(0.3)),
    ),
    child: Text(label,
        style: TextStyle(color: color, fontSize: 9,
            fontWeight: FontWeight.w700, letterSpacing: 0.3)),
  );
}


class _ErrorCard extends StatelessWidget {
  final String message;
  const _ErrorCard({required this.message});

  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 16),
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: _red.withOpacity(0.08),
      borderRadius: BorderRadius.circular(8),
      border: Border.all(color: _red.withOpacity(0.3)),
    ),
    child: Row(children: [
      const Icon(Icons.error_outline, color: _red, size: 18),
      const SizedBox(width: 10),
      Expanded(child: Text(message,
          style: const TextStyle(color: _red, fontSize: 12))),
    ]),
  );
}