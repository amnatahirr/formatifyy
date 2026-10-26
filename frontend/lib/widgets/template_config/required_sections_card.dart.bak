// widgets/template_config/required_sections_card.dart
//
// Drag-and-drop required sections manager.
// Each section has: name (editable), order (auto from position), required toggle.
//
// Usage in TemplateConfigurationScreen:
//   RequiredSectionsCard(
//     sections: _requiredSections,
//     onSectionsChanged: (updated) => setState(() => _requiredSections = updated),
//   )

import 'package:flutter/material.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Data model (mirrors backend RequiredSection)
// ─────────────────────────────────────────────────────────────────────────────

class RequiredSectionItem {
  String name;
  bool required;
  int headingLevel;

  RequiredSectionItem({
    required this.name,
    this.required = true,
    this.headingLevel = 1,
  });

  factory RequiredSectionItem.fromJson(Map<String, dynamic> json) {
    return RequiredSectionItem(
      name: json['name'] as String? ?? '',
      required: json['required'] as bool? ?? true,
      headingLevel: (json['heading_level'] as num?)?.toInt() ?? 1,
    );
  }

  Map<String, dynamic> toJson(int order) => {
        'name': name,
        'order': order,
        'required': required,
        'heading_level': headingLevel,
      };
}

// ─────────────────────────────────────────────────────────────────────────────
// Preset sections — common FYP sections admin can add with one tap
// ─────────────────────────────────────────────────────────────────────────────

const List<String> _kPresets = [
  'Abstract',
  'Introduction',
  'Problem Statement',
  'Objectives',
  'Scope',
  'Literature Review',
  'Methodology',
  'System Design',
  'Implementation',
  'Results',
  'Evaluation',
  'Conclusion',
  'Future Work',
  'References',
  'Acknowledgements',
  'Appendix',
];

// ─────────────────────────────────────────────────────────────────────────────
// Widget
// ─────────────────────────────────────────────────────────────────────────────

class RequiredSectionsCard extends StatefulWidget {
  final List<RequiredSectionItem> sections;
  final ValueChanged<List<RequiredSectionItem>> onSectionsChanged;

  const RequiredSectionsCard({
    super.key,
    required this.sections,
    required this.onSectionsChanged,
  });

  @override
  State<RequiredSectionsCard> createState() => _RequiredSectionsCardState();
}

class _RequiredSectionsCardState extends State<RequiredSectionsCard> {
  late List<RequiredSectionItem> _sections;
  final _newSectionController = TextEditingController();
  bool _showPresets = false;

  // Dark theme colors (matches your existing UI: Color(0xFF0F1419) background)
  static const _cardBg     = Color(0xFF1A2332);
  static const _surfaceBg  = Color(0xFF0F1419);
  static const _borderCol  = Color(0xFF2A3F5F);
  static const _accent      = Color(0xFF4A9EFF);
  static const _accentGreen = Color(0xFF4ADE80);
  static const _textPrimary = Color(0xFFE2E8F0);
  static const _textSecondary = Color(0xFF8899AA);
  static const _dragHandle  = Color(0xFF3A5070);

  @override
  void initState() {
    super.initState();
    _sections = List.from(widget.sections);
  }

  @override
  void didUpdateWidget(RequiredSectionsCard old) {
    super.didUpdateWidget(old);
    // Sync if parent pushed new data (e.g. template loaded)
    if (widget.sections != old.sections) {
      setState(() => _sections = List.from(widget.sections));
    }
  }

  void _notify() => widget.onSectionsChanged(List.from(_sections));

  void _addSection(String name) {
    final trimmed = name.trim();
    if (trimmed.isEmpty) return;
    // Prevent duplicates (case-insensitive)
    if (_sections.any((s) => s.name.toLowerCase() == trimmed.toLowerCase())) {
      _showSnack('Section "$trimmed" already exists');
      return;
    }
    setState(() => _sections.add(RequiredSectionItem(name: trimmed)));
    _notify();
    _newSectionController.clear();
  }

