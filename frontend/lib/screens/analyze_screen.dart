//   }

//   // ── Build ─────────────────────────────────────────────────────────────────

//   @override
//   Widget build(BuildContext context) {
//     return Scaffold(
//       backgroundColor: _bg,
//       body: Row(children: [
//         AppSidebar(
//           selectedIndex: _selectedSidebarIndex,
//           onItemSelected: _handleSidebarSelection,
//         ),
//         Expanded(child: Column(children: [
//           _buildTopBar(),
//           Expanded(child: FutureBuilder<Map<String, dynamic>>(
//             future: _analysisFuture,
//             builder: (ctx, snap) {
//               if (snap.connectionState == ConnectionState.waiting) return _buildLoading();
//               if (snap.hasError) return _buildError(snap.error.toString());
//               return _buildBody(snap.data ?? {});
//             },
//           )),
//         ])),
//       ]),
//     );
//   }

//   // ── Top bar ───────────────────────────────────────────────────────────────

//   Widget _buildTopBar() {
//     return Container(
//       padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
//       decoration: const BoxDecoration(
//           color: _bg, border: Border(bottom: BorderSide(color: _border))),
//       child: Row(children: [
//         IconButton(
//             icon: const Icon(Icons.arrow_back, color: _textPri),
//             onPressed: () => Navigator.pop(context)),
//         const SizedBox(width: 10),
//         Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//           const Text('Analysis Report',
//               style: TextStyle(color: _textPri, fontSize: 17, fontWeight: FontWeight.w700)),
//           Text(widget.documentName, style: const TextStyle(color: _textSec, fontSize: 12)),
//         ]),
//         const Spacer(),
//         Text('Template: ${widget.templateName}',
//             style: const TextStyle(color: _textSec, fontSize: 12)),
//         const SizedBox(width: 20),
//         ElevatedButton.icon(
//           onPressed: () => _handleDownload({'id': widget.documentId}),
//           icon:  const Icon(Icons.download, size: 16),
//           label: const Text('Export'),
//           style: ElevatedButton.styleFrom(
//               backgroundColor: _green, foregroundColor: _textPri,
//               padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10)),
//         ),
//       ]),
//     );
//   }

//   Widget _buildLoading() => const Center(
//     child: Column(mainAxisSize: MainAxisSize.min, children: [
//       CircularProgressIndicator(color: _blue),
//       SizedBox(height: 16),
//       Text('Running Layer 1 → 2 → 3 analysis…', style: TextStyle(color: _textSec)),
//     ]),
//   );

//   Widget _buildError(String msg) => Center(
//     child: Column(mainAxisSize: MainAxisSize.min, children: [
//       const Icon(Icons.error_outline, color: _red, size: 48),
//       const SizedBox(height: 12),
//       Padding(
//           padding: const EdgeInsets.symmetric(horizontal: 32),
//           child: Text(msg, style: const TextStyle(color: _red), textAlign: TextAlign.center)),
//       const SizedBox(height: 16),
//       ElevatedButton(
//           onPressed: () => setState(() => _analysisFuture = _fetchAnalysis()),
//           child: const Text('Retry')),
//     ]),
//   );

//   // ── Main body ─────────────────────────────────────────────────────────────

//   Widget _buildBody(Map<String, dynamic> data) {
//     final structure      = data['structure']      as Map<String, dynamic>? ?? {};
//     final oldIssues      = data['issues']         as List<dynamic>?        ?? [];
//     final score          = structure['score']     as int?
//                         ?? data['compliance_score'] as int? ?? 0;
//     final status         = structure['status']    as String? ?? 'unknown';
//     final summary        = structure['summary']   as Map<String, dynamic>? ?? {};
//     final sectionResults = structure['section_results'] as List<dynamic>? ?? [];
//     final allIssues      = structure['issues']    as List<dynamic>?        ?? [];
//     final docBlocks      = data['document_content'] as List<dynamic>?      ?? [];

//     final structureIssues = allIssues.where((i) =>
//         !['content_mismatch', 'wrong_font_size', 'wrong_bold',
//           'wrong_font', 'wrong_line_spacing'].contains((i as Map)['type'])).toList();

//     final contentIssues =
//         (data['content_issues'] as List<dynamic>?)?.toList() ??
//         allIssues.where((i) => (i as Map)['type'] == 'content_mismatch').toList();

//     final styleIssues =
//         (data['style_issues'] as List<dynamic>?)?.toList() ??
//         allIssues.where((i) => ['wrong_font_size', 'wrong_bold', 'wrong_font', 'wrong_line_spacing']
//             .contains((i as Map)['type'])).toList();

//     final imageIssues = oldIssues
//         .where((i) => (i as Map)['category'] == 'Image Relevance').toList();
//     final imageEthicsIssues = oldIssues
//         .where((i) => (i as Map)['category'] == 'Image Ethics').toList();
//     final formattingIssues = oldIssues
//         .where((i) => (i as Map)['category'] != 'Image Relevance' &&
//                       (i as Map)['category'] != 'Image Ethics').toList();

//     return Column(children: [
//       _buildScoreBanner(score, status, summary, imageIssues.length, imageEthicsIssues.length),
//       Container(
//         color: _surface,
//         child: TabBar(
//           controller: _tabController,
//           indicatorColor: _blue,
//           labelColor: _blue,
//           unselectedLabelColor: _textSec,
//           isScrollable: true,
//           tabs: [
//             Tab(text: 'Structure  (${summary['missing'] ?? 0} missing)'),
//             Tab(text: 'Content Check  (${contentIssues.length})'),
//             Tab(text: 'Style Check  (${styleIssues.length})'),
//             Tab(text: 'Image Relevancy  (${imageIssues.length})'),
//             Tab(text: 'Image Ethics  (${imageEthicsIssues.length})'),
//             Tab(text: 'Bullets'),
//             // ── FIX: show "…" while loading so the user never sees a stale (0)
//             Tab(
//               text: _tablesLoading
//                   ? 'Tables (…)'
//                   : 'Tables (${_calculateTableIssueCount()} issues)',
//             ),
//             Tab(text: 'Document Blocks  (${docBlocks.length})'),
//             Tab(text: 'References'),
//           ],
//         ),
//       ),
//       Expanded(
//         child: TabBarView(
//           controller: _tabController,
//           children: [
//             _buildStructureTab(sectionResults, structureIssues, summary),
//             _buildContentMismatchTab(contentIssues),
//             _buildStyleTab(styleIssues),
//             _buildImageRelevancyTab(imageIssues, formattingIssues),
//             _buildImageEthicsTab(imageEthicsIssues),
//             _buildBulletsTab(),
//             _buildTablesTab(),
//             _buildBlocksTab(docBlocks),
//             _buildReferencesTab(),
//           ],
//         ),
//       ),
//       _buildActionBar(allIssues, oldIssues),
//     ]);
//   }

//   Widget _buildScoreBanner(int score, String status, Map<String, dynamic> summary,
//       [int imageIssueCount = 0, int imageEthicsCount = 0]) {
//     final scoreColor = score >= 80 ? _green : score >= 50 ? _yellow : _red;
//     return Container(
//       color: _surface,
//       padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
//       child: Row(children: [
//         SizedBox(width: 64, height: 64, child: Stack(alignment: Alignment.center, children: [
//           CircularProgressIndicator(
//               value: score / 100, strokeWidth: 6,
//               backgroundColor: _border,
//               valueColor: AlwaysStoppedAnimation(scoreColor)),
//           Text('$score', style: TextStyle(
//               color: scoreColor, fontSize: 18, fontWeight: FontWeight.w800)),
//         ])),
//         const SizedBox(width: 20),
//         Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//           Row(children: [
//             _StatusBadge(status), const SizedBox(width: 12),
//             const Text('Structure Score',
//                 style: TextStyle(color: _textPri, fontSize: 15, fontWeight: FontWeight.w600)),
//           ]),
//           const SizedBox(height: 6),
//           ClipRRect(
//             borderRadius: BorderRadius.circular(4),
//             child: LinearProgressIndicator(
//                 value: score / 100, minHeight: 6,
//                 backgroundColor: _border,
//                 valueColor: AlwaysStoppedAnimation(scoreColor))),
//         ])),
//         const SizedBox(width: 32),
//         _SummaryPill('Found',   '${summary['found']          ?? 0}', _green),
//         const SizedBox(width: 8),
//         _SummaryPill('Missing', '${summary['missing']        ?? 0}', _red),
//         const SizedBox(width: 8),
//         _SummaryPill('Order',   '${summary['wrong_order']    ?? 0}', _yellow),
//         const SizedBox(width: 8),
//         _SummaryPill('Empty',   '${summary['empty']          ?? 0}', _yellow),
//         const SizedBox(width: 8),
//         _SummaryPill('Extra',   '${summary['extra_headings'] ?? 0}', _textSec),
//         const SizedBox(width: 8),
//         _SummaryPill('Content', '${summary['content_issues'] ?? 0}', _orange),
//         const SizedBox(width: 8),
//         _SummaryPill('Style',   '${summary['style_issues']   ?? 0}', _purple),
//         if (imageIssueCount  > 0) ...[const SizedBox(width: 8), _SummaryPill('Images', '$imageIssueCount',  _red)],
//         if (imageEthicsCount > 0) ...[const SizedBox(width: 8), _SummaryPill('Ethics', '$imageEthicsCount', _red)],
//       ]),
//     );
//   }

//   // ─────────────────────────────────────────────────────────────────────────
//   // Tab 1: Structure
//   // ─────────────────────────────────────────────────────────────────────────

//   Widget _buildStructureTab(
//       List<dynamic> sectionResults, List<dynamic> issues, Map<String, dynamic> summary) {
//     if (sectionResults.isEmpty) {
//       return _buildEmptyState(
//           Icons.checklist_rounded, 'No structure data',
//           'Make sure your template has required sections defined in the admin panel.',
//           actionLabel: 'View other checks below →',
//           onAction: () => _tabController.animateTo(1));
//     }
//     return SingleChildScrollView(
//       padding: const EdgeInsets.all(24),
//       child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//         if (summary['content_before_heading'] == true)
//           _buildAlertBanner(
//               '⚠  Content found before the first heading',
//               'Your document has text before any section heading. Move it under an appropriate heading.',
//               _yellow,
//               fixLabel: 'Fix: Move to Introduction',
//               onFix: () => _applyFix('move_content_before_heading', {})),
//         const SizedBox(height: 8),
//         ...sectionResults.asMap().entries
//             .map((e) => _buildSectionRow(e.key, e.value as Map<String, dynamic>)),
//         const SizedBox(height: 24),
//         _buildLayerLegend(),
//       ]),
//     );
//   }

//   Widget _buildSectionRow(int index, Map<String, dynamic> sec) {
//     final name     = sec['name']              as String? ?? '';
//     final order    = sec['order']             as int?    ?? 0;
//     final required = sec['required']          as bool?   ?? true;
//     final status   = sec['status']            as String? ?? 'missing';
//     final matched  = sec['matched_heading']   as String?;
//     final layer    = sec['match_layer']       as String?;
//     final docPos   = sec['document_position'] as int?;
//     final expanded = _expandedSections.contains(index);
//     final statusC  = _statusColor(status);
//     final layerC   = _layerColor(layer);

//     return Container(
//       margin: const EdgeInsets.only(bottom: 8),
//       decoration: BoxDecoration(
//           color: _surface, borderRadius: BorderRadius.circular(10),
//           border: Border.all(color: statusC.withOpacity(0.25))),
//       child: Column(children: [
//         InkWell(
//           borderRadius: BorderRadius.circular(10),
//           onTap: () => setState(() =>
//               expanded ? _expandedSections.remove(index) : _expandedSections.add(index)),
//           child: Padding(
//             padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
//             child: Row(children: [
//               Container(
//                   width: 28, height: 28,
//                   decoration: BoxDecoration(
//                       color: statusC.withOpacity(0.12),
//                       borderRadius: BorderRadius.circular(6)),
//                   alignment: Alignment.center,
//                   child: Text('$order',
//                       style: TextStyle(
//                           color: statusC, fontSize: 11, fontWeight: FontWeight.w700))),
//               const SizedBox(width: 12),
//               Expanded(child: Row(children: [
//                 Text(name,
//                     style: const TextStyle(
//                         color: _textPri, fontSize: 14, fontWeight: FontWeight.w500)),
//                 if (!required) ...[const SizedBox(width: 8), _Tag('optional', _textSec)],
//               ])),
//               if (matched != null && matched != name) ...[
//                 const Icon(Icons.arrow_forward, size: 12, color: _textSec),
//                 const SizedBox(width: 6),
//                 Text(matched, style: const TextStyle(color: _textSec, fontSize: 12)),
//                 const SizedBox(width: 8),
//               ],
//               if (docPos != null)
//                 Text('@$docPos', style: const TextStyle(color: _textSec, fontSize: 11)),
//               const SizedBox(width: 12),
//               if (layer != null) _Tag(layer, layerC),
//               const SizedBox(width: 8),
//               _Tag(status, statusC),
//               const SizedBox(width: 8),
//               Icon(
//                   expanded ? Icons.keyboard_arrow_up : Icons.keyboard_arrow_down,
//                   color: _textSec, size: 18),
//             ]),
//           ),
//         ),
//         if (expanded) _buildFixPanel(name, status, matched, layer, required),
//       ]),
//     );
//   }

//   Widget _buildFixPanel(
//       String name, String status, String? matched, String? layer, bool required) {
//     return Container(
//       width: double.infinity,
//       padding: const EdgeInsets.fromLTRB(56, 0, 16, 16),
//       decoration: const BoxDecoration(
//           color: _bg,
//           borderRadius: BorderRadius.vertical(bottom: Radius.circular(10))),
//       child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//         const Divider(color: _border, height: 1),
//         const SizedBox(height: 12),
//         Text(_fixExplanation(name, status, matched, layer),
//             style: const TextStyle(color: _textSec, fontSize: 12, height: 1.5)),
//         const SizedBox(height: 12),
//         Wrap(spacing: 8, runSpacing: 8,
//             children: _buildFixButtons(name, status, matched)),
//       ]),
//     );
//   }

//   String _fixExplanation(
//       String name, String status, String? matched, String? layer) {
//     switch (status) {
//       case 'missing':     return 'The section "$name" was not found in your document. Add this heading.';
//       case 'wrong_order': return '"$name" appears in the wrong position. It should come earlier.';
//       case 'empty':       return 'The section "$name" has no content after its heading.';
//       case 'found' when layer == 'synonym':
//         return '"$matched" was matched to "$name" via synonym detection. Consider renaming to "$name".';
//       case 'found' when layer == 'fuzzy':
//         return '"$matched" was matched to "$name" via fuzzy match (possible typo). Consider fixing.';
//       default:            return 'Section found and correctly placed. ✓';
//     }
//   }

//   List<Widget> _buildFixButtons(String name, String status, String? matched) {
//     final buttons = <Widget>[];
//     switch (status) {
//       case 'missing':
//         buttons.add(_FixButton(
//             label: 'Add "$name" heading', icon: Icons.add, color: _green,
//             onTap: () => _applyFix('add_heading', {'section': name})));
//         break;
//       case 'wrong_order':
//         buttons.add(_FixButton(
//             label: 'Reorder to correct position', icon: Icons.swap_vert, color: _yellow,
//             onTap: () => _applyFix('reorder_section', {'section': name})));
//         break;
//       case 'empty':
//         buttons.add(_FixButton(
//             label: 'Mark as acknowledged', icon: Icons.check, color: _textSec,
//             onTap: () => _showSnack('Acknowledged', _textSec)));
//         break;
//       case 'found':
//         if (matched != null && matched != name) {
//           buttons.add(_FixButton(
//               label: 'Rename "$matched" → "$name"', icon: Icons.edit, color: _blue,
//               onTap: () => _applyFix('rename_heading', {'old': matched, 'new': name})));
//         }
//         break;
//     }
//     buttons.add(_FixButton(
//         label: 'Ignore', icon: Icons.visibility_off_outlined, color: _textSec,
//         onTap: () => _showSnack('Issue ignored', _textSec)));
//     return buttons;
//   }

//   Widget _buildLayerLegend() {
//     return Container(
//       padding: const EdgeInsets.all(16),
//       decoration: BoxDecoration(
//           color: _surface, borderRadius: BorderRadius.circular(8),
//           border: Border.all(color: _border)),
//       child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//         const Text('Layer 2 — Heading Match Method',
//             style: TextStyle(
//                 color: _textSec, fontSize: 11,
//                 fontWeight: FontWeight.w600, letterSpacing: 0.5)),
//         const SizedBox(height: 10),
//         Wrap(spacing: 16, runSpacing: 8, children: [
//           _LegendItem('exact',    _green,                  'Exact text match'),
//           _LegendItem('synonym',  _blue,                   'Known alias (e.g. "Intro" → "Introduction")'),
//           _LegendItem('fuzzy',    _yellow,                 'Typo correction (e.g. "Methdology")'),
//           _LegendItem('semantic', const Color(0xFFA855F7), 'Semantic similarity (MiniLM)'),
//           _LegendItem('missing',  _red,                    'Not found'),
//         ]),
//       ]),
//     );
//   }

//   Widget _buildAlertBanner(String title, String body, Color color,
//       {String? fixLabel, VoidCallback? onFix}) {
//     return Container(
//       margin: const EdgeInsets.only(bottom: 12),
//       padding: const EdgeInsets.all(14),
//       decoration: BoxDecoration(
//           color: color.withOpacity(0.08), borderRadius: BorderRadius.circular(8),
//           border: Border.all(color: color.withOpacity(0.3))),
//       child: Row(children: [
//         Icon(Icons.warning_amber_rounded, color: color, size: 18),
//         const SizedBox(width: 10),
//         Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//           Text(title,
//               style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.w600)),
//           const SizedBox(height: 2),
//           Text(body, style: const TextStyle(color: _textSec, fontSize: 12)),
//         ])),
//         if (fixLabel != null && onFix != null)
//           TextButton(onPressed: onFix,
//               child: Text(fixLabel, style: TextStyle(color: color, fontSize: 12))),
//       ]),
//     );
//   }

//   // ─────────────────────────────────────────────────────────────────────────
//   // Tab 2: Content Mismatch
//   // ─────────────────────────────────────────────────────────────────────────

//   Widget _buildContentMismatchTab(List<dynamic> issues, {String modelMode = 'zero_shot'}) {
//     if (issues.isEmpty) {
//       return _buildEmptyState(
//           Icons.psychology_outlined, 'No content mismatches detected',
//           modelMode == 'trained_model'
//               ? '✓  Trained ML model found no content mismatches.'
//               : 'Zero-shot semantic check found no obvious mismatches.\n\n'
//                 'Train the model for higher accuracy:\npython checker/clean_and_retrain.py',
//           color: _green);
//     }
//     final hasTrained  = issues.any((i) => (i as Map)['mode'] == 'trained_model');
//     final hasZeroShot = issues.any((i) => (i as Map)['mode'] == 'zero_shot');
//     final hasHybrid   = issues.any((i) => (i as Map)['detection'] == 'hybrid');

//     String modeLabel; String modeDesc; Color modeBannerColor;
//     if (hasHybrid || hasTrained) {
//       modeLabel = '🤖  Hybrid Mode Active (trained + zero-shot)';
//       modeDesc  = 'Both the trained model and semantic similarity agree — high confidence.';
//       modeBannerColor = _green;
//     } else if (hasZeroShot) {
//       modeLabel = '⚡  Zero-Shot Mode Active';
//       modeDesc  = 'Using semantic similarity only. Train the model for better accuracy.';
//       modeBannerColor = _blue;
//     } else {
//       modeLabel = '🔑  Keyword Mode Active';
//       modeDesc  = 'Install sentence-transformers for better results.';
//       modeBannerColor = _yellow;
//     }

//     return SingleChildScrollView(
//       padding: const EdgeInsets.all(24),
//       child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//         _buildInfoBanner(modeLabel, modeDesc, modeBannerColor),
//         const SizedBox(height: 16),
//         ...issues.map((i) => _buildContentIssueCard(i as Map<String, dynamic>)),
//       ]),
//     );
//   }

//   Widget _buildContentIssueCard(Map<String, dynamic> issue) {
//     final heading  = issue['heading']  as String? ?? '';
//     final message  = issue['message']  as String? ?? '';
//     final mode     = issue['mode']     as String? ?? issue['detection'] as String? ?? 'zero_shot';
//     final severity = issue['severity'] as String? ?? 'warning';
//     final confidence     = _safeDouble(issue['confidence'])      ?? 0.0;
//     final ownSimilarity  = _safeDouble(issue['own_similarity']);
//     final bestMatchScore = _safeDouble(issue['best_match_score']);
//     final bestMatchHeading = issue['best_match_heading'] as String?;
//     final pct = (confidence * 100).toInt();
//     final gap = (ownSimilarity != null && bestMatchScore != null)
//         ? bestMatchScore - ownSimilarity : null;

//     String modeText; Color modeColor;
//     if (mode == 'hybrid')                               { modeText = 'HYBRID';    modeColor = _green;  }
//     else if (mode == 'trained_model' || mode == 'trained') { modeText = 'ML MODEL';  modeColor = _green;  }
//     else if (mode == 'zero_shot')                       { modeText = 'ZERO-SHOT'; modeColor = _blue;   }
//     else                                                { modeText = 'KEYWORD';   modeColor = _yellow; }
//     final borderColor = severity == 'error' ? _red : _orange;

//     return Container(
//       margin: const EdgeInsets.only(bottom: 12),
//       padding: const EdgeInsets.all(16),
//       decoration: BoxDecoration(
//           color: _surface, borderRadius: BorderRadius.circular(10),
//           border: Border.all(color: borderColor.withOpacity(0.3))),
//       child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//         Row(children: [
//           Container(width: 4, height: 44,
//               decoration: BoxDecoration(
//                   color: borderColor, borderRadius: BorderRadius.circular(2))),
//           const SizedBox(width: 12),
//           _Tag(severity == 'error' ? 'ERROR' : 'WARNING', borderColor),
//           const SizedBox(width: 6),
//           _Tag('CONTENT MISMATCH', _purple.withOpacity(0.7)),
//           const SizedBox(width: 6),
//           _Tag(modeText, modeColor),
//           const Spacer(),
//           Text('$pct% mismatch',
//               style: TextStyle(
//                   color: pct > 85 ? _red : _orange,
//                   fontSize: 11, fontWeight: FontWeight.w700)),
//         ]),
//         const SizedBox(height: 10),
//         Row(children: [
//           const Icon(Icons.title, color: _orange, size: 14), const SizedBox(width: 6),
//           Text('Section: "$heading"',
//               style: const TextStyle(
//                   color: _textPri, fontSize: 13, fontWeight: FontWeight.w600)),
//         ]),
//         const SizedBox(height: 6),
//         Text(message, style: const TextStyle(color: _textSec, fontSize: 12, height: 1.4)),
//         const SizedBox(height: 10),
//         Row(children: [
//           const Text('Mismatch confidence: ', style: TextStyle(color: _textSec, fontSize: 10)),
//           Expanded(child: ClipRRect(
//             borderRadius: BorderRadius.circular(4),
//             child: LinearProgressIndicator(
//                 value: confidence.clamp(0.0, 1.0), minHeight: 5,
//                 backgroundColor: _border,
//                 valueColor: AlwaysStoppedAnimation(confidence > 0.85 ? _red : _orange)))),
//           const SizedBox(width: 8),
//           Text('$pct%', style: TextStyle(
//               color: confidence > 0.85 ? _red : _orange,
//               fontSize: 10, fontWeight: FontWeight.w700)),
//         ]),
//         if (ownSimilarity != null || bestMatchHeading != null) ...[
//           const SizedBox(height: 10),
//           const Divider(color: _border, height: 1),
//           const SizedBox(height: 10),
//           if (ownSimilarity != null)
//             _DiffRow(
//                 label: 'Own score',
//                 text:  '${ownSimilarity.toStringAsFixed(3)}  ← fit to current heading'
//                        '${ownSimilarity < 0.45 ? "  ⚠ very low" : ""}',
//                 color: ownSimilarity < 0.40 ? _red : ownSimilarity < 0.52 ? _orange : _yellow),
//           if (bestMatchHeading != null && bestMatchScore != null) ...[
//             const SizedBox(height: 6),
//             _DiffRow(
//                 label: 'Better fit',
//                 text:  '"$bestMatchHeading"  →  score: ${bestMatchScore.toStringAsFixed(3)}'
//                        '${gap != null ? "  (gap +${gap.toStringAsFixed(3)})" : ""}',
//                 color: _green),
//             const SizedBox(height: 8),
//             Text('Tip: Consider moving this content to "$bestMatchHeading".',
//                 style: const TextStyle(
//                     color: _textSec, fontSize: 10, fontStyle: FontStyle.italic)),
//           ],
//         ],
//       ]),
//     );
//   }

//   Widget _buildInfoBanner(String title, String body, Color color) {
//     return Container(
//       padding: const EdgeInsets.all(14),
//       decoration: BoxDecoration(
//           color: color.withOpacity(0.06), borderRadius: BorderRadius.circular(8),
//           border: Border.all(color: color.withOpacity(0.2))),
//       child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
//         Icon(Icons.info_outline, color: color, size: 16), const SizedBox(width: 10),
//         Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//           Text(title,
//               style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
//           const SizedBox(height: 4),
//           Text(body, style: const TextStyle(color: _textSec, fontSize: 11, height: 1.5)),
//         ])),
//       ]),
//     );
//   }

//   // ─────────────────────────────────────────────────────────────────────────
//   // Tab 3: Style
//   // ─────────────────────────────────────────────────────────────────────────

//   Widget _buildStyleTab(List<dynamic> issues) {
//     if (issues.isEmpty) {
//       return _buildEmptyState(Icons.palette_outlined, 'No styling issues found',
//           'All font sizes, bold settings, and spacing match the template.', color: _green);
//     }
//     final fontSizeIssues = issues.where((i) => (i as Map)['type'] == 'wrong_font_size').toList();
//     final boldIssues     = issues.where((i) => (i as Map)['type'] == 'wrong_bold').toList();
//     final fontNameIssues = issues.where((i) => (i as Map)['type'] == 'wrong_font').toList();
//     final spacingIssues  = issues.where((i) => (i as Map)['type'] == 'wrong_line_spacing').toList();

//     return SingleChildScrollView(
//       padding: const EdgeInsets.all(24),
//       child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//         _buildInfoBanner(
//             '🎨  Style Check — Template Compliance',
//             'Compares font sizes, bold settings, font names, and line spacing '
//             'against your template rules. Only available for .docx files.',
//             _blue),
//         const SizedBox(height: 16),
//         if (fontSizeIssues.isNotEmpty) ...[
//           _StyleGroupHeader('Font Size',     fontSizeIssues.length, Icons.format_size,           _red),
//           const SizedBox(height: 8),
//           ...fontSizeIssues.map((i) => _buildStyleIssueCard(i as Map<String, dynamic>, _red)),
//           const SizedBox(height: 16),
//         ],
//         if (boldIssues.isNotEmpty) ...[
//           _StyleGroupHeader('Bold / Weight', boldIssues.length,     Icons.format_bold,            _yellow),
//           const SizedBox(height: 8),
//           ...boldIssues.map((i) => _buildStyleIssueCard(i as Map<String, dynamic>, _yellow)),
//           const SizedBox(height: 16),
//         ],
//         if (fontNameIssues.isNotEmpty) ...[
//           _StyleGroupHeader('Font Name',     fontNameIssues.length, Icons.font_download_outlined,  _orange),
//           const SizedBox(height: 8),
//           ...fontNameIssues.map((i) => _buildStyleIssueCard(i as Map<String, dynamic>, _orange)),
//           const SizedBox(height: 16),
//         ],
//         if (spacingIssues.isNotEmpty) ...[
//           _StyleGroupHeader('Line Spacing',  spacingIssues.length,  Icons.format_line_spacing,    _purple),
//           const SizedBox(height: 8),
//           ...spacingIssues.map((i) => _buildStyleIssueCard(i as Map<String, dynamic>, _purple)),
//         ],
//       ]),
//     );
//   }

//   Widget _buildStyleIssueCard(Map<String, dynamic> issue, Color color) {
//     return Container(
//       margin: const EdgeInsets.only(bottom: 8),
//       padding: const EdgeInsets.all(14),
//       decoration: BoxDecoration(
//           color: _surface, borderRadius: BorderRadius.circular(8),
//           border: Border.all(color: color.withOpacity(0.2))),
//       child: Row(children: [
//         Container(width: 3, height: 40,
//             decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2))),
//         const SizedBox(width: 12),
//         Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//           Row(children: [
//             _Tag('WARNING', color), const SizedBox(width: 8),
//             Expanded(child: Text(issue['code'] as String? ?? '',
//                 style: const TextStyle(color: _textSec, fontSize: 10, fontFamily: 'monospace'),
//                 overflow: TextOverflow.ellipsis)),
//           ]),
//           const SizedBox(height: 6),
//           Text(issue['message'] as String? ?? '',
//               style: const TextStyle(color: _textSec, fontSize: 12, height: 1.4)),
//         ])),
//       ]),
//     );
//   }

//   // ─────────────────────────────────────────────────────────────────────────
//   // Tab 4: Image Relevancy
//   // ─────────────────────────────────────────────────────────────────────────

//   Widget _buildImageRelevancyTab(
//       List<dynamic> imageIssues, List<dynamic> formattingIssues) {
//     if (imageIssues.isEmpty && formattingIssues.isEmpty) {
//       return SingleChildScrollView(
//         padding: const EdgeInsets.all(24),
//         child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//           _buildInfoBanner(
//               '✅  No Image Issues Detected',
//               'All images are relevant and no formatting problems were detected. '
//               'You can still run the FYP Image Formatter to standardise captions, sizes, and alignment.',
//               _green),
//           const SizedBox(height: 16),
//           _buildImageFormatterButton(),
//         ]),
//       );
//     }
//     return SingleChildScrollView(
//       padding: const EdgeInsets.all(24),
//       child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//         _buildImageFormatterButton(),
//         const SizedBox(height: 20),
//         if (imageIssues.isNotEmpty) ...[
//           _buildInfoBanner(
//               '🖼  AI Image Relevancy Check',
//               'These images were flagged as potentially irrelevant to the surrounding document content.',
//               _red),
//           const SizedBox(height: 16),
//           ...imageIssues.map((i) => ImageIssueCardEnhanced(
//             issue: i as Map<String, dynamic>,
//             imageBaseUrl: _baseUrl,
//             documentId: widget.documentId,
//             onImageReplaced: (_) => setState(() => _analysisFuture = _fetchAnalysis()),
//             onError: (e) => debugPrint('Image replacement error: $e'),
//           )),
//           if (formattingIssues.isNotEmpty) const SizedBox(height: 28),
//         ],
//         if (formattingIssues.isNotEmpty) ...[
//           Row(children: [
//             const Icon(Icons.warning_amber_rounded, color: _yellow, size: 16),
//             const SizedBox(width: 8),
//             Text('Other Formatting Issues  (${formattingIssues.length})',
//                 style: const TextStyle(
//                     color: _yellow, fontSize: 13, fontWeight: FontWeight.w700)),
//           ]),
//           const SizedBox(height: 12),
//           ...formattingIssues.map(
//               (i) => _buildFormattingIssueCard(i as Map<String, dynamic>)),
//         ],
//       ]),
//     );
//   }

//   String _buildImageUrl(String rawPath) {
//     final cleanPath =
//         rawPath.startsWith('uploads/') ? rawPath.substring('uploads/'.length) : rawPath;
//     final uri      = Uri.tryParse(_baseUrl);
//     final hostBase = uri != null
//         ? '${uri.scheme}://${uri.host}:${uri.port}'
//         : _baseUrl.split('/api').first;
//     return '$hostBase/uploads/$cleanPath';
//   }

//   Widget _buildImageFormatterButton() {
//     return Container(
//       decoration: BoxDecoration(
//         gradient: LinearGradient(
//           colors: [_blue.withOpacity(0.15), _purple.withOpacity(0.10)],
//           begin: Alignment.centerLeft,
//           end:   Alignment.centerRight,
//         ),
//         borderRadius: BorderRadius.circular(10),
//         border: Border.all(color: _blue.withOpacity(0.4)),
//       ),
//       padding: const EdgeInsets.all(16),
//       child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//         Row(children: [
//           Container(
//             padding: const EdgeInsets.all(8),
//             decoration: BoxDecoration(
//                 color: _blue.withOpacity(0.2), borderRadius: BorderRadius.circular(8)),
//             child: const Icon(Icons.auto_fix_high, color: _blue, size: 20),
//           ),
//           const SizedBox(width: 12),
//           const Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//             Text('FYP Image Formatter',
//                 style: TextStyle(color: _textPri, fontSize: 14, fontWeight: FontWeight.w700)),
//             Text('Academic-standard formatting for all images',
//                 style: TextStyle(color: _textSec, fontSize: 11)),
//           ])),
//         ]),
//         const SizedBox(height: 12),
//         Wrap(spacing: 8, runSpacing: 6, children: [
//           _FeatureChip('• Centre-aligned',               _blue),
//           _FeatureChip('• Auto captions',                _blue),
//           _FeatureChip('• Figure numbering',             _blue),
//           _FeatureChip('• Table of Figures',             _blue),
//           _FeatureChip('• Keeps image+caption together', _blue),
//           _FeatureChip('• Aspect-ratio safe',            _blue),
//         ]),
//         const SizedBox(height: 14),
//         SizedBox(
//           width: double.infinity,
//           child: ElevatedButton.icon(
//             onPressed: () => Navigator.push(
//               context,
//               MaterialPageRoute(
//                 builder: (_) => ImageFormatterScreen(
//                   documentId:   widget.documentId,
//                   documentName: widget.documentName,
//                 ),
//               ),
//             ),
//             icon:  const Icon(Icons.auto_fix_high, size: 16),
//             label: const Text('Open Image Formatter',
//                 style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
//             style: ElevatedButton.styleFrom(
//               backgroundColor: _blue,
//               foregroundColor: Colors.white,
//               padding: const EdgeInsets.symmetric(vertical: 12),
//               shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
//             ),
//           ),
//         ),
//       ]),
//     );
//   }

