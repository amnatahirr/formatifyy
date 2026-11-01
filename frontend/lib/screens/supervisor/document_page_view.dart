import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../../models/supervisor_models.dart';

import '../../widgets/tr.dart';
/// Normalised (0..1) box of one paragraph on one page.
class PageRegion {
  final int paragraphId;
  final int page;
  final Rect rect;

  const PageRegion({required this.paragraphId, required this.page, required this.rect});

  factory PageRegion.fromJson(Map<String, dynamic> j) {
    final r = (j['rect'] as List).map((e) => (e as num).toDouble()).toList();
    return PageRegion(
      paragraphId: (j['paragraph_id'] as num).toInt(),
      page: (j['page'] as num).toInt(),
      rect: Rect.fromLTWH(r[0], r[1], r[2], r[3]),
    );
  }
}

class DocumentPageInfo {
  final int index;
  final double widthPt;
  final double heightPt;

  const DocumentPageInfo({required this.index, required this.widthPt, required this.heightPt});

  double get aspect => heightPt <= 0 ? 0.7071 : widthPt / heightPt;

  factory DocumentPageInfo.fromJson(Map<String, dynamic> j) => DocumentPageInfo(
        index: (j['index'] as num).toInt(),
        widthPt: (j['width_pt'] as num).toDouble(),
        heightPt: (j['height_pt'] as num).toDouble(),
      );
}

/// Response of GET .../documents/{id}/pages
class DocumentPagesModel {
  final List<DocumentPageInfo> pages;
  final List<PageRegion> regions;

  const DocumentPagesModel({required this.pages, required this.regions});

  factory DocumentPagesModel.fromJson(Map<String, dynamic> j) => DocumentPagesModel(
        pages: (j['pages'] as List? ?? const [])
            .map((e) => DocumentPageInfo.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList(),
        regions: (j['regions'] as List? ?? const [])
            .map((e) => PageRegion.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList(),
      );

  Map<int, List<PageRegion>> get regionsByPage {
    final out = <int, List<PageRegion>>{};
    for (final r in this.regions) {
      out.putIfAbsent(r.page, () => []).add(r);
    }
    return out;
  }
}

const double _pageMaxWidth = 794;
const Color _unresolvedFill = Color(0x66FFD54F);
const Color _resolvedFill = Color(0x55B0B7C3);

/// Word-faithful viewer: each page is the real rendered page image, with an
/// invisible (or highlighted, when commented) layer on top of every paragraph.
/// Long-press a paragraph -> [onLongPress] (same comment flow as the block view).
///
/// This widget scrolls by itself (lazy ListView), so put it in an Expanded,
/// not inside another SingleChildScrollView.
class DocumentPageView extends StatefulWidget {
  final DocumentPagesModel pages;
  final Map<int, DocumentParagraphModel> paragraphsById;
  final Future<Uint8List> Function(int pageIndex) loadPage;
  final void Function(DocumentParagraphModel) onLongPress;

  const DocumentPageView({
    super.key,
    required this.pages,
    required this.paragraphsById,
    required this.loadPage,
    required this.onLongPress,
  });

  @override
  State<DocumentPageView> createState() => _DocumentPageViewState();
}

class _DocumentPageViewState extends State<DocumentPageView> {
  final Map<int, Future<Uint8List>> _cache = {};
  late Map<int, List<PageRegion>> _byPage = widget.pages.regionsByPage;

  @override
  void didUpdateWidget(covariant DocumentPageView old) {
    super.didUpdateWidget(old);
    if (!identical(old.pages, widget.pages)) {
      _byPage = widget.pages.regionsByPage;
      _cache.clear();
    }
  }

  Future<Uint8List> _image(int i) => _cache.putIfAbsent(i, () => widget.loadPage(i));

  Color? _fill(PageRegion r) {
    switch (widget.paragraphsById[r.paragraphId]?.highlight) {
      case 'unresolved':
        return _unresolvedFill;
      case 'resolved':
        return _resolvedFill;
      default:
        return null;
    }
  }

  Widget _page(DocumentPageInfo info) {
    final regions = _byPage[info.index] ?? const <PageRegion>[];
    return AspectRatio(
      aspectRatio: info.aspect,
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          boxShadow: [
            BoxShadow(color: Colors.black.withOpacity(0.35), blurRadius: 18, offset: const Offset(0, 8)),
          ],
        ),
        child: LayoutBuilder(
          builder: (context, box) {
            final w = box.maxWidth;
            final h = box.maxHeight;
            return Stack(
              children: [
                Positioned.fill(
                  child: FutureBuilder<Uint8List>(
                    future: _image(info.index),
                    builder: (context, snap) {
                      if (snap.hasError) {
                        return Center(
                          child: TextButton.icon(
                            onPressed: () => setState(() => _cache.remove(info.index)),
                            icon: const Icon(Icons.refresh),
                            label: const Tr('Page failed to load. Retry'),
                          ),
                        );
                      }
                      if (!snap.hasData) {
                        return const Center(child: CircularProgressIndicator(strokeWidth: 2));
                      }
                      return Image.memory(snap.data!, fit: BoxFit.fill, gaplessPlayback: true);
                    },
                  ),
                ),
                for (final r in regions)
                  Positioned(
                    left: r.rect.left * w,
                    top: r.rect.top * h,
                    width: r.rect.width * w,
                    height: r.rect.height * h,
                    child: GestureDetector(
                      behavior: HitTestBehavior.translucent,
                      onLongPress: () {
                        final p = widget.paragraphsById[r.paragraphId];
                        if (p != null) widget.onLongPress(p);
                      },
                      child: ColoredBox(color: _fill(r) ?? Colors.transparent),
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final pages = widget.pages.pages;
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 16),
      itemCount: pages.length,
      itemBuilder: (context, i) {
        return Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: _pageMaxWidth),
            child: Padding(
              padding: const EdgeInsets.only(bottom: 18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _page(pages[i]),
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(
                      'Page ${i + 1} of ${pages.length}',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(0.5)),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}