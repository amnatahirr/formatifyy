import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:frontend/screens/qr_upload_service.dart';
import 'package:http/http.dart' as dio;
import 'package:provider/provider.dart';
import 'package:http/http.dart' as http;
import '../providers/auth_provider.dart';
import '../providers/document_provider.dart';
import '../providers/fyp_provider.dart';
import '../providers/template_provider.dart';
import '../config/api_config.dart';
import '../config/dev_user_config.dart';
import 'analyze_screen.dart';
import 'package:url_launcher/url_launcher.dart';
import '../theme/app_theme.dart';
import '../widgets/admin/admin_ui.dart';
import '../widgets/freeform_analyze_dialogs.dart';
import '../utils/analysis_nav.dart';

import '../widgets/tr.dart';
class NewReportScreen extends StatefulWidget {
  final Map<String, dynamic>? selectedTemplate;
  /// When true, renders inside StudentDashboard (no outer Scaffold).
  final bool embedded;

  const NewReportScreen({
    Key? key,
    this.selectedTemplate,
    this.embedded = false,
  }) : super(key: key);

  @override
  State<NewReportScreen> createState() => _NewReportScreenState();
}

class _NewReportScreenState extends State<NewReportScreen> {
  AppPalette get _p => context.watch<ThemeProvider>().palette;
  bool _isGoogleDriveConnected = false;
  final TextEditingController _titleController = TextEditingController();
  final TextEditingController _contentController = TextEditingController();
  Map<String, dynamic>? _selectedTemplate;
  bool _isProcessing = false;
  File? _selectedFile;
  bool _autoFormatDetection = true;
  bool _secureProcessing = true;
  bool _preserveFormatting = true;
  int _selectedUploadOption = 1; // 1 = file, 2 = paste, 3 = google drive
  String _googleEmail = '';

