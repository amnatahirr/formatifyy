import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/collaboration_provider.dart';
import 'project_download_screen.dart';

class MergeConflictScreen extends StatefulWidget {
  final int projectId;
  final int mergeId;

  const MergeConflictScreen({
    super.key,
    required this.projectId,
    required this.mergeId,
  });

  @override
  State<MergeConflictScreen> createState() => _MergeConflictScreenState();
}

class _MergeConflictScreenState extends State<MergeConflictScreen> {
  final Map<int, TextEditingController> _resolutions = {};
  final GlobalKey<AnimatedListState> _listKey = GlobalKey<AnimatedListState>();
  List<Map<String, dynamic>> _visibleConflicts = [];
  int _pendingCount = 0;
  bool _completing = false;
  bool _initialLoad = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final vc = context.read<CollaborationProvider>();
    await vc.loadMergeStatus(widget.projectId, widget.mergeId);
    if (!mounted) return;
    _syncFromProvider(vc);
    setState(() => _initialLoad = false);
  }

  void _syncFromProvider(CollaborationProvider vc) {
    final status = vc.mergeStatus ?? {};
    final all = (status['conflicts'] as List? ?? [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
    _visibleConflicts = all.where((c) => c['status'] != 'resolved').toList();
    _pendingCount = status['pending_conflicts'] as int? ?? _visibleConflicts.length;
  }

  @override
  void dispose() {
    for (final c in _resolutions.values) {
      c.dispose();
    }
    super.dispose();
  }

  TextEditingController _controllerFor(int conflictId, String initial) {
    return _resolutions.putIfAbsent(
      conflictId,
      () => TextEditingController(text: initial),
    );
  }

  void _useVariant(int conflictId, String content) {
    _controllerFor(conflictId, content).text = content;
    setState(() {});
  }

  Future<void> _resolve(int conflictId, int listIndex) async {
    final vc = context.read<CollaborationProvider>();
    final content = _resolutions[conflictId]?.text ?? '';
    if (content.trim().isEmpty) return;

    final result = await vc.resolveConflict(
      projectId: widget.projectId,
      mergeId: widget.mergeId,
      conflictId: conflictId,
      resolutionContent: content,
    );
    if (!mounted || result == null) return;

    final removed = _visibleConflicts[listIndex];
    _listKey.currentState?.removeItem(
      listIndex,
      (context, animation) => _buildConflictCard(
        removed,
        listIndex,
        animation: animation,
        removing: true,
      ),
      duration: const Duration(milliseconds: 350),
    );

    setState(() {
      _visibleConflicts.removeAt(listIndex);
      _pendingCount = result['pending_conflicts'] as int? ?? (_pendingCount - 1);
    });

    if (_pendingCount <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('All conflicts resolved!'),
          backgroundColor: Color(0xFF10B981),
        ),
      );
    }
  }

  Future<void> _completeMerge() async {
    setState(() => _completing = true);
    final vc = context.read<CollaborationProvider>();

    final result = await vc.completeMerge(widget.projectId, widget.mergeId);
    if (!mounted) return;
    setState(() => _completing = false);

    if (result != null) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => ProjectDownloadScreen(
            projectId: widget.projectId,
            mergeId: widget.mergeId,
            analysisReport: result['analysis_report'] is Map
                ? Map<String, dynamic>.from(result['analysis_report'] as Map)
                : null,
          ),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(vc.error ?? 'Merge failed')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final vc = context.watch<CollaborationProvider>();
    final status = vc.mergeStatus ?? {};
    final totalConflicts = status['conflict_count'] as int? ?? 0;
    final mergeState = status['status'] as String? ?? 'detecting';
    final allResolved = _pendingCount <= 0 && totalConflicts > 0;

    return Scaffold(
      backgroundColor: const Color(0xFF0F1419),
      appBar: AppBar(
        backgroundColor: const Color(0xFF141B27),
        title: const Text('Merge & Conflict Resolution'),
      ),
      body: _initialLoad && vc.loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                if (allResolved) _allResolvedBanner() else _statusBanner(mergeState, _pendingCount, totalConflicts),
                const SizedBox(height: 16),
                if (totalConflicts == 0)
                  const Text(
                    'No conflicts detected. Ready to assemble the final document in template order.',
                    style: TextStyle(color: Color(0xFF10B981)),
                  )
                else if (_visibleConflicts.isEmpty && allResolved)
                  _allResolvedBanner()
                else
                  AnimatedList(
                    key: _listKey,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    initialItemCount: _visibleConflicts.length,
                    itemBuilder: (context, index, animation) {
                      if (index >= _visibleConflicts.length) {
                        return const SizedBox.shrink();
                      }
                      return _buildConflictCard(
                        _visibleConflicts[index],
                        index,
                        animation: animation,
                      );
                    },
                  ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: (_pendingCount > 0 || _completing) ? null : _completeMerge,
                    icon: _completing
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : Icon(
                            allResolved || totalConflicts == 0
                                ? Icons.check_circle
                                : Icons.pending,
                          ),
                    label: Text(
                      _pendingCount > 0
                          ? 'Resolve $_pendingCount conflict(s) first'
                          : 'Complete Merge & Run Analysis',
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF10B981),
                      disabledBackgroundColor: const Color(0xFF2D3748),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                  ),
                ),
              ],
            ),
    );
  }

  Widget _allResolvedBanner() {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 400),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF10B981).withOpacity(0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF10B981).withOpacity(0.4)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: const Color(0xFF10B981).withOpacity(0.2),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.check_circle, color: Color(0xFF10B981), size: 28),
          ),
          const SizedBox(width: 16),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'All conflicts resolved',
                  style: TextStyle(
                    color: Color(0xFF10B981),
                    fontWeight: FontWeight.w700,
                    fontSize: 16,
                  ),
                ),
                SizedBox(height: 4),
                Text(
                  'You can now complete the merge and generate the final document.',
                  style: TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _statusBanner(String status, int pending, int total) {
    final color = pending == 0 ? const Color(0xFF10B981) : const Color(0xFFF59E0B);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Text(
        'Status: $status · $total conflict(s) · $pending pending',
        style: TextStyle(color: color, fontWeight: FontWeight.w600),
      ),
    );
  }

  Widget _buildConflictCard(
    Map<String, dynamic> c,
    int listIndex, {
    Animation<double>? animation,
    bool removing = false,
  }) {
    final id = c['id'] as int;
    final type = c['conflict_type'] as String? ?? '';
    final details = Map<String, dynamic>.from(c['details'] as Map? ?? {});

    String initial = c['resolution_content'] as String? ?? '';
    if (initial.isEmpty && type == 'multi_author') {
      final variants = details['variants'] as List? ?? [];
      if (variants.isNotEmpty) {
        initial = (variants.first as Map)['content'] as String? ?? '';
      }
    } else if (initial.isEmpty) {
      initial = details['content_preview'] as String? ??
          (details['section_a'] as Map?)?['content'] as String? ??
          '';
    }

    final card = Card(
      color: const Color(0xFF1A1F2E),
      margin: const EdgeInsets.only(bottom: 14),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _typeChip(type),
                const Spacer(),
                const Text(
                  'PENDING',
                  style: TextStyle(
                    color: Color(0xFFF59E0B),
                    fontWeight: FontWeight.w700,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              details['description'] as String? ?? '',
              style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 12),
            ),
            const SizedBox(height: 12),
            if (type == 'multi_author') _multiAuthorView(id, details),
            if (type == 'duplicate_content') _duplicateView(details),
            if (type == 'section_mismatch') _mismatchView(details),
            const SizedBox(height: 12),
            TextField(
              controller: _controllerFor(id, initial),
              maxLines: 6,
              decoration: const InputDecoration(
                labelText: 'Resolution content',
                hintText: 'Edit or pick merged content for this conflict',
              ),
            ),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: ElevatedButton(
                onPressed: removing ? null : () => _resolve(id, listIndex),
                child: const Text('Save Resolution'),
              ),
            ),
          ],
        ),
      ),
    );

    if (animation != null) {
      return SizeTransition(
        sizeFactor: CurvedAnimation(parent: animation, curve: Curves.easeInOut),
        child: FadeTransition(opacity: animation, child: card),
      );
    }
    return card;
  }

  Widget _typeChip(String type) {
    final labels = {
      'multi_author': 'Multi-author',
      'duplicate_content': 'Duplicate content',
      'section_mismatch': 'Section mismatch',
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: const Color(0xFF6366F1).withOpacity(0.15),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        labels[type] ?? type,
        style: const TextStyle(color: Color(0xFF6366F1), fontSize: 11, fontWeight: FontWeight.w600),
      ),
    );
  }

  Widget _multiAuthorView(int conflictId, Map<String, dynamic> details) {
    final variants = (details['variants'] as List? ?? [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: variants.map((v) {
        final content = v['content'] as String? ?? '';
        return Expanded(
          child: Container(
            margin: const EdgeInsets.only(right: 8),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: const Color(0xFF0F1419),
              borderRadius: BorderRadius.circular(6),
              border: Border.all(color: const Color(0xFF2D3748)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  v['author_name'] as String? ?? '',
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                    fontSize: 11,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  content,
                  style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 10),
                  maxLines: 8,
                  overflow: TextOverflow.ellipsis,
                ),
                TextButton(
                  onPressed: () => _useVariant(conflictId, content),
                  child: const Text('Use this', style: TextStyle(fontSize: 10)),
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _duplicateView(Map<String, dynamic> details) {
    final a = Map<String, dynamic>.from(details['section_a'] as Map? ?? {});
    final b = Map<String, dynamic>.from(details['section_b'] as Map? ?? {});
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(child: _sidePanel(a['section_name'] as String? ?? 'A', a['content'] as String? ?? '')),
        const SizedBox(width: 8),
        Expanded(child: _sidePanel(b['section_name'] as String? ?? 'B', b['content'] as String? ?? '')),
      ],
    );
  }

  Widget _mismatchView(Map<String, dynamic> details) {
    return _sidePanel(
      details['section_name'] as String? ?? 'Section',
      details['content_preview'] as String? ?? '',
    );
  }

  Widget _sidePanel(String title, String content) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1419),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: const Color(0xFF2D3748)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 11),
          ),
          const SizedBox(height: 6),
          Text(content, style: const TextStyle(color: Color(0xFF94A3B8), fontSize: 10)),
        ],
      ),
    );
  }
}