//   Widget _buildFormattingIssueCard(Map<String, dynamic> issue) {
//     final isCritical = (issue['type'] as String? ?? '') == 'CRITICAL';
//     final color      = isCritical ? _red : _yellow;
//     return Container(
//       margin: const EdgeInsets.only(bottom: 8),
//       padding: const EdgeInsets.all(14),
//       decoration: BoxDecoration(
//           color: _surface, borderRadius: BorderRadius.circular(8),
//           border: Border.all(color: color.withOpacity(0.25))),
//       child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//         Row(children: [
//           Container(width: 3, height: 36,
//               decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2))),
//           const SizedBox(width: 12),
//           Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//             Row(children: [
//               _Tag(isCritical ? 'CRITICAL' : 'WARNING', color), const SizedBox(width: 8),
//               Expanded(child: Text(issue['category'] as String? ?? '',
//                   style: const TextStyle(color: _textSec, fontSize: 11, fontFamily: 'monospace'),
//                   overflow: TextOverflow.ellipsis)),
//               if ((issue['line'] as int? ?? 0) > 0)
//                 Text('Line ${issue['line']}',
//                     style: const TextStyle(color: _textSec, fontSize: 10)),
//             ]),
//             const SizedBox(height: 4),
//             Text(issue['description'] as String? ?? '',
//                 style: const TextStyle(color: _textSec, fontSize: 12)),
//           ])),
//         ]),
//         if ((issue['current']    as String? ?? '').isNotEmpty ||
//             (issue['suggestion'] as String? ?? '').isNotEmpty) ...[
//           const SizedBox(height: 10),
//           const Divider(color: _border, height: 1),
//           const SizedBox(height: 10),
//           if ((issue['current'] as String? ?? '').isNotEmpty)
//             _DiffRow(label: 'Current', text: issue['current'], color: _red),
//           if ((issue['suggestion'] as String? ?? '').isNotEmpty) ...[
//             const SizedBox(height: 6),
//             _DiffRow(label: 'Suggestion', text: issue['suggestion'], color: _green),
//           ],
//         ],
//       ]),
//     );
//   }

//   // ─────────────────────────────────────────────────────────────────────────
//   // Tab 5: Image Ethics
//   // ─────────────────────────────────────────────────────────────────────────

//   Widget _buildImageEthicsTab(List<dynamic> ethicsIssues) {
//     if (ethicsIssues.isEmpty) {
//       return _buildEmptyState(Icons.verified_user_outlined, 'No ethical issues detected',
//           'All images passed the ethical content check.', color: _green);
//     }
//     return SingleChildScrollView(
//       padding: const EdgeInsets.all(24),
//       child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//         _buildInfoBanner(
//             '🚫  Image Ethics Check',
//             'These images were flagged as potentially unethical or inappropriate. '
//             'Review and remove before publishing.',
//             _red),
//         const SizedBox(height: 16),
//         ...ethicsIssues.map((i) => _buildImageEthicsCard(i as Map<String, dynamic>)),
//       ]),
//     );
//   }

//   Widget _buildImageEthicsCard(Map<String, dynamic> issue) {
//     final rawPath    = issue['image_path']   as String? ?? '';
//     final filename   = issue['current']      as String? ?? rawPath;
//     final reason     = issue['description']  as String? ?? issue['message'] as String? ?? 'Flagged as unethical.';
//     final category   = issue['sub_category'] as String? ?? issue['ethics_category'] as String? ?? 'Unethical Content';
//     final confidence = _safeDouble(issue['confidence']) ?? 1.0;
//     final pct        = (confidence * 100).toInt();
//     final imageUrl   = _buildImageUrl(rawPath);

//     return Container(
//       margin: const EdgeInsets.only(bottom: 16),
//       decoration: BoxDecoration(
//           color: _surface, borderRadius: BorderRadius.circular(10),
//           border: Border.all(color: _red.withOpacity(0.45), width: 1.5)),
//       clipBehavior: Clip.antiAlias,
//       child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
//         Container(
//           color: _red.withOpacity(0.15),
//           padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
//           child: Row(children: [
//             const Icon(Icons.block, color: _red, size: 16), const SizedBox(width: 8),
//             const Text('🚫  Unethical Image Detected',
//                 style: TextStyle(color: _red, fontSize: 13, fontWeight: FontWeight.w600)),
//             const Spacer(),
//             _Tag('ETHICS VIOLATION', _red), const SizedBox(width: 8),
//             Text('$pct% confidence', style: const TextStyle(color: _textSec, fontSize: 11)),
//           ]),
//         ),
//         Padding(
//           padding: const EdgeInsets.fromLTRB(14, 10, 14, 0),
//           child: Row(children: [
//             const Icon(Icons.label_outline, color: _textSec, size: 13),
//             const SizedBox(width: 6),
//             const Text('Category: ', style: TextStyle(color: _textSec, fontSize: 11)),
//             _Tag(category, _red),
//           ]),
//         ),
//         Image.network(imageUrl, height: 200, fit: BoxFit.contain,
//             color: Colors.black.withOpacity(0.55), colorBlendMode: BlendMode.darken,
//             errorBuilder: (_, __, ___) => Container(
//                 height: 100, color: _surface2, alignment: Alignment.center,
//                 child: const Icon(Icons.broken_image, color: _textSec, size: 28))),
//         Padding(
//           padding: const EdgeInsets.all(14),
//           child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//             Row(children: [
//               const Icon(Icons.attach_file, color: _textSec, size: 12), const SizedBox(width: 4),
//               Expanded(child: Text(filename,
//                   style: const TextStyle(color: _textSec, fontSize: 11, fontFamily: 'monospace'),
//                   overflow: TextOverflow.ellipsis)),
//             ]),
//             const SizedBox(height: 10),
//             Text(reason, style: const TextStyle(color: _textSec, fontSize: 12, height: 1.4)),
//             const SizedBox(height: 10),
//             Row(children: [
//               const Text('Detection confidence: ',
//                   style: TextStyle(color: _textSec, fontSize: 11)),
//               Expanded(child: ClipRRect(
//                 borderRadius: BorderRadius.circular(4),
//                 child: LinearProgressIndicator(
//                     value: confidence.clamp(0.0, 1.0), minHeight: 5,
//                     backgroundColor: _border,
//                     valueColor: const AlwaysStoppedAnimation(_red)))),
//               const SizedBox(width: 8),
//               Text('$pct%',
//                   style: const TextStyle(color: _red, fontSize: 11, fontWeight: FontWeight.w700)),
//             ]),
//             const SizedBox(height: 10),
//             _buildAlertBanner('Action Required',
//                 'Remove or replace this image immediately.', _red),
//           ]),
//         ),
//       ]),
//     );
//   }

//   // ─────────────────────────────────────────────────────────────────────────
//   // Tab 6: Bullets
//   // ─────────────────────────────────────────────────────────────────────────

//   Widget _buildBulletsTab() {
//     return _BulletsTabContent(
//       documentId: widget.documentId,
//       userId: context.read<AuthProvider>().userId ?? 0,
//     );
//   }

//   // ─────────────────────────────────────────────────────────────────────────
//   // Tab 7: Tables
//   // ─────────────────────────────────────────────────────────────────────────

//   Widget _buildTablesTab() {
//     if (_tablesLoading) {
//       return const Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
//         CircularProgressIndicator(color: _blue),
//         SizedBox(height: 16),
//         Text('Scanning document for tables…',
//             style: TextStyle(color: _textSec, fontSize: 13)),
//       ]));
//     }

//     if (_tablesError != null && _tables.isEmpty) {
//       return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
//         const Icon(Icons.error_outline, color: _red, size: 48),
//         const SizedBox(height: 12),
//         Text(_tablesError!, style: const TextStyle(color: _red, fontSize: 13)),
//         const SizedBox(height: 16),
//         ElevatedButton(onPressed: _loadTables, child: const Text('Retry')),
//       ]));
//     }

//     final tablesWithIssues = _tables.where((t) => !t.isClean).toList();

//     if (_tables.isEmpty) {
//       return _buildEmptyState(Icons.table_chart_outlined, 'No tables detected',
//           'Your document contains no tables, or only unsupported PDF tables were found.');
//     }

//     if (tablesWithIssues.isEmpty) {
//       return _buildEmptyState(Icons.check_circle_outline, 'All tables are formatted',
//           'All tables are clean and properly formatted.', color: _green);
//     }

//     return Column(children: [
//       if (_tablesSuccess != null)
//         _buildBanner(_tablesSuccess!, _green, Icons.check_circle_outline),
//       if (_tablesError != null)
//         _buildBanner(_tablesError!, _red, Icons.error_outline),

//       Expanded(child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
//         // ── Left: table list ───────────────────────────────────────────────
//         Expanded(child: ListView(padding: const EdgeInsets.all(20), children: [
//           Row(children: [
//             OutlinedButton.icon(
//               onPressed: tablesWithIssues.isNotEmpty
//                   ? () => setState(() => _selectedTableIndices.isEmpty
//                       ? _selectedTableIndices.addAll(tablesWithIssues.map((t) => t.index))
//                       : _selectedTableIndices.clear())
//                   : null,
//               icon: Icon(
//                   _selectedTableIndices.isNotEmpty ? Icons.deselect : Icons.select_all,
//                   size: 14),
//               label: Text(
//                   _selectedTableIndices.isNotEmpty ? 'Clear All' : 'Select All',
//                   style: const TextStyle(fontSize: 12)),
//               style: OutlinedButton.styleFrom(
//                   foregroundColor: _blue,
//                   side: const BorderSide(color: _border),
//                   padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8)),
//             ),
//             const SizedBox(width: 12),
//             _Tag('${tablesWithIssues.length} tables with issues', _yellow),
//             const SizedBox(width: 6),
//             _Tag('${tablesWithIssues.fold(0, (s, t) => s + t.issueCount)} issues', _yellow),
//             if (_selectedTableIndices.isNotEmpty) ...[
//               const SizedBox(width: 6),
//               _Tag('${_selectedTableIndices.length} selected', _purple),
//             ],
//           ]),
//           const SizedBox(height: 16),
//           ...tablesWithIssues.map((t) => _buildTableCard(t)),
//           const SizedBox(height: 80),
//         ])),

//         // ── Right: sidebar ─────────────────────────────────────────────────
//         _buildTablesSidebar(),
//       ])),

//       _buildTablesActionBar(),
//     ]);
//   }

//   Widget _buildBanner(String msg, Color color, IconData icon) {
//     return Container(
//       width: double.infinity,
//       padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
//       color: color.withOpacity(0.10),
//       child: Row(children: [
//         Icon(icon, color: color, size: 14), const SizedBox(width: 8),
//         Expanded(child: Text(msg, style: TextStyle(color: color, fontSize: 12))),
//       ]),
//     );
//   }

//   Widget _buildTableCard(_TableMeta table) {
//     final isSelected = _selectedTableIndices.contains(table.index);
//     final isExpanded = _expandedTableCards.contains(table.index);
//     final issueColor = table.isClean ? _green : _yellow;

//     return Container(
//       margin: const EdgeInsets.only(bottom: 10),
//       decoration: BoxDecoration(
//         color: _surface, borderRadius: BorderRadius.circular(10),
//         border: Border.all(
//             color: isSelected ? _blue : _border, width: isSelected ? 1.5 : 0.5),
//       ),
//       child: Column(children: [
//         InkWell(
//           borderRadius: BorderRadius.circular(10),
//           onTap: () => setState(() => isExpanded
//               ? _expandedTableCards.remove(table.index)
//               : _expandedTableCards.add(table.index)),
//           child: Padding(
//             padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
//             child: Row(children: [
//               // Checkbox
//               GestureDetector(
//                 onTap: () => setState(() => isSelected
//                     ? _selectedTableIndices.remove(table.index)
//                     : _selectedTableIndices.add(table.index)),
//                 behavior: HitTestBehavior.opaque,
//                 child: Padding(
//                   padding: const EdgeInsets.only(right: 10),
//                   child: AnimatedContainer(
//                     duration: const Duration(milliseconds: 150),
//                     width: 20, height: 20,
//                     decoration: BoxDecoration(
//                         color: isSelected ? _blue : Colors.transparent,
//                         border: Border.all(
//                             color: isSelected ? _blue : _border, width: 1.5),
//                         borderRadius: BorderRadius.circular(4)),
//                     child: isSelected
//                         ? const Icon(Icons.check, color: Colors.white, size: 14)
//                         : null,
//                   ),
//                 ),
//               ),
//               // Table badge
//               Container(
//                 padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
//                 decoration: BoxDecoration(
//                     color: _surface2, borderRadius: BorderRadius.circular(5),
//                     border: Border.all(color: _border)),
//                 child: Text(table.label,
//                     style: const TextStyle(
//                         color: _textSec, fontSize: 11, fontWeight: FontWeight.w600)),
//               ),
//               const SizedBox(width: 10),
//               // Info
//               Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//                 Text('${table.rowCount} rows × ${table.colCount} columns',
//                     style: const TextStyle(
//                         color: _textPri, fontSize: 13, fontWeight: FontWeight.w500)),
//                 const SizedBox(height: 2),
//                 Row(children: [
//                   if (table.hasHeaderRow) ...[
//                     const Icon(Icons.title, color: _green, size: 11),
//                     const SizedBox(width: 3),
//                     const Text('Header row',
//                         style: TextStyle(color: _green, fontSize: 10)),
//                     const SizedBox(width: 8),
//                   ] else ...[
//                     const Icon(Icons.warning_amber, color: _yellow, size: 11),
//                     const SizedBox(width: 3),
//                     const Text('No header',
//                         style: TextStyle(color: _yellow, fontSize: 10)),
//                     const SizedBox(width: 8),
//                   ],
//                   _Tag(table.source.toUpperCase(), _textSec),
//                 ]),
//               ])),
//               // Issue badge
//               Container(
//                 padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
//                 decoration: BoxDecoration(
//                     color: issueColor.withOpacity(0.12),
//                     borderRadius: BorderRadius.circular(12),
//                     border: Border.all(color: issueColor.withOpacity(0.3))),
//                 child: Text(
//                     table.isClean
//                         ? 'Clean'
//                         : '${table.issueCount} issue${table.issueCount > 1 ? "s" : ""}',
//                     style: TextStyle(
//                         color: issueColor, fontSize: 11, fontWeight: FontWeight.w600)),
//               ),
//               const SizedBox(width: 8),
//               Icon(
//                   isExpanded ? Icons.keyboard_arrow_up : Icons.keyboard_arrow_down,
//                   color: _textSec, size: 18),
//             ]),
//           ),
//         ),
//         if (isExpanded)
//           Container(
//             decoration: const BoxDecoration(
//                 color: _bg,
//                 borderRadius: BorderRadius.vertical(bottom: Radius.circular(10))),
//             child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//               const Divider(color: _border, height: 1),
//               if (table.previewRows.isNotEmpty) ...[
//                 const Padding(
//                   padding: EdgeInsets.fromLTRB(14, 12, 14, 6),
//                   child: Text('PREVIEW',
//                       style: TextStyle(color: _textSec, fontSize: 10,
//                           fontWeight: FontWeight.w700, letterSpacing: 0.6)),
//                 ),
//                 Padding(
//                   padding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
//                   child: ClipRRect(
//                     borderRadius: BorderRadius.circular(6),
//                     child: Table(
//                       border: TableBorder.all(color: _border, width: 0.5),
//                       defaultColumnWidth: const FlexColumnWidth(),
//                       children: table.previewRows.asMap().entries.map((entry) {
//                         final isHeader = entry.key == 0 && table.hasHeaderRow;
//                         return TableRow(
//                           decoration: BoxDecoration(
//                               color: isHeader ? _blue.withOpacity(0.12) : Colors.transparent),
//                           children: entry.value.map((cell) => Padding(
//                             padding: const EdgeInsets.symmetric(
//                                 horizontal: 8, vertical: 6),
//                             child: Text(cell,
//                               style: TextStyle(
//                                   color: isHeader ? _blue : _textSec, fontSize: 11,
//                                   fontWeight: isHeader
//                                       ? FontWeight.w600 : FontWeight.w400),
//                               overflow: TextOverflow.ellipsis),
//                           )).toList(),
//                         );
//                       }).toList(),
//                     ),
//                   ),
//                 ),
//               ],
//               if (table.issues.isNotEmpty) ...[
//                 const Padding(
//                   padding: EdgeInsets.fromLTRB(14, 0, 14, 6),
//                   child: Text('ISSUES',
//                       style: TextStyle(color: _textSec, fontSize: 10,
//                           fontWeight: FontWeight.w700, letterSpacing: 0.6)),
//                 ),
//                 ...table.issues.map((issue) {
//                   final Color c;
//                   final IconData ic;
//                   switch (issue.severity) {
//                     case 'error':   c = _red;    ic = Icons.error_outline;         break;
//                     case 'warning': c = _yellow; ic = Icons.warning_amber_rounded; break;
//                     default:        c = _blue;   ic = Icons.info_outline;
//                   }
//                   return Padding(
//                     padding: const EdgeInsets.fromLTRB(14, 0, 14, 8),
//                     child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
//                       Icon(ic, color: c, size: 13), const SizedBox(width: 6),
//                       Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
//                           children: [
//                         Text(issue.code, style: TextStyle(color: c, fontSize: 10,
//                             fontWeight: FontWeight.w700, fontFamily: 'monospace')),
//                         const SizedBox(height: 2),
//                         Text(issue.message, style: const TextStyle(
//                             color: _textSec, fontSize: 11, height: 1.4)),
//                       ])),
//                     ]),
//                   );
//                 }),
//                 const SizedBox(height: 12),
//               ] else
//                 const Padding(
//                   padding: EdgeInsets.fromLTRB(14, 8, 14, 16),
//                   child: Row(children: [
//                     Icon(Icons.check_circle_outline, color: _green, size: 14),
//                     SizedBox(width: 6),
//                     Text('No issues detected',
//                         style: TextStyle(color: _green, fontSize: 12)),
//                   ]),
//                 ),
//             ]),
//           ),
//       ]),
//     );
//   }

//   Widget _buildTablesSidebar() {
//     return Container(
//       width: 280,
//       decoration: const BoxDecoration(
//           color: _surface, border: Border(left: BorderSide(color: _border))),
//       child: SingleChildScrollView(
//         padding: const EdgeInsets.all(16),
//         child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//           const Text('FORMATTING PRESET',
//               style: TextStyle(color: _textSec, fontSize: 10,
//                   fontWeight: FontWeight.w700, letterSpacing: 0.6)),
//           const SizedBox(height: 10),
//           _buildPresetButton('academic',     'Academic',
//               'Bold header · Banded rows · TNR 12pt',      Icons.school_outlined,          _blue),
//           const SizedBox(height: 6),
//           _buildPresetButton('professional', 'Professional',
//               'Dark header · Full borders · Calibri 11pt', Icons.business_center_outlined, _purple),
//           const SizedBox(height: 6),
//           _buildPresetButton('minimal',      'Minimal',
//               'Thin borders only · Arial 11pt',            Icons.minimize_outlined,        _textSec),
//           const SizedBox(height: 20),

//           const Text('FORMAT RULES',
//               style: TextStyle(color: _textSec, fontSize: 10,
//                   fontWeight: FontWeight.w700, letterSpacing: 0.6)),
//           const SizedBox(height: 10),
//           _buildRuleToggle('Bold header row',             'header_bold'),
//           _buildRuleToggle('Banded rows',                 'banded_rows'),
//           _buildRuleToggle('Consistent borders',          'borders'),
//           _buildRuleToggle('Center table',                'center_table'),
//           _buildRuleToggle('Repeat header on page break', 'repeat_header'),
//           _buildRuleToggle('Auto-fit to page width',      'auto_fit'),
//         ]),
//       ),
//     );
//   }

//   Widget _buildPresetButton(
//       String key, String label, String desc, IconData icon, Color color) {
//     final isActive = _tablePreset == key;
//     return GestureDetector(
//       onTap: () => _setTablePreset(key),
//       child: AnimatedContainer(
//         duration: const Duration(milliseconds: 150),
//         padding: const EdgeInsets.all(10),
//         decoration: BoxDecoration(
//             color: isActive ? color.withOpacity(0.12) : _surface2,
//             borderRadius: BorderRadius.circular(8),
//             border: Border.all(
//                 color: isActive ? color : _border, width: isActive ? 1.5 : 0.5)),
//         child: Row(children: [
//           Icon(icon, color: isActive ? color : _textSec, size: 16),
//           const SizedBox(width: 10),
//           Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//             Text(label, style: TextStyle(
//                 color: isActive ? color : _textPri,
//                 fontSize: 12, fontWeight: FontWeight.w600)),
//             Text(desc, style: const TextStyle(color: _textSec, fontSize: 10),
//                 overflow: TextOverflow.ellipsis),
//           ])),
//           if (isActive) Icon(Icons.check_circle, color: color, size: 14),
//         ]),
//       ),
//     );
//   }

//   Widget _buildRuleToggle(String label, String key) {
//     return Padding(
//       padding: const EdgeInsets.only(bottom: 4),
//       child: Row(children: [
//         Expanded(child: Text(label,
//             style: const TextStyle(color: _textSec, fontSize: 12))),
//         Transform.scale(
//           scale: 0.75,
//           child: Switch(
//             value: _tableRules[key] ?? true,
//             onChanged: (v) => setState(() => _tableRules[key] = v),
//             activeColor: _blue,
//             inactiveThumbColor: _textSec,
//             inactiveTrackColor: _border,
//           ),
//         ),
//       ]),
//     );
//   }

//   Widget _buildTablesActionBar() {
//     final count = _selectedTableIndices.length;
//     return Container(
//       padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
//       decoration: const BoxDecoration(
//           color: _surface, border: Border(top: BorderSide(color: _border))),
//       child: Row(children: [
//         Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//           Text(
//               count == 0
//                   ? 'No tables selected'
//                   : '$count table${count > 1 ? "s" : ""} selected',
//               style: TextStyle(
//                   color: count > 0 ? _textPri : _textSec,
//                   fontSize: 13, fontWeight: FontWeight.w600)),
//           Text('Preset: $_tablePreset',
//               style: const TextStyle(color: _textSec, fontSize: 11)),
//         ]),
//         const Spacer(),
//         TextButton.icon(
//           onPressed: _tablesLoading ? null : _loadTables,
//           icon:  const Icon(Icons.refresh, size: 14),
//           label: const Text('Re-scan', style: TextStyle(fontSize: 12)),
//           style: TextButton.styleFrom(foregroundColor: _textSec),
//         ),
//         const SizedBox(width: 12),
//         ElevatedButton.icon(
//           onPressed: (count == 0 || _tablesFormatting) ? null : _applyTableFormatting,
//           icon: _tablesFormatting
//               ? const SizedBox(width: 14, height: 14,
//                   child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
//               : const Icon(Icons.auto_fix_high, size: 16),
//           label: Text(
//               _tablesFormatting ? 'Applying…'
//               : count == 0      ? 'Select tables above'
//               : 'Apply Formatting ($count)',
//               style: const TextStyle(fontSize: 13)),
//           style: ElevatedButton.styleFrom(
//             backgroundColor:        count > 0 ? _purple : _surface2,
//             foregroundColor:        count > 0 ? Colors.white : _textSec,
//             disabledBackgroundColor: _surface2,
//             padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
//             shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
//           ),
//         ),
//       ]),
//     );
//   }

//   // ─────────────────────────────────────────────────────────────────────────
//   // Tab 8: Document Blocks
//   // ─────────────────────────────────────────────────────────────────────────

//   Widget _buildBlocksTab(List<dynamic> blocks) {
//     if (blocks.isEmpty) {
//       return _buildEmptyState(Icons.article_outlined, 'No document content',
//           'The document could not be parsed or is empty.');
//     }
//     return ListView.builder(
//       padding: const EdgeInsets.all(24),
//       itemCount: blocks.length,
//       itemBuilder: (ctx, i) {
//         final block = blocks[i] as Map<String, dynamic>;
//         final type  = block['type']  as String? ?? 'paragraph';
//         final text  = block['text']  as String? ?? '';
//         final level = block['level'] as int?;

//         Color typeColor; IconData typeIcon; double leftPad = 0;
//         switch (type) {
//           case 'heading':
//             typeColor = _blue;   typeIcon = Icons.title;
//             leftPad   = ((level ?? 1) - 1) * 16.0;
//             break;
//           case 'list_item':
//             typeColor = _yellow; typeIcon = Icons.format_list_bulleted; leftPad = 16;
//             break;
//           case 'table':
//             typeColor = const Color(0xFFA855F7); typeIcon = Icons.table_chart_outlined;
//             break;
//           default:
//             typeColor = _textSec; typeIcon = Icons.short_text;
//         }
//         return Container(
//           margin: const EdgeInsets.only(bottom: 4),
//           padding: EdgeInsets.fromLTRB(16 + leftPad, 10, 16, 10),
//           decoration: BoxDecoration(
//               color: _surface, borderRadius: BorderRadius.circular(6),
//               border: Border(left: BorderSide(color: typeColor, width: 3))),
//           child: Row(children: [
//             SizedBox(width: 32,
//                 child: Text('${i + 1}',
//                     style: const TextStyle(
//                         color: _textSec, fontSize: 10, fontFamily: 'monospace'))),
//             Icon(typeIcon, color: typeColor, size: 14), const SizedBox(width: 10),
//             _Tag(type + (level != null ? ' H$level' : ''), typeColor),
//             const SizedBox(width: 10),
//             Expanded(child: Text(
//                 text.length > 120 ? '${text.substring(0, 120)}…' : text,
//                 style: TextStyle(
//                     color: type == 'heading' ? _textPri : _textSec,
//                     fontSize: type == 'heading' ? 13 : 12,
//                     fontWeight: type == 'heading'
//                         ? FontWeight.w600 : FontWeight.w400))),
//           ]),
//         );
//       },
//     );
//   }

//   // ─────────────────────────────────────────────────────────────────────────
//   // Tab 9: References
//   // ─────────────────────────────────────────────────────────────────────────

//   Widget _buildReferencesTab() {
//     final userId = context.read<AuthProvider>().userId ?? 0;
//     return SingleChildScrollView(
//       padding: const EdgeInsets.all(24),
//       child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//         Row(children: [
//           Container(
//             padding: const EdgeInsets.all(8),
//             decoration: BoxDecoration(
//                 color: _purple.withOpacity(0.15), borderRadius: BorderRadius.circular(8)),
//             child: const Icon(Icons.format_list_numbered, color: _purple, size: 20),
//           ),
//           const SizedBox(width: 12),
//           const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//             Text('Reference Formatter',
//                 style: TextStyle(
//                     color: _textPri, fontSize: 16, fontWeight: FontWeight.w700)),
//             Text('Detect, clean and reformat your References section',
//                 style: TextStyle(color: _textSec, fontSize: 12)),
//           ]),
//         ]),
//         const SizedBox(height: 8),
//         Container(
//           padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
//           decoration: BoxDecoration(
//               color: _purple.withOpacity(0.07), borderRadius: BorderRadius.circular(8),
//               border: Border.all(color: _purple.withOpacity(0.25))),
//           child: Row(children: [
//             const Icon(Icons.info_outline, color: _purple, size: 15),
//             const SizedBox(width: 10),
//             Expanded(
//               child: Text(
//                 'Rules are set by your university admin in the template. '
//                 'Press "Scan References" to preview, then "Format References" to apply.',
//                 style: TextStyle(
//                     color: _purple.withOpacity(0.85), fontSize: 12, height: 1.5),
//               ),
//             ),
//           ]),
//         ),
//         const SizedBox(height: 20),
//         ReferenceFormatterWidget(
//           documentId: widget.documentId,
//           userId: userId,
//         ),
//       ]),
//     );
//   }

//   // ── Action bar ────────────────────────────────────────────────────────────

//   Widget _buildActionBar(List<dynamic> allIssues, List<dynamic> oldIssues) {
//     final total  = allIssues.length + oldIssues.length;
//     final errors = allIssues.where((i) => (i as Map)['severity'] == 'error').length;
//     return Container(
//       padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
//       decoration: const BoxDecoration(
//           color: _surface, border: Border(top: BorderSide(color: _border))),
//       child: Row(children: [
//         Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//           Text('$total issues  ·  $errors errors',
//               style: const TextStyle(color: _textPri, fontSize: 13)),
//           const Text('Fix all issues to improve your score',
//               style: TextStyle(color: _textSec, fontSize: 11)),
//         ]),
//         const Spacer(),
//         TextButton(
//             onPressed: () => _showSnack('All issues ignored', _textSec),
//             child: const Text('Ignore All', style: TextStyle(color: _textSec))),
//         const SizedBox(width: 12),
//         ElevatedButton.icon(
//           onPressed: _isApplyingFix ? null : _applyAllFixes,
//           icon: _isApplyingFix
//               ? const SizedBox(width: 14, height: 14,
//                   child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
//               : const Icon(Icons.auto_fix_high, size: 16),
//           label: Text(_isApplyingFix ? 'Applying…' : 'Apply All Fixes'),
//           style: ElevatedButton.styleFrom(
//               backgroundColor: _purple, foregroundColor: _textPri,
//               padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12)),
//         ),
//       ]),
//     );
//   }

//   // ── Empty state ───────────────────────────────────────────────────────────

//   Widget _buildEmptyState(IconData icon, String title, String subtitle,
//       {Color color = _textSec, String? actionLabel, VoidCallback? onAction}) {
//     return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
//       Icon(icon, color: color.withOpacity(0.4), size: 56),
//       const SizedBox(height: 16),
//       Text(title,
//           style: TextStyle(color: color, fontSize: 16, fontWeight: FontWeight.w600)),
//       const SizedBox(height: 6),
//       Padding(
//           padding: const EdgeInsets.symmetric(horizontal: 48),
//           child: Text(subtitle,
//               style: const TextStyle(color: _textSec, fontSize: 12),
//               textAlign: TextAlign.center)),
//       if (actionLabel != null && onAction != null) ...[
//         const SizedBox(height: 16),
//         TextButton(onPressed: onAction,
//             child: Text(actionLabel, style: const TextStyle(color: _blue))),
//       ],
//     ]));
//   }
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Bullets Tab Content Widget
// // ─────────────────────────────────────────────────────────────────────────────

// class _BulletsTabContent extends StatefulWidget {
//   final int documentId;
//   final int userId;
//   const _BulletsTabContent({required this.documentId, required this.userId});
//   @override
//   State<_BulletsTabContent> createState() => _BulletsTabContentState();
// }

// class _BulletsTabContentState extends State<_BulletsTabContent> {
//   late Future<Map<String, dynamic>> _bulletsFuture;
//   final String _baseUrl = ApiConfig.getBaseUrl();
//   int? _applyingGroupIndex;

//   @override
//   void initState() {
//     super.initState();
//     _bulletsFuture = _analyzeBullets();
//   }

//   Future<Map<String, dynamic>> _analyzeBullets() async {
//     try {
//       final response = await http.get(Uri.parse(
//         '$_baseUrl/documents/analyze-bullets/${widget.documentId}?user_id=${widget.userId}',
//       ));
//       if (response.statusCode == 200) {
//         return json.decode(response.body) as Map<String, dynamic>;
//       }
//       return {'error': 'Failed to analyze bullets (${response.statusCode})'};
//     } catch (e) {
//       return {'error': e.toString()};
//     }
//   }

