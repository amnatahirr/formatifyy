import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/collaboration_provider.dart';

class SectionEditorScreen extends StatefulWidget {
  final int projectId;
  final String sectionId;
  final String sectionName;
  final String initialContent;

  const SectionEditorScreen({
    super.key,
    required this.projectId,
    required this.sectionId,
    required this.sectionName,
    required this.initialContent,
  });

  @override
  State<SectionEditorScreen> createState() => _SectionEditorScreenState();
}

class _SectionEditorScreenState extends State<SectionEditorScreen> {
  late final TextEditingController _content;
  final _message = TextEditingController();
  bool _saving = false;
  bool _loadingImages = true;
  List<Map<String, dynamic>> _images = [];

  @override
  void initState() {
    super.initState();
    _content = TextEditingController(text: widget.initialContent);
    _loadImages();
  }

  Future<void> _loadImages() async {
    final vc = context.read<CollaborationProvider>();
    final images = await vc.loadSectionImages(widget.projectId, widget.sectionId);
    if (mounted) {
      setState(() {
        _images = images;
        _loadingImages = false;
      });
    }
  }

  @override
  void dispose() {
    _content.dispose();
    _message.dispose();
    super.dispose();
  }

  Future<void> _pickAndUploadImage() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.image,
      withData: false,
    );
    if (result == null || result.files.single.path == null) return;

    final vc = context.read<CollaborationProvider>();
    final uploaded = await vc.uploadSectionImage(
      widget.projectId,
      widget.sectionId,
      File(result.files.single.path!),
    );

    if (!mounted) return;
    if (uploaded != null) {
      setState(() => _images.add(uploaded));
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Image uploaded'),
          backgroundColor: Color(0xFF10B981),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(vc.error ?? 'Upload failed')),
      );
    }
  }

  Future<void> _removeImage(int imageId) async {
    final vc = context.read<CollaborationProvider>();
    final ok = await vc.deleteSectionImage(
      widget.projectId,
      widget.sectionId,
      imageId,
    );
    if (!mounted) return;
    if (ok) {
      setState(() => _images.removeWhere((img) => img['id'] == imageId));
    }
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    final vc = context.read<CollaborationProvider>();

    final ok = await vc.saveSection(
      projectId: widget.projectId,
      sectionId: widget.sectionId,
      content: _content.text,
      message: _message.text.trim(),
    );

    if (!mounted) return;
    setState(() => _saving = false);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(ok ? 'Commit saved — broadcast to team' : (vc.error ?? 'Save failed')),
        backgroundColor: ok ? const Color(0xFF10B981) : const Color(0xFFEF4444),
      ),
    );
    if (ok) Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    final vc = context.watch<CollaborationProvider>();

    return Scaffold(
      backgroundColor: const Color(0xFF0F1419),
      appBar: AppBar(
        backgroundColor: const Color(0xFF141B27),
        title: Text(widget.sectionName),
        actions: [
          TextButton(
            onPressed: _saving ? null : _save,
            child: _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Save Commit'),
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            TextField(
              controller: _message,
              decoration: const InputDecoration(
                labelText: 'Commit message (optional)',
                hintText: 'e.g. Added methodology details',
              ),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: TextField(
                controller: _content,
                maxLines: null,
                expands: true,
                textAlignVertical: TextAlignVertical.top,
                decoration: InputDecoration(
                  alignLabelWithHint: true,
                  labelText: 'Section content',
                  hintText: 'Write content for "${widget.sectionName}"...',
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                const Text(
                  'Attached Images',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                  ),
                ),
                const Spacer(),
                OutlinedButton.icon(
                  onPressed: _pickAndUploadImage,
                  icon: const Icon(Icons.image, size: 16),
                  label: const Text('Upload Image'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: const Color(0xFF6366F1),
                    side: const BorderSide(color: Color(0xFF6366F1)),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            if (_loadingImages)
              const SizedBox(
                height: 80,
                child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
              )
            else if (_images.isEmpty)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: const Color(0xFF1A1F2E),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFF2D3748)),
                ),
                child: const Text(
                  'No images attached. Upload images to include them in the merged document.',
                  style: TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
                  textAlign: TextAlign.center,
                ),
              )
            else
              SizedBox(
                height: 90,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: _images.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 10),
                  itemBuilder: (_, i) {
                    final img = _images[i];
                    final imageId = img['id'] as int;
                    final url = vc.sectionImageUrl(
                      widget.projectId,
                      widget.sectionId,
                      imageId,
                    );
                    return Stack(
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: Image.network(
                            url,
                            width: 90,
                            height: 90,
                            fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) => Container(
                              width: 90,
                              height: 90,
                              color: const Color(0xFF2D3748),
                              child: const Icon(Icons.broken_image, color: Color(0xFF94A3B8)),
                            ),
                          ),
                        ),
                        Positioned(
                          top: 2,
                          right: 2,
                          child: GestureDetector(
                            onTap: () => _removeImage(imageId),
                            child: Container(
                              padding: const EdgeInsets.all(2),
                              decoration: const BoxDecoration(
                                color: Color(0xFFEF4444),
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(Icons.close, size: 14, color: Colors.white),
                            ),
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),
            const SizedBox(height: 12),
            const Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Every save creates a permanent commit. Images are included when the section is merged.',
                style: TextStyle(color: Color(0xFF94A3B8), fontSize: 11),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