  void _removeSection(int index) {
    setState(() => _sections.removeAt(index));
    _notify();
  }

  void _toggleRequired(int index) {
    setState(() => _sections[index].required = !_sections[index].required);
    _notify();
  }

  void _renameSection(int index, String newName) {
    final trimmed = newName.trim();
    if (trimmed.isEmpty) return;
    setState(() => _sections[index].name = trimmed);
    _notify();
  }

  void _setHeadingLevel(int index, int level) {
    setState(() => _sections[index].headingLevel = level);
    _notify();
  }

  void _onReorder(int oldIndex, int newIndex) {
    setState(() {
      if (newIndex > oldIndex) newIndex--;
      final item = _sections.removeAt(oldIndex);
      _sections.insert(newIndex, item);
    });
    _notify();
  }

  void _showSnack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: _cardBg),
    );
  }

  void _showRenameDialog(int index) {
    final ctrl = TextEditingController(text: _sections[index].name);
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: _cardBg,
        title: const Text('Rename Section',
            style: TextStyle(color: _textPrimary, fontSize: 16)),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          style: const TextStyle(color: _textPrimary),
          decoration: InputDecoration(
            hintText: 'Section name',
            hintStyle: const TextStyle(color: _textSecondary),
            enabledBorder: OutlineInputBorder(
              borderSide: const BorderSide(color: _borderCol),
              borderRadius: BorderRadius.circular(8),
            ),
            focusedBorder: OutlineInputBorder(
              borderSide: const BorderSide(color: _accent),
              borderRadius: BorderRadius.circular(8),
            ),
          ),
          onSubmitted: (v) {
            _renameSection(index, v);
            Navigator.pop(context);
          },
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel', style: TextStyle(color: _textSecondary)),
          ),
          TextButton(
            onPressed: () {
              _renameSection(index, ctrl.text);
              Navigator.pop(context);
            },
            child: const Text('Save', style: TextStyle(color: _accent)),
          ),
        ],
      ),
    );
  }

  // ── Build ──────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final requiredCount  = _sections.where((s) => s.required).length;
    final optionalCount  = _sections.length - requiredCount;

    return Container(
      decoration: BoxDecoration(
        color: _cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _borderCol),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header ────────────────────────────────────────────────────────
          _buildHeader(requiredCount, optionalCount),

          const Divider(color: _borderCol, height: 1),

          // ── Reorderable list ──────────────────────────────────────────────
          if (_sections.isEmpty)
            _buildEmptyState()
          else
            _buildList(),

          const Divider(color: _borderCol, height: 1),

          // ── Add section row ───────────────────────────────────────────────
          _buildAddRow(),

          // ── Presets panel ─────────────────────────────────────────────────
          if (_showPresets) _buildPresetsPanel(),
        ],
      ),
    );
  }

  Widget _buildHeader(int requiredCount, int optionalCount) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: _accent.withOpacity(0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.list_alt_rounded, color: _accent, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Required Sections',
                    style: TextStyle(
                        color: _textPrimary,
                        fontSize: 16,
                        fontWeight: FontWeight.w600)),
                const SizedBox(height: 2),
                Text(
                  '$requiredCount required · $optionalCount optional · drag to reorder',
                  style: const TextStyle(color: _textSecondary, fontSize: 12),
                ),
              ],
            ),
          ),
          // Presets toggle button
          _SmallButton(
            label: 'Presets',
            icon: Icons.add_box_outlined,
            active: _showPresets,
            onTap: () => setState(() => _showPresets = !_showPresets),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 32),
      child: Center(
        child: Column(
          children: [
            Icon(Icons.playlist_add, color: _textSecondary.withOpacity(0.5), size: 40),
            const SizedBox(height: 12),
            const Text('No sections yet',
                style: TextStyle(color: _textSecondary, fontSize: 14)),
            const SizedBox(height: 4),
            const Text('Add sections below or use Presets',
                style: TextStyle(color: _textSecondary, fontSize: 12)),
          ],
        ),
      ),
    );
  }

  Widget _buildList() {
    return ReorderableListView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      onReorder: _onReorder,
      // Remove the default drag handle from the ReorderableListView header area
      proxyDecorator: (child, index, animation) {
        return Material(
          color: Colors.transparent,
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: _accent.withOpacity(0.08),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: _accent.withOpacity(0.4)),
            ),
            child: child,
          ),
        );
      },
      itemCount: _sections.length,
      itemBuilder: (context, index) {
        final section = _sections[index];
        return _SectionTile(
          key: ValueKey('section_${index}_${section.name}'),
          section: section,
          order: index + 1,
          onToggleRequired: () => _toggleRequired(index),
          onRemove: () => _removeSection(index),
          onRename: () => _showRenameDialog(index),
          onHeadingLevelChanged: (lvl) => _setHeadingLevel(index, lvl),
        );
      },
    );
  }

  Widget _buildAddRow() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _newSectionController,
              style: const TextStyle(color: _textPrimary, fontSize: 14),
              decoration: InputDecoration(
                hintText: 'Type a custom section name...',
                hintStyle: const TextStyle(color: _textSecondary, fontSize: 14),
                filled: true,
                fillColor: _surfaceBg,
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                border: OutlineInputBorder(
                  borderSide: const BorderSide(color: _borderCol),
                  borderRadius: BorderRadius.circular(8),
                ),
                enabledBorder: OutlineInputBorder(
                  borderSide: const BorderSide(color: _borderCol),
                  borderRadius: BorderRadius.circular(8),
                ),
                focusedBorder: OutlineInputBorder(
                  borderSide: const BorderSide(color: _accent),
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              onSubmitted: _addSection,
            ),
          ),
          const SizedBox(width: 10),
          GestureDetector(
            onTap: () => _addSection(_newSectionController.text),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: _accent,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Row(
                children: [
                  Icon(Icons.add, color: Colors.white, size: 16),
                  SizedBox(width: 6),
                  Text('Add', style: TextStyle(color: Colors.white, fontSize: 14)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPresetsPanel() {
    // Which presets are not already added?
    final existing = _sections.map((s) => s.name.toLowerCase()).toSet();
    final available = _kPresets.where((p) => !existing.contains(p.toLowerCase())).toList();

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _surfaceBg,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _borderCol),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Common FYP Sections — tap to add',
              style: TextStyle(color: _textSecondary, fontSize: 12)),
          const SizedBox(height: 10),
          available.isEmpty
              ? const Text('All presets already added ✓',
                  style: TextStyle(color: _accentGreen, fontSize: 12))
              : Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: available
                      .map((p) => _PresetChip(
                            label: p,
                            onTap: () {
                              _addSection(p);
                              setState(() {}); // refresh available list
                            },
                          ))
                      .toList(),
                ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Section tile (one row in the list)
// ─────────────────────────────────────────────────────────────────────────────

class _SectionTile extends StatelessWidget {
  final RequiredSectionItem section;
  final int order;
  final VoidCallback onToggleRequired;
  final VoidCallback onRemove;
  final VoidCallback onRename;
  final ValueChanged<int> onHeadingLevelChanged;

  static const _cardBg      = Color(0xFF1A2332);
  static const _surfaceBg   = Color(0xFF0F1419);
  static const _borderCol   = Color(0xFF2A3F5F);
  static const _accent       = Color(0xFF4A9EFF);
  static const _accentGreen  = Color(0xFF4ADE80);
  static const _textPrimary  = Color(0xFFE2E8F0);
  static const _textSecondary = Color(0xFF8899AA);
  static const _dragHandle   = Color(0xFF3A5070);

  const _SectionTile({
    super.key,
    required this.section,
    required this.order,
    required this.onToggleRequired,
    required this.onRemove,
    required this.onRename,
    required this.onHeadingLevelChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
      decoration: BoxDecoration(
        color: _cardBg,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: section.required ? _borderCol : _dragHandle.withOpacity(0.5),
        ),
      ),
      child: Row(
        children: [
          // Drag handle
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10),
            child: Icon(Icons.drag_indicator, color: _dragHandle, size: 20),
          ),

          // Order badge
          Container(
            width: 26,
            height: 26,
            decoration: BoxDecoration(
              color: _accent.withOpacity(0.12),
              borderRadius: BorderRadius.circular(6),
            ),
            alignment: Alignment.center,
            child: Text(
              '$order',
              style: const TextStyle(
                  color: _accent, fontSize: 11, fontWeight: FontWeight.w700),
            ),
          ),

          const SizedBox(width: 12),

          // Section name
          Expanded(
            child: Text(
              section.name,
              style: TextStyle(
                color: section.required ? _textPrimary : _textSecondary,
                fontSize: 14,
                fontWeight: section.required ? FontWeight.w500 : FontWeight.w400,
                decoration: section.required ? null : TextDecoration.none,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),

          const SizedBox(width: 8),

          // Heading level selector
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6),
            decoration: BoxDecoration(
              color: _surfaceBg,
              borderRadius: BorderRadius.circular(6),
              border: Border.all(color: _borderCol),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<int>(
                value: section.headingLevel.clamp(1, 4),
                dropdownColor: _cardBg,
                style: const TextStyle(color: _textPrimary, fontSize: 11),
                items: const [
                  DropdownMenuItem(value: 1, child: Text('H1')),
                  DropdownMenuItem(value: 2, child: Text('H2')),
                  DropdownMenuItem(value: 3, child: Text('H3')),
                  DropdownMenuItem(value: 4, child: Text('H4')),
                ],
                onChanged: (v) {
                  if (v != null) onHeadingLevelChanged(v);
                },
              ),
            ),
          ),

          // Required / Optional badge
          GestureDetector(
            onTap: onToggleRequired,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: section.required
                    ? _accentGreen.withOpacity(0.12)
                    : _dragHandle.withOpacity(0.2),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: section.required
                      ? _accentGreen.withOpacity(0.4)
                      : _dragHandle.withOpacity(0.4),
                ),
              ),
              child: Text(
                section.required ? 'Required' : 'Optional',
                style: TextStyle(
                  color: section.required ? _accentGreen : _textSecondary,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),

          // Rename
          IconButton(
            icon: const Icon(Icons.edit_outlined, size: 16),
            color: _textSecondary,
            tooltip: 'Rename',
            onPressed: onRename,
            splashRadius: 16,
          ),

          // Remove
          IconButton(
            icon: const Icon(Icons.close, size: 16),
            color: _textSecondary,
            tooltip: 'Remove',
            onPressed: onRemove,
            splashRadius: 16,
          ),

          const SizedBox(width: 4),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Small helpers
// ─────────────────────────────────────────────────────────────────────────────

class _SmallButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool active;
  final VoidCallback onTap;

  static const _accent    = Color(0xFF4A9EFF);
  static const _borderCol = Color(0xFF2A3F5F);
  static const _textSecondary = Color(0xFF8899AA);

  const _SmallButton({
    required this.label,
    required this.icon,
    required this.active,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: active ? _accent.withOpacity(0.12) : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
              color: active ? _accent.withOpacity(0.5) : _borderCol),
        ),
        child: Row(
          children: [
            Icon(icon,
                size: 14, color: active ? _accent : _textSecondary),
            const SizedBox(width: 5),
            Text(label,
                style: TextStyle(
                    fontSize: 12,
                    color: active ? _accent : _textSecondary)),
          ],
        ),
      ),
    );
  }
}

class _PresetChip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  static const _surfaceBg  = Color(0xFF0F1419);
  static const _borderCol  = Color(0xFF2A3F5F);
  static const _accent      = Color(0xFF4A9EFF);
  static const _textSecondary = Color(0xFF8899AA);

  const _PresetChip({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: _surfaceBg,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: _borderCol),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.add, color: _accent, size: 12),
            const SizedBox(width: 4),
            Text(label,
                style: const TextStyle(color: _textSecondary, fontSize: 12)),
          ],
        ),
      ),
    );
  }
}