//   Future<void> _applyGroupBullets(
//       int groupIndex, List<Map<String, dynamic>> groupItems) async {
//     setState(() { _applyingGroupIndex = groupIndex; });
//     try {
//       final paraIndices =
//           groupItems.map((item) => item['index']).whereType<int>().toList();
//       if (paraIndices.isEmpty) {
//         _showSnack('No paragraph indices for this group.', _red);
//         setState(() { _applyingGroupIndex = null; });
//         return;
//       }
//       final resp = await http.post(
//         Uri.parse('$_baseUrl/documents/apply-fix/${widget.documentId}'
//             '?user_id=${widget.userId}&fix_type=apply_section_bullets'),
//         headers: {'Content-Type': 'application/json'},
//         body: jsonEncode({'para_indices': paraIndices}),
//       );
//       if (resp.statusCode == 200) {
//         _showSnack('Bullets applied to ${paraIndices.length} item(s)!', _green);
//         setState(() {
//           _bulletsFuture     = _analyzeBullets();
//           _applyingGroupIndex = null;
//         });
//       } else {
//         _showSnack('Failed: ${resp.body}', _red);
//         setState(() { _applyingGroupIndex = null; });
//       }
//     } catch (e) {
//       _showSnack('Error: $e', _red);
//       setState(() { _applyingGroupIndex = null; });
//     }
//   }

//   void _showSnack(String msg, Color color) {
//     if (!mounted) return;
//     ScaffoldMessenger.of(context)
//         .showSnackBar(SnackBar(content: Text(msg), backgroundColor: color));
//   }

//   @override
//   Widget build(BuildContext context) {
//     return FutureBuilder<Map<String, dynamic>>(
//       future: _bulletsFuture,
//       builder: (context, snapshot) {
//         if (snapshot.connectionState == ConnectionState.waiting) {
//           return const Center(
//               child: CircularProgressIndicator(
//                   valueColor: AlwaysStoppedAnimation(_blue)));
//         }
//         if (snapshot.hasError || snapshot.data?['error'] != null) {
//           return Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
//             const Icon(Icons.error_outline, size: 48, color: _red),
//             const SizedBox(height: 12),
//             const Text('Error analyzing bullets',
//                 style: TextStyle(color: _textPri, fontSize: 14)),
//           ]));
//         }

//         final data            = snapshot.data ?? {};
//         final detectedBullets = (data['detected_bullets'] as List<dynamic>? ?? [])
//             .map((e) => Map<String, dynamic>.from(e as Map)).toList();
//         final summary         = data['summary'] != null
//             ? Map<String, dynamic>.from(data['summary'] as Map)
//             : <String, dynamic>{};
//         final bulletGroups    = (data['bullet_groups'] as List<dynamic>? ?? [])
//             .map((group) => (group as List<dynamic>)
//                 .map((e) => Map<String, dynamic>.from(e as Map)).toList())
//             .toList();

//         if (detectedBullets.isEmpty && bulletGroups.isEmpty) {
//           final alreadyFormatted = (summary['total_detected'] ?? 0) == 0;
//           return Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
//             Icon(
//               alreadyFormatted
//                   ? Icons.check_circle_outline
//                   : Icons.format_list_bulleted_outlined,
//               size: 56,
//               color: alreadyFormatted ? _green : _textSec,
//             ),
//             const SizedBox(height: 16),
//             Text(
//               alreadyFormatted
//                   ? 'All lists are already formatted'
//                   : 'No unformatted lists detected',
//               style: TextStyle(
//                   color: alreadyFormatted ? _green : _textPri,
//                   fontSize: 15, fontWeight: FontWeight.w600),
//             ),
//             const SizedBox(height: 8),
//             Padding(
//               padding: const EdgeInsets.symmetric(horizontal: 40),
//               child: Text(
//                 alreadyFormatted
//                     ? 'Every list in this document already has bullet or numbered '
//                       'formatting applied. If you want to re-detect, delete the '
//                       'working copy from the server and re-upload.'
//                     : 'No list groups were detected in this document. '
//                       'The document may not contain any list-like content.',
//                 style: const TextStyle(color: _textSec, fontSize: 12, height: 1.5),
//                 textAlign: TextAlign.center,
//               ),
//             ),
//           ]));
//         }

//         return SingleChildScrollView(
//           padding: const EdgeInsets.all(24),
//           child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//             _buildBulletsSummary(summary),
//             const SizedBox(height: 24),
//             if (bulletGroups.isNotEmpty) ...[
//               const SizedBox(height: 8),
//               Row(children: [
//                 const Icon(Icons.format_list_bulleted, color: _blue, size: 18),
//                 const SizedBox(width: 8),
//                 const Text('Detected Bullet Groups',
//                     style: TextStyle(
//                         color: _textPri, fontSize: 16, fontWeight: FontWeight.w700)),
//                 const SizedBox(width: 8),
//                 Container(
//                   padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
//                   decoration: BoxDecoration(
//                       color: _blue.withOpacity(0.15),
//                       borderRadius: BorderRadius.circular(10)),
//                   child: Text('${bulletGroups.length}',
//                       style: const TextStyle(
//                           color: _blue, fontSize: 12, fontWeight: FontWeight.w700)),
//                 ),
//               ]),
//               const SizedBox(height: 6),
//               const Text(
//                   'Each group is a list that needs bullet formatting. '
//                   'Click "Apply Bullets" to format it.',
//                   style: TextStyle(color: _textSec, fontSize: 12)),
//               const SizedBox(height: 16),
//               ListView.separated(
//                 shrinkWrap: true,
//                 physics: const NeverScrollableScrollPhysics(),
//                 itemCount: bulletGroups.length,
//                 separatorBuilder: (_, __) => const SizedBox(height: 12),
//                 itemBuilder: (context, groupIndex) {
//                   final group      = bulletGroups[groupIndex];
//                   final isApplying = _applyingGroupIndex == groupIndex;
//                   return Container(
//                     decoration: BoxDecoration(
//                         color: _surface2.withOpacity(0.6),
//                         borderRadius: BorderRadius.circular(10),
//                         border: Border.all(color: _blue.withOpacity(0.35))),
//                     child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
//                       Container(
//                         padding: const EdgeInsets.symmetric(
//                             horizontal: 12, vertical: 10),
//                         decoration: BoxDecoration(
//                             color: _blue.withOpacity(0.08),
//                             borderRadius: const BorderRadius.only(
//                                 topLeft: Radius.circular(10),
//                                 topRight: Radius.circular(10))),
//                         child: Row(children: [
//                           const Icon(Icons.format_list_bulleted,
//                               color: _blue, size: 14),
//                           const SizedBox(width: 6),
//                           Text('Group ${groupIndex + 1}',
//                               style: const TextStyle(
//                                   color: _blue, fontSize: 13,
//                                   fontWeight: FontWeight.w700)),
//                           const SizedBox(width: 8),
//                           Container(
//                             padding: const EdgeInsets.symmetric(
//                                 horizontal: 7, vertical: 2),
//                             decoration: BoxDecoration(
//                                 color: _blue.withOpacity(0.18),
//                                 borderRadius: BorderRadius.circular(10)),
//                             child: Text(
//                                 '${group.length} item${group.length == 1 ? "" : "s"}',
//                                 style: const TextStyle(
//                                     color: _blue, fontSize: 10,
//                                     fontWeight: FontWeight.w600)),
//                           ),
//                         ]),
//                       ),
//                       Padding(
//                         padding: const EdgeInsets.fromLTRB(12, 10, 12, 0),
//                         child: Column(
//                           crossAxisAlignment: CrossAxisAlignment.start,
//                           children: group.asMap().entries.map((entry) {
//                             final itemText =
//                                 entry.value['text'] as String? ?? '';
//                             final conf =
//                                 (entry.value['confidence'] as num?)
//                                     ?.toDouble() ?? 0.0;
//                             Color dotColor = _yellow;
//                             if (conf > 0.8) dotColor = _green;
//                             if (conf < 0.5) dotColor = _red;
//                             return Padding(
//                               padding: const EdgeInsets.only(bottom: 6),
//                               child: Row(
//                                   crossAxisAlignment: CrossAxisAlignment.start,
//                                   children: [
//                                 Container(
//                                     margin: const EdgeInsets.only(
//                                         top: 5, right: 8),
//                                     width: 7, height: 7,
//                                     decoration: BoxDecoration(
//                                         color: dotColor,
//                                         shape: BoxShape.circle)),
//                                 Text('${entry.key + 1}. ',
//                                     style: const TextStyle(
//                                         color: _textSec, fontSize: 12)),
//                                 Expanded(child: Text(
//                                     itemText.length > 90
//                                         ? '${itemText.substring(0, 90)}...'
//                                         : itemText,
//                                     style: const TextStyle(
//                                         color: _textPri, fontSize: 12))),
//                               ]),
//                             );
//                           }).toList(),
//                         ),
//                       ),
//                       Padding(
//                         padding: const EdgeInsets.all(12),
//                         child: SizedBox(
//                           width: double.infinity,
//                           child: ElevatedButton.icon(
//                             onPressed: _applyingGroupIndex != null
//                                 ? null
//                                 : () => _applyGroupBullets(groupIndex, group),
//                             icon: isApplying
//                                 ? const SizedBox(width: 14, height: 14,
//                                     child: CircularProgressIndicator(
//                                         strokeWidth: 2, color: Colors.white))
//                                 : const Icon(Icons.auto_fix_high, size: 15),
//                             label: Text(
//                                 isApplying
//                                     ? 'Applying bullets…'
//                                     : 'Apply Bullets to This Group',
//                                 style: const TextStyle(fontSize: 12)),
//                             style: ElevatedButton.styleFrom(
//                               backgroundColor: _blue,
//                               foregroundColor: Colors.white,
//                               disabledBackgroundColor: _blue.withOpacity(0.35),
//                               padding: const EdgeInsets.symmetric(
//                                   horizontal: 14, vertical: 10),
//                               shape: RoundedRectangleBorder(
//                                   borderRadius: BorderRadius.circular(7)),
//                             ),
//                           ),
//                         ),
//                       ),
//                     ]),
//                   );
//                 },
//               ),
//             ],
//           ]),
//         );
//       },
//     );
//   }

//   Widget _buildBulletsSummary(Map<String, dynamic> summary) {
//     return Row(children: [
//       Expanded(child: _SummaryCard(
//           icon: Icons.format_list_bulleted, label: 'Detected',
//           value: '${summary['total_detected'] ?? 0}', color: _blue)),
//       const SizedBox(width: 12),
//       Expanded(child: _SummaryCard(
//           icon: Icons.check_circle, label: 'High Confidence',
//           value: '${summary['high_confidence'] ?? 0}', color: _green)),
//       const SizedBox(width: 12),
//       Expanded(child: _SummaryCard(
//           icon: Icons.warning, label: 'Medium',
//           value: '${summary['medium_confidence'] ?? 0}', color: _yellow)),
//       const SizedBox(width: 12),
//       Expanded(child: _SummaryCard(
//           icon: Icons.help_outline, label: 'Groups',
//           value: '${summary['total_groups'] ?? 0}', color: _purple)),
//     ]);
//   }
// }

// // ─────────────────────────────────────────────────────────────────────────────
// // Shared reusable widgets
// // ─────────────────────────────────────────────────────────────────────────────

// class _Tag extends StatelessWidget {
//   final String text; final Color color;
//   const _Tag(this.text, this.color);
//   @override
//   Widget build(BuildContext context) => Container(
//     padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
//     decoration: BoxDecoration(
//         color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(4),
//         border: Border.all(color: color.withOpacity(0.3))),
//     child: Text(text, style: TextStyle(
//         color: color, fontSize: 10,
//         fontWeight: FontWeight.w600, letterSpacing: 0.3)),
//   );
// }

// class _StatusBadge extends StatelessWidget {
//   final String status;
//   const _StatusBadge(this.status);
//   @override
//   Widget build(BuildContext context) {
//     final color = status == 'pass' ? _green : _red;
//     final icon  = status == 'pass'
//         ? Icons.check_circle_outline : Icons.cancel_outlined;
//     return Row(mainAxisSize: MainAxisSize.min, children: [
//       Icon(icon, color: color, size: 16), const SizedBox(width: 4),
//       Text(status.toUpperCase(),
//           style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w700)),
//     ]);
//   }
// }

// class _SummaryCard extends StatelessWidget {
//   final IconData icon;
//   final String label, value;
//   final Color color;
//   const _SummaryCard({
//     required this.icon, required this.label,
//     required this.value, required this.color,
//   });
//   @override
//   Widget build(BuildContext context) => Container(
//     decoration: BoxDecoration(
//         color: _surface2, borderRadius: BorderRadius.circular(8),
//         border: Border.all(color: color.withOpacity(0.3))),
//     padding: const EdgeInsets.all(12),
//     child: Column(children: [
//       Icon(icon, color: color, size: 20), const SizedBox(height: 8),
//       Text(value,
//           style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.w700)),
//       const SizedBox(height: 4),
//       Text(label, style: const TextStyle(color: _textSec, fontSize: 11)),
//     ]),
//   );
// }

// class _SummaryPill extends StatelessWidget {
//   final String label, value; final Color color;
//   const _SummaryPill(this.label, this.value, this.color);
//   @override
//   Widget build(BuildContext context) =>
//       Column(mainAxisSize: MainAxisSize.min, children: [
//         Text(value, style: TextStyle(
//             color: color, fontSize: 18, fontWeight: FontWeight.w800)),
//         Text(label, style: const TextStyle(color: _textSec, fontSize: 10)),
//       ]);
// }

// class _FixButton extends StatelessWidget {
//   final String label; final IconData icon;
//   final Color color;  final VoidCallback onTap;
//   const _FixButton({
//     required this.label, required this.icon,
//     required this.color, required this.onTap,
//   });
//   @override
//   Widget build(BuildContext context) => GestureDetector(
//     onTap: onTap,
//     child: Container(
//       padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
//       decoration: BoxDecoration(
//           color: color.withOpacity(0.10), borderRadius: BorderRadius.circular(6),
//           border: Border.all(color: color.withOpacity(0.3))),
//       child: Row(mainAxisSize: MainAxisSize.min, children: [
//         Icon(icon, color: color, size: 13), const SizedBox(width: 6),
//         Text(label, style: TextStyle(color: color, fontSize: 12)),
//       ]),
//     ),
//   );
// }

// class _StyleGroupHeader extends StatelessWidget {
//   final String label; final int count;
//   final IconData icon; final Color color;
//   const _StyleGroupHeader(this.label, this.count, this.icon, this.color);
//   @override
//   Widget build(BuildContext context) => Row(children: [
//     Icon(icon, color: color, size: 16), const SizedBox(width: 8),
//     Text(label, style: TextStyle(
//         color: color, fontSize: 13, fontWeight: FontWeight.w700)),
//     const SizedBox(width: 8),
//     Container(
//       padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
//       decoration: BoxDecoration(
//           color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(10)),
//       child: Text('$count', style: TextStyle(
//           color: color, fontSize: 11, fontWeight: FontWeight.w700))),
//   ]);
// }

// class _LegendItem extends StatelessWidget {
//   final String label, description; final Color color;
//   const _LegendItem(this.label, this.color, this.description);
//   @override
//   Widget build(BuildContext context) => Row(mainAxisSize: MainAxisSize.min, children: [
//     _Tag(label, color), const SizedBox(width: 6),
//     Text(description, style: const TextStyle(color: _textSec, fontSize: 11)),
//   ]);
// }

// class _DiffRow extends StatelessWidget {
//   final String label, text; final Color color;
//   const _DiffRow({required this.label, required this.text, required this.color});
//   @override
//   Widget build(BuildContext context) =>
//       Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
//         Container(
//           width: 72,
//           padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
//           decoration: BoxDecoration(
//               color: color.withOpacity(0.10), borderRadius: BorderRadius.circular(4)),
//           child: Text(label, style: TextStyle(
//               color: color, fontSize: 10, fontWeight: FontWeight.w700))),
//         const SizedBox(width: 10),
//         Expanded(child: Text(
//             text.length > 120 ? '${text.substring(0, 120)}…' : text,
//             style: TextStyle(
//                 color: color.withOpacity(0.85),
//                 fontSize: 11, fontFamily: 'monospace'))),
//       ]);
// }

// class _FeatureChip extends StatelessWidget {
//   final String label;
//   final Color  color;
//   const _FeatureChip(this.label, this.color, {Key? key}) : super(key: key);

//   @override
//   Widget build(BuildContext context) => Container(
//     padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
//     decoration: BoxDecoration(
//       color: color.withOpacity(0.10),
//       borderRadius: BorderRadius.circular(20),
//       border: Border.all(color: color.withOpacity(0.25)),
//     ),
//     child: Text(label, style: TextStyle(
//         color: color.withOpacity(0.85),
//         fontSize: 10, fontWeight: FontWeight.w500)),
//   );
// }

// frontend/lib/screens/analyze_screen.dart
//
// CHANGES vs previous version (Tables tab only — everything else is untouched):
//
//  1. _buildTablesSidebar()
//       • Removed the three preset-picker buttons (Academic / Professional / Minimal)
//       • Removed the FORMAT RULES toggles
//       • Now shows a read-only "Template Style" card that reflects what the
//         admin saved, with a "Configured by template" badge.
//       • Keeps the section header so the panel still looks intentional.
//
//  2. _buildTablesActionBar()
//       • Action button now reads "Apply Template Style (N)" instead of
//         "Apply Formatting (N)".
//       • The bottom-left label no longer says "Preset: academic" — it says
//         "Style: from template" so the user knows where the rules come from.
//       • Calls _applyTemplateFormatting() instead of _applyTableFormatting().
//
//  3. _applyTemplateFormatting()   ← NEW method
//       • Calls POST /api/tables/format-with-template/{documentId}
//         with the widget.templateId that is already passed into AnalyzeScreen.
//       • On success clears selection, reloads tables, shows snack — identical
//         UX to the old preset flow.
//       • The OLD _applyTableFormatting() is kept unchanged (still used by
//         nothing in the UI, but left so no dead-code warnings break the build
//         — remove it later if desired).
//
//  Nothing else in this file was altered.

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../providers/auth_provider.dart';
import '../config/api_config.dart';
import '../widgets/app_sidebar.dart';
import '../widgets/export_dialog.dart';
import '../widgets/freeform_analyze_dialogs.dart';
import '../providers/document_provider.dart';
import 'package:frontend/providers/qr_service.dart';
import '../widgets/image_issue_card_enhanced.dart';
import '../widgets/document_preview_panel.dart';
import '../widgets/image_replacement_dialog.dart';
import '../models/json_parse.dart';
import '../services/image_replacement_service.dart';
import ' image_formatter_screen.dart';
import '../widgets/reference_formatter_widget.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Color palette — follows ThemeProvider (light / dark)
// ─────────────────────────────────────────────────────────────────────────────
AppPalette _ap = AppPalette.dark;

Color get _bg => _ap.scaffold;
Color get _surface => _ap.surface;
Color get _surface2 => _ap.surfaceElevated;
Color get _border => _ap.border;
Color get _textPri => _ap.textPrimary;
Color get _textSec => _ap.textSecondary;
const _green = Color(0xFF10B981);
const _yellow = Color(0xFFF59E0B);
const _red = Color(0xFFEF4444);
const _blue = Color(0xFF4A9EFF);
const _purple = Color(0xFF6366F1);
const _orange = Color(0xFFF97316);

Color _layerColor(String? layer) {
  switch (layer) {
    case 'exact':
      return _green;
    case 'synonym':
      return _blue;
    case 'fuzzy':
      return _yellow;
    case 'semantic':
      return const Color(0xFFA855F7);
    default:
      return _red;
  }
}

Color _statusColor(String status) {
  switch (status) {
    case 'found':
      return _green;
    case 'missing':
      return _red;
    case 'wrong_order':
      return _yellow;
    case 'empty':
      return _yellow;
    default:
      return _textSec;
  }
}

double? _safeDouble(dynamic value) {
  if (value == null) return null;
  if (value is double) return value;
  if (value is int) return value.toDouble();
  if (value is String) return double.tryParse(value);
  return null;
}

// ─────────────────────────────────────────────────────────────────────────────
// TABLE DATA MODELS
// ─────────────────────────────────────────────────────────────────────────────

class _TableIssue {
  final String code;
  final String message;
  final String severity;
  final int? row;
  final int? col;
  final String? action;

  const _TableIssue({
    required this.code,
    required this.message,
    required this.severity,
    this.row,
    this.col,
    this.action,
  });

  factory _TableIssue.fromJson(Map<String, dynamic> j) => _TableIssue(
    code: j['code'] as String? ?? '',
    message: j['message'] as String? ?? '',
    severity: j['severity'] as String? ?? 'info',
    row: (j['row'] as num?)?.toInt(),
    col: (j['col'] as num?)?.toInt(),
    action: j['action'] as String?,
  );

  bool get isFillableEmptyCell =>
      code == 'EMPTY_CELL' &&
      action == 'fill_cell' &&
      row != null &&
      col != null;

  bool get isNormalizeFontIssue =>
      code == 'FONT_INCONSISTENT' && action == 'normalize_font';
}

class _TableMeta {
  final int index;
  final String label;
  final int rowCount;
  final int colCount;
  final bool hasHeaderRow;
  final List<_TableIssue> issues;
  final List<List<String>> previewRows;
  final String source;

  const _TableMeta({
    required this.index,
    required this.label,
    required this.rowCount,
    required this.colCount,
    required this.hasHeaderRow,
    required this.issues,
    required this.previewRows,
    required this.source,
  });

  factory _TableMeta.fromJson(Map<String, dynamic> j) {
    final rawIssues = j['issues'] as List<dynamic>? ?? [];
    final rawPreview = j['preview_rows'] as List<dynamic>? ?? [];
    return _TableMeta(
      index: (j['index'] as num?)?.toInt() ?? 0,
      label: j['label'] as String? ?? 'Table',
      rowCount: (j['row_count'] as num?)?.toInt() ?? 0,
      colCount: (j['col_count'] as num?)?.toInt() ?? 0,
      hasHeaderRow: j['has_header_row'] as bool? ?? false,
      source: j['source'] as String? ?? 'docx',
      issues:
          rawIssues
              .map((e) => _TableIssue.fromJson(e as Map<String, dynamic>))
              .toList(),
      previewRows:
          rawPreview
              .map(
                (row) =>
                    (row as List<dynamic>).map((c) => c.toString()).toList(),
              )
              .toList(),
    );
  }

  int get issueCount => issues.length;
  bool get isClean => issues.isEmpty;
}

// ─────────────────────────────────────────────────────────────────────────────
// Main screen
// ─────────────────────────────────────────────────────────────────────────────
class AnalyzeScreen extends StatefulWidget {
  final int documentId;
  final String documentName;
  final int templateId;
  final String templateName;
  /// When true, uses /documents/analyze-freeform and AI-guided export UI.
  final bool freeformAnalysis;

  const AnalyzeScreen({
    Key? key,
    required this.documentId,
    required this.documentName,
    required this.templateId,
    required this.templateName,
    this.freeformAnalysis = false,
  }) : super(key: key);

  @override
  State<AnalyzeScreen> createState() => _AnalyzeScreenState();
}