  @override
  void initState() {
    super.initState();
    _titleController.addListener(_onPasteFieldsChanged);
    _contentController.addListener(_onPasteFieldsChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _loadTemplatesAndDocuments();
    });
    if (widget.selectedTemplate != null) {
      _selectedTemplate = widget.selectedTemplate;
    }
  }

  void _onPasteFieldsChanged() {
    if (mounted) setState(() {});
  }

  void _loadTemplatesAndDocuments() {
    Future.microtask(() async {
      if (!mounted) return;
      final auth = context.read<AuthProvider>();
      if (auth.hasGoogleDrive) {
        setState(() {
          _isGoogleDriveConnected = true;
          _googleEmail = auth.googleDriveEmail ?? '';
        });
      } else if (auth.userId != null) {
        await auth.checkGoogleDriveStatus();
        if (!mounted) return;
        if (auth.hasGoogleDrive) {
          setState(() {
            _isGoogleDriveConnected = true;
            _googleEmail = auth.googleDriveEmail ?? '';
          });
        }
      }
      if (auth.userId != null) {
        context.read<TemplateProvider>().fetchUserTemplates(auth.userId!);
        context.read<DocumentProvider>().fetchDocuments(auth.userId!);
        final email = (auth.userEmail ?? auth.email ?? '').trim();
        final fyp = context.read<FypProvider>();
        if (fyp.fypGroupId == null && email.isNotEmpty) {
          await fyp.fetchAssignmentStatus(
            userId: auth.userId!,
            email: email,
          );
        }
      }
    });
  }

  Future<void> _selectFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['doc', 'docx', 'pdf', 'txt'],
    );

    if (result != null && result.files.single.path != null) {
      setState(() {
        _selectedFile = File(result.files.single.path!);
      });
    }
  }

  Future<void> _createReport() async {
    if (_titleController.text.isEmpty) {
      _showError('Please enter a document title');
      return;
    }

    if (_contentController.text.isEmpty) {
      _showError('Please paste or type your content');
      return;
    }

    if (_selectedTemplate == null) {
      _showError('Please select a template');
      return;
    }

    setState(() => _isProcessing = true);

    try {
      final auth = context.read<AuthProvider>();

      // FIX: Capture template values BEFORE any state changes
      final capturedTemplateId = _selectedTemplate!['id'];
      final capturedTemplateName =
          _selectedTemplate!['name'] ?? 'Unknown Template';
      final capturedTitle = _titleController.text.trim();

      // Create report and get document ID
      final response = await _createReportAndGetId(
        capturedTitle,
        _contentController.text,
        capturedTemplateId,
        auth.userId!,
      );

      if (response != null) {
        _showSuccess('Report created successfully!');

        _titleController.clear();
        _contentController.clear();
        setState(() => _selectedTemplate = null);

        context.read<DocumentProvider>().markReadyForSupervisorSubmit(
          documentId: response['document_id'] as int,
          filename: response['filename'] as String? ?? 'report.docx',
          title: capturedTitle.isNotEmpty
              ? capturedTitle
              : (response['filename'] as String? ?? 'Report'),
        );

        // Navigate using the captured (non-null) values
        if (mounted) {
          AnalysisNav.open(AnalysisRequest(
  documentId: response['document_id'] as int,
  documentName: response['filename'] as String,
  templateId: capturedTemplateId,
  templateName: capturedTemplateName,
));
        }
      } else {
        _showError('Failed to create report');
      }
    } catch (e) {
      _showError('Error: $e');
    } finally {
      setState(() => _isProcessing = false);
    }
  }

  Future<Map<String, dynamic>?> _createReportAndGetId(
    String title,
    String content,
    int templateId,
    int userId,
  ) async {
    try {
      // Same endpoint as DocumentProvider.uploadPastedContent (+ create-report alias).
      final response = await http.post(
        Uri.parse(
          '${ApiConfig.getBaseUrl()}/documents/upload-text'
          '?template_id=$templateId&user_id=$userId',
        ),
        headers: ApiConfig.getHeaders(json: true),
        body: jsonEncode({
          'title': title,
          'content': content,
          'template_id': templateId,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return {
          'document_id': data['document_id'],
          'filename': data['filename'] ?? title,
        };
      } else {
        debugPrint('[v0] Create report failed: ${response.body}');
        return null;
      }
    } catch (e) {
      debugPrint('[v0] Create report error: $e');
      return null;
    }
  }

  Future<void> _uploadFile() async {
    if (_selectedFile == null) {
      _showError('Please select a file');
      return;
    }

    if (_selectedTemplate == null) {
      _showError('Please select a template');
      return;
    }

    setState(() => _isProcessing = true);

    try {
      final auth = context.read<AuthProvider>();
      final docProvider = context.read<DocumentProvider>();

      // Upload document and get response with document ID
      final response = await _uploadDocumentAndGetId(
        _selectedFile!,
        _selectedTemplate!['id'],
        auth.userId!,
      );

      if (response != null) {
        _showSuccess('File uploaded successfully!');
        final filename = response['filename'] as String? ??
            _selectedFile!.path.split(RegExp(r'[\\/]')).last;
        context.read<DocumentProvider>().markReadyForSupervisorSubmit(
          documentId: response['document_id'] as int,
          filename: filename,
          title: filename,
        );
        setState(() => _selectedFile = null);

        // Navigate to analyze screen
        if (mounted) {
  AnalysisNav.open(AnalysisRequest(
    documentId: response['document_id'] as int,
    documentName: response['filename'] as String,
    templateId: _selectedTemplate!['id'] as int,
    templateName: (_selectedTemplate!['name'] ?? 'Unknown Template').toString(),
  ));
}
      } else {
        _showError(docProvider.errorMessage ?? 'Failed to upload file');
      }
    } catch (e) {
      _showError('Error: $e');
    } finally {
      setState(() => _isProcessing = false);
    }
  }

  Future<Map<String, dynamic>?> _uploadDocumentAndGetId(
    File file,
    int templateId,
    int userId,
  ) async {
    try {
      final uri = Uri.parse(
        '${ApiConfig.getBaseUrl()}/documents/upload?template_id=$templateId&user_id=$userId',
      );

      var request = http.MultipartRequest('POST', uri);
      request.headers.addAll(ApiConfig.getHeaders());
      request.files.add(await http.MultipartFile.fromPath('file', file.path));

      var response = await request.send();
      final responseBody = await response.stream.bytesToString();

      if (response.statusCode == 200) {
        final data = jsonDecode(responseBody);
        return {
          'document_id': data['document_id'],
          'filename': data['filename'],
        };
      } else {
        debugPrint('[v0] Upload failed: $responseBody');
        return null;
      }
    } catch (e) {
      debugPrint('[v0] Upload error: $e');
      return null;
    }
  }

  /// Non-student: analyze without org template (after confirmation).
  Future<void> _analyzeWithoutTemplate() async {
    final auth = context.read<AuthProvider>();
    if (auth.isStudent) return;

    final confirmed = await confirmAnalyzeWithoutTemplate(context);
    if (!confirmed || !mounted) return;

    // Prefer selected file; else pasted content; else prompt to pick a file.
    if (_selectedFile == null &&
        _contentController.text.trim().isEmpty &&
        _selectedUploadOption == 1) {
      await _selectFile();
    }

    setState(() => _isProcessing = true);
    try {
      Map<String, dynamic>? response;
      final docs = context.read<DocumentProvider>();

      if (_selectedFile != null) {
        response = await docs.uploadDocumentFreeform(_selectedFile!, auth.userId!);
      } else if (_contentController.text.trim().isNotEmpty) {
        response = await docs.uploadPastedContentFreeform(
          _contentController.text,
          auth.userId!,
        );
      } else {
        _showError('Select a file or paste content first');
        return;
      }

      if (response == null) {
        _showError(docs.errorMessage ?? 'Freeform upload failed');
        return;
      }

      final docId = response['document_id'] as int;
      final filename = (response['filename'] ?? 'Document').toString();
      docs.markReadyForSupervisorSubmit(
        documentId: docId,
        filename: filename,
        title: filename,
      );

      if (!mounted) return;
AnalysisNav.open(AnalysisRequest(
  documentId: docId,
  documentName: filename,
  templateId: 0,
  templateName: 'AI general analysis — no template applied',
  freeform: true,
));
    } catch (e) {
      _showError('Error: $e');
    } finally {
      if (mounted) setState(() => _isProcessing = false);
    }
  }

  bool _isFetchingDriveFiles = false;
  List<Map<String, dynamic>> _driveFiles = [];

  void _showGoogleDriveOptions() async {
    final auth = context.read<AuthProvider>();
    String email = '';

    await showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: _p.surface,
        title: Tr('Connect Google Drive',
          style: TextStyle(color: _p.textPrimary),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Tr('Enter your Google email to authorize access:',
              style: TextStyle(
                fontSize: 13,
                color: _p.textSecondary,
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              style: TextStyle(color: _p.textPrimary),
              decoration: InputDecoration(
                hintText: 'example@gmail.com',
                hintStyle: TextStyle(color: _p.textMuted),
                filled: true,
                fillColor: _p.surfaceAlt,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(6),
                ),
              ),
              onChanged: (value) => email = value,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Tr('Cancel',
              style: TextStyle(color: _p.textSecondary),
            ),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(context);
              await _connectGoogleDrive();
            },
            child: const Tr('Connect via OAuth'),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF10B981),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _connectGoogleDrive() async {
    try {
      final auth = context.read<AuthProvider>();
      final success = await auth.connectGoogleDrive();

      if (success) {
        _showSuccess('Google Drive connected successfully!');
        setState(() => _isGoogleDriveConnected = true);
      } else {
        _showError(auth.errorMessage ?? 'Failed to connect Google Drive');
      }
    } catch (e) {
      _showError('Error connecting Google Drive: $e');
    }
  }

  Future<void> _fetchGoogleDriveFiles(int userId) async {
    try {
      setState(() {
        _isFetchingDriveFiles = true;
        _driveFiles = [];
      });

      final response = await http.get(
        Uri.parse(
          '${ApiConfig.getBaseUrl()}/uploads/google-drive/files?user_id=$userId',
        ),
        headers: ApiConfig.getHeaders(),
      );

      if (response.statusCode != 200) {
        String detail = 'Unknown error';
        try {
          final errorData = jsonDecode(response.body);
          detail = '${errorData['detail'] ?? response.body}';
        } catch (_) {
          detail = response.body.isNotEmpty ? response.body : 'HTTP ${response.statusCode}';
        }
        _showError('Failed to fetch files: $detail');
        return;
      }

      final data = jsonDecode(response.body);
      final files = List<Map<String, dynamic>>.from(data['files'] ?? []);
      setState(() => _driveFiles = files);

      if (files.isEmpty) {
        _showError('No files found in Google Drive');
        return;
      }

      if (!mounted) return;

      showDialog(
        context: context,
        builder: (context) => Dialog(
          backgroundColor: _p.surface,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(
              _p.isDark ? _p.cardRadius : 12,
            ),
            side: BorderSide(
              color: _p.isDark ? _p.borderStrong : _p.border,
            ),
          ),
          child: Container(
            width: 450,
            height: 400,
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Tr('Select File from Google Drive',
                  style: TextStyle(
                    color: _p.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 16),
                Expanded(
                  child: _driveFiles.isEmpty
                      ? Center(
                          child: Tr('No files found',
                            style: TextStyle(color: _p.textSecondary),
                          ),
                        )
                      : ListView.builder(
                          itemCount: _driveFiles.length,
                          itemBuilder: (context, index) {
                            final file = _driveFiles[index];
                            return ListTile(
                              leading: Icon(
                                _getFileIcon(file['mimeType'] ?? ''),
                                color: _p.textSecondary,
                              ),
                              title: Text(
                                file['name'] ?? 'Unknown',
                                style: TextStyle(color: _p.textPrimary),
                                overflow: TextOverflow.ellipsis,
                              ),
                              subtitle: Text(
                                file['mimeType'] ?? '',
                                style: TextStyle(
                                  color: _p.textSecondary,
                                  fontSize: 11,
                                ),
                              ),
                              onTap: () {
                                Navigator.pop(context);
                                _importFromGoogleDrive(
                                  userId,
                                  file['id'],
                                  file['name'] ?? 'GoogleDrive_File',
                                );
                              },
                            );
                          },
                        ),
                ),
                const SizedBox(height: 12),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Tr('Cancel'),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    } catch (e) {
      _showError('Error fetching files: $e');
    } finally {
      if (mounted) setState(() => _isFetchingDriveFiles = false);
    }
  }

  IconData _getFileIcon(String mimeType) {
    if (mimeType.contains('pdf')) return Icons.picture_as_pdf;
    if (mimeType.contains('document') || mimeType.contains('word'))
      return Icons.description;
    if (mimeType.contains('spreadsheet') || mimeType.contains('excel'))
      return Icons.table_chart;
    if (mimeType.contains('presentation')) return Icons.slideshow;
    if (mimeType.contains('image')) return Icons.image;
    return Icons.insert_drive_file;
  }

  Future<void> _importFromGoogleDrive(
    int userId,
    String fileId,
    String filename,
  ) async {
    if (_selectedTemplate == null) {
      _showError('Please select a template first');
      return;
    }

    try {
      setState(() => _isProcessing = true);
      final capturedTemplateId = _selectedTemplate!['id'];
      final capturedTemplateName =
          _selectedTemplate!['name'] ?? 'Unknown Template';

      final response = await http.post(
        Uri.parse(
          '${ApiConfig.getBaseUrl()}/uploads/download-from-google-drive'
          '?user_id=$userId'
          '&file_id=$fileId'
          '&filename=${Uri.encodeComponent(filename)}'
          '&template_id=$capturedTemplateId',
        ),
        headers: ApiConfig.getHeaders(),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final docId = data['document_id'] as int?;
        final importedName =
            (data['filename'] as String?) ?? filename;
        _showSuccess('File imported successfully!');
        if (docId != null) {
          context.read<DocumentProvider>().markReadyForSupervisorSubmit(
            documentId: docId,
            filename: importedName,
            title: importedName,
          );
          context.read<DocumentProvider>().fetchDocuments(userId);
 if (mounted) {
  final data = jsonDecode(response.body) as Map<String, dynamic>;
  AnalysisNav.open(AnalysisRequest(
    documentId: data['document_id'] as int,
    documentName: data['filename'] as String,
    templateId: _selectedTemplate!['id'] as int,
    templateName: (_selectedTemplate!['name'] ?? 'Unknown Template').toString(),
  ));
}
        }
      } else {
        String detail = 'Unknown error';
        try {
          final data = jsonDecode(response.body);
          detail = '${data['detail'] ?? response.body}';
        } catch (_) {
          detail = response.body.isNotEmpty
              ? response.body
              : 'HTTP ${response.statusCode}';
        }
        _showError('Failed to import file: $detail');
      }
    } catch (e) {
      _showError('Error: $e');
    } finally {
      if (mounted) setState(() => _isProcessing = false);
    }
  }

void _showError(String message) {
  if (!mounted) return; // ← ADD THIS
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(message), backgroundColor: Colors.red),
  );
}

void _showSuccess(String message) {
  if (!mounted) return; // ← ADD THIS
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text(message), backgroundColor: Colors.green),
  );
}

  @override
  void dispose() {
    _titleController.removeListener(_onPasteFieldsChanged);
    _contentController.removeListener(_onPasteFieldsChanged);
    _titleController.dispose();
    _contentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final fyp = context.watch<FypProvider>();
    final docs = context.watch<DocumentProvider>();
    final hasFyp = DevUserConfig.hasFypModule;
    final showSubmit = hasFyp &&
        fyp.fypGroupId != null &&
        docs.pendingSubmitDocumentId != null;
    final isResubmit = hasFyp && docs.resubmitPriorSubmissionId != null;

    final body = SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (isResubmit) ...[
              _buildResubmitBanner(),
              const SizedBox(height: 16),
            ],
            if (showSubmit) ...[
              _buildSupervisorSubmitBanner(),
              const SizedBox(height: 24),
            ],
           
            const SizedBox(height: 8),
            Row(
              children: [
                _buildOptionButton(
                  index: 1,
                  icon: Icons.upload_file,
                  label: 'Upload File',
                  color: _p.accent,
                ),
                const SizedBox(width: 16),
                _buildOptionButton(
                  index: 2,
                  icon: Icons.edit,
                  label: 'Paste Content',
                  color: const Color(0xFF8B5CF6),
                ),
                const SizedBox(width: 16),
                _buildOptionButton(
                  index: 3,
                  icon: Icons.cloud,
                  label: 'Google Drive',
                  color: const Color(0xFF10B981),
                ),
                const SizedBox(width: 16),
                _buildOptionButton(
                  index: 4,
                  icon: Icons.qr_code,
                  label: 'Upload from Phone',
                  color: const Color(0xFFF59E0B),
                ),
              ],
            ),
            const SizedBox(height: 32),
            if (_selectedUploadOption == 1)
              _buildFileUploadContent()
            else if (_selectedUploadOption == 2)
              _buildPasteContentUI()
            else if (_selectedUploadOption == 3)
              _buildGoogleDriveUI()
            else if (_selectedUploadOption == 4)
              _buildUploadFromPhoneUI(),
          ],
        ),
    );

    if (widget.embedded) {
      return ColoredBox(
        color: _p.scaffold,
        child: body,
      );
    }

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: _p.ambientGlowBackdrop(child: body),
    );
  }

  Widget _buildResubmitBanner() {
    final docs = context.watch<DocumentProvider>();
    final priorId = docs.resubmitPriorSubmissionId;
    final sourceId = docs.resubmitSourceDocumentId;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFF59E0B).withOpacity(0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFF59E0B).withOpacity(0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Tr('Uploading a new version',
            style: TextStyle(
              color: Color(0xFFF59E0B),
              fontWeight: FontWeight.w700,
              fontSize: 14,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            [
              if (priorId != null) 'Prior submission #$priorId.',
              if (sourceId != null)
                'source_document_id=$sourceId will be used until you upload a revised file.',
              'Upload or paste your revised report, then Submit for Supervisor Review.',
            ].join(' '),
            style: TextStyle(
              color: _p.textSecondary,
              fontSize: 12,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSupervisorSubmitBanner() {
    final docs = context.watch<DocumentProvider>();
    final filename = docs.pendingSubmitFilename ?? 'document';
    final hasAnalysis =
        docs.pendingSubmitDocumentId != null &&
        docs.analysisReportFor(docs.pendingSubmitDocumentId!) != null;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: _p.surface,
        borderRadius: BorderRadius.circular(_p.isDark ? _p.cardRadius : 12),
        border: Border.all(color: _p.accent.withOpacity(0.35)),
        boxShadow: _p.isDark ? _p.cardShadow : null,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Tr('Ready for supervisor review',
            style: TextStyle(
              color: _p.textPrimary,
              fontSize: 15,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            filename,
            style: TextStyle(color: _p.textSecondary, fontSize: 13),
          ),
          const SizedBox(height: 4),
          Text(
            hasAnalysis
                ? 'AI analysis snapshot will be attached.'
                : 'No AI analysis cached yet — submit will still work; run Analyze first for grammar/plagiarism scores.',
            style: TextStyle(
              color: _p.textMuted,
              fontSize: 12,
            ),
          ),
          const SizedBox(height: 14),
          SizedBox(
            height: 44,
            child: ElevatedButton.icon(
              onPressed:
                  docs.isSubmittingFinal ? null : _submitForSupervisorReview,
              icon: docs.isSubmittingFinal
                  ? SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.send_outlined, size: 18),
              label: Text(
                docs.isSubmittingFinal
                    ? 'Submitting...'
                    : 'Submit for Supervisor Review',
              ),
              style: ElevatedButton.styleFrom(
                foregroundColor: Colors.white,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _submitForSupervisorReview() async {
    final auth = context.read<AuthProvider>();
    final fyp = context.read<FypProvider>();
    final docs = context.read<DocumentProvider>();

    final userId = auth.userId;
    final email = (auth.userEmail ?? auth.email ?? '').trim();
    var groupId = fyp.fypGroupId;
    final docId = docs.pendingSubmitDocumentId;
    final filename = docs.pendingSubmitFilename ?? 'document.docx';
    final title = docs.pendingSubmitTitle ?? filename;

    if (userId == null || email.isEmpty) {
      _showError('Please sign in again to submit.');
      return;
    }
    if (groupId == null) {
      await fyp.fetchAssignmentStatus(userId: userId, email: email);
      groupId = fyp.fypGroupId;
    }
    if (groupId == null || docId == null) {
      _showError('No active FYP group or document ready to submit.');
      return;
    }

    final result = await docs.submitFinalSubmission(
      userId: userId,
      groupId: groupId,
      title: title,
      filename: filename,
      studentContactEmail: email,
      // Prefer newly uploaded doc; fall back to prior source_document_id from Status Tracker.
      sourceDocumentId: docId ?? docs.resubmitSourceDocumentId,
      analysisReport: docId != null ? docs.analysisReportFor(docId) : null,
    );

    if (!mounted) return;
    if (result != null) {
      _showSuccess('Submitted for supervisor review.');
    } else if (docs.lastSubmitErrorCode == 'deadline_passed') {
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor:
              _p.isDark ? _p.surfaceElevated : const Color(0xFF161B22),
          title: const Tr('Submissions closed',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
          ),
          content: Text(
            docs.errorMessage ??
                'The semester deadline has passed — submissions are closed.',
            style: TextStyle(color: Colors.white.withOpacity(0.8), height: 1.4),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Tr('OK'),
            ),
          ],
        ),
      );
    } else {
      _showError(docs.errorMessage ?? 'Submit failed');
    }
  }

  Widget _buildUploadFromPhoneUI() {
    final auth = context.watch<AuthProvider>();

    return Row(
      children: [
        Expanded(
          child: Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: _p.surface,
              borderRadius: BorderRadius.circular(
                _p.isDark ? _p.cardRadius : 12,
              ),
              border: Border.all(
                color: _p.isDark ? _p.borderStrong : _p.border,
              ),
              boxShadow: _p.isDark ? _p.cardShadow : null,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF59E0B).withOpacity(0.2),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.qr_code,
                        color: Color(0xFFF59E0B),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Tr('Upload from Phone',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: _p.textPrimary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                Tr('Scan QR code using your phone to upload a document.',
                  style: TextStyle(color: _p.textSecondary),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  height: 48,
                  child: ElevatedButton.icon(
                    icon: const Icon(Icons.qr_code),
                    label: const Tr('Generate QR Code'),
                    onPressed:
                        (_selectedTemplate != null && auth.userId != null)
                        ? () => _handleUploadFromPhone(auth.userId!)
                        : null,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFF59E0B),
                    ),
                  ),
                ),
                if (_selectedTemplate == null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Tr('Please select a template first',
                      style: TextStyle(color: Colors.orange.withOpacity(0.8)),
                    ),
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 24),
        Expanded(child: _buildTemplateSelector()),
      ],
    );
  }

  Widget _buildOptionButton({
    required int index,
    required IconData icon,
    required String label,
    required Color color,
  }) {
    final isSelected = _selectedUploadOption == index;

    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _selectedUploadOption = index),
        child: Container(
          decoration: BoxDecoration(
            color: isSelected
                ? color.withOpacity(0.2)
                : _p.surface,
            borderRadius: BorderRadius.circular(
              _p.isDark ? _p.cardRadius : 12,
            ),
            border: Border.all(
              color: isSelected
                  ? color
                  : (_p.isDark ? _p.borderStrong : _p.border),
              width: isSelected ? 2 : 1,
            ),
            boxShadow: isSelected && _p.isDark ? _p.cardShadow : null,
          ),
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 32, color: color),
              const SizedBox(height: 12),
              Text(
                label,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: _p.textPrimary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
Future<void> _handleUploadFromPhone(int userId) async {
  try {
    final result = await QRUploadService.generateUploadQr(
      userId,
      _selectedTemplate!['id'],
    );

    if (!mounted) return; // ← ADD THIS

    final qrBase64 = result['qr_base64'];
    final deepLink = result['deep_link']; // ← WAS 'upload_url' (wrong key, backend sends 'deep_link')

    if (qrBase64 == null) {
      throw Exception('Invalid QR response from server');
    }

    showDialog(
      context: context,
      builder: (_) => Dialog(
        backgroundColor: Colors.white,
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Tr('Scan to Upload from Phone',
                style: TextStyle(fontWeight: FontWeight.bold, color: Colors.black),
              ),
              const SizedBox(height: 16),
              Image.memory(base64Decode(qrBase64), width: 250, height: 250),
              const SizedBox(height: 12),
              if (deepLink != null)
                SelectableText(deepLink, style: const TextStyle(fontSize: 12)),
            ],
          ),
        ),
      ),
    );
  } catch (e) {
    if (!mounted) return; // ← ADD THIS
    _showError('Failed to generate QR: $e');
  }
}

  Widget _buildFileUploadContent() {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Container(
            decoration: BoxDecoration(
              color: _p.surface,
              borderRadius: BorderRadius.circular(
                _p.isDark ? _p.cardRadius : 12,
              ),
              border: Border.all(
                color: _p.isDark ? _p.borderStrong : _p.border,
              ),
              boxShadow: _p.isDark ? _p.cardShadow : null,
            ),
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: _p.accentSoft,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Icon(
                        Icons.upload_file,
                        color: _p.accent,
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Tr('Upload File',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: _p.textPrimary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                if (_selectedFile == null)
                  GestureDetector(
                    onTap: _selectFile,
                    child: Container(
                      decoration: BoxDecoration(
                        color: _p.surfaceAlt,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: _p.borderStrong,
                          strokeAlign: BorderSide.strokeAlignOutside,
                        ),
                      ),
                      padding: const EdgeInsets.symmetric(
                        vertical: 40,
                        horizontal: 24,
                      ),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.cloud_upload,
                            size: 48,
                            color: _p.textMuted,
                          ),
                          const SizedBox(height: 16),
                          Tr('Click to upload or drag files',
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w500,
                              color: _p.textPrimary,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Tr('Supported: DOC, DOCX, PDF, TXT',
                            style: TextStyle(
                              fontSize: 12,
                              color: _p.textMuted,
                            ),
                          ),
                        ],
                      ),
                    ),
                  )
                else
                  Container(
                    decoration: BoxDecoration(
                      color: _p.surfaceAlt,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: const Color(0xFF10B981).withOpacity(0.5),
                      ),
                    ),
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.check_circle,
                          color: Color(0xFF10B981),
                          size: 24,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Tr('File selected',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: _p.textSecondary,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                _selectedFile!.path.split('/').last,
                                style: TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600,
                                  color: _p.textPrimary,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ),
                        ),
                        GestureDetector(
                          onTap: () => setState(() => _selectedFile = null),
                          child: Icon(
                            Icons.close,
                            color: _p.textMuted,
                          ),
                        ),
                      ],
                    ),
                  ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  height: 48,
                  child: ElevatedButton.icon(
                    onPressed:
                        (_selectedFile != null &&
                            _selectedTemplate != null &&
                            !_isProcessing)
                        ? _uploadFile
                        : null,
                    icon: _isProcessing
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor: AlwaysStoppedAnimation<Color>(
                                Colors.white,
                              ),
                            ),
                          )
                        : const Icon(Icons.upload),
                    label: Text(
                      _isProcessing ? 'Processing...' : 'Upload & Process',
                    ),
                    style: ElevatedButton.styleFrom(
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 24),
        Expanded(child: _buildTemplateSelector()),
      ],
    );
  }

  Widget _buildPasteContentUI() {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          flex: 2,
          child: Container(
            decoration: BoxDecoration(
              color: _p.surface,
              borderRadius: BorderRadius.circular(
                _p.isDark ? _p.cardRadius : 12,
              ),
              border: Border.all(
                color: _p.isDark ? _p.borderStrong : _p.border,
              ),
              boxShadow: _p.isDark ? _p.cardShadow : null,
            ),
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: const Color(0xFF8B5CF6).withOpacity(0.2),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.edit,
                        color: Color(0xFF8B5CF6),
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Tr('Paste Content',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: _p.textPrimary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                // Title Field
                TextField(
                  controller: _titleController,
                  style: TextStyle(color: _p.textPrimary),
                  decoration: InputDecoration(
                    labelText: 'Document Title',
                    labelStyle: TextStyle(color: _p.textSecondary),
                    filled: true,
                    fillColor: _p.surfaceAlt,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide(
                        color: _p.border,
                      ),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide(
                        color: _p.border,
                      ),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: const BorderSide(color: Color(0xFF8B5CF6)),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                // Content Field
                TextField(
                  controller: _contentController,
                  style: TextStyle(color: _p.textPrimary),
                  maxLines: 10,
                  decoration: InputDecoration(
                    labelText: 'Paste your content here...',
                    alignLabelWithHint: true,
                    labelStyle: TextStyle(color: _p.textSecondary),
                    filled: true,
                    fillColor: _p.surfaceAlt,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide(
                        color: _p.border,
                      ),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide(
                        color: _p.border,
                      ),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: const BorderSide(color: Color(0xFF8B5CF6)),
                    ),
                  ),
                ),
                const SizedBox(height: 24),
                // Create Report Button
                // NOTE: The button is only enabled when title, content AND template are all filled
                SizedBox(
                  width: double.infinity,
                  height: 48,
                  child: ElevatedButton.icon(
                    onPressed:
                        (_titleController.text.isNotEmpty &&
                            _contentController.text.isNotEmpty &&
                            _selectedTemplate != null &&
                            !_isProcessing)
                        ? _createReport
                        : null,
                    icon: _isProcessing
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor: AlwaysStoppedAnimation<Color>(
                                Colors.white,
                              ),
                            ),
                          )
                        : const Icon(Icons.auto_fix_high),
                    label: Text(
                      _isProcessing ? 'Processing...' : 'Create Report',
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF8B5CF6),
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                ),
                // Helper text shown when template not yet selected
                if (_selectedTemplate == null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Tr('Select a template on the right to enable this button',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.orange.withOpacity(0.8),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 24),
        Expanded(child: _buildTemplateSelector()),
      ],
    );
  }

  Widget _buildGoogleDriveUI() {
    final auth = context.watch<AuthProvider>();
    final userId = auth.userId;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Container(
            decoration: BoxDecoration(
              color: _p.surface,
              borderRadius: BorderRadius.circular(
                _p.isDark ? _p.cardRadius : 12,
              ),
              border: Border.all(
                color: _p.isDark ? _p.borderStrong : _p.border,
              ),
              boxShadow: _p.isDark ? _p.cardShadow : null,
            ),
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: const Color(0xFF10B981).withOpacity(0.2),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.cloud,
                        color: Color(0xFF10B981),
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Tr('Google Drive',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: _p.textPrimary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                Container(
                  decoration: BoxDecoration(
                    color: _p.surfaceAlt,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: _isGoogleDriveConnected
                          ? const Color(0xFF10B981).withOpacity(0.5)
                          : _p.border,
                    ),
                  ),
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      Icon(
                        _isGoogleDriveConnected
                            ? Icons.check_circle
                            : Icons.cloud_off,
                        size: 48,
                        color: _isGoogleDriveConnected
                            ? const Color(0xFF10B981)
                            : _p.textMuted,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        _isGoogleDriveConnected
                            ? 'Connected to Google Drive'
                            : 'Not connected',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w500,
                          color: _isGoogleDriveConnected
                              ? const Color(0xFF10B981)
                              : _p.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                if (!_isGoogleDriveConnected)
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton.icon(
                      onPressed: _showGoogleDriveOptions,
                      icon: const Icon(Icons.link),
                      label: const Tr('Connect Google Drive'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF10B981),
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                    ),
                  )
                else
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: ElevatedButton.icon(
                      onPressed:
                          (_selectedTemplate != null &&
                              userId != null &&
                              !_isFetchingDriveFiles)
                          ? () => _fetchGoogleDriveFiles(userId)
                          : null,
                      icon: _isFetchingDriveFiles
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor: AlwaysStoppedAnimation<Color>(
                                  Colors.white,
                                ),
                              ),
                            )
                          : const Icon(Icons.folder_open),
                      label: Text(
                        _isFetchingDriveFiles
                            ? 'Loading...'
                            : 'Upload Document from Drive',
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF10B981),
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                    ),
                  ),
                if (_selectedTemplate == null && _isGoogleDriveConnected)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Tr('Please select a template first',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.orange.withOpacity(0.8),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 24),
        Expanded(child: _buildTemplateSelector()),
      ],
    );
  }

  Widget _buildTemplateSelector() {
    return Container(
      decoration: BoxDecoration(
        color: _p.surface,
        borderRadius: BorderRadius.circular(_p.isDark ? _p.cardRadius : 12),
        border: Border.all(color: _p.isDark ? _p.borderStrong : _p.border),
        boxShadow: _p.isDark ? _p.cardShadow : null,
      ),
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFFF59E0B).withOpacity(0.2),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.description,
                  color: Color(0xFFF59E0B),
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Tr('Select Template',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: _p.textPrimary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          Consumer<TemplateProvider>(
            builder: (context, templateProvider, child) {
              if (templateProvider.isLoading) {
                return const Center(
                  child: Padding(
                    padding: EdgeInsets.all(32),
                    child: CircularProgressIndicator(),
                  ),
                );
              }

              final templates = templateProvider.templates;

              if (templates.isEmpty) {
                return Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: _p.surfaceAlt,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Column(
                    children: [
                      Icon(
                        Icons.folder_off,
                        size: 32,
                        color: _p.textMuted,
                      ),
                      const SizedBox(height: 12),
                      Tr('No templates available',
                        style: TextStyle(color: _p.textSecondary),
                      ),
                    ],
                  ),
                );
              }

              return ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: templates.length,
                separatorBuilder: (_, __) => const SizedBox(height: 8),
                itemBuilder: (context, index) {
                  final template = templates[index];
                  final isSelected = _selectedTemplate?['id'] == template['id'];

                  return GestureDetector(
                    onTap: () {
                      setState(() => _selectedTemplate = template);
                    },
                    child: Container(
                      decoration: BoxDecoration(
                        color: isSelected
                            ? const Color(0xFFF59E0B).withOpacity(0.2)
                            : _p.surfaceAlt,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: isSelected
                              ? const Color(0xFFF59E0B)
                              : _p.border,
                        ),
                      ),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 14,
                        vertical: 14,
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.center,
                        children: [
                          Icon(
                            isSelected
                                ? Icons.radio_button_checked
                                : Icons.radio_button_off,
                            color: isSelected
                                ? const Color(0xFFF59E0B)
                                : _p.textMuted,
                            size: 20,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Builder(
                              builder: (context) {
                                final name = (template['name'] ??
                                        'Unnamed Template')
                                    .toString();
                                final description =
                                    (template['description'] ?? '')
                                        .toString()
                                        .trim();
                                if (description.isEmpty) {
                                  return Text(
                                    name,
                                    style: TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w500,
                                      height: 1.25,
                                      color: _p.textPrimary,
                                    ),
                                  );
                                }
                                return Column(
                                  mainAxisSize: MainAxisSize.min,
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      name,
                                      style: TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.w500,
                                        height: 1.25,
                                        color: _p.textPrimary,
                                      ),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      description,
                                      style: TextStyle(
                                        fontSize: 12,
                                        height: 1.25,
                                        color: _p.textSecondary,
                                      ),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ],
                                );
                              },
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              );
            },
          ),
          if (!context.watch<AuthProvider>().isStudent) ...[
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _isProcessing ? null : _analyzeWithoutTemplate,
                icon: const Icon(Icons.auto_awesome, size: 18),
                label: const Tr('Analyze without template'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AdminColors.primary,
                  side: BorderSide(color: AdminColors.primary.withOpacity(0.7)),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}