class _AnalyzeScreenState extends State<AnalyzeScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  late Future<Map<String, dynamic>> _analysisFuture;
  String _baseUrl = '';
  int _selectedSidebarIndex = 2;
  bool _isApplyingFix = false;
  bool _isFixApplied = false;
  bool _isDownloading = false;

  final Set<int> _expandedSections = {};
  final Set<String> _fixingStyleIssues = {};

  // Style issues — lifted out of FutureBuilder so fixes can remove them
  // instantly without triggering a full re-analysis.
  List<dynamic> _styleIssues = [];
  bool _styleIssuesInitialized = false;

  /// Freeform path: suggested auto-apply fixes + manual notes from analyze-freeform.
  List<Map<String, dynamic>> _freeformSuggestedFixes = [];
  List<Map<String, dynamic>> _freeformManualNotes = [];

  // Document review preview state
  List<Map<String, dynamic>> _previewBlocks = [];
  List<Map<String, dynamic>> _pipelineIssues = [];
  final Map<String, String> _appliedFixes = {};
  final Set<String> _ignoredIssueIds = {};
  final Set<String> _resolvedIssueIds = {};

  // ── Heading style check state ─────────────────────────────────────────────
  List<dynamic> _headingStyleResults = [];
  bool _headingStyleLoading = false;
  String? _headingStyleError;
  final Set<String> _applyingHeadingStyle = {};
  bool _headingStyleLoaded = false;
  bool _stylesNotApplied = true;
  bool _applyingTemplateStyles = false;

  // ── Template heading analysis (from analyze response) ─────────────────────
  List<Map<String, dynamic>> _templateHeadingMatches = [];
  final Set<String> _applyingTemplateHeadingFixes = {};
  final Set<String> _appliedTemplateHeadingFixes = {};
  bool _applyingAllTemplateHeadings = false;

  // ── Paragraph style check state ───────────────────────────────────────────
  List<dynamic> _paragraphStyleIssues = [];
  bool _paragraphStyleLoading = false;
  String? _paragraphStyleError;
  bool _paragraphStyleLoaded = false;
  bool _applyingAllParaStyle = false;

  // ── Document lists (TOC / LOT / LOF) state ────────────────────────────────
  Map<String, dynamic> _tocData = {};
  bool _tocLoading = false;
  String? _tocError;
  bool _tocLoaded = false;
  bool _applyingTocStyle = false;
  bool _addingToc = false;
  bool _generatingLists = false;
  bool _includeToc = false;
  bool _includeLot = false;
  bool _includeLof = false;

  // ── Content check state ───────────────────────────────────────────────────
  List<dynamic> _contentIssues = [];
  bool _contentLoading = false;
  String? _contentError;
  bool _contentLoaded = false;
  int _totalSections = 0;

  // ── Tables tab state ──────────────────────────────────────────────────────
  List<_TableMeta> _tables = [];
  bool _tablesLoading = false;
  bool _tablesFormatting = false;
  String? _tablesError;
  String? _tablesSuccess;
  final Set<int> _selectedTableIndices = {};
  // _tablePreset / _tableRules kept for the legacy _applyTableFormatting()
  // which is no longer called from the UI but left for safety.
  String _tablePreset = 'academic';
  final Set<int> _expandedTableCards = {};
  Map<String, bool> _tableRules = {
    'header_bold': true,
    'banded_rows': true,
    'borders': true,
    'center_table': true,
    'repeat_header': true,
    'auto_fit': true,
  };

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 9, vsync: this);
    _tabController.addListener(_onAnalysisTabChanged);
    _baseUrl = ApiConfig.getBaseUrl();
    _analysisFuture = _fetchAnalysis();
    // Preload table issues so the Tables tab badge has a real count.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _loadTables();
    });
  }

  void _onAnalysisTabChanged() {
    if (_tabController.indexIsChanging) return;
    // Tables tab (after Image Relevance)
    if (_tabController.index == 5) {
      if (!_tablesLoading) {
        _loadTables();
      }
      return;
    }
    // Document Lists tab
    if (_tabController.index == 8) {
      _loadTocCheck();
    }
  }

  @override
  void dispose() {
    _tabController.removeListener(_onAnalysisTabChanged);
    _tabController.dispose();
    super.dispose();
  }

  String get _imageHostBase {
    final uri = Uri.tryParse(_baseUrl);
    if (uri != null) return '${uri.scheme}://${uri.host}:${uri.port}';
    return _baseUrl.split('/api').first;
  }

  String _issueCategory(Map<dynamic, dynamic> issue) {
    return (issue['category'] as String? ??
            issue['function'] as String? ??
            '')
        .toLowerCase();
  }

  bool _isImageRelevanceIssue(Map<dynamic, dynamic> issue) {
    final cat = _issueCategory(issue);
    return cat == 'image relevance' || cat == 'image_relevance';
  }

  bool _isImageEthicsIssue(Map<dynamic, dynamic> issue) {
    final cat = _issueCategory(issue);
    return cat == 'image ethics' || cat == 'image_ethics';
  }

  List<dynamic> _issuesForFunction(List<dynamic> issues, String func) {
    final needle = func.toLowerCase().replaceAll(' ', '_');
    return issues.where((i) {
      final m = i as Map;
      final fn = (m['function'] as String? ?? '').toLowerCase().replaceAll(' ', '_');
      final cat = (m['category'] as String? ?? '').toLowerCase().replaceAll(' ', '_');
      final type = (m['type'] as String? ?? '').toLowerCase().replaceAll(' ', '_');
      return fn == needle || cat == needle || type == needle;
    }).toList();
  }

  /// Issues still open (not ignored / not resolved after fix or image replace).
  List<dynamic> _visibleIssues(List<dynamic> issues) {
    return issues.where((i) {
      final id = (i as Map)['issue_id'] as String? ?? '';
      return !_ignoredIssueIds.contains(id) && !_resolvedIssueIds.contains(id);
    }).toList();
  }

  List<Map<String, dynamic>> _asBlockList(List<dynamic> raw) {
    if (raw.isEmpty) return [];
    if (raw.first is Map) {
      return raw.map((b) => Map<String, dynamic>.from(b as Map)).toList();
    }
    return raw.asMap().entries.map((e) {
      return {
        'paragraph_id': 'p${e.key}',
        'type': 'paragraph',
        'text': e.value.toString(),
        'page': 1,
      };
    }).toList();
  }

  void _seedPreviewData(Map<String, dynamic> data) {
    final blocks = _asBlockList(
      data['document_blocks'] as List<dynamic>? ??
          data['document_content'] as List<dynamic>? ??
          [],
    );
    final issues =
        (data['issues'] as List<dynamic>? ?? [])
            .map((i) => Map<String, dynamic>.from(i as Map))
            .toList();
    final headingMatches =
        (data['template_heading_matches'] as List<dynamic>? ?? [])
            .map((m) => Map<String, dynamic>.from(m as Map))
            .toList();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      setState(() {
        _previewBlocks = blocks;
        _pipelineIssues = issues;
        _templateHeadingMatches = headingMatches;
        _appliedTemplateHeadingFixes.clear();
      });
    });
  }

  void _mergeWorkingDocumentState(
    Map<String, dynamic> data, {
    String? pid,
    String? suggestion,
    String? issueId,
  }) {
    if (!mounted) return;
    setState(() {
      if (issueId != null && issueId.isNotEmpty) {
        _resolvedIssueIds.add(issueId);
      }
      if (pid != null && pid.isNotEmpty && suggestion != null && suggestion.isNotEmpty) {
        _appliedFixes[pid] = suggestion;
      }
      final blocks = data['document_blocks'] as List<dynamic>?;
      if (blocks != null && blocks.isNotEmpty) {
        _previewBlocks = blocks
            .map((b) => Map<String, dynamic>.from(b as Map))
            .toList();
      }
      _isFixApplied = true;
    });
  }

  int _headingLevelFromMatch(Map<String, dynamic> match) {
    final fromExpected = match['expected_level'];
    if (fromExpected is num) return fromExpected.toInt();
    final level = (match['level'] as String? ?? 'h1').toLowerCase();
    final m = RegExp(r'h(\d)').firstMatch(level);
    return m != null ? int.tryParse(m.group(1)!) ?? 1 : 1;
  }

  List<Map<String, dynamic>> get _visibleTemplateHeadingMatches =>
      _templateHeadingMatches.where((m) {
        if (m['is_heading'] == true) return true;
        // Keep discarded Claude extras visible so the user can reverse the decision
        return m['source'] == 'claude_only' && m['user_decision'] == 'discard';
      }).toList();

  List<Map<String, dynamic>> get _fixableTemplateHeadingMatches =>
      _visibleTemplateHeadingMatches.where((m) {
        final pid = m['paragraph_id'] as String? ?? '';
        if (pid.isEmpty) return false;
        if (_appliedTemplateHeadingFixes.contains(pid)) return false;
        // Claude extras must be Keep'd before style apply / Apply All
        final decision = (m['user_decision'] as String? ?? '').toLowerCase();
        if (decision == 'pending' || decision == 'discard') return false;
        if ((m['fix_status'] as String? ?? '') == 'awaiting_confirmation') {
          return false;
        }
        return m['fix_needed'] == true;
      }).toList();

  Future<void> _decideExtraHeading(
    Map<String, dynamic> match,
    String decision,
  ) async {
    final pid = match['paragraph_id'] as String? ?? '';
    if (pid.isEmpty) return;

    setState(() => _applyingTemplateHeadingFixes.add(pid));
    try {
      final auth = context.read<AuthProvider>();
      final level = _headingLevelFromMatch(match);
      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/documents/heading-decision/${widget.documentId}?user_id=${auth.userId}',
        ),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'paragraph_id': pid,
          'decision': decision,
          'heading_level': level,
          'apply_style': decision == 'keep',
        }),
      );

      if (resp.statusCode == 200) {
        final data = json.decode(resp.body) as Map<String, dynamic>;
        if (data['document_blocks'] != null) {
          _mergeWorkingDocumentState(data);
        }
        setState(() {
          final idx = _templateHeadingMatches.indexWhere(
            (m) => m['paragraph_id'] == pid,
          );
          if (idx != -1) {
            if (decision == 'keep') {
              _appliedTemplateHeadingFixes.add(pid);
              _templateHeadingMatches[idx] = {
                ..._templateHeadingMatches[idx],
                'user_decision': 'keep',
                'is_heading': true,
                'fix_needed': false,
                'fix_status': 'ok',
                'status': 'ok',
                'current_type': 'heading',
                'current_level': level,
                'fix_description':
                    'Kept as Heading $level (detected by Claude; not in template).',
              };
            } else {
              _appliedTemplateHeadingFixes.remove(pid);
              _templateHeadingMatches[idx] = {
                ..._templateHeadingMatches[idx],
                'user_decision': 'discard',
                'is_heading': false,
                'fix_needed': false,
                'fix_status': 'discarded_by_user',
                'status': 'discarded',
                'current_type': 'paragraph',
                'fix_description':
                    'Discarded — treated as body text (not in template).',
              };
            }
          }
        });
        _showSnack(
          decision == 'keep'
              ? 'Heading kept and style applied!'
              : 'Heading discarded.',
          decision == 'keep' ? _green : _textSec,
        );
      } else {
        _showSnack('Decision failed: ${resp.body}', _red);
      }
    } catch (e) {
      _showSnack('Error: $e', _red);
    } finally {
      if (mounted) {
        setState(() => _applyingTemplateHeadingFixes.remove(pid));
      }
    }
  }

  Future<void> _applyTemplateHeadingFix(Map<String, dynamic> match) async {
    final pid = match['paragraph_id'] as String? ?? '';
    if (pid.isEmpty) return;
    final decision = (match['user_decision'] as String? ?? '').toLowerCase();
    if (match['source'] == 'claude_only' &&
        (decision == 'pending' || decision.isEmpty || decision == 'discard')) {
      _showSnack(
        'Confirm this Claude-detected heading with Keep first.',
        _yellow,
      );
      return;
    }

    setState(() => _applyingTemplateHeadingFixes.add(pid));
    try {
      final auth = context.read<AuthProvider>();
      final level = _headingLevelFromMatch(match);
      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/documents/apply-content-fix/${widget.documentId}?user_id=${auth.userId}',
        ),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'fix_type': 'heading',
          'paragraph_id': pid,
          'heading_level': level,
        }),
      );

      if (resp.statusCode == 200) {
        final data = json.decode(resp.body) as Map<String, dynamic>;
        _mergeWorkingDocumentState(data);
        setState(() {
          _appliedTemplateHeadingFixes.add(pid);
          final idx = _templateHeadingMatches.indexWhere(
            (m) => m['paragraph_id'] == pid,
          );
          if (idx != -1) {
            _templateHeadingMatches[idx] = {
              ..._templateHeadingMatches[idx],
              'fix_needed': false,
              'fix_status': 'ok',
              'status': 'ok',
              'current_type': 'heading',
              'current_level': level,
            };
          }
          _pipelineIssues.removeWhere(
            (i) =>
                (i['issue_id'] as String? ?? '') == 'heading_match_$pid' ||
                ((i['paragraph_id'] as String? ?? '') == pid &&
                    (i['source'] as String? ?? '') ==
                        'template_heading_analysis'),
          );
        });
        _showSnack('Heading style applied!', _green);
      } else {
        _showSnack('Fix failed: ${resp.body}', _red);
      }
    } catch (e) {
      _showSnack('Error: $e', _red);
    } finally {
      if (mounted) {
        setState(() => _applyingTemplateHeadingFixes.remove(pid));
      }
    }
  }

  Future<void> _applyAllTemplateHeadingFixes() async {
    final fixable = _fixableTemplateHeadingMatches;
    if (fixable.isEmpty) {
      _showSnack('No heading fixes to apply.', _textSec);
      return;
    }

    setState(() => _applyingAllTemplateHeadings = true);
    var applied = 0;
    try {
      for (final match in fixable) {
        final pid = match['paragraph_id'] as String? ?? '';
        if (pid.isEmpty || _appliedTemplateHeadingFixes.contains(pid)) continue;

        final auth = context.read<AuthProvider>();
        final level = _headingLevelFromMatch(match);
        final resp = await http.post(
          Uri.parse(
            '$_baseUrl/documents/apply-content-fix/${widget.documentId}?user_id=${auth.userId}',
          ),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'fix_type': 'heading',
            'paragraph_id': pid,
            'heading_level': level,
          }),
        );

        if (resp.statusCode == 200) {
          final data = json.decode(resp.body) as Map<String, dynamic>;
          _mergeWorkingDocumentState(data);
          setState(() {
            _appliedTemplateHeadingFixes.add(pid);
            final idx = _templateHeadingMatches.indexWhere(
              (m) => m['paragraph_id'] == pid,
            );
            if (idx != -1) {
              _templateHeadingMatches[idx] = {
                ..._templateHeadingMatches[idx],
                'fix_needed': false,
                'fix_status': 'ok',
                'status': 'ok',
                'current_type': 'heading',
                'current_level': level,
              };
            }
            _pipelineIssues.removeWhere(
              (i) =>
                  (i['issue_id'] as String? ?? '') == 'heading_match_$pid' ||
                  ((i['paragraph_id'] as String? ?? '') == pid &&
                      (i['source'] as String? ?? '') ==
                          'template_heading_analysis'),
            );
          });
          applied++;
        }
      }
      _showSnack(
        applied > 0
            ? 'Applied $applied heading fix${applied == 1 ? '' : 'es'}!'
            : 'No heading fixes were applied.',
        applied > 0 ? _green : _yellow,
      );
    } catch (e) {
      _showSnack('Error: $e', _red);
    } finally {
      if (mounted) setState(() => _applyingAllTemplateHeadings = false);
    }
  }

  Future<bool> _applyContentFixToBackend(
    Map<String, dynamic> issue,
    String correctedText,
  ) async {
    final auth = context.read<AuthProvider>();
    final pid = issue['paragraph_id'] as String? ?? '';
    final issueId = issue['issue_id'] as String? ?? '';
    final fn = (issue['function'] as String? ?? issue['category'] as String? ?? '').toLowerCase();
    final issueType = (issue['type'] as String? ?? '').toLowerCase();
    final isHeadingFix = fn.contains('format') && issueType == 'heading_style';
    final isBulletFix = issueType == 'missing_bullets';
    final isParaRel = fn.contains('para') && fn.contains('relevance');

    if (isParaRel) {
      _showSnack(
        'Paragraph moves are structural — reformat in Word or use Apply All Fixes for styles.',
        _yellow,
      );
      return false;
    }

    if (!isBulletFix && pid.isEmpty) return false;

    final body = <String, dynamic>{
      'paragraph_id': pid,
      'original': issue['original'] ?? issue['current'] ?? '',
      'suggestion': issue['suggestion'] ?? correctedText,
    };
    if (isHeadingFix) {
      body['fix_type'] = 'heading';
      body['heading_level'] = issue['heading_level'] ?? _inferHeadingLevel(issue['suggestion'] as String? ?? correctedText);
    } else if (isBulletFix) {
      body['fix_type'] = 'bullets';
      body['para_indices'] = issue['para_indices'] ??
          (issue['fix_details'] as Map<String, dynamic>?)?['para_indices'] ??
          [];
    }
    try {
      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/documents/apply-content-fix/${widget.documentId}?user_id=${auth.userId}',
        ),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      );
      if (resp.statusCode == 200) {
        final data = json.decode(resp.body) as Map<String, dynamic>;
        _mergeWorkingDocumentState(
          data,
          pid: pid,
          suggestion: issue['suggestion'] as String? ?? correctedText,
          issueId: issueId,
        );
        return true;
      }
      _showSnack('Fix failed: ${resp.body}', _red);
      return false;
    } catch (e) {
      _showSnack('Error applying fix: $e', _red);
      return false;
    }
  }

  void _handleImageReplaceSuccess(Map<String, dynamic> result, {String? issueId}) {
    final imageIndex = jsonIntOr(result['image_index'], -1);
    final imageId = result['image_id'] as String? ?? '';
    final newPath = result['image_path'] as String? ?? '';
    final cleared = result['cleared'] == true;
    final cacheBust = DateTime.now().millisecondsSinceEpoch;

    final blocks = result['document_blocks'] as List<dynamic>?;
    if (blocks != null && blocks.isNotEmpty) {
      _mergeWorkingDocumentState(result, issueId: issueId);
    }

    setState(() {
      if (cleared) {
        for (final i in _pipelineIssues) {
          final fn = (i['function'] as String? ?? i['category'] as String? ?? '').toLowerCase();
          final idx = jsonInt(i['image_index']);
          final iid = i['image_id'] as String? ?? '';
          final matchesImage = (imageIndex >= 0 && idx == imageIndex) ||
              (imageId.isNotEmpty && iid == imageId) ||
              (imageId.isEmpty && imageIndex < 0 &&
                  (fn.contains('image_relevance') || fn.contains('image_ethics')));
          if (matchesImage &&
              (fn.contains('image_relevance') ||
                  fn.contains('image_ethics') ||
                  fn.contains('image ethics') ||
                  fn.contains('image relevance'))) {
            final id = i['issue_id'] as String? ?? '';
            if (id.isNotEmpty) _resolvedIssueIds.add(id);
          }
        }
        // Also resolve the specific card that triggered replace
        if (issueId != null && issueId.isNotEmpty) {
          _resolvedIssueIds.add(issueId);
        }
      } else if (issueId != null && issueId.isNotEmpty) {
        _resolvedIssueIds.add(issueId);
      }
      for (final block in _previewBlocks) {
        if (jsonIntOr(block['image_index'], -1) == imageIndex && newPath.isNotEmpty) {
          block['image_path'] = '$newPath?v=$cacheBust';
        }
      }
      _isFixApplied = true;
    });
    _showSnack(
      cleared ? 'Image verified — issue cleared' : 'Image replaced successfully',
      _green,
    );
  }

  bool _isImageIssueFn(String fn) {
    final f = fn.toLowerCase();
    return f.contains('image_relevance') ||
        f.contains('image_ethics') ||
        f.contains('image ethics') ||
        f.contains('image relevance');
  }

  void _handleImageRemoveSuccess(Map<String, dynamic> result, {String? issueId}) {
    final imageIndex = jsonIntOr(result['image_index'], -1);
    final imageId = result['image_id'] as String? ?? '';

    final blocks = result['document_blocks'] as List<dynamic>?;
    if (blocks != null && blocks.isNotEmpty) {
      _mergeWorkingDocumentState(result, issueId: issueId);
    }

    setState(() {
      for (final i in _pipelineIssues) {
        final fn = (i['function'] as String? ?? i['category'] as String? ?? '').toLowerCase();
        if (!_isImageIssueFn(fn)) continue;
        final idx = jsonIntOr(i['image_index'], -1);
        final iid = i['image_id'] as String? ?? '';
        final matches = (imageIndex >= 0 && idx == imageIndex) ||
            (imageId.isNotEmpty && iid == imageId);
        if (matches) {
          final id = i['issue_id'] as String? ?? '';
          if (id.isNotEmpty) _resolvedIssueIds.add(id);
        } else if (imageIndex >= 0 && idx > imageIndex) {
          // DOCX image order shifted after removal — keep later issues aligned
          final newIdx = idx - 1;
          i['image_index'] = newIdx;
          i['image_id'] = 'img$newIdx';
        }
      }
      if (issueId != null && issueId.isNotEmpty) {
        _resolvedIssueIds.add(issueId);
      }
      if (blocks == null || blocks.isEmpty) {
        _previewBlocks.removeWhere(
          (b) => jsonIntOr(b['image_index'], -1) == imageIndex,
        );
        for (final block in _previewBlocks) {
          final idx = jsonIntOr(block['image_index'], -1);
          if (idx > imageIndex) {
            final newIdx = idx - 1;
            block['image_index'] = newIdx;
            block['image_id'] = 'img$newIdx';
          }
        }
      }
      _isFixApplied = true;
    });
    _showSnack('Image removed from document', _green);
  }

  int _inferHeadingLevel(String text) {
    final match = RegExp(r'heading\s*(\d)', caseSensitive: false).firstMatch(text);
    if (match != null) return int.tryParse(match.group(1)!) ?? 1;
    return 1;
  }

  void _handlePreviewApplyFix(String issueId, String correctedText) {
    final issue = _pipelineIssues.firstWhere(
      (i) => i['issue_id'] == issueId,
      orElse: () => {},
    );
    if (issue.isEmpty) return;
    final pid = issue['paragraph_id'] as String? ?? '';
    setState(() {
      if (pid.isNotEmpty) _appliedFixes[pid] = correctedText;
      _ignoredIssueIds.remove(issueId);
      _isFixApplied = true;
    });
    _applyContentFixToBackend(issue, correctedText).then((ok) {
      if (!ok && mounted) {
        setState(() => _resolvedIssueIds.remove(issueId));
      }
    });
  }

  void _handlePreviewIgnore(String issueId) {
    setState(() => _ignoredIssueIds.add(issueId));
  }

  Future<void> _applyAllFixesAndStyles() async {
    setState(() => _isApplyingFix = true);
    try {
      final auth = context.read<AuthProvider>();
      final fixes = <Map<String, dynamic>>[];

      for (final i in _pipelineIssues) {
        final pid = i['paragraph_id'] as String? ?? '';
        final issueId = i['issue_id'] as String? ?? '';
        if (_ignoredIssueIds.contains(issueId) ||
            _resolvedIssueIds.contains(issueId)) {
          continue;
        }
        final fn =
            (i['function'] as String? ?? i['category'] as String? ?? '')
                .toLowerCase();
        final itype = (i['type'] as String? ?? '').toLowerCase();

        // Heading style fixes
        if ((fn.contains('format') || fn.contains('style')) &&
            (itype == 'heading_style' || itype == 'heading')) {
          if (pid.isEmpty) continue;
          fixes.add({
            'paragraph_id': pid,
            'fix_type': 'heading',
            'type': 'heading_style',
            'heading_level': i['heading_level'] ??
                _inferHeadingLevel(i['suggestion'] as String? ?? ''),
          });
          continue;
        }

        // Bullet / list fixes
        if (itype == 'missing_bullets' ||
            itype == 'list_formatting' ||
            (i['fix_type'] as String? ?? '') == 'apply_section_bullets') {
          final indices = <int>[];
          final rawIndices = i['para_indices'];
          if (rawIndices is List) {
            for (final v in rawIndices) {
              if (v is int) {
                indices.add(v);
              } else if (v is num) {
                indices.add(v.toInt());
              }
            }
          }
          final details = i['fix_details'];
          if (indices.isEmpty && details is Map) {
            final di = details['para_indices'];
            if (di is List) {
              for (final v in di) {
                if (v is int) {
                  indices.add(v);
                } else if (v is num) {
                  indices.add(v.toInt());
                }
              }
            }
          }
          if (indices.isEmpty && pid.isNotEmpty) {
            final m = RegExp(r'^p(\d+)$').firstMatch(pid);
            if (m != null) indices.add(int.parse(m.group(1)!));
          }
          fixes.add({
            'paragraph_id': pid,
            'fix_type': 'apply_section_bullets',
            'type': itype.isEmpty ? 'missing_bullets' : itype,
            'para_indices': indices,
            'fix_details': {'para_indices': indices},
          });
          continue;
        }

        // Grammar / content text fixes
        if (fn.contains('grammar') &&
            (i['suggestion'] as String? ?? '').isNotEmpty &&
            pid.isNotEmpty) {
          fixes.add({
            'paragraph_id': pid,
            'original': i['original'] ?? i['current'] ?? '',
            'suggestion':
                _appliedFixes[pid] ?? i['suggestion'],
          });
        }
      }

      // Also include template heading mismatches awaiting style
      for (final match in _templateHeadingMatches) {
        if (match is! Map) continue;
        if (match['fix_needed'] != true) continue;
        if ((match['source'] as String? ?? '') == 'missing') continue;
        final pid = match['paragraph_id'] as String? ?? '';
        if (pid.isEmpty) continue;
        final already = fixes.any(
          (f) =>
              f['paragraph_id'] == pid && f['fix_type'] == 'heading',
        );
        if (already) continue;
        fixes.add({
          'paragraph_id': pid,
          'fix_type': 'heading',
          'type': 'heading_style',
          'heading_level': match['expected_level'] ??
              match['heading_level'] ??
              1,
          'source': match['source'],
        });
      }

      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/documents/apply-all-fixes/${widget.documentId}?user_id=${auth.userId}',
        ),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'fixes': fixes,
          'include_toc': _includeToc,
          'include_lot': _includeLot,
          'include_lof': _includeLof,
        }),
      );
      if (resp.statusCode == 200) {
        final data = json.decode(resp.body) as Map<String, dynamic>;
        _mergeWorkingDocumentState(data);
        final bullets = data['bullet_fixes'] as Map?;
        final bulletCount = (bullets?['applied'] as List?)?.length ?? 0;
        _showSnack(
          'All fixes applied'
          '${bulletCount > 0 ? ' ($bulletCount list items)' : ''}!',
          _green,
        );
        setState(() {
          _styleIssues = [];
          _isFixApplied = true;
        });
      } else {
        _showSnack('Apply-all failed: ${resp.body}', _red);
      }
    } catch (e) {
      _showSnack('Error: $e', _red);
    } finally {
      setState(() => _isApplyingFix = false);
    }
  }

  // ── API — analysis ────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> _fetchAnalysis() async {
    // Reset so _buildBody re-seeds _styleIssues from fresh server data
    _styleIssuesInitialized = false;
    final auth = context.read<AuthProvider>();
    final path = widget.freeformAnalysis
        ? '$_baseUrl/documents/analyze-freeform/${widget.documentId}'
        : '$_baseUrl/documents/analyze/${widget.documentId}';
    final resp = await http.get(
      Uri.parse('$path?user_id=${auth.userId}'),
      headers: ApiConfig.getHeaders(),
    );
    if (resp.statusCode != 200) {
      throw Exception('Analysis failed (${resp.statusCode}): ${resp.body}');
    }
    final data = jsonDecode(resp.body) as Map<String, dynamic>;
    debugPrint(
      '[AnalyzeScreen] structure score : ${(data["structure"] as Map?)?["score"]}',
    );
    debugPrint(
      '[AnalyzeScreen] table_issues    : ${(data["table_issues"] as List?)?.length}',
    );
    if (widget.freeformAnalysis) {
      _freeformSuggestedFixes = List<Map<String, dynamic>>.from(
        ((data['suggested_fixes'] as List?) ?? const []).map(
          (e) => Map<String, dynamic>.from(e as Map),
        ),
      );
      _freeformManualNotes = List<Map<String, dynamic>>.from(
        ((data['suggested_manual_notes'] as List?) ?? const []).map(
          (e) => Map<String, dynamic>.from(e as Map),
        ),
      );
    }
    // Persist slim report on DocumentProvider for final_submissions (no recompute).
    try {
      context.read<DocumentProvider>().cacheAnalysisReport(
        widget.documentId,
        data,
      );
    } catch (e) {
      debugPrint('[AnalyzeScreen] cacheAnalysisReport skipped: $e');
    }
    return data;
  }

  // ── API — heading style check ─────────────────────────────────────────────

  Future<void> _loadHeadingStyleCheck() async {
    setState(() {
      _headingStyleLoading = true;
      _headingStyleError = null;
    });
    try {
      final auth = context.read<AuthProvider>();
      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/heading-style-check/${widget.documentId}?user_id=${auth.userId}',
        ),
      );
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        setState(() {
          _headingStyleResults = data['results'] as List<dynamic>? ?? [];
          _stylesNotApplied = data['styles_not_applied'] as bool? ?? false;
          _headingStyleLoaded = true;
        });
      } else {
        setState(
          () =>
              _headingStyleError = 'Failed (${resp.statusCode}): ${resp.body}',
        );
      }
    } catch (e) {
      setState(() { _headingStyleError = 'Network error: $e'; });
    } finally {
      setState(() { _headingStyleLoading = false; });
    }
  }

  /// Calls the detect-template-headings endpoint which internally calls
  /// apply_template_headings to write Word Heading styles to the working copy.
  Future<void> _applyTemplateHeadingStyles() async {
    setState(() { _applyingTemplateStyles = true; });
    try {
      final auth = context.read<AuthProvider>();
      final mismatches =
          _headingStyleResults
              .where((r) => r['status'] == 'style_mismatch')
              .toList();

      if (mismatches.isEmpty) {
        _showSnack('No style mismatches to fix.', _textSec);
        return;
      }

      int fixedCount = 0;
      for (var result in mismatches) {
        final resp = await http.post(
          Uri.parse(
            '$_baseUrl/apply-heading-style/${widget.documentId}?user_id=${auth.userId}',
          ),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'para_index': result['paraIndex'],
            'heading_level': result['heading_level'] ?? 1,
          }),
        );

        if (resp.statusCode == 200) {
          setState(() {
            final idx = _headingStyleResults.indexWhere(
              (r) =>
                  (r as Map)['heading'] == result['heading'] &&
                  r['paraIndex'] == result['paraIndex'],
            );
            if (idx != -1) {
              (_headingStyleResults[idx] as Map<String, dynamic>)['status'] =
                  'ok';
            }
          });
          fixedCount++;
        }
      }

      _showSnack('Fixed $fixedCount heading style(s)!', _green);
      setState(() {
        _isFixApplied = true;
        _stylesNotApplied = false;
      });
    } catch (e) {
      _showSnack('Error: $e', _red);
    } finally {
      setState(() { _applyingTemplateStyles = false; });
    }
  }

  Future<void> _applyHeadingStyle(Map<String, dynamic> result) async {
    final key = '${result['heading']}_${result['paraIndex']}';
    setState(() { _applyingHeadingStyle.add(key); });
    try {
      final auth = context.read<AuthProvider>();
      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/apply-heading-style/${widget.documentId}?user_id=${auth.userId}',
        ),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'para_index': result['paraIndex'],
          'heading_level': result['heading_level'] ?? 1,
        }),
      );
      if (resp.statusCode == 200) {
        setState(() {
          final idx = _headingStyleResults.indexWhere(
            (r) => (r as Map)['heading'] == result['heading'],
          );
          if (idx != -1) {
            (_headingStyleResults[idx] as Map<String, dynamic>)['status'] =
                'ok';
          }
        });
        _showSnack('Heading style applied!', _green);
      } else {
        _showSnack('Style fix failed: ${resp.body}', _red);
      }
    } catch (e) {
      _showSnack('Error: $e', _red);
    } finally {
      setState(() { _applyingHeadingStyle.remove(key); });
    }
  }

  Future<void> _addMissingHeading(Map<String, dynamic> result) async {
    final key = 'add_${result['heading']}';
    setState(() { _applyingHeadingStyle.add(key); });
    try {
      final auth = context.read<AuthProvider>();
      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/add-missing-heading/${widget.documentId}?user_id=${auth.userId}',
        ),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'section_name': result['heading'],
          'heading_level': result['heading_level'] ?? 1,
          'insert_at_end': true,
          // Pass section_order so the backend inserts the heading
          // at the correct position in the document (not just appended at end)
          'section_order': result['order'],
        }),
      );
      if (resp.statusCode == 200) {
        setState(() {
          final idx = _headingStyleResults.indexWhere(
            (r) => (r as Map)['heading'] == result['heading'],
          );
          if (idx != -1) {
            (_headingStyleResults[idx] as Map<String, dynamic>)['status'] =
                'ok';
          }
        });
        _showSnack('Heading "${result['heading']}" added!', _green);
      } else {
        _showSnack('Failed to add heading: ${resp.body}', _red);
      }
    } catch (e) {
      _showSnack('Error: $e', _red);
    } finally {
      setState(() { _applyingHeadingStyle.remove(key); });
    }
  }

  // ── API — paragraph style check ───────────────────────────────────────────

  Future<void> _loadParagraphStyleCheck() async {
    setState(() {
      _paragraphStyleLoading = true;
      _paragraphStyleError = null;
    });
    try {
      final auth = context.read<AuthProvider>();
      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/paragraph-style-check/${widget.documentId}?user_id=${auth.userId}',
        ),
      );
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        setState(() {
          _paragraphStyleIssues = data['issues'] as List<dynamic>? ?? [];
          _paragraphStyleLoaded = true;
        });
      } else {
        setState(() { _paragraphStyleError = 'Failed (${resp.statusCode})'; });
      }
    } catch (e) {
      setState(() { _paragraphStyleError = 'Network error: $e'; });
    } finally {
      setState(() { _paragraphStyleLoading = false; });
    }
  }

  Future<void> _applyAllParagraphStyle() async {
    setState(() { _applyingAllParaStyle = true; });
    try {
      final auth = context.read<AuthProvider>();
      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/apply-paragraph-style/${widget.documentId}?user_id=${auth.userId}',
        ),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'para_indices': null}),
      );
      if (resp.statusCode == 200) {
        setState(() { _paragraphStyleIssues = []; });
        _showSnack('All paragraph styles fixed!', _green);
      } else {
        _showSnack('Failed: ${resp.body}', _red);
      }
    } catch (e) {
      _showSnack('Error: $e', _red);
    } finally {
      setState(() { _applyingAllParaStyle = false; });
    }
  }

  // ── API — TOC check ───────────────────────────────────────────────────────

  Future<void> _loadTocCheck() async {
    setState(() {
      _tocLoading = true;
      _tocError = null;
    });
    try {
      final auth = context.read<AuthProvider>();
      final resp = await http.get(
        Uri.parse(
          '$_baseUrl/toc-check/${widget.documentId}?user_id=${auth.userId}',
        ),
      );
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        setState(() {
          _tocData = data;
          _tocLoaded = true;
        });
      } else {
        setState(() { _tocError = 'Failed (${resp.statusCode})'; });
      }
    } catch (e) {
      setState(() { _tocError = 'Network error: $e'; });
    } finally {
      setState(() { _tocLoading = false; });
    }
  }

  Future<void> _generateSelectedLists() async {
    if (!_includeToc && !_includeLot && !_includeLof) {
      _showSnack('Enable at least one list option to generate', _yellow);
      return;
    }

    setState(() { _generatingLists = true; });
    try {
      final auth = context.read<AuthProvider>();
      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/generate-document-lists/${widget.documentId}'
          '?user_id=${auth.userId}',
        ),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'include_toc': _includeToc,
          'include_lot': _includeLot,
          'include_lof': _includeLof,
        }),
      );
      final data = jsonDecode(resp.body) as Map<String, dynamic>;

      if (resp.statusCode == 200) {
        final parts = <String>[];
        if (data['toc_added'] == true) {
          parts.add('Table of Contents');
        }
        if (data['lot_added'] == true) {
          parts.add('List of Tables');
        }
        if (data['lof_added'] == true) {
          parts.add('List of Figures');
        }

        if (parts.isEmpty) {
          _showSnack(
            'No new lists were added — selected lists may already exist '
            'or required content was not found.',
            _yellow,
          );
        } else {
          _showSnack('Generated: ${parts.join(', ')}', _green);
        }
        await _loadTocCheck();
      } else {
        _showSnack(
          data['message'] as String? ?? 'Failed to generate lists: ${resp.body}',
          _red,
        );
      }
    } catch (e) {
      _showSnack('Error generating lists: $e', _red);
    } finally {
      setState(() { _generatingLists = false; });
    }
  }

  Future<void> _applyTocStyle() async {
    setState(() { _applyingTocStyle = true; });
    try {
      final auth = context.read<AuthProvider>();
      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/apply-toc-style/${widget.documentId}?user_id=${auth.userId}',
        ),
      );
      if (resp.statusCode == 200) {
        _showSnack('TOC styles applied!', _green);
        _loadTocCheck();
      } else if (resp.statusCode == 409) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        _showSnack(data['message'] as String? ?? 'No TOC found', _yellow);
      } else {
        _showSnack('Failed: ${resp.body}', _red);
      }
    } catch (e) {
      _showSnack('Error: $e', _red);
    } finally {
      setState(() { _applyingTocStyle = false; });
    }
  }

  Future<void> _addToc() async {
    setState(() { _addingToc = true; });
    try {
      final auth = context.read<AuthProvider>();
      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/add-toc/${widget.documentId}?user_id=${auth.userId}',
        ),
      );
      final data = jsonDecode(resp.body) as Map<String, dynamic>;
      if (resp.statusCode == 200) {
        _showSnack('TOC inserted with ${data['entry_count']} entries!', _green);
        setState(() {
          _tocLoaded = false;
        });
        _loadTocCheck();
      } else if (resp.statusCode == 409) {
        _showSnack(data['message'] as String? ?? 'TOC already exists', _yellow);
      } else if (resp.statusCode == 422) {
        _showSnack(
          data['message'] as String? ?? 'No headings found to build TOC',
          _orange,
        );
      } else {
        _showSnack('Failed to add TOC: ${resp.body}', _red);
      }
    } catch (e) {
      _showSnack('Error adding TOC: $e', _red);
    } finally {
      setState(() { _addingToc = false; });
    }
  }

  // ── API — tables ──────────────────────────────────────────────────────────

  Future<void> _loadTables() async {
    setState(() {
      _tablesLoading = true;
      _tablesError = null;
    });
    try {
      final auth = context.read<AuthProvider>();
      final url =
          '$_baseUrl/tables/detect/${widget.documentId}?user_id=${auth.userId}';
      debugPrint('[Tables] detecting → $url');
      final resp = await http.get(Uri.parse(url));
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        final rawTables = data['tables'] as List<dynamic>? ?? [];
        setState(() {
          _tables =
              rawTables
                  .map((t) => _TableMeta.fromJson(t as Map<String, dynamic>))
                  .toList();
        });
        debugPrint('[Tables] loaded ${_tables.length} table(s)');
      } else {
        setState(
          () => _tablesError = 'Failed to detect tables (${resp.statusCode})',
        );
      }
    } catch (e) {
      setState(() { _tablesError = 'Network error: $e'; });
    } finally {
      setState(() { _tablesLoading = false; });
    }
  }

  int _calculateTableIssueCount() {
    return _tables.fold<int>(0, (sum, table) => sum + table.issueCount);
  }

  Future<void> _promptAndFillEmptyCell(_TableMeta table, _TableIssue issue) async {
    if (!issue.isFillableEmptyCell) return;

    final controller = TextEditingController();
    final row = issue.row!;
    final col = issue.col!;

    final text = await showDialog<String>(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          backgroundColor: _surface,
          title: Text(
            'Fill empty cell',
            style: TextStyle(color: _textPri, fontSize: 16, fontWeight: FontWeight.w700),
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${table.label} · Row ${row + 1}, Column ${col + 1}',
                style: TextStyle(color: _textSec, fontSize: 12),
              ),
              const SizedBox(height: 14),
              TextField(
                controller: controller,
                autofocus: true,
                maxLines: 3,
                style: TextStyle(color: _textPri, fontSize: 14),
                decoration: InputDecoration(
                  hintText: 'Enter text for this cell',
                  hintStyle: TextStyle(color: _textSec.withOpacity(0.7)),
                  filled: true,
                  fillColor: _bg,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: BorderSide(color: _border),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: BorderSide(color: _border),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: const BorderSide(color: _blue),
                  ),
                ),
                onSubmitted: (v) => Navigator.of(ctx).pop(v.trim()),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: Text('Cancel', style: TextStyle(color: _textSec)),
            ),
            ElevatedButton(
              onPressed: () => Navigator.of(ctx).pop(controller.text.trim()),
              style: ElevatedButton.styleFrom(
                backgroundColor: _blue,
                foregroundColor: Colors.white,
              ),
              child: const Text('Save to cell'),
            ),
          ],
        );
      },
    );

    // Dispose after dialog closes
    controller.dispose();

    if (text == null || text.isEmpty) return;
    await _fillEmptyCell(
      tableIndex: table.index,
      row: row,
      col: col,
      text: text,
    );
  }

  Future<void> _fillEmptyCell({
    required int tableIndex,
    required int row,
    required int col,
    required String text,
  }) async {
    setState(() {
      _tablesFormatting = true;
      _tablesError = null;
      _tablesSuccess = null;
    });
    try {
      final auth = context.read<AuthProvider>();
      final url =
          '$_baseUrl/tables/fill-cell/${widget.documentId}?user_id=${auth.userId}';
      final resp = await http.post(
        Uri.parse(url),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'table_index': tableIndex,
          'row': row,
          'col': col,
          'text': text,
        }),
      );
      if (resp.statusCode == 200) {
        setState(() {
          _tablesSuccess =
              'Filled cell at row ${row + 1}, column ${col + 1}';
        });
        _showSnack(_tablesSuccess!, _green);
        await _loadTables();
      } else {
        setState(() {
          _tablesError = 'Failed to fill cell: ${resp.body}';
        });
        _showSnack(_tablesError!, _red);
      }
    } catch (e) {
      setState(() {
        _tablesError = 'Error filling cell: $e';
      });
      _showSnack(_tablesError!, _red);
    } finally {
      setState(() {
        _tablesFormatting = false;
      });
    }
  }

  Future<void> _normalizeTableFonts(_TableMeta table) async {
    setState(() {
      _tablesFormatting = true;
      _tablesError = null;
      _tablesSuccess = null;
    });
    try {
      final auth = context.read<AuthProvider>();
      final url =
          '$_baseUrl/tables/normalize-fonts/${widget.documentId}?user_id=${auth.userId}';
      final resp = await http.post(
        Uri.parse(url),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'table_index': table.index}),
      );
      if (resp.statusCode == 200) {
        setState(() {
          _tablesSuccess =
              'Normalized fonts in ${table.label} to match template style';
        });
        _showSnack(_tablesSuccess!, _green);
        await _loadTables();
      } else {
        setState(() {
          _tablesError = 'Failed to normalize fonts: ${resp.body}';
        });
        _showSnack(_tablesError!, _red);
      }
    } catch (e) {
      setState(() {
        _tablesError = 'Error normalizing fonts: $e';
      });
      _showSnack(_tablesError!, _red);
    } finally {
      setState(() {
        _tablesFormatting = false;
      });
    }
  }

  // ── API — content check ───────────────────────────────────────────────────

  Future<void> _loadContentCheck() async {
    if (_contentLoaded) return; // don't reload on tab switch
    setState(() {
      _contentLoading = true;
      _contentError = null;
    });
    try {
      final auth = context.read<AuthProvider>();
      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/content-check/${widget.documentId}'
          '?user_id=${auth.userId}',
        ),
      );
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        setState(() {
          _contentIssues = data['issues'] as List<dynamic>? ?? [];
          _totalSections = (data['total_sections'] as num?)?.toInt() ?? 0;
          _contentLoaded = true;
        });
      } else {
        setState(
          () => _contentError = 'Failed (${resp.statusCode}): ${resp.body}',
        );
      }
    } catch (e) {
      setState(() { _contentError = 'Network error: $e'; });
    } finally {
      setState(() { _contentLoading = false; });
    }
  }

  // ── NEW: Apply formatting using the admin's saved template style ──────────
  //
  // Calls POST /api/tables/format-with-template/{documentId}
  // Passes widget.templateId so the backend reads formatting_rules['table_style']
  // from the template and applies it — no manual preset needed.

  Future<void> _applyTemplateFormatting() async {
    if (_selectedTableIndices.isEmpty) return;

    setState(() {
      _tablesFormatting = true;
      _tablesError = null;
      _tablesSuccess = null;
    });

    try {
      final auth = context.read<AuthProvider>();
      final url =
          '$_baseUrl/tables/format-with-template/${widget.documentId}'
          '?user_id=${auth.userId}';
      final selectedCount = _selectedTableIndices.length;

      debugPrint('[Tables] applyTemplateFormatting → $url');
      debugPrint(
        '[Tables]   template_id=${widget.templateId}  '
        'indices=${_selectedTableIndices.toList()..sort()}',
      );

      final resp = await http.post(
        Uri.parse(url),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'template_id': widget.templateId,
          'selected_indices': _selectedTableIndices.toList()..sort(),
        }),
      );

      if (resp.statusCode == 200) {
        setState(() {
          _selectedTableIndices.clear();
          _expandedTableCards.clear();
          _tablesSuccess =
              '$selectedCount table(s) formatted using '
              '"${widget.templateName}" template style.';
        });
        _showSnack(_tablesSuccess!, _green);
        await _loadTables();
      } else {
        setState(() { _tablesError = 'Formatting failed: ${resp.body}'; });
        _showSnack(_tablesError!, _red);
      }
    } catch (e) {
      setState(() { _tablesError = 'Error: $e'; });
      _showSnack(_tablesError!, _red);
    } finally {
      setState(() { _tablesFormatting = false; });
    }
  }

  // ── Legacy preset-based formatting (kept, no longer wired to UI) ──────────

  Future<void> _applyTableFormatting() async {
    if (_selectedTableIndices.isEmpty) return;
    setState(() {
      _tablesFormatting = true;
      _tablesError = null;
      _tablesSuccess = null;
    });
    try {
      final auth = context.read<AuthProvider>();
      final url =
          '$_baseUrl/tables/format/${widget.documentId}?user_id=${auth.userId}';
      final selectedCount = _selectedTableIndices.length;
      final resp = await http.post(
        Uri.parse(url),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'selected_indices': _selectedTableIndices.toList()..sort(),
          'preset': _tablePreset,
          'custom_rules': _tableRules,
        }),
      );
      if (resp.statusCode == 200) {
        setState(() {
          _tablesSuccess =
              '$selectedCount table(s) formatted with "$_tablePreset" preset.';
          _selectedTableIndices.clear();
        });
        _showSnack(_tablesSuccess!, _green);
        await _loadTables();
      } else {
        setState(() { _tablesError = 'Formatting failed: ${resp.body}'; });
        _showSnack(_tablesError!, _red);
      }
    } catch (e) {
      setState(() { _tablesError = 'Error: $e'; });
      _showSnack(_tablesError!, _red);
    } finally {
      setState(() { _tablesFormatting = false; });
    }
  }

  void _setTablePreset(String preset) {
    setState(() {
      _tablePreset = preset;
      switch (preset) {
        case 'academic':
          _tableRules = {
            'header_bold': true,
            'banded_rows': true,
            'borders': true,
            'center_table': true,
            'repeat_header': true,
            'auto_fit': true,
          };
          break;
        case 'professional':
          _tableRules = {
            'header_bold': true,
            'banded_rows': false,
            'borders': true,
            'center_table': true,
            'repeat_header': true,
            'auto_fit': true,
          };
          break;
        case 'minimal':
          _tableRules = {
            'header_bold': false,
            'banded_rows': false,
            'borders': true,
            'center_table': false,
            'repeat_header': false,
            'auto_fit': true,
          };
          break;
      }
    });
  }

  // ── API — fixes ───────────────────────────────────────────────────────────

  Future<void> _applyFix(String fixType, Map<String, dynamic> details) async {
    setState(() { _isApplyingFix = true; });
    try {
      final auth = context.read<AuthProvider>();
      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/documents/apply-fix/${widget.documentId}'
          '?user_id=${auth.userId}&fix_type=$fixType',
        ),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(details),
      );
      if (resp.statusCode == 200) {
        final data = json.decode(resp.body) as Map<String, dynamic>;
        _mergeWorkingDocumentState(data);
        _showSnack('Fix applied!', _green);
        setState(() {
          if (fixType == 'apply_section_bullets') {
            _styleIssues.removeWhere(
              (i) => (i as Map)['type'] == 'missing_bullets',
            );
          }
        });
      } else {
        _showSnack('Fix failed: ${resp.body}', _red);
      }
    } catch (e) {
      _showSnack('Error: $e', _red);
    } finally {
      setState(() { _isApplyingFix = false; });
    }
  }

  // ── Style fix — instant: fires request, removes card from UI immediately ───
  //
  // No re-analysis after a style fix. The issue card is removed from
  // _styleIssues state the moment the backend confirms success, giving
  // an instant response with zero pipeline re-runs.

  Future<void> _applyStyleFix(
    Map<String, dynamic> issue,
    String issueKey,
  ) async {
    setState(() { _fixingStyleIssues.add(issueKey); });
    try {
      final auth = context.read<AuthProvider>();

      const typeToFixType = {
        'wrong_font_size': 'fix_font_size',
        'wrong_bold': 'fix_bold',
        'wrong_font': 'fix_font_name',
        'wrong_line_spacing': 'fix_line_spacing',
      };
      final fixType =
          typeToFixType[issue['type'] as String? ?? ''] ?? 'fix_all_style';

      // Forward paragraph targeting + expected values to the backend
      final details = <String, dynamic>{};
      if (issue['para_index'] != null)
        details['para_index'] = issue['para_index'];
      if (issue['para_indices'] != null)
        details['para_indices'] = issue['para_indices'];
      if (issue['block_type'] != null)
        details['block_type'] = issue['block_type'];
      if (issue['heading_level'] != null)
        details['heading_level'] = issue['heading_level'];
      if (issue['expected_font_size'] != null)
        details['expected_font_size'] = issue['expected_font_size'];
      if (issue['expected_bold'] != null)
        details['expected_bold'] = issue['expected_bold'];
      if (issue['expected_font_name'] != null)
        details['expected_font_name'] = issue['expected_font_name'];
      if (issue['expected_line_spacing'] != null)
        details['expected_line_spacing'] = issue['expected_line_spacing'];

      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/documents/apply-fix/${widget.documentId}'
          '?user_id=${auth.userId}&fix_type=$fixType',
        ),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(details),
      );

      if (resp.statusCode == 200) {
        // ── Remove this issue from local state instantly — NO re-analysis ──
        setState(() {
          _styleIssues.removeWhere((i) {
            final m = i as Map;
            return m['type'] == issue['type'] &&
                m['code'] == issue['code'] &&
                // match on para_index when present, else on message text
                (issue['para_index'] != null
                    ? m['para_index'] == issue['para_index']
                    : m['message'] == issue['message']);
          });
        });
        _showSnack('Fixed!', _green);
      } else {
        _showSnack('Fix failed: ${resp.body}', _red);
      }
    } catch (e) {
      _showSnack('Error: $e', _red);
    } finally {
      setState(() { _fixingStyleIssues.remove(issueKey); });
    }
  }

  Future<void> _applyAllStyleFixes() async {
    setState(() { _isApplyingFix = true; });
    try {
      final auth = context.read<AuthProvider>();
      final url = Uri.parse(
        '$_baseUrl/documents/apply-all-style-fixes/${widget.documentId}?user_id=${auth.userId}',
      );
      debugPrint('[v0] Apply-all-style-fixes URL: $url');
      final resp = await http.post(url);
      if (resp.statusCode == 200) {
        _showSnack('Template styles applied!', _green);
        // ── LOCAL STATE ONLY — no re-analysis ──────────────────────────
        // Clear the general style issues list so all issue cards disappear.
        // Mark every heading result as 'ok' so their cards turn green.
        // Clear paragraph issues. Enable the Download button.
        // We intentionally do NOT call _fetchAnalysis(), _loadHeadingStyleCheck()
        // or _loadParagraphStyleCheck() — that would re-run the full pipeline.
        setState(() {
          _styleIssues = [];
          for (final r in _headingStyleResults) {
            (r as Map<String, dynamic>)['status'] = 'ok';
          }
          _paragraphStyleIssues = [];
          _isFixApplied = true;
        });
      } else {
        _showSnack('Apply-all failed: ${resp.body}', _red);
      }
    } catch (e) {
      _showSnack('Error: $e', _red);
    } finally {
      setState(() { _isApplyingFix = false; });
    }
  }

  Future<void> _downloadDirectly() async {
    setState(() { _isDownloading = true; });
    try {
      final docProvider = context.read<DocumentProvider>();
      final auth = context.read<AuthProvider>();

      final success = await docProvider.downloadFormattedDocument(
        widget.documentId,
        auth.userId!,
        format: 'docx',
      );

      if (mounted) {
        _showSnack(
          success ? 'Document downloaded successfully!' : 'Download failed',
          success ? _green : _red,
        );
      }
    } catch (e) {
      _showSnack('Download error: $e', _red);
    } finally {
      setState(() { _isDownloading = false; });
    }
  }

  void _handleSidebarSelection(int index) {
    setState(() { _selectedSidebarIndex = index; });
    switch (index) {
      case 0:
        final auth = context.read<AuthProvider>();
        final route = auth.isAdmin
            ? '/admin-dashboard'
            : auth.isSupervisor
                ? '/supervisor-dashboard'
                : '/student-dashboard';
        Navigator.pushNamedAndRemoveUntil(context, route, (_) => false);
        break;
      case 1:
        Navigator.pushNamedAndRemoveUntil(context, '/new-report', (_) => false);
        break;
      case 3:
        Navigator.pushNamedAndRemoveUntil(context, '/collaboration', (_) => false);
        break;
    }
  }

  void _handleDownload(Map<String, dynamic> doc) {
    if (widget.freeformAnalysis) {
      _handleFreeformExportPreview();
      return;
    }
    showDialog(
      context: context,
      builder:
          (_) => Dialog(
            insetPadding: const EdgeInsets.all(20),
            child: ConstrainedBox(
              constraints: BoxConstraints(
                maxHeight: MediaQuery.of(context).size.height * 0.85,
                maxWidth: 500,
              ),
              child: SingleChildScrollView(
                child: ExportDialog(
                  onExport: (
                    format, {
                    bool applyBullets = true,
                    bool autoDetect = true,
                  }) async {
                    final docProvider = context.read<DocumentProvider>();
                    final authProvider = Provider.of<AuthProvider>(
                      context,
                      listen: false,
                    );
                    final success = await docProvider.downloadFormattedDocument(
                      doc['id'],
                      authProvider.userId!,
                      format: format,
                      applyBullets: applyBullets,
                      autoDetectBullets: autoDetect,
                    );
                    if (mounted) {
                      _showSnack(
                        success ? 'Downloaded as $format!' : 'Download failed',
                        success ? _green : _red,
                      );
                    }
                  },
                  onQRCode: () async {
                    try {
                      final result = await QRService.generateQr(doc['id']);
                      final qrBase64 = result['qr_base64'];
                      if (qrBase64 == null || qrBase64.isEmpty)
                        throw "QR data missing";
                      if (!mounted) return;
                      showDialog(
                        context: context,
                        useRootNavigator: true,
                        builder:
                            (_) => Dialog(
                              child: Padding(
                                padding: const EdgeInsets.all(20),
                                child: Image.memory(
                                  base64Decode(qrBase64),
                                  width: 250,
                                  height: 250,
                                ),
                              ),
                            ),
                      );
                    } catch (e) {
                      _showSnack('Failed to generate QR: $e', _red);
                    }
                  },
                ),
              ),
            ),
          ),
    );
  }

  /// Checkpoint: show pre-export summary only — does NOT write the file yet.
  Future<void> _handleFreeformExportPreview() async {
    final applied = _freeformSuggestedFixes
        .where((f) => f['auto_applicable'] == true)
        .toList();
    final confirmed = await showFreeformExportSummaryDialog(
      context,
      appliedFixes: applied,
      manualNotes: _freeformManualNotes,
    );
    if (!mounted) return;
    if (confirmed) {
      // Export write intentionally not wired yet — awaiting checkpoint approval.
      _showSnack(
        'Export confirmed in UI — file write not wired yet (checkpoint).',
        _yellow,
      );
    }
  }

  // ── Build ─────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    _ap = context.watch<ThemeProvider>().palette;
    return Scaffold(
      backgroundColor: _bg,
      body: Row(
        children: [
          AppSidebar(
            selectedIndex: _selectedSidebarIndex,
            onItemSelected: _handleSidebarSelection,
          ),
          Expanded(
            child: Column(
              children: [
                _buildTopBar(),
                Expanded(
                  child: FutureBuilder<Map<String, dynamic>>(
                    future: _analysisFuture,
                    builder: (ctx, snap) {
                      if (snap.connectionState == ConnectionState.waiting)
                        return _buildLoading();
                      if (snap.hasError)
                        return _buildError(snap.error.toString());
                      return _buildBody(snap.data ?? {});
                    },
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── Top bar ───────────────────────────────────────────────────────────────

  Widget _buildTopBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      decoration: BoxDecoration(
        color: _bg,
        border: Border(bottom: BorderSide(color: _border)),
      ),
      child: Row(
        children: [
          IconButton(
            icon: Icon(Icons.arrow_back, color: _textPri),
            onPressed: () => Navigator.pop(context),
          ),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Analysis Report',
                style: TextStyle(
                  color: _textPri,
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                ),
              ),
              Text(
                widget.documentName,
                style: TextStyle(color: _textSec, fontSize: 12),
              ),
            ],
          ),
          const Spacer(),
          Text(
            widget.freeformAnalysis
                ? widget.templateName
                : 'Template: ${widget.templateName}',
            style: TextStyle(
              color: widget.freeformAnalysis ? _purple : _textSec,
              fontSize: 12,
              fontWeight:
                  widget.freeformAnalysis ? FontWeight.w600 : FontWeight.w400,
            ),
          ),
          const SizedBox(width: 20),
          ElevatedButton.icon(
            onPressed: () => _handleDownload({'id': widget.documentId}),
            icon: const Icon(Icons.download, size: 16),
            label: Text(
              widget.freeformAnalysis ? 'Export (AI-guided)' : 'Export',
            ),
            style: ElevatedButton.styleFrom(
              backgroundColor: _green,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoading() => Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        CircularProgressIndicator(color: _blue),
        SizedBox(height: 16),
        Text(
          'Running Layer 1 → 2 → 3 analysis…',
          style: TextStyle(color: _textSec),
        ),
      ],
    ),
  );

  Widget _buildError(String msg) => Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.error_outline, color: _red, size: 48),
        const SizedBox(height: 12),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32),
          child: Text(
            msg,
            style: const TextStyle(color: _red),
            textAlign: TextAlign.center,
          ),
        ),
        const SizedBox(height: 16),
        ElevatedButton(
          onPressed: () => setState(() {
            _analysisFuture = _fetchAnalysis();
          }),
          child: const Text('Retry'),
        ),
      ],
    ),
  );

  // ── Main body ─────────────────────────────────────────────────────────────

  Widget _buildBody(Map<String, dynamic> data) {
    final structure = data['structure'] as Map<String, dynamic>? ?? {};
    final oldIssues = data['issues'] as List<dynamic>? ?? [];
    _templateHeadingMatches =
        (data['template_heading_matches'] as List<dynamic>? ?? [])
            .map((m) => Map<String, dynamic>.from(m as Map))
            .toList();
    final score =
        (structure['score'] as num?)?.toInt() ?? (data['compliance_score'] as num?)?.toInt() ?? 0;
    final status = structure['status'] as String? ?? 'unknown';
    final summary = structure['summary'] as Map<String, dynamic>? ?? {};
    _seedPreviewData(data);

    final grammarIssues = _visibleIssues(_issuesForFunction(oldIssues, 'grammar'));
    final formattingIssues = _visibleIssues(_issuesForFunction(oldIssues, 'formatting'));
    final formattingTabCount = formattingIssues.length + _fixableTemplateHeadingMatches.length;
    final imageEthicsIssues = _visibleIssues(_issuesForFunction(oldIssues, 'image_ethics'));
    final imageIssues = _visibleIssues(_issuesForFunction(oldIssues, 'image_relevance'));
    final paraRelevanceIssues = _visibleIssues(_issuesForFunction(oldIssues, 'para_relevance'));
    final plagiarismIssues = _visibleIssues(_issuesForFunction(oldIssues, 'plagiarism'));
    final openIssueCount = _visibleIssues(oldIssues).length;

    return Column(
      children: [
        _buildScoreBanner(
          score,
          status,
          summary,
          imageIssues.length,
          imageEthicsIssues.length,
          _calculateTableIssueCount(),
        ),
        Container(
          color: _surface,
          child: TabBar(
            controller: _tabController,
            indicatorColor: _blue,
            labelColor: _blue,
            unselectedLabelColor: _textSec,
            isScrollable: true,
            tabs: [
              Tab(text: 'Review  ($openIssueCount)'),
              Tab(text: 'Grammar  (${grammarIssues.length})'),
              Tab(text: 'Formatting  ($formattingTabCount)'),
              Tab(text: 'Image Ethics  (${imageEthicsIssues.length})'),
              Tab(text: 'Image Relevance  (${imageIssues.length})'),
              Tab(
                text: _tablesLoading
                    ? 'Tables  (…)'
                    : 'Tables  (${_calculateTableIssueCount()})',
              ),
              Tab(text: 'Para Relevance  (${paraRelevanceIssues.length})'),
              Tab(text: 'Plagiarism  (${plagiarismIssues.length})'),
              Tab(text: 'Document Lists'),
            ],
          ),
        ),
        Expanded(
          child: TabBarView(
            controller: _tabController,
            children: [
              _buildReviewTab(),
              _buildFunctionTab(
                'Grammar',
                grammarIssues,
                Icons.spellcheck,
                'Checks spelling, punctuation, and grammar errors.',
              ),
              _buildFormattingTab(formattingIssues),
              _buildImageEthicsTab(imageEthicsIssues),
              _buildImageRelevancyTab(imageIssues, const []),
              _buildTablesTab(),
              _buildFunctionTab(
                'Paragraph Relevance',
                paraRelevanceIssues,
                Icons.account_tree_outlined,
                'Detects paragraphs placed under the wrong heading.',
              ),
              _buildFunctionTab(
                'Plagiarism',
                plagiarismIssues,
                Icons.gpp_maybe_outlined,
                'Pattern-based detection of style shifts and unattributed quotes.',
              ),
              _buildDocumentListsTab(),
            ],
          ),
        ),
        _buildActionBar(oldIssues),
      ],
    );
  }

  Widget _buildFormattingTab(List<dynamic> issues) {
    final visible = issues.where((i) {
      final id = (i as Map)['issue_id'] as String? ?? '';
      return !_ignoredIssueIds.contains(id) && !_resolvedIssueIds.contains(id);
    }).toList();

    final headingMatches = _visibleTemplateHeadingMatches;
    final fixableCount = _fixableTemplateHeadingMatches.length;

    if (headingMatches.isEmpty && visible.isEmpty) {
      return _buildEmptyState(
        Icons.format_shapes,
        'No formatting issues',
        'Checks heading hierarchy, spacing, and template structure.',
        color: _green,
      );
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (headingMatches.isNotEmpty) ...[
            _buildInfoBanner(
              'Template Heading Analysis',
              'Headings are detected by Claude, then cross-checked against your template. '
                  'Extra headings not in the template need Keep or Discard before styling.',
              _blue,
            ),
            const SizedBox(height: 12),
            if (fixableCount > 0)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _applyingAllTemplateHeadings
                        ? null
                        : _applyAllTemplateHeadingFixes,
                    icon: _applyingAllTemplateHeadings
                        ? const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.auto_fix_high, size: 16),
                    label: Text(
                      _applyingAllTemplateHeadings
                          ? 'Applying…'
                          : 'Apply All Heading Fixes ($fixableCount)',
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _green,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
              ),
            ...headingMatches.map(_buildTemplateHeadingCard),
            if (visible.isNotEmpty) const SizedBox(height: 24),
          ],
          if (visible.isNotEmpty) ...[
            _buildInfoBanner(
              'Formatting',
              'Additional formatting issues found by the analysis pipeline.',
              _purple,
            ),
            const SizedBox(height: 16),
            ...visible.map(
              (i) => _buildPipelineIssueCard(i as Map<String, dynamic>),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildTemplateHeadingCard(Map<String, dynamic> match) {
    final pid = match['paragraph_id'] as String? ?? '';
    final text = match['text'] as String? ?? '';
    final level = _headingLevelFromMatch(match);
    final matched = match['matched_template_heading'] as String?;
    final source = match['source'] as String? ?? '';
    final userDecision =
        (match['user_decision'] as String? ?? '').toLowerCase();
    final isClaudeExtra = source == 'claude_only';
    final isPendingExtra =
        isClaudeExtra && (userDecision == 'pending' || userDecision.isEmpty);
    final isDiscarded = isClaudeExtra && userDecision == 'discard';
    final fixNeeded = match['fix_needed'] == true &&
        !_appliedTemplateHeadingFixes.contains(pid) &&
        !isPendingExtra &&
        !isDiscarded;
    final isApplied = _appliedTemplateHeadingFixes.contains(pid) ||
        ((match['status'] as String? ?? '') == 'ok' && !fixNeeded);
    final isApplying = _applyingTemplateHeadingFixes.contains(pid);
    final fixStatus = match['fix_status'] as String? ?? '';
    final fixDescription =
        match['fix_description'] as String? ?? match['reason'] as String? ?? '';
    final detectionConf =
        ((match['detection_confidence'] as num?) ?? 0).toDouble();
    final matchConf = match['match_confidence'];
    final headingKind = match['heading_kind'] as String? ?? '';
    final isUnnumberedSub =
        headingKind == 'unnumbered_subheading';

    final Color accentColor = isDiscarded
        ? _textSec
        : isPendingExtra
            ? _yellow
            : isApplied
                ? _green
                : fixNeeded
                    ? _orange
                    : (isUnnumberedSub
                        ? _blue
                        : (matched == null ? _yellow : _blue));
    final String statusLabel = isDiscarded
        ? 'DISCARDED'
        : isPendingExtra
            ? 'CONFIRM'
            : isApplied
                ? 'FIXED'
                : fixNeeded
                    ? 'NEEDS FIX'
                    : (isUnnumberedSub
                        ? 'SUB-HEADING'
                        : (matched == null ? 'UNMATCHED' : 'OK'));

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: accentColor.withOpacity(0.35)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: accentColor.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  alignment: Alignment.center,
                  child: Icon(
                    isDiscarded
                        ? Icons.remove_circle_outline
                        : isPendingExtra
                            ? Icons.help_outline
                            : isApplied
                                ? Icons.check_circle_outline
                                : Icons.title,
                    color: accentColor,
                    size: 16,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              text,
                              style: TextStyle(
                                color: _textPri,
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          _Tag(statusLabel, accentColor),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 6,
                        runSpacing: 4,
                        children: [
                          _Tag('H$level', _blue),
                          if (isClaudeExtra) _Tag('Claude extra', _yellow),
                          if (isUnnumberedSub)
                            _Tag('Unnumbered sub-heading', _purple),
                          if (matched != null) _Tag(matched, _purple),
                          _Tag(
                            'Detect ${(detectionConf * 100).round()}%',
                            _textSec,
                          ),
                          if (matchConf != null)
                            _Tag(
                              'Match ${((matchConf as num) * 100).round()}%',
                              _textSec,
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (fixDescription.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                fixDescription,
                style: TextStyle(color: _textSec, fontSize: 11, height: 1.4),
              ),
            ],
            if (isPendingExtra || isDiscarded) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: isApplying
                          ? null
                          : () => _decideExtraHeading(match, 'keep'),
                      icon: isApplying
                          ? const SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Icon(Icons.check, size: 16),
                      label: Text(isDiscarded ? 'Keep as heading' : 'Keep'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _green,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 10),
                      ),
                    ),
                  ),
                  if (isPendingExtra) ...[
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: isApplying
                            ? null
                            : () => _decideExtraHeading(match, 'discard'),
                        icon: const Icon(Icons.close, size: 16),
                        label: const Text('Discard'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: _textSec,
                          side: BorderSide(color: _textSec.withOpacity(0.4)),
                          padding: const EdgeInsets.symmetric(vertical: 10),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ] else if (fixNeeded) ...[
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: isApplying ? null : () => _applyTemplateHeadingFix(match),
                  icon: isApplying
                      ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.build_circle_outlined, size: 16),
                  label: Text(
                    isApplying
                        ? 'Applying…'
                        : 'Apply Heading $level Style',
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _green,
                    foregroundColor: Colors.white,
                  ),
                ),
              ),
            ] else if (fixStatus == 'unmatched' &&
                !isApplied &&
                !isUnnumberedSub &&
                !isClaudeExtra) ...[
              const SizedBox(height: 8),
              Text(
                'This heading is not in your template outline. No automatic rename is applied.',
                style: TextStyle(color: _yellow.withOpacity(0.9), fontSize: 11),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildFunctionTab(
    String title,
    List<dynamic> issues,
    IconData icon,
    String description,
  ) {
    final visible = issues.where((i) {
      final id = (i as Map)['issue_id'] as String? ?? '';
      return !_ignoredIssueIds.contains(id) && !_resolvedIssueIds.contains(id);
    }).toList();

    if (visible.isEmpty) {
      return _buildEmptyState(
        icon,
        'No $title issues',
        description,
        color: _green,
      );
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildInfoBanner(title, description, _blue),
          const SizedBox(height: 16),
          ...visible.map(
            (i) => _buildPipelineIssueCard(i as Map<String, dynamic>),
          ),
        ],
      ),
    );
  }

  Widget _buildScoreBanner(
    int score,
    String status,
    Map<String, dynamic> summary, [
    int imageIssueCount = 0,
    int imageEthicsCount = 0,
    int tableIssueCount = 0,
  ]) {
    final scoreColor =
        score >= 80
            ? _green
            : score >= 50
            ? _yellow
            : _red;
    return Container(
      color: _surface,
      padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
      child: Row(
        children: [
          SizedBox(
            width: 64,
            height: 64,
            child: Stack(
              alignment: Alignment.center,
              children: [
                CircularProgressIndicator(
                  value: score / 100,
                  strokeWidth: 6,
                  backgroundColor: _border,
                  valueColor: AlwaysStoppedAnimation(scoreColor),
                ),
                Text(
                  '$score',
                  style: TextStyle(
                    color: scoreColor,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 20),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    _StatusBadge(status),
                    const SizedBox(width: 12),
                    Text(
                      'Structure Score',
                      style: TextStyle(
                        color: _textPri,
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: score / 100,
                    minHeight: 6,
                    backgroundColor: _border,
                    valueColor: AlwaysStoppedAnimation(scoreColor),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 32),
          _SummaryPill('Found', '${summary['found'] ?? 0}', _green),
          const SizedBox(width: 8),
          _SummaryPill('Missing', '${summary['missing'] ?? 0}', _red),
          const SizedBox(width: 8),
          _SummaryPill('Order', '${summary['wrong_order'] ?? 0}', _yellow),
          const SizedBox(width: 8),
          _SummaryPill('Empty', '${summary['empty'] ?? 0}', _yellow),
          const SizedBox(width: 8),
          _SummaryPill('Extra', '${summary['extra_headings'] ?? 0}', _textSec),
          const SizedBox(width: 8),
          _SummaryPill('Content', '${summary['content_issues'] ?? 0}', _orange),
          const SizedBox(width: 8),
          _SummaryPill('Style', '${summary['style_issues'] ?? 0}', _purple),
          if (imageIssueCount > 0) ...[
            const SizedBox(width: 8),
            _SummaryPill('Images', '$imageIssueCount', _red),
          ],
          if (imageEthicsCount > 0) ...[
            const SizedBox(width: 8),
            _SummaryPill('Ethics', '$imageEthicsCount', _red),
          ],
          if (tableIssueCount > 0) ...[
            const SizedBox(width: 8),
            _SummaryPill('Tables', '$tableIssueCount', _yellow),
          ],
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Tab 0: Document Review (side-by-side preview)
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildReviewTab() {
    return DocumentPreviewPanel(
      blocks: _previewBlocks,
      issues: _pipelineIssues,
      imageBaseUrl: _imageHostBase,
      documentId: widget.documentId,
      appliedFixes: _appliedFixes,
      ignoredIssueIds: _ignoredIssueIds,
      resolvedIssueIds: _resolvedIssueIds,
      onApplyFix: _handlePreviewApplyFix,
      onIgnoreIssue: _handlePreviewIgnore,
      onImageReplaced: (result, issue) => _handleImageReplaceSuccess(
        result,
        issueId: issue['issue_id'] as String?,
      ),
      onImageRemoved: (result, issue) => _handleImageRemoveSuccess(
        result,
        issueId: issue['issue_id'] as String?,
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Tab 1: Structure
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildStructureTab(
    List<dynamic> sectionResults,
    List<dynamic> issues,
    Map<String, dynamic> summary,
  ) {
    if (sectionResults.isEmpty) {
      return _buildEmptyState(
        Icons.checklist_rounded,
        'No structure data',
        'Make sure your template has required sections defined in the admin panel.',
        actionLabel: 'View other checks below →',
        onAction: () => _tabController.animateTo(1),
      );
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (summary['content_before_heading'] == true)
            _buildAlertBanner(
              '⚠  Content found before the first heading',
              'Your document has text before any section heading. Move it under an appropriate heading.',
              _yellow,
              fixLabel: 'Fix: Move to Introduction',
              onFix: () => _applyFix('move_content_before_heading', {}),
            ),
          const SizedBox(height: 8),

          // ── Section presence rows (existing) ─────────────────────────────
          ...sectionResults.asMap().entries.map(
            (e) => _buildSectionRow(e.key, e.value as Map<String, dynamic>),
          ),
          const SizedBox(height: 24),
          _buildLayerLegend(),
          const SizedBox(height: 32),

          // ── Heading Style Check ──────────────────────────────────────────
          _buildHeadingStyleSection(),
          const SizedBox(height: 32),

          // ── Paragraph Style Check ────────────────────────────────────────
          _buildParagraphStyleSection(),
        ],
      ),
    );
  }

  Widget _buildHeadingStyleSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Section header
        Row(
          children: [
            const Icon(Icons.format_size, color: _blue, size: 18),
            const SizedBox(width: 8),
            Text(
              'Heading Style Compliance',
              style: TextStyle(
                color: _textPri,
                fontSize: 15,
                fontWeight: FontWeight.w700,
              ),
            ),
            const Spacer(),
            if (_headingStyleLoading)
              const SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(strokeWidth: 2, color: _blue),
              )
            else
              TextButton.icon(
                onPressed: () {
                  setState(() { _headingStyleLoaded = false; });
                  _loadHeadingStyleCheck();
                },
                icon: const Icon(Icons.refresh, size: 13),
                label: const Text('Refresh', style: TextStyle(fontSize: 11)),
                style: TextButton.styleFrom(foregroundColor: _textSec),
              ),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          'Checks if each required heading exists and has the correct font, size, and bold settings per the template.',
          style: TextStyle(color: _textSec, fontSize: 11, height: 1.4),
        ),
        const SizedBox(height: 12),

        if (_headingStyleError != null)
          _buildAlertBanner('Error', _headingStyleError!, _red)
        else if (_headingStyleLoading)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Center(child: CircularProgressIndicator(color: _blue)),
          )
        // ── Styles not yet applied: show a single prompt button ─────────
        else if (_stylesNotApplied)
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: _blue.withOpacity(0.06),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: _blue.withOpacity(0.25)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.info_outline, color: _blue, size: 16),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Heading styles have not been applied yet.',
                        style: TextStyle(
                          color: _blue,
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  'Apply template heading styles first so the compliance check can accurately report PASS/FAIL for each section.',
                  style: TextStyle(color: _textSec, fontSize: 11, height: 1.4),
                ),
                const SizedBox(height: 14),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed:
                        _applyingTemplateStyles
                            ? null
                            : _applyTemplateHeadingStyles,
                    icon:
                        _applyingTemplateStyles
                            ? const SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                            : const Icon(Icons.auto_fix_high, size: 16),
                    label: Text(
                      _applyingTemplateStyles
                          ? 'Applying…'
                          : 'Apply Template Heading Styles',
                      style: const TextStyle(fontSize: 13),
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _blue,
                      foregroundColor: Colors.white,
                      disabledBackgroundColor: _blue.withOpacity(0.35),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 12,
                      ),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          )
        // ── Styles applied: show all-clear or per-heading PASS/FAIL ─────
        else if (_headingStyleResults.isEmpty && _headingStyleLoaded)
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: _green.withOpacity(0.06),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: _green.withOpacity(0.2)),
            ),
            child: const Row(
              children: [
                Icon(Icons.check_circle_outline, color: _green, size: 16),
                SizedBox(width: 10),
                Text(
                  'All headings have correct template styling  ✓',
                  style: TextStyle(color: _green, fontSize: 13),
                ),
              ],
            ),
          )
        else
          ..._headingStyleResults.map(
            (r) => _buildHeadingStyleCard(r as Map<String, dynamic>),
          ),
      ],
    );
  }

  Widget _buildHeadingStyleCard(Map<String, dynamic> result) {
    final status = result['status'] as String? ?? 'ok';
    final name = result['heading'] as String? ?? '';
    final paraIdx = (result['paraIndex'] as num?)?.toInt();
    final matchedTxt = result['matched_text'] as String?;
    final level = (result['heading_level'] as num?)?.toInt() ?? 1;
    final expected = result['expected_style'] as Map? ?? {};
    final actual = result['actual_style'] as Map? ?? {};
    final mismatches = (result['mismatches'] as List?)?.cast<String>() ?? [];
    final required = result['required'] as bool? ?? true;
    final key = '${name}_$paraIdx';
    final isApplying =
        _applyingHeadingStyle.contains(key) ||
        _applyingHeadingStyle.contains('add_$name') ||
        _applyingHeadingStyle.contains('${name}_null');

    // if (status == 'ok') return const SizedBox.shrink();

    final Color accentColor =
        status == 'missing' ? _red : (status == 'ok' ? _green : _orange);
    final IconData icon =
        status == 'missing'
            ? Icons.add_circle_outline
            : (status == 'ok' ? Icons.check_circle : Icons.style_outlined);

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: accentColor.withOpacity(0.3)),
      ),
      child: Column(
        children: [
          // ── Header row ────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 10),
            child: Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: accentColor.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  alignment: Alignment.center,
                  child: Icon(icon, color: accentColor, size: 16),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            name,
                            style: TextStyle(
                              color: _textPri,
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(width: 8),
                          _Tag('H$level', _blue),
                          if (!required) ...[
                            const SizedBox(width: 6),
                            _Tag('optional', _textSec),
                          ],
                        ],
                      ),
                      const SizedBox(height: 3),
                      if (status == 'missing')
                        Text(
                          'Heading not found in document',
                          style: TextStyle(
                            color: _red.withOpacity(0.8),
                            fontSize: 11,
                          ),
                        )
                      else if (matchedTxt != null)
                        Text(
                          'Found: "$matchedTxt"',
                          style: TextStyle(color: _textSec, fontSize: 11),
                          overflow: TextOverflow.ellipsis,
                        ),
                    ],
                  ),
                ),
                _Tag(
                  status == 'missing'
                      ? 'MISSING'
                      : (status == 'ok' ? 'FIXED' : 'STYLE MISMATCH'),
                  accentColor,
                ),
              ],
            ),
          ),

          // ── Mismatch details for style_mismatch ────────────────────────
          if (status == 'style_mismatch' && mismatches.isNotEmpty)
            Container(
              width: double.infinity,
              margin: const EdgeInsets.fromLTRB(14, 0, 14, 10),
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: _bg,
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: _border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      // Expected
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'EXPECTED',
                              style: TextStyle(
                                color: _green,
                                fontSize: 9,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 0.5,
                              ),
                            ),
                            const SizedBox(height: 4),
                            if (expected['font_name'] != null)
                              Text(
                                'Font: ${expected['font_name']}',
                                style: TextStyle(
                                  color: _textSec,
                                  fontSize: 10,
                                ),
                              ),
                            if (expected['font_size'] != null)
                              Text(
                                'Size: ${expected['font_size']}pt',
                                style: TextStyle(
                                  color: _textSec,
                                  fontSize: 10,
                                ),
                              ),
                            if (expected['bold'] != null)
                              Text(
                                'Bold: ${expected['bold']}',
                                style: TextStyle(
                                  color: _textSec,
                                  fontSize: 10,
                                ),
                              ),
                          ],
                        ),
                      ),
                      Icon(
                        Icons.arrow_forward,
                        color: _textSec,
                        size: 12,
                      ),
                      // Actual
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'ACTUAL',
                              style: TextStyle(
                                color: _red,
                                fontSize: 9,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 0.5,
                              ),
                            ),
                            const SizedBox(height: 4),
                            if (actual['font_name'] != null)
                              Text(
                                'Font: ${actual['font_name']}',
                                style: TextStyle(
                                  color: _textSec,
                                  fontSize: 10,
                                ),
                              ),
                            if (actual['font_size'] != null)
                              Text(
                                'Size: ${actual['font_size']}pt',
                                style: TextStyle(
                                  color: _textSec,
                                  fontSize: 10,
                                ),
                              ),
                            if (actual['bold'] != null)
                              Text(
                                'Bold: ${actual['bold']}',
                                style: TextStyle(
                                  color: _textSec,
                                  fontSize: 10,
                                ),
                              ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),

          // ── Action button ─────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
            child: SizedBox(
              width: double.infinity,
              child:
                  status == 'ok'
                      ? Container(
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        decoration: BoxDecoration(
                          color: _green.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: _green.withOpacity(0.3)),
                        ),
                        child: const Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.check, color: _green, size: 14),
                            SizedBox(width: 8),
                            Text(
                              'Heading styling matches template',
                              style: TextStyle(
                                color: _green,
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      )
                      : ElevatedButton.icon(
                        onPressed:
                            isApplying
                                ? null
                                : () {
                                  if (status == 'missing') {
                                    _addMissingHeading(result);
                                  } else {
                                    _applyHeadingStyle(result);
                                  }
                                },
                        icon:
                            isApplying
                                ? const SizedBox(
                                  width: 13,
                                  height: 13,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: Colors.white,
                                  ),
                                )
                                : Icon(
                                  status == 'missing'
                                      ? Icons.add
                                      : Icons.auto_fix_high,
                                  size: 14,
                                ),
                        label: Text(
                          isApplying
                              ? 'Applying…'
                              : status == 'missing'
                              ? 'Add "$name" with Template Style'
                              : 'Apply Template Style to Heading',
                          style: const TextStyle(fontSize: 12),
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: accentColor,
                          foregroundColor: Colors.white,
                          disabledBackgroundColor: accentColor.withOpacity(
                            0.35,
                          ),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 10,
                          ),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(6),
                          ),
                        ),
                      ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildParagraphStyleSection() {
    final issueCount = _paragraphStyleIssues.length;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.article_outlined, color: _purple, size: 18),
            const SizedBox(width: 8),
            Text(
              'Paragraph Style Compliance',
              style: TextStyle(
                color: _textPri,
                fontSize: 15,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(width: 8),
            if (issueCount > 0)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: _orange.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '$issueCount issues',
                  style: const TextStyle(
                    color: _orange,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            const Spacer(),
            if (_paragraphStyleLoading)
              const SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: _purple,
                ),
              )
            else
              TextButton.icon(
                onPressed: () {
                  setState(() {
                    _paragraphStyleLoaded = false;
                  });
                  _loadParagraphStyleCheck();
                },
                icon: const Icon(Icons.refresh, size: 13),
                label: const Text('Refresh', style: TextStyle(fontSize: 11)),
                style: TextButton.styleFrom(foregroundColor: _textSec),
              ),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          'Scans all body paragraphs for font, size, alignment, and line-spacing compliance.',
          style: TextStyle(color: _textSec, fontSize: 11, height: 1.4),
        ),
        const SizedBox(height: 12),

        if (_paragraphStyleError != null)
          _buildAlertBanner('Error', _paragraphStyleError!, _red)
        else if (_paragraphStyleLoading)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Center(child: CircularProgressIndicator(color: _purple)),
          )
        else if (_paragraphStyleIssues.isEmpty && _paragraphStyleLoaded)
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: _green.withOpacity(0.06),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: _green.withOpacity(0.2)),
            ),
            child: const Row(
              children: [
                Icon(Icons.check_circle_outline, color: _green, size: 16),
                SizedBox(width: 10),
                Text(
                  'All paragraphs match template styling  ✓',
                  style: TextStyle(color: _green, fontSize: 13),
                ),
              ],
            ),
          )
        else if (_paragraphStyleIssues.isNotEmpty) ...[
          // Apply all button
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _applyingAllParaStyle ? null : _applyAllParagraphStyle,
              icon:
                  _applyingAllParaStyle
                      ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                      : const Icon(Icons.auto_fix_high, size: 14),
              label: Text(
                _applyingAllParaStyle
                    ? 'Applying to all paragraphs…'
                    : 'Fix All $issueCount Paragraphs',
                style: const TextStyle(fontSize: 12),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: _purple,
                foregroundColor: Colors.white,
                disabledBackgroundColor: _purple.withOpacity(0.35),
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 10,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(6),
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          // Issue list (collapsed — show first 5)
          ..._paragraphStyleIssues
              .take(5)
              .map(
                (i) => _buildParagraphStyleIssueRow(i as Map<String, dynamic>),
              ),
          if (_paragraphStyleIssues.length > 5)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                '… and ${_paragraphStyleIssues.length - 5} more paragraphs',
                style: TextStyle(color: _textSec, fontSize: 11),
              ),
            ),
        ],
      ],
    );
  }

  Widget _buildParagraphStyleIssueRow(Map<String, dynamic> issue) {
    final preview = issue['text_preview'] as String? ?? '';
    final mismatches = (issue['mismatches'] as List?)?.cast<Map>() ?? [];
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: _orange.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.short_text, color: _orange, size: 13),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  preview,
                  style: TextStyle(color: _textSec, fontSize: 11),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          if (mismatches.isNotEmpty) ...[
            const SizedBox(height: 4),
            Wrap(
              spacing: 6,
              runSpacing: 4,
              children:
                  mismatches.map((m) {
                    final prop = m['property'] as String? ?? '';
                    final expected = m['expected'];
                    final actual = m['actual'];
                    return Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: _orange.withOpacity(0.08),
                        borderRadius: BorderRadius.circular(4),
                        border: Border.all(color: _orange.withOpacity(0.2)),
                      ),
                      child: Text(
                        '$prop: $actual → $expected',
                        style: const TextStyle(
                          color: _orange,
                          fontSize: 9,
                          fontFamily: 'monospace',
                        ),
                      ),
                    );
                  }).toList(),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildSectionRow(int index, Map<String, dynamic> sec) {
    final name = sec['name'] as String? ?? '';
    final order = (sec['order'] as num?)?.toInt() ?? 0;
    final required = sec['required'] as bool? ?? true;
    final status = sec['status'] as String? ?? 'missing';
    final matched = sec['matched_heading'] as String?;
    final layer = sec['match_layer'] as String?;
    final docPos = (sec['document_position'] as num?)?.toInt();
    final expanded = _expandedSections.contains(index);
    final statusC = _statusColor(status);
    final layerC = _layerColor(layer);

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: statusC.withOpacity(0.25)),
      ),
      child: Column(
        children: [
          InkWell(
            borderRadius: BorderRadius.circular(10),
            onTap:
                () => setState(
                  () =>
                      expanded
                          ? _expandedSections.remove(index)
                          : _expandedSections.add(index),
                ),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              child: Row(
                children: [
                  Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      color: statusC.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    alignment: Alignment.center,
                    child: Text(
                      '$order',
                      style: TextStyle(
                        color: statusC,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Row(
                      children: [
                        Text(
                          name,
                          style: TextStyle(
                            color: _textPri,
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        if (!required) ...[
                          const SizedBox(width: 8),
                          _Tag('optional', _textSec),
                        ],
                      ],
                    ),
                  ),
                  if (matched != null && matched != name) ...[
                    Icon(Icons.arrow_forward, size: 12, color: _textSec),
                    const SizedBox(width: 6),
                    Text(
                      matched,
                      style: TextStyle(color: _textSec, fontSize: 12),
                    ),
                    const SizedBox(width: 8),
                  ],
                  if (docPos != null)
                    Text(
                      '@$docPos',
                      style: TextStyle(color: _textSec, fontSize: 11),
                    ),
                  const SizedBox(width: 12),
                  if (layer != null) _Tag(layer, layerC),
                  const SizedBox(width: 8),
                  _Tag(status, statusC),
                  const SizedBox(width: 8),
                  Icon(
                    expanded
                        ? Icons.keyboard_arrow_up
                        : Icons.keyboard_arrow_down,
                    color: _textSec,
                    size: 18,
                  ),
                ],
              ),
            ),
          ),
          if (expanded) _buildFixPanel(name, status, matched, layer, required),
        ],
      ),
    );
  }

  Widget _buildFixPanel(
    String name,
    String status,
    String? matched,
    String? layer,
    bool required,
  ) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(56, 0, 16, 16),
      decoration: BoxDecoration(
        color: _bg,
        borderRadius: BorderRadius.vertical(bottom: Radius.circular(10)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Divider(color: _border, height: 1),
          const SizedBox(height: 12),
          Text(
            _fixExplanation(name, status, matched, layer),
            style: TextStyle(color: _textSec, fontSize: 12, height: 1.5),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: _buildFixButtons(name, status, matched),
          ),
        ],
      ),
    );
  }

  String _fixExplanation(
    String name,
    String status,
    String? matched,
    String? layer,
  ) {
    switch (status) {
      case 'missing':
        return 'The section "$name" was not found in your document. Add this heading.';
      case 'wrong_order':
        return '"$name" appears in the wrong position. It should come earlier.';
      case 'empty':
        return 'The section "$name" has no content after its heading.';
      case 'found' when layer == 'synonym':
        return '"$matched" was matched to "$name" via synonym detection. Consider renaming to "$name".';
      case 'found' when layer == 'fuzzy':
        return '"$matched" was matched to "$name" via fuzzy match (possible typo). Consider fixing.';
      default:
        return 'Section found and correctly placed. ✓';
    }
  }

  List<Widget> _buildFixButtons(String name, String status, String? matched) {
    final buttons = <Widget>[];
    switch (status) {
      case 'missing':
        buttons.add(
          _FixButton(
            label: 'Add "$name" heading',
            icon: Icons.add,
            color: _green,
            onTap: () => _applyFix('add_heading', {'section': name}),
          ),
        );
        break;
      case 'wrong_order':
        buttons.add(
          _FixButton(
            label: 'Reorder to correct position',
            icon: Icons.swap_vert,
            color: _yellow,
            onTap: () => _applyFix('reorder_section', {'section': name}),
          ),
        );
        break;
      case 'empty':
        buttons.add(
          _FixButton(
            label: 'Mark as acknowledged',
            icon: Icons.check,
            color: _textSec,
            onTap: () => _showSnack('Acknowledged', _textSec),
          ),
        );
        break;
      case 'found':
        if (matched != null && matched != name) {
          buttons.add(
            _FixButton(
              label: 'Rename "$matched" → "$name"',
              icon: Icons.edit,
              color: _blue,
              onTap:
                  () => _applyFix('rename_heading', {
                    'old': matched,
                    'new': name,
                  }),
            ),
          );
        }
        break;
    }
    buttons.add(
      _FixButton(
        label: 'Ignore',
        icon: Icons.visibility_off_outlined,
        color: _textSec,
        onTap: () => _showSnack('Issue ignored', _textSec),
      ),
    );
    return buttons;
  }

  Widget _buildLayerLegend() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Layer 2 — Heading Match Method',
            style: TextStyle(
              color: _textSec,
              fontSize: 11,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 16,
            runSpacing: 8,
            children: [
              _LegendItem('exact', _green, 'Exact text match'),
              _LegendItem(
                'synonym',
                _blue,
                'Known alias (e.g. "Intro" → "Introduction")',
              ),
              _LegendItem(
                'fuzzy',
                _yellow,
                'Typo correction (e.g. "Methdology")',
              ),
              _LegendItem(
                'semantic',
                const Color(0xFFA855F7),
                'Semantic similarity (MiniLM)',
              ),
              _LegendItem('missing', _red, 'Not found'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildAlertBanner(
    String title,
    String body,
    Color color, {
    String? fixLabel,
    VoidCallback? onFix,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          Icon(Icons.warning_amber_rounded, color: color, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    color: color,
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  body,
                  style: TextStyle(color: _textSec, fontSize: 12),
                ),
              ],
            ),
          ),
          if (fixLabel != null && onFix != null)
            TextButton(
              onPressed: onFix,
              child: Text(
                fixLabel,
                style: TextStyle(color: color, fontSize: 12),
              ),
            ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Tab 2: Content Mismatch
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildContentMismatchTab(
    List<dynamic> issues, {
    String modelMode = 'zero_shot',
  }) {
    if (issues.isEmpty) {
      return _buildEmptyState(
        Icons.psychology_outlined,
        'No content issues detected',
        'Grammar, paragraph relevance, and plagiarism checks found no issues.',
        color: _green,
      );
    }
    final hasTrained = issues.any((i) => (i as Map)['mode'] == 'trained_model');
    final hasZeroShot = issues.any((i) => (i as Map)['mode'] == 'zero_shot');
    final hasHybrid = issues.any((i) => (i as Map)['detection'] == 'hybrid');

    String modeLabel;
    String modeDesc;
    Color modeBannerColor;
    if (hasHybrid || hasTrained) {
      modeLabel = '🤖  Hybrid Mode Active (trained + zero-shot)';
      modeDesc =
          'Both the trained model and semantic similarity agree — high confidence.';
      modeBannerColor = _green;
    } else if (hasZeroShot) {
      modeLabel = '⚡  Zero-Shot Mode Active';
      modeDesc =
          'Using semantic similarity only. Train the model for better accuracy.';
      modeBannerColor = _blue;
    } else {
      modeLabel = '🔑  Keyword Mode Active';
      modeDesc = 'Install sentence-transformers for better results.';
      modeBannerColor = _yellow;
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildInfoBanner(modeLabel, modeDesc, modeBannerColor),
          const SizedBox(height: 16),
          ...issues.map(
            (i) => _buildContentIssueCard(i as Map<String, dynamic>),
          ),
        ],
      ),
    );
  }

  Widget _buildContentIssueCard(Map<String, dynamic> issue) {
    final func = issue['function'] as String? ?? '';
    if (func.isNotEmpty) {
      return _buildPipelineIssueCard(issue);
    }

    final heading = issue['heading'] as String? ?? '';
    final message = issue['message'] as String? ?? '';
    final mode =
        issue['mode'] as String? ??
        issue['detection'] as String? ??
        'zero_shot';
    final severity = issue['severity'] as String? ?? 'warning';
    final confidence = _safeDouble(issue['confidence']) ?? 0.0;
    final ownSimilarity = _safeDouble(issue['own_similarity']);
    final bestMatchScore = _safeDouble(issue['best_match_score']);
    final bestMatchHeading = issue['best_match_heading'] as String?;
    final pct = (confidence * 100).toInt();
    final gap =
        (ownSimilarity != null && bestMatchScore != null)
            ? bestMatchScore - ownSimilarity
            : null;
    String modeText;
    Color modeColor;
    if (mode == 'hybrid') {
      modeText = 'HYBRID';
      modeColor = _green;
    } else if (mode == 'trained_model' || mode == 'trained') {
      modeText = 'ML MODEL';
      modeColor = _green;
    } else if (mode == 'zero_shot') {
      modeText = 'ZERO-SHOT';
      modeColor = _blue;
    } else {
      modeText = 'KEYWORD';
      modeColor = _yellow;
    }
    final borderColor = severity == 'error' ? _red : _orange;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: borderColor.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 4,
                height: 44,
                decoration: BoxDecoration(
                  color: borderColor,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(width: 12),
              _Tag(severity == 'error' ? 'ERROR' : 'WARNING', borderColor),
              const SizedBox(width: 6),
              _Tag('CONTENT MISMATCH', _purple.withOpacity(0.7)),
              const SizedBox(width: 6),
              _Tag(modeText, modeColor),
              const Spacer(),
              Text(
                '$pct% mismatch',
                style: TextStyle(
                  color: pct > 85 ? _red : _orange,
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              const Icon(Icons.title, color: _orange, size: 14),
              const SizedBox(width: 6),
              Text(
                'Section: "$heading"',
                style: TextStyle(
                  color: _textPri,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            message,
            style: TextStyle(color: _textSec, fontSize: 12, height: 1.4),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Text(
                'Mismatch confidence: ',
                style: TextStyle(color: _textSec, fontSize: 10),
              ),
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: confidence.clamp(0.0, 1.0),
                    minHeight: 5,
                    backgroundColor: _border,
                    valueColor: AlwaysStoppedAnimation(
                      confidence > 0.85 ? _red : _orange,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '$pct%',
                style: TextStyle(
                  color: confidence > 0.85 ? _red : _orange,
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          if (ownSimilarity != null || bestMatchHeading != null) ...[
            const SizedBox(height: 10),
            Divider(color: _border, height: 1),
            const SizedBox(height: 10),
            if (ownSimilarity != null)
              _DiffRow(
                label: 'Own score',
                text:
                    '${ownSimilarity.toStringAsFixed(3)}  ← fit to current heading'
                    '${ownSimilarity < 0.45 ? "  ⚠ very low" : ""}',
                color:
                    ownSimilarity < 0.40
                        ? _red
                        : ownSimilarity < 0.52
                        ? _orange
                        : _yellow,
              ),
            if (bestMatchHeading != null && bestMatchScore != null) ...[
              const SizedBox(height: 6),
              _DiffRow(
                label: 'Better fit',
                text:
                    '"$bestMatchHeading"  →  score: ${bestMatchScore.toStringAsFixed(3)}'
                    '${gap != null ? "  (gap +${gap.toStringAsFixed(3)})" : ""}',
                color: _green,
              ),
              const SizedBox(height: 8),
              Text(
                'Tip: Consider moving this content to "$bestMatchHeading".',
                style: TextStyle(
                  color: _textSec,
                  fontSize: 10,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }

  Widget _buildPipelineIssueCard(Map<String, dynamic> issue) {
    final issueId = issue['issue_id'] as String? ?? '';
    final category = issue['category'] as String? ?? issue['function'] as String? ?? 'Issue';
    final severity = (issue['severity'] as String? ?? 'minor').toLowerCase();
    final borderColor = severity == 'major' ? _red : _yellow;
    final description = issue['description'] as String? ?? issue['reason'] as String? ?? '';
    final original = issue['original'] as String? ?? issue['current'] as String? ?? '';
    final suggestion = issue['suggestion'] as String? ?? '';
    final pid = issue['paragraph_id'] as String? ?? '';
    final fn = (issue['function'] as String? ?? issue['category'] as String? ?? '').toLowerCase();
    final issueType = (issue['type'] as String? ?? '').toLowerCase();
    final isParaRel = fn.contains('para') && fn.contains('relevance');
    final isHeadingFix = fn.contains('format') && issueType == 'heading_style';
    final isBulletFix = issueType == 'missing_bullets';
    final canFix = !isParaRel &&
        (isBulletFix || (pid.isNotEmpty && (suggestion.isNotEmpty || isHeadingFix)));

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: borderColor.withOpacity(0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _Tag(severity.toUpperCase(), borderColor),
              const SizedBox(width: 8),
              _Tag(category.toUpperCase(), _blue),
              if ((issue['page'] as num?) != null && (issue['page'] as num) > 0) ...[
                const Spacer(),
                Text('Page ${issue['page']}', style: TextStyle(color: _textSec, fontSize: 11)),
              ],
            ],
          ),
          if (description.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(description, style: TextStyle(color: _textSec, fontSize: 12, height: 1.4)),
          ],
          if (original.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: _DiffRow(label: 'Original', text: original, color: _red),
            ),
          if (suggestion.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: _DiffRow(label: 'Suggestion', text: suggestion, color: _green),
            ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: () {
                    setState(() => _ignoredIssueIds.add(issueId));
                    _showSnack('Issue ignored', _textSec);
                  },
                  child: const Text('Ignore'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: canFix ? _green : _surface2,
                  ),
                  onPressed: canFix
                      ? () async {
                          await _applyContentFixToBackend(issue, suggestion);
                          if (mounted && _resolvedIssueIds.contains(issueId)) {
                            _showSnack('Fix applied', _green);
                          }
                        }
                      : null,
                  child: Text(isBulletFix ? 'Apply Bullets' : 'Apply Fix'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildInfoBanner(String title, String body, Color color) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withOpacity(0.06),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline, color: color, size: 16),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    color: color,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  body,
                  style: TextStyle(
                    color: _textSec,
                    fontSize: 11,
                    height: 1.5,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Tab 3: Style
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildStyleTab(List<dynamic> issues) {
    if (issues.isEmpty) {
      return _buildEmptyState(
        Icons.check_circle_outline,
        'All styles match template requirements ✓',
        'All font sizes, bold settings, and spacing match the template.',
        color: _green,
      );
    }
    final fontSizeIssues =
        issues.where((i) => (i as Map)['type'] == 'wrong_font_size').toList();
    final boldIssues =
        issues.where((i) => (i as Map)['type'] == 'wrong_bold').toList();
    final fontNameIssues =
        issues.where((i) => (i as Map)['type'] == 'wrong_font').toList();
    final spacingIssues =
        issues
            .where((i) => (i as Map)['type'] == 'wrong_line_spacing')
            .toList();
    final aiFormattingIssues =
        issues
            .where((i) => (i as Map)['function'] == 'formatting')
            .toList();

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildInfoBanner(
            '🎨  Style Check — Template Compliance',
            'Compares font sizes, bold settings, font names, and line spacing '
                'against your template rules. Only available for .docx files.',
            _blue,
          ),
          const SizedBox(height: 16),
          if (aiFormattingIssues.isNotEmpty) ...[
            _StyleGroupHeader(
              'AI Formatting Check',
              aiFormattingIssues.length,
              Icons.rule,
              _purple,
            ),
            const SizedBox(height: 8),
            ...aiFormattingIssues.map(
              (i) => _buildPipelineIssueCard(i as Map<String, dynamic>),
            ),
            const SizedBox(height: 16),
          ],
          if (fontSizeIssues.isNotEmpty) ...[
            _StyleGroupHeader(
              'Font Size',
              fontSizeIssues.length,
              Icons.format_size,
              _red,
            ),
            const SizedBox(height: 8),
            ...fontSizeIssues.map(
              (i) => _buildStyleIssueCard(i as Map<String, dynamic>, _red),
            ),
            const SizedBox(height: 16),
          ],
          if (boldIssues.isNotEmpty) ...[
            _StyleGroupHeader(
              'Bold / Weight',
              boldIssues.length,
              Icons.format_bold,
              _yellow,
            ),
            const SizedBox(height: 8),
            ...boldIssues.map(
              (i) => _buildStyleIssueCard(i as Map<String, dynamic>, _yellow),
            ),
            const SizedBox(height: 16),
          ],
          if (fontNameIssues.isNotEmpty) ...[
            _StyleGroupHeader(
              'Font Name',
              fontNameIssues.length,
              Icons.font_download_outlined,
              _orange,
            ),
            const SizedBox(height: 8),
            ...fontNameIssues.map(
              (i) => _buildStyleIssueCard(i as Map<String, dynamic>, _orange),
            ),
            const SizedBox(height: 16),
          ],
          if (spacingIssues.isNotEmpty) ...[
            _StyleGroupHeader(
              'Line Spacing',
              spacingIssues.length,
              Icons.format_line_spacing,
              _purple,
            ),
            const SizedBox(height: 8),
            ...spacingIssues.map(
              (i) => _buildStyleIssueCard(i as Map<String, dynamic>, _purple),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildStyleIssueCard(Map<String, dynamic> issue, Color color) {
    // Unique key per card so each spinner is independent
    final issueKey =
        '${issue['type']}_${issue['code']}_'
        '${issue['para_index'] ?? issue['block_type'] ?? issue['message']}';
    final isFixing = _fixingStyleIssues.contains(issueKey);

    const typeLabels = {
      'wrong_font_size': 'Fix Font Size',
      'wrong_bold': 'Fix Bold',
      'wrong_font': 'Fix Font Name',
      'wrong_line_spacing': 'Fix Line Spacing',
      'missing_bullets': 'Apply Bullets',
    };
    final isBullet = issue['type'] == 'missing_bullets';
    final canFix = typeLabels.containsKey(issue['type'] as String? ?? '');

    // Build expected vs actual diff hint
    String? hint;
    if (issue['expected_font_size'] != null &&
        issue['actual_font_size'] != null)
      hint =
          'Expected ${issue['expected_font_size']}pt  •  Got ${issue['actual_font_size']}pt';
    else if (issue['expected_bold'] != null && issue['actual_bold'] != null)
      hint =
          'Expected bold=${issue['expected_bold']}  •  Got bold=${issue['actual_bold']}';
    else if (issue['expected_font_name'] != null &&
        issue['actual_font_name'] != null)
      hint =
          'Expected "${issue['expected_font_name']}"  •  Got "${issue['actual_font_name']}"';
    else if (issue['expected_line_spacing'] != null &&
        issue['actual_line_spacing'] != null)
      hint =
          'Expected ×${issue['expected_line_spacing']}  •  Got ×${issue['actual_line_spacing']}';

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Issue header ──────────────────────────────────────────────────
          Row(
            children: [
              Container(
                width: 3,
                height: 40,
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        _Tag('WARNING', color),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            issue['code'] as String? ?? '',
                            style: TextStyle(
                              color: _textSec,
                              fontSize: 10,
                              fontFamily: 'monospace',
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      issue['message'] as String? ?? '',
                      style: TextStyle(
                        color: _textSec,
                        fontSize: 12,
                        height: 1.4,
                      ),
                    ),
                    if (hint != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        hint,
                        style: TextStyle(
                          color: color.withOpacity(0.80),
                          fontSize: 11,
                          fontFamily: 'monospace',
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),

          // ── Fix button ────────────────────────────────────────────────────
          // UX: do NOT show 100+ per-issue style fix buttons.
          // Only keep the dedicated bullet fix button (usually few).
          if (canFix && isBullet) ...[
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed:
                    isFixing
                        ? null
                        : () {
                          _applyFix(
                            issue['fix_type'] as String? ??
                                'apply_section_bullets',
                            (issue['fix_details'] as Map<String, dynamic>?) ??
                                {},
                          );
                        },
                icon:
                    isFixing
                        ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                        : const Icon(Icons.auto_fix_high, size: 14),
                label: Text(
                  isFixing ? 'Applying…' : 'Apply Bullets',
                  style: const TextStyle(fontSize: 12),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: color,
                  foregroundColor: Colors.white,
                  disabledBackgroundColor: color.withOpacity(0.35),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 9,
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(6),
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Tab 4: Image Relevancy
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildImageRelevancyTab(
    List<dynamic> imageIssues,
    List<dynamic> formattingIssues,
  ) {
    final visible = imageIssues.where((i) {
      final id = (i as Map)['issue_id'] as String? ?? '';
      return !_ignoredIssueIds.contains(id) && !_resolvedIssueIds.contains(id);
    }).toList();
    if (visible.isEmpty && formattingIssues.isEmpty) {
      return SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildInfoBanner(
              '✅  No Image Issues Detected',
              'All images are relevant and no formatting problems were detected. '
                  'You can still run the FYP Image Formatter to standardise captions, sizes, and alignment.',
              _green,
            ),
            const SizedBox(height: 16),
            _buildImageFormatterButton(),
          ],
        ),
      );
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildImageFormatterButton(),
          const SizedBox(height: 20),
          if (visible.isNotEmpty) ...[
            _buildInfoBanner(
              '🖼  AI Image Relevancy Check',
              'These images were flagged as potentially irrelevant to the surrounding document content.',
              _red,
            ),
            const SizedBox(height: 16),
            ...visible.map(
              (i) {
                final issue = i as Map<String, dynamic>;
                return ImageIssueCardEnhanced(
                  issue: issue,
                  imageBaseUrl: _imageHostBase,
                  documentId: widget.documentId,
                  userId: context.read<AuthProvider>().userId,
                  onImageReplaced: (result) => _handleImageReplaceSuccess(
                    result,
                    issueId: issue['issue_id'] as String?,
                  ),
                  onImageRemoved: (result) => _handleImageRemoveSuccess(
                    result,
                    issueId: issue['issue_id'] as String?,
                  ),
                  onIgnore: () {
                    final issueId = issue['issue_id'] as String? ?? '';
                    setState(() => _ignoredIssueIds.add(issueId));
                    _showSnack('Issue ignored', _textSec);
                  },
                  onError: (e) => _showSnack('Image error: $e', _red),
                );
              },
            ),
            if (formattingIssues.isNotEmpty) const SizedBox(height: 28),
          ],
          if (formattingIssues.isNotEmpty) ...[
            Row(
              children: [
                const Icon(
                  Icons.warning_amber_rounded,
                  color: _yellow,
                  size: 16,
                ),
                const SizedBox(width: 8),
                Text(
                  'Other Formatting Issues  (${formattingIssues.length})',
                  style: const TextStyle(
                    color: _yellow,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ...formattingIssues.map(
              (i) => _buildFormattingIssueCard(i as Map<String, dynamic>),
            ),
          ],
        ],
      ),
    );
  }

  String _buildImageUrl(String rawPath) {
    final cleanPath =
        rawPath.startsWith('uploads/')
            ? rawPath.substring('uploads/'.length)
            : rawPath;
    final uri = Uri.tryParse(_baseUrl);
    final hostBase =
        uri != null
            ? '${uri.scheme}://${uri.host}:${uri.port}'
            : _baseUrl.split('/api').first;
    return '$hostBase/uploads/$cleanPath';
  }

  Widget _buildImageFormatterButton() {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [_blue.withOpacity(0.15), _purple.withOpacity(0.10)],
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
        ),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: _blue.withOpacity(0.4)),
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: _blue.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.auto_fix_high, color: _blue, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'FYP Image Formatter',
                      style: TextStyle(
                        color: _textPri,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    Text(
                      'Academic-standard formatting for all images',
                      style: TextStyle(color: _textSec, fontSize: 11),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: [
              _FeatureChip('• Centre-aligned', _blue),
              _FeatureChip('• Auto captions', _blue),
              _FeatureChip('• Figure numbering', _blue),
              _FeatureChip('• Table of Figures', _blue),
              _FeatureChip('• Keeps image+caption together', _blue),
              _FeatureChip('• Aspect-ratio safe', _blue),
            ],
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed:
                  () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder:
                          (_) => ImageFormatterScreen(
                            documentId: widget.documentId,
                            documentName: widget.documentName,
                          ),
                    ),
                  ),
              icon: const Icon(Icons.auto_fix_high, size: 16),
              label: const Text('Open Image Formatter'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFormattingIssueCard(Map<String, dynamic> issue) {
    final isCritical = (issue['type'] as String? ?? '') == 'CRITICAL';
    final color = isCritical ? _red : _yellow;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 3,
                height: 36,
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        _Tag(isCritical ? 'CRITICAL' : 'WARNING', color),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            issue['category'] as String? ?? '',
                            style: TextStyle(
                              color: _textSec,
                              fontSize: 11,
                              fontFamily: 'monospace',
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        if (((issue['line'] as num?)?.toInt() ?? 0) > 0)
                          Text(
                            'Line ${issue['line']}',
                            style: TextStyle(
                              color: _textSec,
                              fontSize: 10,
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      issue['description'] as String? ??
                          issue['reason'] as String? ??
                          issue['message'] as String? ??
                          '',
                      style: TextStyle(color: _textSec, fontSize: 12),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if ((issue['current'] as String? ?? '').isNotEmpty ||
              (issue['suggestion'] as String? ?? '').isNotEmpty) ...[
            const SizedBox(height: 10),
            Divider(color: _border, height: 1),
            const SizedBox(height: 10),
            if ((issue['current'] as String? ?? '').isNotEmpty)
              _DiffRow(label: 'Current', text: issue['current'], color: _red),
            if ((issue['suggestion'] as String? ?? '').isNotEmpty) ...[
              const SizedBox(height: 6),
              _DiffRow(
                label: 'Suggestion',
                text: issue['suggestion'],
                color: _green,
              ),
            ],
          ],
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Tab 5: Image Ethics
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildImageEthicsTab(List<dynamic> ethicsIssues) {
    final visible = ethicsIssues.where((i) {
      final id = (i as Map)['issue_id'] as String? ?? '';
      return !_ignoredIssueIds.contains(id) && !_resolvedIssueIds.contains(id);
    }).toList();
    if (visible.isEmpty) {
      return _buildEmptyState(
        Icons.verified_user_outlined,
        'No ethical issues detected',
        'All images passed the ethical content check.',
        color: _green,
      );
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildInfoBanner(
            'Unethical images flagged',
            'These images are shown so you can identify them. Review each one and replace with appropriate academic content before publishing.',
            _red,
          ),
          const SizedBox(height: 16),
          ...visible.map(
            (i) => _buildImageEthicsCard(i as Map<String, dynamic>),
          ),
        ],
      ),
    );
  }

  Widget _buildImageEthicsCard(Map<String, dynamic> issue) {
    final rawPath = issue['image_path'] as String? ?? '';
    final filename = issue['current'] as String? ?? rawPath;
    final reason =
        issue['description'] as String? ??
        issue['message'] as String? ??
        'Flagged as unethical.';
    final category =
        issue['sub_category'] as String? ??
        issue['ethics_category'] as String? ??
        'Unethical Content';
    final confidence = _safeDouble(issue['confidence']) ?? 1.0;
    final pct = (confidence * 100).toInt();

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: _red.withOpacity(0.45), width: 1.5),
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            color: _red.withOpacity(0.15),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Row(
              children: [
                const Icon(Icons.block, color: _red, size: 16),
                const SizedBox(width: 8),
                const Text(
                  '🚫  Unethical Image Detected',
                  style: TextStyle(
                    color: _red,
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                _Tag('ETHICS VIOLATION', _red),
                const SizedBox(width: 8),
                Text(
                  '$pct% confidence',
                  style: TextStyle(color: _textSec, fontSize: 11),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 0),
            child: Row(
              children: [
                Icon(Icons.label_outline, color: _textSec, size: 13),
                const SizedBox(width: 6),
                Text(
                  'Category: ',
                  style: TextStyle(color: _textSec, fontSize: 11),
                ),
                _Tag(category, _red),
              ],
            ),
          ),
          Container(
            height: 200,
            color: _surface2,
            child: rawPath.isEmpty
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.broken_image, color: _textSec, size: 40),
                        const SizedBox(height: 8),
                        Text(
                          'Image preview unavailable',
                          style: TextStyle(color: _textSec, fontSize: 12),
                        ),
                      ],
                    ),
                  )
                : Stack(
                    fit: StackFit.expand,
                    children: [
                      Image.network(
                        _buildImageUrl(rawPath),
                        fit: BoxFit.contain,
                        loadingBuilder: (ctx, child, progress) {
                          if (progress == null) return child;
                          return Center(
                            child: CircularProgressIndicator(
                              value: progress.expectedTotalBytes != null
                                  ? progress.cumulativeBytesLoaded /
                                      progress.expectedTotalBytes!
                                  : null,
                              color: _blue,
                              strokeWidth: 2,
                            ),
                          );
                        },
                        errorBuilder: (_, __, ___) => Center(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.broken_image, color: _textSec, size: 28),
                              const SizedBox(height: 6),
                              Text(
                                'Failed to load image',
                                style: TextStyle(color: _textSec, fontSize: 11),
                              ),
                            ],
                          ),
                        ),
                      ),
                      Positioned(
                        left: 0,
                        right: 0,
                        bottom: 0,
                        child: Container(
                          color: _red.withOpacity(0.85),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 6,
                          ),
                          child: const Text(
                            'Unethical — review and replace this image',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
          ),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.attach_file, color: _textSec, size: 12),
                    const SizedBox(width: 4),
                    Expanded(
                      child: Text(
                        filename,
                        style: TextStyle(
                          color: _textSec,
                          fontSize: 11,
                          fontFamily: 'monospace',
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  reason,
                  style: TextStyle(
                    color: _textSec,
                    fontSize: 12,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Text(
                      'Detection confidence: ',
                      style: TextStyle(color: _textSec, fontSize: 11),
                    ),
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: confidence.clamp(0.0, 1.0),
                          minHeight: 5,
                          backgroundColor: _border,
                          valueColor: const AlwaysStoppedAnimation(_red),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '$pct%',
                      style: const TextStyle(
                        color: _red,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                _buildAlertBanner(
                  'Action Required',
                  'Replace this image with appropriate academic content.',
                  _red,
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    icon: const Icon(Icons.image_search, size: 16),
                    label: const Text('Replace Image'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _blue,
                      foregroundColor: Colors.white,
                    ),
                    onPressed: () {
                      final auth = context.read<AuthProvider>();
                      final service = ImageReplacementService(imageBaseUrl: _imageHostBase);
                      showDialog(
                        context: context,
                        builder: (ctx) => ImageReplacementDialog(
                          documentId: widget.documentId,
                          imageIndex: jsonIntOr(issue['image_index'], 0),
                          currentImagePath: rawPath,
                          service: service,
                          userId: auth.userId,
                          onSuccess: (result) => _handleImageReplaceSuccess(
                            result,
                            issueId: issue['issue_id'] as String?,
                          ),
                          onError: (e) => _showSnack('Error: $e', _red),
                        ),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.delete_outline, size: 16),
                    label: const Text('Remove Image'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: _red,
                      side: BorderSide(color: _red.withOpacity(0.55)),
                    ),
                    onPressed: () async {
                      final confirmed = await showDialog<bool>(
                        context: context,
                        builder: (ctx) => AlertDialog(
                          backgroundColor: _surface,
                          title: Text(
                            'Remove Image?',
                            style: TextStyle(color: _textPri),
                          ),
                          content: Text(
                            'This permanently deletes the image from the document. '
                            'A nearby figure caption will also be removed if present.',
                            style: TextStyle(color: _textSec, fontSize: 13),
                          ),
                          actions: [
                            TextButton(
                              onPressed: () => Navigator.pop(ctx, false),
                              child: Text('Cancel', style: TextStyle(color: _textSec)),
                            ),
                            ElevatedButton(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: _red,
                                foregroundColor: Colors.white,
                              ),
                              onPressed: () => Navigator.pop(ctx, true),
                              child: const Text('Remove'),
                            ),
                          ],
                        ),
                      );
                      if (confirmed != true || !mounted) return;
                      try {
                        final auth = context.read<AuthProvider>();
                        final service =
                            ImageReplacementService(imageBaseUrl: _imageHostBase);
                        final result = await service.removeImage(
                          documentId: widget.documentId,
                          imageIndex: jsonIntOr(issue['image_index'], 0),
                          userId: auth.userId,
                        );
                        if (!mounted) return;
                        _handleImageRemoveSuccess(
                          result,
                          issueId: issue['issue_id'] as String?,
                        );
                      } catch (e) {
                        if (mounted) _showSnack('Remove failed: $e', _red);
                      }
                    },
                  ),
                ),
                const SizedBox(height: 8),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    onPressed: () {
                      final issueId = issue['issue_id'] as String? ?? '';
                      setState(() => _ignoredIssueIds.add(issueId));
                      _showSnack('Issue ignored', _textSec);
                    },
                    child: const Text('Ignore'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Tab 6: Bullets
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildBulletsTab() {
    return _BulletsTabContent(
      documentId: widget.documentId,
      userId: context.read<AuthProvider>().userId ?? 0,
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Tab 7: Tables
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildTablesTab() {
    if (_tablesLoading) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(color: _blue),
            SizedBox(height: 16),
            Text(
              'Scanning document for tables…',
              style: TextStyle(color: _textSec, fontSize: 13),
            ),
          ],
        ),
      );
    }

    if (_tablesError != null && _tables.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, color: _red, size: 48),
            const SizedBox(height: 12),
            Text(
              _tablesError!,
              style: const TextStyle(color: _red, fontSize: 13),
            ),
            const SizedBox(height: 16),
            ElevatedButton(onPressed: _loadTables, child: const Text('Retry')),
          ],
        ),
      );
    }

    final tablesWithIssues = _tables.where((t) => !t.isClean).toList();
    // Prefer showing issue tables; if none, show all so users can still apply style.
    final displayTables =
        tablesWithIssues.isNotEmpty ? tablesWithIssues : _tables;

    if (_tables.isEmpty) {
      return _buildEmptyState(
        Icons.table_chart_outlined,
        'No tables detected',
        'Your document contains no tables, or only unsupported PDF tables were found.',
      );
    }

    return Column(
      children: [
        if (_tablesSuccess != null)
          _buildBanner(_tablesSuccess!, _green, Icons.check_circle_outline),
        if (_tablesError != null)
          _buildBanner(_tablesError!, _red, Icons.error_outline),
        if (tablesWithIssues.isEmpty)
          _buildBanner(
            'All ${_tables.length} table(s) look good — select any to apply template style.',
            _green,
            Icons.check_circle_outline,
          ),

        Expanded(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Left: table list ─────────────────────────────────────────
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    Row(
                      children: [
                        OutlinedButton.icon(
                          onPressed:
                              displayTables.isNotEmpty
                                  ? () => setState(
                                    () =>
                                        _selectedTableIndices.isEmpty
                                            ? _selectedTableIndices.addAll(
                                              displayTables.map((t) => t.index),
                                            )
                                            : _selectedTableIndices.clear(),
                                  )
                                  : null,
                          icon: Icon(
                            _selectedTableIndices.isNotEmpty
                                ? Icons.deselect
                                : Icons.select_all,
                            size: 14,
                          ),
                          label: Text(
                            _selectedTableIndices.isNotEmpty
                                ? 'Clear All'
                                : 'Select All',
                            style: const TextStyle(fontSize: 12),
                          ),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: _blue,
                            side: BorderSide(color: _border),
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 8,
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        _Tag(
                          tablesWithIssues.isEmpty
                              ? '${_tables.length} tables'
                              : '${tablesWithIssues.length} tables with issues',
                          tablesWithIssues.isEmpty ? _green : _yellow,
                        ),
                        const SizedBox(width: 6),
                        _Tag(
                          '${_calculateTableIssueCount()} issues',
                          tablesWithIssues.isEmpty ? _green : _yellow,
                        ),
                        if (_selectedTableIndices.isNotEmpty) ...[
                          const SizedBox(width: 6),
                          _Tag(
                            '${_selectedTableIndices.length} selected',
                            _purple,
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 16),
                    ...displayTables.map((t) => _buildTableCard(t)),
                  ],
                ),
              ),

              // ── Right: sidebar ───────────────────────────────────────────
              _buildTablesSidebar(),
            ],
          ),
        ),

        _buildTablesActionBar(),
      ],
    );
  }

  Widget _buildBanner(String msg, Color color, IconData icon) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
      color: color.withOpacity(0.10),
      child: Row(
        children: [
          Icon(icon, color: color, size: 14),
          const SizedBox(width: 8),
          Expanded(
            child: Text(msg, style: TextStyle(color: color, fontSize: 12)),
          ),
        ],
      ),
    );
  }

  Widget _buildTableCard(_TableMeta table) {
    final isSelected = _selectedTableIndices.contains(table.index);
    final isExpanded = _expandedTableCards.contains(table.index);
    final issueColor = table.isClean ? _green : _yellow;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: _surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: isSelected ? _blue : _border,
          width: isSelected ? 1.5 : 0.5,
        ),
      ),
      child: Column(
        children: [
          InkWell(
            borderRadius: BorderRadius.circular(10),
            onTap:
                () => setState(
                  () =>
                      isExpanded
                          ? _expandedTableCards.remove(table.index)
                          : _expandedTableCards.add(table.index),
                ),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              child: Row(
                children: [
                  GestureDetector(
                    onTap:
                        () => setState(
                          () =>
                              isSelected
                                  ? _selectedTableIndices.remove(table.index)
                                  : _selectedTableIndices.add(table.index),
                        ),
                    behavior: HitTestBehavior.opaque,
                    child: Padding(
                      padding: const EdgeInsets.only(right: 10),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 150),
                        width: 20,
                        height: 20,
                        decoration: BoxDecoration(
                          color: isSelected ? _blue : Colors.transparent,
                          border: Border.all(
                            color: isSelected ? _blue : _border,
                            width: 1.5,
                          ),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child:
                            isSelected
                                ? const Icon(
                                  Icons.check,
                                  color: Colors.white,
                                  size: 14,
                                )
                                : null,
                      ),
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 3,
                    ),
                    decoration: BoxDecoration(
                      color: _surface2,
                      borderRadius: BorderRadius.circular(5),
                      border: Border.all(color: _border),
                    ),
                    child: Text(
                      table.label,
                      style: TextStyle(
                        color: _textSec,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${table.rowCount} rows × ${table.colCount} columns',
                          style: TextStyle(
                            color: _textPri,
                            fontSize: 13,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Row(
                          children: [
                            if (table.hasHeaderRow) ...[
                              const Icon(Icons.title, color: _green, size: 11),
                              const SizedBox(width: 3),
                              const Text(
                                'Header row',
                                style: TextStyle(color: _green, fontSize: 10),
                              ),
                              const SizedBox(width: 8),
                            ] else ...[
                              const Icon(
                                Icons.warning_amber,
                                color: _yellow,
                                size: 11,
                              ),
                              const SizedBox(width: 3),
                              const Text(
                                'No header',
                                style: TextStyle(color: _yellow, fontSize: 10),
                              ),
                              const SizedBox(width: 8),
                            ],
                            _Tag(table.source.toUpperCase(), _textSec),
                          ],
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: issueColor.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: issueColor.withOpacity(0.3)),
                    ),
                    child: Text(
                      table.isClean
                          ? 'Clean'
                          : '${table.issueCount} issue${table.issueCount > 1 ? "s" : ""}',
                      style: TextStyle(
                        color: issueColor,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Icon(
                    isExpanded
                        ? Icons.keyboard_arrow_up
                        : Icons.keyboard_arrow_down,
                    color: _textSec,
                    size: 18,
                  ),
                ],
              ),
            ),
          ),
          if (isExpanded)
            Container(
              decoration: BoxDecoration(
                color: _bg,
                borderRadius: BorderRadius.vertical(
                  bottom: Radius.circular(10),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Divider(color: _border, height: 1),
                  if (table.previewRows.isNotEmpty) ...[
                    Padding(
                      padding: EdgeInsets.fromLTRB(14, 12, 14, 6),
                      child: Text(
                        'PREVIEW',
                        style: TextStyle(
                          color: _textSec,
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.6,
                        ),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(6),
                        child: Table(
                          border: TableBorder.all(color: _border, width: 0.5),
                          defaultColumnWidth: const FlexColumnWidth(),
                          children:
                              table.previewRows.asMap().entries.map((entry) {
                                final isHeader =
                                    entry.key == 0 && table.hasHeaderRow;
                                return TableRow(
                                  decoration: BoxDecoration(
                                    color:
                                        isHeader
                                            ? _blue.withOpacity(0.12)
                                            : Colors.transparent,
                                  ),
                                  children:
                                      entry.value.asMap().entries.map((cellEntry) {
                                        final cell = cellEntry.value;
                                        final isEmptyCell = cell.trim().isEmpty;
                                        return Padding(
                                          padding: const EdgeInsets.symmetric(
                                            horizontal: 8,
                                            vertical: 6,
                                          ),
                                          child: Container(
                                            padding: isEmptyCell
                                                ? const EdgeInsets.symmetric(
                                                    horizontal: 4,
                                                    vertical: 2,
                                                  )
                                                : EdgeInsets.zero,
                                            decoration: isEmptyCell
                                                ? BoxDecoration(
                                                    color: _yellow.withOpacity(0.12),
                                                    borderRadius:
                                                        BorderRadius.circular(4),
                                                    border: Border.all(
                                                      color: _yellow.withOpacity(0.45),
                                                    ),
                                                  )
                                                : null,
                                            child: Text(
                                              isEmptyCell ? '(empty)' : cell,
                                              style: TextStyle(
                                                color: isEmptyCell
                                                    ? _yellow
                                                    : (isHeader ? _blue : _textSec),
                                                fontSize: 11,
                                                fontWeight: isHeader
                                                    ? FontWeight.w600
                                                    : FontWeight.w400,
                                                fontStyle: isEmptyCell
                                                    ? FontStyle.italic
                                                    : FontStyle.normal,
                                              ),
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                          ),
                                        );
                                      }).toList(),
                                );
                              }).toList(),
                        ),
                      ),
                    ),
                  ],
                  if (table.issues.isNotEmpty) ...[
                    Padding(
                      padding: EdgeInsets.fromLTRB(14, 0, 14, 6),
                      child: Text(
                        'ISSUES',
                        style: TextStyle(
                          color: _textSec,
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.6,
                        ),
                      ),
                    ),
                    ...table.issues.map((issue) {
                      final Color c;
                      final IconData ic;
                      switch (issue.severity) {
                        case 'error':
                          c = _red;
                          ic = Icons.error_outline;
                          break;
                        case 'warning':
                          c = _yellow;
                          ic = Icons.warning_amber_rounded;
                          break;
                        default:
                          c = _blue;
                          ic = Icons.info_outline;
                      }
                      return Padding(
                        padding: const EdgeInsets.fromLTRB(14, 0, 14, 8),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(ic, color: c, size: 13),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    issue.code,
                                    style: TextStyle(
                                      color: c,
                                      fontSize: 10,
                                      fontWeight: FontWeight.w700,
                                      fontFamily: 'monospace',
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    issue.message,
                                    style: TextStyle(
                                      color: _textSec,
                                      fontSize: 11,
                                      height: 1.4,
                                    ),
                                  ),
                                  if (issue.isFillableEmptyCell) ...[
                                    const SizedBox(height: 8),
                                    Align(
                                      alignment: Alignment.centerLeft,
                                      child: OutlinedButton.icon(
                                        onPressed: _tablesFormatting
                                            ? null
                                            : () => _promptAndFillEmptyCell(
                                                  table,
                                                  issue,
                                                ),
                                        icon: const Icon(
                                          Icons.edit_note,
                                          size: 14,
                                        ),
                                        label: const Text(
                                          'Fill empty cell',
                                          style: TextStyle(fontSize: 11),
                                        ),
                                        style: OutlinedButton.styleFrom(
                                          foregroundColor: _blue,
                                          side: BorderSide(color: _blue.withOpacity(0.5)),
                                          padding: const EdgeInsets.symmetric(
                                            horizontal: 10,
                                            vertical: 6,
                                          ),
                                          visualDensity: VisualDensity.compact,
                                        ),
                                      ),
                                    ),
                                  ],
                                  if (issue.isNormalizeFontIssue) ...[
                                    const SizedBox(height: 8),
                                    Align(
                                      alignment: Alignment.centerLeft,
                                      child: OutlinedButton.icon(
                                        onPressed: _tablesFormatting
                                            ? null
                                            : () => _normalizeTableFonts(table),
                                        icon: const Icon(
                                          Icons.font_download_outlined,
                                          size: 14,
                                        ),
                                        label: const Text(
                                          'Normalize font',
                                          style: TextStyle(fontSize: 11),
                                        ),
                                        style: OutlinedButton.styleFrom(
                                          foregroundColor: _purple,
                                          side: BorderSide(
                                            color: _purple.withOpacity(0.5),
                                          ),
                                          padding: const EdgeInsets.symmetric(
                                            horizontal: 10,
                                            vertical: 6,
                                          ),
                                          visualDensity: VisualDensity.compact,
                                        ),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            ),
                          ],
                        ),
                      );
                    }),
                    const SizedBox(height: 12),
                  ] else
                    const Padding(
                      padding: EdgeInsets.fromLTRB(14, 8, 14, 16),
                      child: Row(
                        children: [
                          Icon(
                            Icons.check_circle_outline,
                            color: _green,
                            size: 14,
                          ),
                          SizedBox(width: 6),
                          Text(
                            'No issues detected',
                            style: TextStyle(color: _green, fontSize: 12),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  // ── CHANGED: Sidebar now shows template info instead of preset picker ─────
  //
  // The three preset cards and rule toggles are removed.
  // Instead the user sees:
  //   • A "TEMPLATE STYLE" header with the active template name.
  //   • A brief explanation of what will happen when they apply.
  //   • A read-only list of what the template configures (font, header, etc.)
  //     sourced from the same labels as TableStylesCard in the admin panel.
  //   • An info note matching the one already in TableStylesCard.

  Widget _buildTablesSidebar() {
    return Container(
      width: 280,
      decoration: BoxDecoration(
        color: _surface,
        border: Border(left: BorderSide(color: _border)),
      ),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Header ────────────────────────────────────────────────────────
            Text(
              'TEMPLATE STYLE',
              style: TextStyle(
                color: _textSec,
                fontSize: 10,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.6,
              ),
            ),
            const SizedBox(height: 10),

            // ── Active template card ──────────────────────────────────────────
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: _purple.withOpacity(0.10),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: _purple.withOpacity(0.35),
                  width: 1.5,
                ),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: _purple.withOpacity(0.18),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: const Icon(
                      Icons.table_chart_outlined,
                      color: _purple,
                      size: 16,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.templateName,
                          style: TextStyle(
                            color: _textPri,
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                        Text(
                          'Configured by admin',
                          style: TextStyle(color: _textSec, fontSize: 10),
                        ),
                      ],
                    ),
                  ),
                  // "active" checkmark
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 6,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: _purple.withOpacity(0.18),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Text(
                      'ACTIVE',
                      style: TextStyle(
                        color: _purple,
                        fontSize: 9,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 16),

            // ── What will be applied ──────────────────────────────────────────
            Text(
              'WHAT GETS APPLIED',
              style: TextStyle(
                color: _textSec,
                fontSize: 10,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.6,
              ),
            ),
            const SizedBox(height: 8),

            _sidebarInfoRow(
              Icons.font_download_outlined,
              'Font family & size',
              'As set by admin in template',
            ),
            _sidebarInfoRow(
              Icons.title,
              'Header row style',
              'Bold, alignment & background colour',
            ),
            _sidebarInfoRow(
              Icons.format_align_left,
              'Body row alignment',
              'Left / center / right per template',
            ),
            _sidebarInfoRow(
              Icons.view_agenda_outlined,
              'Banded rows',
              'Alternating row shading if enabled',
            ),
            _sidebarInfoRow(
              Icons.border_all,
              'Borders',
              'Colour & thickness per template',
            ),
            _sidebarInfoRow(
              Icons.space_bar,
              'Cell padding',
              'Top / bottom / left / right (twips)',
            ),
            _sidebarInfoRow(
              Icons.center_focus_strong,
              'Layout',
              'Centre table, auto-fit & repeat header',
            ),

            const SizedBox(height: 16),

            // ── Info note (mirrors TableStylesCard) ───────────────────────────
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: _purple.withOpacity(0.07),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: _purple.withOpacity(0.22)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.info_outline, size: 13, color: _purple),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Table styles are configured by your admin in the '
                      'template settings. Select tables on the left, then '
                      'tap "Apply Template Style" to format them.',
                      style: TextStyle(
                        fontSize: 11,
                        color: _textSec,
                        height: 1.5,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // Small icon + label row used inside the sidebar.
  Widget _sidebarInfoRow(IconData icon, String label, String sub) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Icon(icon, color: _textSec, size: 14),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    color: _textPri,
                    fontSize: 11,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                Text(
                  sub,
                  style: TextStyle(color: _textSec, fontSize: 10),
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── CHANGED: Action bar — calls _applyTemplateFormatting() ───────────────
  //
  // • Button label changed to "Apply Template Style (N)"
  // • Bottom-left subtitle changed from "Preset: academic" to
  //   "Style: from template · ${widget.templateName}"

  Widget _buildTablesActionBar() {
    final count = _selectedTableIndices.length;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
      decoration: BoxDecoration(
        color: _surface,
        border: Border(top: BorderSide(color: _border)),
      ),
      child: Row(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                count == 0
                    ? 'No tables selected'
                    : '$count table${count > 1 ? "s" : ""} selected',
                style: TextStyle(
                  color: count > 0 ? _textPri : _textSec,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
              // ── Changed subtitle ──────────────────────────────────────────────
              Text(
                'Style: from template · ${widget.templateName}',
                style: TextStyle(color: _textSec, fontSize: 11),
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
          const Spacer(),
          TextButton.icon(
            onPressed: _tablesLoading ? null : _loadTables,
            icon: const Icon(Icons.refresh, size: 14),
            label: const Text('Re-scan', style: TextStyle(fontSize: 12)),
            style: TextButton.styleFrom(foregroundColor: _textSec),
          ),
          const SizedBox(width: 12),
          // ── Changed button: calls _applyTemplateFormatting ────────────────
          ElevatedButton.icon(
            onPressed:
                (count == 0 || _tablesFormatting)
                    ? null
                    : _applyTemplateFormatting,
            icon:
                _tablesFormatting
                    ? const SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                    : const Icon(Icons.auto_fix_high, size: 16),
            label: Text(
              _tablesFormatting
                  ? 'Applying…'
                  : count == 0
                  ? 'Select tables above'
                  : 'Apply Template Style ($count)',
              style: const TextStyle(fontSize: 13),
            ),
            style: ElevatedButton.styleFrom(
              backgroundColor: count > 0 ? _purple : _surface2,
              foregroundColor: count > 0 ? Colors.white : _textSec,
              disabledBackgroundColor: _surface2,
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Tab 8: Document Lists (TOC / LOT / LOF)
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildDocumentListsTab() {
    if (_tocLoading && !_tocLoaded) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(color: _blue),
            SizedBox(height: 14),
            Text(
              'Scanning document structure…',
              style: TextStyle(color: _textSec, fontSize: 12),
            ),
          ],
        ),
      );
    }

    if (_tocError != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, color: _red, size: 40),
            const SizedBox(height: 10),
            Text(_tocError!, style: const TextStyle(color: _red, fontSize: 12)),
            const SizedBox(height: 14),
            ElevatedButton(
              onPressed: _loadTocCheck,
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    final headingCount = (_tocData['heading_count'] as num?)?.toInt() ?? 0;
    final tableCount = (_tocData['table_count'] as num?)?.toInt() ?? 0;
    final figureCount = (_tocData['figure_count'] as num?)?.toInt() ?? 0;
    final hasToc = _tocData['has_toc'] as bool? ?? false;
    final tocPopulated = _tocData['toc_populated'] as bool? ?? false;
    final hasLot = _tocData['has_lot'] as bool? ?? false;
    final hasLof = _tocData['has_lof'] as bool? ?? false;
    final headings = _tocData['headings'] as List<dynamic>? ?? [];
    final tablesMissingCaptions =
        (_tocData['tables_missing_captions'] as num?)?.toInt() ?? 0;
    final figuresMissingCaptions =
        (_tocData['figures_missing_captions'] as num?)?.toInt() ?? 0;

    final canGenerateToc = headingCount > 0;
    final canGenerateLot = tableCount > 0;
    final canGenerateLof = figureCount > 0;
    final anySelected = _includeToc || _includeLot || _includeLof;

    return Column(
      children: [
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: _blue.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(Icons.toc, color: _blue, size: 20),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Document Lists',
                            style: TextStyle(
                              color: _textPri,
                              fontSize: 16,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          Text(
                            'Generate dynamic Word fields for TOC, tables, and figures',
                            style: TextStyle(color: _textSec, fontSize: 12),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                _buildInfoBanner(
                  'How it works',
                  'Toggle the lists you want, then click Generate. '
                      'Word will populate page numbers when you open the exported '
                      'document and choose Update Table / Update Field.',
                  _blue,
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _Tag('$headingCount headings', _blue),
                    _Tag('$tableCount tables', _purple),
                    _Tag('$figureCount figures', _orange),
                  ],
                ),
                const SizedBox(height: 20),
                _buildListToggleCard(
                  title: 'Table of Contents',
                  subtitle: 'Auto-generate from document heading hierarchy (Heading 1–3)',
                  icon: Icons.format_list_bulleted,
                  color: _blue,
                  value: _includeToc,
                  enabled: canGenerateToc,
                  statusTag: hasToc
                      ? (tocPopulated ? 'Added' : 'Placeholder')
                      : null,
                  statusColor: hasToc
                      ? (tocPopulated ? _green : _yellow)
                      : null,
                  warning: hasToc && !tocPopulated
                      ? 'TOC field exists but is empty — click Generate to populate it'
                      : null,
                  disabledReason: canGenerateToc
                      ? null
                      : 'No headings detected — apply heading styles first',
                  onChanged: (v) => setState(() => _includeToc = v),
                ),
                const SizedBox(height: 12),
                _buildListToggleCard(
                  title: 'List of Tables',
                  subtitle: 'Auto-generate from table captions (Table N: …)',
                  icon: Icons.table_chart_outlined,
                  color: _purple,
                  value: _includeLot,
                  enabled: canGenerateLot,
                  statusTag: hasLot ? 'Added' : null,
                  statusColor: hasLot ? _green : null,
                  disabledReason: canGenerateLot
                      ? null
                      : 'No tables detected in this document',
                  warning: tablesMissingCaptions > 0
                      ? '$tablesMissingCaptions table(s) missing captions — '
                          'captions will be added automatically'
                      : null,
                  onChanged: (v) => setState(() => _includeLot = v),
                ),
                const SizedBox(height: 12),
                _buildListToggleCard(
                  title: 'List of Figures',
                  subtitle: 'Auto-generate from figure captions (Figure N: …)',
                  icon: Icons.image_outlined,
                  color: _orange,
                  value: _includeLof,
                  enabled: canGenerateLof,
                  statusTag: hasLof ? 'Added' : null,
                  statusColor: hasLof ? _green : null,
                  disabledReason: canGenerateLof
                      ? null
                      : 'No figures/images detected in this document',
                  warning: figuresMissingCaptions > 0
                      ? '$figuresMissingCaptions figure(s) missing captions — '
                          'format images first or captions will be added'
                      : null,
                  onChanged: (v) => setState(() => _includeLof = v),
                ),
                if (headings.isNotEmpty) ...[
                  const SizedBox(height: 24),
                  Text(
                    'Detected Headings',
                    style: TextStyle(
                      color: _textPri,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 8),
                  ...headings.take(12).map((h) {
                    final item = h as Map<String, dynamic>;
                    final level = (item['level'] as num?)?.toInt() ?? 1;
                    final text = item['text'] as String? ?? '';
                    return Container(
                      margin: const EdgeInsets.only(bottom: 4),
                      padding: EdgeInsets.fromLTRB(12 + (level - 1) * 14.0, 8, 12, 8),
                      decoration: BoxDecoration(
                        color: _surface,
                        borderRadius: BorderRadius.circular(6),
                        border: const Border(
                          left: BorderSide(color: _blue, width: 3),
                        ),
                      ),
                      child: Row(
                        children: [
                          _Tag('H$level', _blue),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              text,
                              style: TextStyle(
                                color: _textPri,
                                fontSize: 12,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                        ],
                      ),
                    );
                  }),
                  if (headings.length > 12)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text(
                        '+ ${headings.length - 12} more headings',
                        style: TextStyle(color: _textSec, fontSize: 11),
                      ),
                    ),
                ],
              ],
            ),
          ),
        ),
        _buildDocumentListsActionBar(anySelected: anySelected),
      ],
    );
  }

  Widget _buildListToggleCard({
    required String title,
    required String subtitle,
    required IconData icon,
    required Color color,
    required bool value,
    required bool enabled,
    String? statusTag,
    Color? statusColor,
    required ValueChanged<bool> onChanged,
    String? disabledReason,
    String? warning,
  }) {
    return Opacity(
      opacity: enabled ? 1.0 : 0.55,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: _surface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: value && enabled ? color.withOpacity(0.45) : _border,
            width: value && enabled ? 1.5 : 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(icon, color: color, size: 18),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              title,
                              style: TextStyle(
                                color: _textPri,
                                fontSize: 14,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          if (statusTag != null)
                            _Tag(statusTag, statusColor ?? _green),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        subtitle,
                        style: TextStyle(
                          color: _textSec,
                          fontSize: 11,
                          height: 1.4,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Transform.scale(
                  scale: 0.9,
                  child: Switch(
                    value: value,
                    onChanged: enabled ? onChanged : null,
                    activeColor: color,
                    inactiveThumbColor: _textSec,
                    inactiveTrackColor: _border,
                  ),
                ),
              ],
            ),
            if (!enabled && disabledReason != null) ...[
              const SizedBox(height: 10),
              Text(
                disabledReason,
                style: TextStyle(
                  color: _red.withOpacity(0.85),
                  fontSize: 11,
                ),
              ),
            ],
            if (enabled && warning != null) ...[
              const SizedBox(height: 10),
              Text(
                warning,
                style: TextStyle(
                  color: _yellow.withOpacity(0.9),
                  fontSize: 11,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildDocumentListsActionBar({required bool anySelected}) {
    final selectedCount = [
      if (_includeToc) 'TOC',
      if (_includeLot) 'LOT',
      if (_includeLof) 'LOF',
    ].length;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
      decoration: BoxDecoration(
        color: _surface,
        border: Border(top: BorderSide(color: _border)),
      ),
      child: Row(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                anySelected
                    ? '$selectedCount list${selectedCount == 1 ? '' : 's'} selected'
                    : 'No lists selected',
                style: TextStyle(
                  color: anySelected ? _textPri : _textSec,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
              Text(
                'Fields update page numbers in Microsoft Word',
                style: TextStyle(color: _textSec, fontSize: 11),
              ),
            ],
          ),
          const Spacer(),
          TextButton.icon(
            onPressed: _tocLoading ? null : _loadTocCheck,
            icon: const Icon(Icons.refresh, size: 14),
            label: const Text('Re-scan', style: TextStyle(fontSize: 12)),
            style: TextButton.styleFrom(foregroundColor: _textSec),
          ),
          const SizedBox(width: 12),
          ElevatedButton.icon(
            onPressed: (!anySelected || _generatingLists)
                ? null
                : _generateSelectedLists,
            icon: _generatingLists
                ? const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.playlist_add_check, size: 16),
            label: Text(
              _generatingLists
                  ? 'Generating…'
                  : anySelected
                      ? 'Generate Selected Lists'
                      : 'Select lists above',
              style: const TextStyle(fontSize: 13),
            ),
            style: ElevatedButton.styleFrom(
              backgroundColor: anySelected ? _blue : _surface2,
              foregroundColor: anySelected ? Colors.white : _textSec,
              disabledBackgroundColor: _surface2,
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showSnack(String msg, Color color) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: color,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Tab 8: Document Blocks
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildBlocksTab(List<dynamic> blocks) {
    if (blocks.isEmpty) {
      return _buildEmptyState(
        Icons.article_outlined,
        'No document content',
        'The document could not be parsed or is empty.',
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(24),
      itemCount: blocks.length,
      itemBuilder: (ctx, i) {
        final block = blocks[i] as Map<String, dynamic>;
        final type = block['type'] as String? ?? 'paragraph';
        final text = block['text'] as String? ?? '';
        final level = (block['level'] as num?)?.toInt();
        Color typeColor;
        IconData typeIcon;
        double leftPad = 0;
        switch (type) {
          case 'heading':
            typeColor = _blue;
            typeIcon = Icons.title;
            leftPad = ((level ?? 1) - 1) * 16.0;
            break;
          case 'list_item':
            typeColor = _yellow;
            typeIcon = Icons.format_list_bulleted;
            leftPad = 16;
            break;
          case 'table':
            typeColor = const Color(0xFFA855F7);
            typeIcon = Icons.table_chart_outlined;
            break;
          default:
            typeColor = _textSec;
            typeIcon = Icons.short_text;
        }
        return Container(
          margin: const EdgeInsets.only(bottom: 4),
          padding: EdgeInsets.fromLTRB(16 + leftPad, 10, 16, 10),
          decoration: BoxDecoration(
            color: _surface,
            borderRadius: BorderRadius.circular(6),
            border: Border(left: BorderSide(color: typeColor, width: 3)),
          ),
          child: Row(
            children: [
              SizedBox(
                width: 32,
                child: Text(
                  '${i + 1}',
                  style: TextStyle(
                    color: _textSec,
                    fontSize: 10,
                    fontFamily: 'monospace',
                  ),
                ),
              ),
              Icon(typeIcon, color: typeColor, size: 14),
              const SizedBox(width: 10),
              _Tag(type + (level != null ? ' H$level' : ''), typeColor),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  text.length > 120 ? '${text.substring(0, 120)}…' : text,
                  style: TextStyle(
                    color: type == 'heading' ? _textPri : _textSec,
                    fontSize: type == 'heading' ? 13 : 12,
                    fontWeight:
                        type == 'heading' ? FontWeight.w600 : FontWeight.w400,
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Tab 9: References
  // ─────────────────────────────────────────────────────────────────────────

  Widget _buildReferencesTab() {
    final userId = context.read<AuthProvider>().userId ?? 0;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: _purple.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.format_list_numbered,
                  color: _purple,
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Reference Formatter',
                    style: TextStyle(
                      color: _textPri,
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  Text(
                    'Detect, clean and reformat your References section',
                    style: TextStyle(color: _textSec, fontSize: 12),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: _purple.withOpacity(0.07),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: _purple.withOpacity(0.25)),
            ),
            child: Row(
              children: [
                const Icon(Icons.info_outline, color: _purple, size: 15),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Rules are set by your university admin in the template. '
                    'Press "Scan References" to preview, then "Format References" to apply.',
                    style: TextStyle(
                      color: _purple.withOpacity(0.85),
                      fontSize: 12,
                      height: 1.5,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          ReferenceFormatterWidget(
            documentId: widget.documentId,
            userId: userId,
          ),
        ],
      ),
    );
  }

  // ── Action bar ────────────────────────────────────────────────────────────

  Widget _buildActionBar(List<dynamic> oldIssues) {
    final activeIssues = oldIssues.where((i) {
      final id = (i as Map)['issue_id'] as String? ?? '';
      return !_ignoredIssueIds.contains(id) && !_resolvedIssueIds.contains(id);
    }).length;
    final majorCount = oldIssues.where((i) {
      final sev = ((i as Map)['severity'] as String? ?? '').toLowerCase();
      return sev == 'major' || sev == 'critical' || sev == 'error';
    }).length;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
      decoration: BoxDecoration(
        color: _surface,
        border: Border(top: BorderSide(color: _border)),
      ),
      child: Row(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '$activeIssues issues  ·  $majorCount major',
                style: TextStyle(color: _textPri, fontSize: 13),
              ),
              Text(
                'Review highlights, apply fixes, then download',
                style: TextStyle(color: _textSec, fontSize: 11),
              ),
            ],
          ),
          const Spacer(),
          TextButton(
            onPressed: () => _showSnack('All issues ignored', _textSec),
            child: Text('Ignore All', style: TextStyle(color: _textSec)),
          ),
          const SizedBox(width: 12),
          _isFixApplied
              ? ElevatedButton.icon(
                onPressed: _isDownloading ? null : _downloadDirectly,
                icon:
                    _isDownloading
                        ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                        : const Icon(Icons.download, size: 16),
                label: Text(
                  _isDownloading
                      ? 'Downloading...'
                      : 'Download Formatted Document',
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: _green,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 12,
                  ),
                ),
              )
              : ElevatedButton.icon(
                onPressed: _isApplyingFix ? null : _applyAllFixesAndStyles,
                icon:
                    _isApplyingFix
                        ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                        : const Icon(Icons.auto_fix_high, size: 16),
                label: Text(
                  _isApplyingFix
                      ? 'Applying all fixes...'
                      : 'Apply All Fixes',
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: _purple,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 12,
                  ),
                ),
              ),
        ],
      ),
    );
  }

  // ── Empty state ───────────────────────────────────────────────────────────

  Widget _buildEmptyState(
    IconData icon,
    String title,
    String subtitle, {
    Color? color,
    String? actionLabel,
    VoidCallback? onAction,
  }) {
    final c = color ?? _textSec;
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: c.withOpacity(0.4), size: 56),
          const SizedBox(height: 16),
          Text(
            title,
            style: TextStyle(
              color: c,
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 6),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 48),
            child: Text(
              subtitle,
              style: TextStyle(color: _textSec, fontSize: 12),
              textAlign: TextAlign.center,
            ),
          ),
          if (actionLabel != null && onAction != null) ...[
            const SizedBox(height: 16),
            TextButton(
              onPressed: onAction,
              child: Text(actionLabel, style: const TextStyle(color: _blue)),
            ),
          ],
        ],
      ),
    );
  }

  // ── Content Check tab UI ──────────────────────────────────────────────────

  Widget _buildContentCheckTab() {
    if (_contentLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_contentError != null) {
      return Center(
        child: Column(
          children: [
            const SizedBox(height: 24),
            Icon(Icons.error_outline, color: Colors.red.shade300, size: 40),
            const SizedBox(height: 12),
            Text(_contentError!, style: TextStyle(color: Colors.red.shade300)),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () {
                _contentLoaded = false;
                _loadContentCheck();
              },
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }
    if (!_contentLoaded) {
      return Center(
        child: ElevatedButton.icon(
          onPressed: _loadContentCheck,
          icon: const Icon(Icons.search),
          label: const Text('Run Content Check'),
        ),
      );
    }

    // ── Summary banner ────────────────────────────────────────────────────
    final mismatches =
        _contentIssues
            .where((i) => (i as Map)['type'] == 'content_mismatch')
            .length;
    final synonyms =
        _contentIssues
            .where((i) => (i as Map)['type'] == 'synonym_heading')
            .length;

    return RefreshIndicator(
      onRefresh: () async {
        _contentLoaded = false;
        await _loadContentCheck();
      },
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _ContentSummaryCard(
            totalSections: _totalSections,
            mismatches: mismatches,
            synonyms: synonyms,
          ),
          const SizedBox(height: 16),

          if (_contentIssues.isEmpty)
            _emptyContentCheck()
          else ...[
            Text(
              '${_contentIssues.length} issue${_contentIssues.length == 1 ? '' : 's'} found',
              style: Theme.of(
                context,
              ).textTheme.titleSmall?.copyWith(color: Colors.grey.shade500),
            ),
            const SizedBox(height: 8),
            ..._contentIssues.map((raw) {
              final issue = raw as Map<String, dynamic>;
              return _ContentIssueCard(issue: issue);
            }),
          ],
        ],
      ),
    );
  }

  Widget _emptyContentCheck() => Column(
    mainAxisSize: MainAxisSize.min,
    children: [
      const SizedBox(height: 32),
      Icon(Icons.check_circle_outline, color: Colors.green.shade400, size: 52),
      const SizedBox(height: 12),
      Text(
        'Content looks good!',
        style: Theme.of(
          context,
        ).textTheme.titleMedium?.copyWith(color: Colors.green.shade400),
      ),
      const SizedBox(height: 6),
      Text(
        'No content mismatches or synonym headings detected.',
        textAlign: TextAlign.center,
        style: Theme.of(context).textTheme.bodySmall,
      ),
    ],
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Bullets Tab Content Widget  (unchanged)
// ─────────────────────────────────────────────────────────────────────────────

class _BulletsTabContent extends StatefulWidget {
  final int documentId;
  final int userId;
  const _BulletsTabContent({required this.documentId, required this.userId});
  @override
  State<_BulletsTabContent> createState() => _BulletsTabContentState();
}

class _BulletsTabContentState extends State<_BulletsTabContent> {
  late Future<Map<String, dynamic>> _bulletsFuture;
  final String _baseUrl = ApiConfig.getBaseUrl();
  int? _applyingGroupIndex;

  @override
  void initState() {
    super.initState();
    _bulletsFuture = _analyzeBullets();
  }

  Future<Map<String, dynamic>> _analyzeBullets() async {
    try {
      final response = await http.get(
        Uri.parse(
          '$_baseUrl/documents/analyze-bullets/${widget.documentId}?user_id=${widget.userId}',
        ),
      );
      if (response.statusCode == 200) {
        return json.decode(response.body) as Map<String, dynamic>;
      }
      return {'error': 'Failed to analyze bullets (${response.statusCode})'};
    } catch (e) {
      return {'error': e.toString()};
    }
  }

  Future<void> _applyGroupBullets(
    int groupIndex,
    List<Map<String, dynamic>> groupItems,
  ) async {
    setState(() { _applyingGroupIndex = groupIndex; });
    try {
      final paraIndices =
          groupItems.map((item) => item['index']).whereType<int>().toList();
      if (paraIndices.isEmpty) {
        _showSnack('No paragraph indices for this group.', _red);
        setState(() { _applyingGroupIndex = null; });
        return;
      }
      final resp = await http.post(
        Uri.parse(
          '$_baseUrl/documents/apply-fix/${widget.documentId}'
          '?user_id=${widget.userId}&fix_type=apply_section_bullets',
        ),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'para_indices': paraIndices}),
      );
      if (resp.statusCode == 200) {
        try {
          final data = json.decode(resp.body) as Map<String, dynamic>;
          final applied = (data['applied'] as List<dynamic>? ?? []).length;
          final skipped = (data['skipped'] as List<dynamic>? ?? []).length;
          if (skipped > 0) {
            _showSnack('Applied: $applied, skipped: $skipped (headings/empty).', _yellow);
          } else {
            _showSnack('Bullets applied to $applied item(s)!', _green);
          }
        } catch (_) {
          _showSnack('Bullets applied!', _green);
        }
        setState(() {
          _bulletsFuture = _analyzeBullets();
          _applyingGroupIndex = null;
        });
      } else {
        _showSnack('Failed: ${resp.body}', _red);
        setState(() { _applyingGroupIndex = null; });
      }
    } catch (e) {
      _showSnack('Error: $e', _red);
      setState(() { _applyingGroupIndex = null; });
    }
  }

  void _showSnack(String msg, Color color) {
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(msg), backgroundColor: color));
  }

  @override
  Widget build(BuildContext context) {
    _ap = context.watch<ThemeProvider>().palette;
    return FutureBuilder<Map<String, dynamic>>(
      future: _bulletsFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(
            child: CircularProgressIndicator(
              valueColor: AlwaysStoppedAnimation(_blue),
            ),
          );
        }
        if (snapshot.hasError || snapshot.data?['error'] != null) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, size: 48, color: _red),
                const SizedBox(height: 12),
                Text(
                  'Error analyzing bullets',
                  style: TextStyle(color: _textPri, fontSize: 14),
                ),
              ],
            ),
          );
        }

        final data = snapshot.data ?? {};
        final detectedBullets =
            (data['detected_bullets'] as List<dynamic>? ?? [])
                .map((e) => Map<String, dynamic>.from(e as Map))
                .toList();
        final summary =
            data['summary'] != null
                ? Map<String, dynamic>.from(data['summary'] as Map)
                : <String, dynamic>{};
        final bulletGroups =
            (data['bullet_groups'] as List<dynamic>? ?? [])
                .map(
                  (group) =>
                      (group as List<dynamic>)
                          .map((e) => Map<String, dynamic>.from(e as Map))
                          .toList(),
                )
                .toList();

        if (detectedBullets.isEmpty && bulletGroups.isEmpty) {
          final alreadyFormatted = (summary['total_detected'] ?? 0) == 0;
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  alreadyFormatted
                      ? Icons.check_circle_outline
                      : Icons.format_list_bulleted_outlined,
                  size: 56,
                  color: alreadyFormatted ? _green : _textSec,
                ),
                const SizedBox(height: 16),
                Text(
                  alreadyFormatted
                      ? 'All lists are already formatted'
                      : 'No unformatted lists detected',
                  style: TextStyle(
                    color: alreadyFormatted ? _green : _textPri,
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 40),
                  child: Text(
                    alreadyFormatted
                        ? 'Every list in this document already has bullet or numbered '
                            'formatting applied. If you want to re-detect, delete the '
                            'working copy from the server and re-upload.'
                        : 'No list groups were detected in this document. '
                            'The document may not contain any list-like content.',
                    style: TextStyle(
                      color: _textSec,
                      fontSize: 12,
                      height: 1.5,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
              ],
            ),
          );
        }

        return SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildBulletsSummary(summary),
              const SizedBox(height: 24),
              if (bulletGroups.isNotEmpty) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    const Icon(
                      Icons.format_list_bulleted,
                      color: _blue,
                      size: 18,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Detected Bullet Groups',
                      style: TextStyle(
                        color: _textPri,
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: _blue.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        '${bulletGroups.length}',
                        style: const TextStyle(
                          color: _blue,
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),

                ListView.separated(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: bulletGroups.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  itemBuilder: (context, groupIndex) {
                    final group = bulletGroups[groupIndex];
                    final isApplying = _applyingGroupIndex == groupIndex;
                    return Container(
                      decoration: BoxDecoration(
                        color: _surface2.withOpacity(0.6),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: _blue.withOpacity(0.35)),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 10,
                            ),
                            decoration: BoxDecoration(
                              color: _blue.withOpacity(0.08),
                              borderRadius: const BorderRadius.only(
                                topLeft: Radius.circular(10),
                                topRight: Radius.circular(10),
                              ),
                            ),
                            child: Row(
                              children: [
                                const Icon(
                                  Icons.format_list_bulleted,
                                  color: _blue,
                                  size: 14,
                                ),
                                const SizedBox(width: 6),
                                Text(
                                  'Group ${groupIndex + 1}',
                                  style: const TextStyle(
                                    color: _blue,
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                                const SizedBox(width: 8),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 7,
                                    vertical: 2,
                                  ),
                                  decoration: BoxDecoration(
                                    color: _blue.withOpacity(0.18),
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  child: Text(
                                    '${group.length} item${group.length == 1 ? "" : "s"}',
                                    style: const TextStyle(
                                      color: _blue,
                                      fontSize: 10,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Padding(
                            padding: const EdgeInsets.fromLTRB(12, 10, 12, 0),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children:
                                  group.asMap().entries.map((entry) {
                                    final itemText =
                                        entry.value['text'] as String? ?? '';
                                    final conf =
                                        (entry.value['confidence'] as num?)
                                            ?.toDouble() ??
                                        0.0;
                                    Color dotColor = _yellow;
                                    if (conf > 0.8) dotColor = _green;
                                    if (conf < 0.5) dotColor = _red;
                                    return Padding(
                                      padding: const EdgeInsets.only(bottom: 6),
                                      child: Row(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Container(
                                            margin: const EdgeInsets.only(
                                              top: 5,
                                              right: 8,
                                            ),
                                            width: 7,
                                            height: 7,
                                            decoration: BoxDecoration(
                                              color: dotColor,
                                              shape: BoxShape.circle,
                                            ),
                                          ),
                                          Text(
                                            '${entry.key + 1}. ',
                                            style: TextStyle(
                                              color: _textSec,
                                              fontSize: 12,
                                            ),
                                          ),
                                          Expanded(
                                            child: Text(
                                              itemText.length > 90
                                                  ? '${itemText.substring(0, 90)}...'
                                                  : itemText,
                                              style: TextStyle(
                                                color: _textPri,
                                                fontSize: 12,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                    );
                                  }).toList(),
                            ),
                          ),
                          Padding(
                            padding: const EdgeInsets.all(12),
                            child: SizedBox(
                              width: double.infinity,
                              child: ElevatedButton.icon(
                                onPressed:
                                    _applyingGroupIndex != null
                                        ? null
                                        : () => _applyGroupBullets(
                                          groupIndex,
                                          group,
                                        ),
                                icon:
                                    isApplying
                                        ? const SizedBox(
                                          width: 14,
                                          height: 14,
                                          child: CircularProgressIndicator(
                                            strokeWidth: 2,
                                            color: Colors.white,
                                          ),
                                        )
                                        : const Icon(
                                          Icons.auto_fix_high,
                                          size: 15,
                                        ),
                                label: Text(
                                  isApplying
                                      ? 'Applying bullets…'
                                      : 'Apply Bullets to This Group',
                                  style: const TextStyle(fontSize: 12),
                                ),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: _blue,
                                  foregroundColor: Colors.white,
                                  disabledBackgroundColor: _blue.withOpacity(
                                    0.35,
                                  ),
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 14,
                                    vertical: 10,
                                  ),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(7),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ],
            ],
          ),
        );
      },
    );
  }

  Widget _buildBulletsSummary(Map<String, dynamic> summary) {
    return Row(
      children: [
        Expanded(
          child: _SummaryCard(
            icon: Icons.format_list_bulleted,
            label: 'Detected',
            value: '${summary['total_detected'] ?? 0}',
            color: _blue,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _SummaryCard(
            icon: Icons.check_circle,
            label: 'High Confidence',
            value: '${summary['high_confidence'] ?? 0}',
            color: _green,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _SummaryCard(
            icon: Icons.warning,
            label: 'Medium',
            value: '${summary['medium_confidence'] ?? 0}',
            color: _yellow,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _SummaryCard(
            icon: Icons.help_outline,
            label: 'Groups',
            value: '${summary['total_groups'] ?? 0}',
            color: _purple,
          ),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared reusable widgets  (all unchanged)
// ─────────────────────────────────────────────────────────────────────────────

class _Tag extends StatelessWidget {
  final String text;
  final Color color;
  const _Tag(this.text, this.color);
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
    decoration: BoxDecoration(
      color: color.withOpacity(0.12),
      borderRadius: BorderRadius.circular(4),
      border: Border.all(color: color.withOpacity(0.3)),
    ),
    child: Text(
      text,
      style: TextStyle(
        color: color,
        fontSize: 10,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.3,
      ),
    ),
  );
}

class _StatusBadge extends StatelessWidget {
  final String status;
  const _StatusBadge(this.status);
  @override
  Widget build(BuildContext context) {
    final color = status == 'pass' ? _green : _red;
    final icon =
        status == 'pass' ? Icons.check_circle_outline : Icons.cancel_outlined;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, color: color, size: 16),
        const SizedBox(width: 4),
        Text(
          status.toUpperCase(),
          style: TextStyle(
            color: color,
            fontSize: 12,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}

class _SummaryCard extends StatelessWidget {
  final IconData icon;
  final String label, value;
  final Color color;
  const _SummaryCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });
  @override
  Widget build(BuildContext context) => Container(
    decoration: BoxDecoration(
      color: _surface2,
      borderRadius: BorderRadius.circular(8),
      border: Border.all(color: color.withOpacity(0.3)),
    ),
    padding: const EdgeInsets.all(12),
    child: Column(
      children: [
        Icon(icon, color: color, size: 20),
        const SizedBox(height: 8),
        Text(
          value,
          style: TextStyle(
            color: color,
            fontSize: 18,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 4),
        Text(label, style: TextStyle(color: _textSec, fontSize: 11)),
      ],
    ),
  );
}

class _SummaryPill extends StatelessWidget {
  final String label, value;
  final Color color;
  const _SummaryPill(this.label, this.value, this.color);
  @override
  Widget build(BuildContext context) => Column(
    mainAxisSize: MainAxisSize.min,
    children: [
      Text(
        value,
        style: TextStyle(
          color: color,
          fontSize: 18,
          fontWeight: FontWeight.w800,
        ),
      ),
      Text(label, style: TextStyle(color: _textSec, fontSize: 10)),
    ],
  );
}

class _FixButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;
  const _FixButton({
    required this.label,
    required this.icon,
    required this.color,
    required this.onTap,
  });
  @override
  Widget build(BuildContext context) => GestureDetector(
    onTap: onTap,
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 13),
          const SizedBox(width: 6),
          Text(label, style: TextStyle(color: color, fontSize: 12)),
        ],
      ),
    ),
  );
}

class _StyleGroupHeader extends StatelessWidget {
  final String label;
  final int count;
  final IconData icon;
  final Color color;
  const _StyleGroupHeader(this.label, this.count, this.icon, this.color);
  @override
  Widget build(BuildContext context) => Row(
    children: [
      Icon(icon, color: color, size: 16),
      const SizedBox(width: 8),
      Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 13,
          fontWeight: FontWeight.w700,
        ),
      ),
      const SizedBox(width: 8),
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(
          color: color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(
          '$count',
          style: TextStyle(
            color: color,
            fontSize: 11,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    ],
  );
}

class _LegendItem extends StatelessWidget {
  final String label, description;
  final Color color;
  const _LegendItem(this.label, this.color, this.description);
  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      _Tag(label, color),
      const SizedBox(width: 6),
      Text(description, style: TextStyle(color: _textSec, fontSize: 11)),
    ],
  );
}

class _DiffRow extends StatelessWidget {
  final String label, text;
  final Color color;
  const _DiffRow({
    required this.label,
    required this.text,
    required this.color,
  });
  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Container(
        width: 72,
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
        decoration: BoxDecoration(
          color: color.withOpacity(0.10),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: color,
            fontSize: 10,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      const SizedBox(width: 10),
      Expanded(
        child: Text(
          text.length > 120 ? '${text.substring(0, 120)}…' : text,
          style: TextStyle(
            color: color.withOpacity(0.85),
            fontSize: 11,
            fontFamily: 'monospace',
          ),
        ),
      ),
    ],
  );
}

class _FeatureChip extends StatelessWidget {
  final String label;
  final Color color;
  const _FeatureChip(this.label, this.color, {Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
    decoration: BoxDecoration(
      color: color.withOpacity(0.10),
      borderRadius: BorderRadius.circular(20),
      border: Border.all(color: color.withOpacity(0.25)),
    ),
    child: Text(
      label,
      style: TextStyle(
        color: color.withOpacity(0.85),
        fontSize: 10,
        fontWeight: FontWeight.w500,
      ),
    ),
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Content Check widget classes
// ─────────────────────────────────────────────────────────────────────────────

class _ContentSummaryCard extends StatelessWidget {
  const _ContentSummaryCard({
    required this.totalSections,
    required this.mismatches,
    required this.synonyms,
  });

  final int totalSections;
  final int mismatches;
  final int synonyms;

  @override
  Widget build(BuildContext context) {
    final allGood = mismatches == 0 && synonyms == 0;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color:
            allGood
                ? Colors.green.shade900.withOpacity(0.25)
                : Colors.orange.shade900.withOpacity(0.25),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: allGood ? Colors.green.shade700 : Colors.orange.shade700,
          width: 0.5,
        ),
      ),
      child: Row(
        children: [
          Icon(
            allGood ? Icons.check_circle : Icons.warning_amber_rounded,
            color: allGood ? Colors.green.shade400 : Colors.orange.shade400,
            size: 28,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  allGood
                      ? 'Content placement is correct'
                      : 'Content issues detected',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                const SizedBox(height: 4),
                Text(
                  '$totalSections sections checked · '
                  '$mismatches mismatch${mismatches == 1 ? '' : 'es'} · '
                  '$synonyms synonym${synonyms == 1 ? '' : 's'}',
                  style: Theme.of(
                    context,
                  ).textTheme.bodySmall?.copyWith(color: Colors.grey.shade400),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ContentIssueCard extends StatelessWidget {
  const _ContentIssueCard({required this.issue});

  final Map<String, dynamic> issue;

  @override
  Widget build(BuildContext context) {
    final type = issue['type'] as String? ?? '';
    final severity = issue['severity'] as String? ?? 'warning';
    final heading = issue['heading'] as String? ?? '';
    final message = issue['message'] as String? ?? '';
    final detection = issue['detection'] as String? ?? '';
    final bestMatch = issue['best_match_heading'] as String?;
    final ownScore = issue['own_similarity'];
    final bestScore = issue['best_match_score'];
    final confidence = issue['confidence'];

    final isError = severity == 'error';
    final isMismatch = type == 'content_mismatch';

    final borderColor = isError ? Colors.red.shade700 : Colors.orange.shade700;
    final bgColor =
        isError
            ? Colors.red.shade900.withOpacity(0.15)
            : Colors.orange.shade900.withOpacity(0.12);

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: borderColor, width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header row ─────────────────────────────────────────────
          Row(
            children: [
              Icon(
                isMismatch ? Icons.swap_horiz : Icons.label_off,
                size: 16,
                color: isError ? Colors.red.shade400 : Colors.orange.shade400,
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  heading,
                  style: Theme.of(context).textTheme.titleSmall,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              _badge(detection.isNotEmpty ? detection : type),
            ],
          ),
          const SizedBox(height: 8),
          // ── Message ────────────────────────────────────────────────
          Text(message, style: Theme.of(context).textTheme.bodySmall),
          // ── Scores (content mismatch only) ────────────────────────
          if (isMismatch && bestMatch != null) ...[
            const SizedBox(height: 10),
            _ScoreRow(
              label: 'Score under "${issue['canonical_heading'] ?? heading}"',
              score: ownScore is num ? ownScore.toDouble() : null,
              isOwn: true,
            ),
            const SizedBox(height: 4),
            _ScoreRow(
              label: 'Score under "$bestMatch"',
              score: bestScore is num ? bestScore.toDouble() : null,
              isOwn: false,
            ),
            if (confidence is num) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  Text(
                    'Confidence: ',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  Text(
                    '${(confidence * 100).round()}%',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontWeight: FontWeight.w600,
                      color:
                          isError
                              ? Colors.red.shade400
                              : Colors.orange.shade400,
                    ),
                  ),
                ],
              ),
            ],
          ],
        ],
      ),
    );
  }

  Widget _badge(String label) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
    decoration: BoxDecoration(
      color: Colors.grey.shade800,
      borderRadius: BorderRadius.circular(4),
    ),
    child: Text(
      label,
      style: const TextStyle(fontSize: 10, color: Colors.white70),
    ),
  );
}

class _ScoreRow extends StatelessWidget {
  const _ScoreRow({
    required this.label,
    required this.score,
    required this.isOwn,
  });

  final String label;
  final double? score;
  final bool isOwn;

  @override
  Widget build(BuildContext context) {
    final pct = score != null ? (score! * 100).round() : 0;
    final barColor = isOwn ? Colors.grey.shade600 : Colors.orange.shade600;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: Theme.of(
            context,
          ).textTheme.bodySmall?.copyWith(color: Colors.grey.shade400),
        ),
        const SizedBox(height: 3),
        Row(
          children: [
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(2),
                child: LinearProgressIndicator(
                  value: score ?? 0,
                  minHeight: 6,
                  backgroundColor: Colors.grey.shade800,
                  valueColor: AlwaysStoppedAnimation(barColor),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Text('$pct%', style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ],
    );
  }
}
