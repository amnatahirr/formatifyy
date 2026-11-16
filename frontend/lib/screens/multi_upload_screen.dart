import 'dart:io';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:file_picker/file_picker.dart';
import '../providers/upload_provider.dart';
import '../providers/auth_provider.dart';
import '../providers/template_provider.dart';
import '../providers/document_provider.dart';
import '../widgets/google_drive_browser_widget.dart';
import '../widgets/admin/admin_ui.dart';
import '../widgets/freeform_analyze_dialogs.dart';
import 'analyze_screen.dart';
import '../utils/analysis_nav.dart';

import '../widgets/tr.dart';

class MultiUploadScreen extends StatefulWidget {
  const MultiUploadScreen({Key? key}) : super(key: key);

  @override
  State<MultiUploadScreen> createState() => _MultiUploadScreenState();
}

class _MultiUploadScreenState extends State<MultiUploadScreen> {
  int _selectedTemplateId = 0;

  @override
  void initState() {
    super.initState();
    // Load templates, documents, and initialize Google Drive on init
    Future.microtask(() {
      final auth = context.read<AuthProvider>();
      final uploads = context.read<UploadProvider>();
      context.read<TemplateProvider>().fetchTemplates(auth.userId ?? 0);
      uploads.loadUserDocuments(auth.userId ?? 0);

      // Initialize Google Drive for the logged-in user
      if (auth.userId != null) {
        uploads.initializeGoogleDrive(
          userId: auth.userId ?? 0,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final templates = context.watch<TemplateProvider>();
    final uploads = context.watch<UploadProvider>();

    // NOTE: TabBar tabs aur TabBarView children ki ginti hamesha barabar honi chahiye.
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Tr('Upload Documents'),
          elevation: 0,
          bottom: const TabBar(
            tabs: [
              Tab(icon: Icon(Icons.folder), text: 'Local'),
              Tab(icon: Icon(Icons.cloud), text: 'Google Drive'),
              Tab(icon: Icon(Icons.list), text: 'My Uploads'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            // Local Upload Tab
            _buildLocalUploadTab(auth, templates, uploads),

            // Google Drive Tab
            _buildGoogleDriveTab(auth, templates, uploads),

            // My Uploads Tab
            _buildMyUploadsTab(auth, uploads),
          ],
        ),
      ),
    );
  }

  // ============ PICK + UPLOAD (works on app AND web/mobile browser) ============
  Future<void> _pickAndUpload(AuthProvider auth, UploadProvider uploads) async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: const ['pdf', 'docx'],
        withData: kIsWeb, // web par path nahi milta, bytes chahiye
      );

      if (result == null || result.files.isEmpty) return;
      final file = result.files.first;

      if (kIsWeb && file.bytes == null) {
        _showSnack('Could not read the selected file', isError: true);
        return;
      }
      if (!kIsWeb && file.path == null) {
        _showSnack('Could not read the selected file', isError: true);
        return;
      }

      final ok = await uploads.uploadLocalFile(
        userId: auth.userId ?? 0,
        templateId: _selectedTemplateId,
        filePath: kIsWeb ? null : file.path,
        bytes: kIsWeb ? file.bytes : null,
        filename: file.name,
      );

      if (!mounted) return;
      _showSnack(
        ok
            ? 'File uploaded successfully!'
            : (uploads.uploadErrorMessage ?? 'Upload failed'),
        isError: !ok,
      );
    } catch (e) {
      if (!mounted) return;
      _showSnack('Upload error: $e', isError: true);
    }
  }

  void _showSnack(String message, {bool isError = false}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? Colors.red : Colors.green,
      ),
    );
  }

  // ============ LOCAL UPLOAD TAB ============
  Widget _buildLocalUploadTab(
    AuthProvider auth,
    TemplateProvider templates,
    UploadProvider uploads,
  ) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SizedBox(height: 12),
          const Tr(
            'Upload from Your Device',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 24),

          // Template Selection
          const Tr('Select Template',
              style: TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          DropdownButton<int>(
            isExpanded: true,
            value: _selectedTemplateId > 0 ? _selectedTemplateId : null,
            hint: const Tr('Choose a template'),
            items: templates.templates.map((template) {
              final id = template['id'] is int
                  ? template['id'] as int
                  : int.parse(template['id'].toString());
              return DropdownMenuItem<int>(
                value: id,
                child: Text(template['name']?.toString() ?? 'Unknown'),
              );
            }).toList(),
            onChanged: (value) {
              setState(() {
                _selectedTemplateId = value ?? 0;
              });
            },
          ),
          if (!auth.isStudent) ...[
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: uploads.isUploading
                    ? null
                    : () => _analyzeWithoutTemplate(auth),
                icon: const Icon(Icons.auto_awesome, size: 18),
                label: const Tr('Analyze without template'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AdminColors.primary,
                  side: BorderSide(
                      color: AdminColors.primary.withOpacity(0.7)),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
              ),
            ),
          ],
          const SizedBox(height: 24),

          // Upload Button
          ElevatedButton.icon(
            onPressed: _selectedTemplateId > 0 && !uploads.isUploading
                ? () => _pickAndUpload(auth, uploads)
                : null,
            icon: uploads.isUploading
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.upload_file),
            label: Text(uploads.isUploading ? 'Uploading...' : 'Choose File'),
            style: ElevatedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 12),
            ),
          ),
          if (_selectedTemplateId == 0) ...[
            const SizedBox(height: 8),
            const Tr(
              'Pehle upar se template select karein, phir Choose File chalega.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ],

          // Progress
          if (uploads.isUploading) ...[
            const SizedBox(height: 16),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: uploads.uploadProgress > 0
                    ? uploads.uploadProgress / 100
                    : null,
                minHeight: 6,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '${uploads.uploadProgress}%',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 12),
            ),
          ],

          // Error Message
          if (uploads.uploadErrorMessage != null) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.red.shade900.withOpacity(0.2),
                border: Border.all(color: Colors.red),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                uploads.uploadErrorMessage!,
                style: const TextStyle(color: Colors.red),
              ),
            ),
          ],

          // Info
          const SizedBox(height: 32),
          _buildFeatureCard(
            icon: Icons.speed,
            title: 'Quick Upload',
            description: 'Upload documents directly from your device storage',
          ),
          const SizedBox(height: 12),
          _buildFeatureCard(
            icon: Icons.format_shapes,
            title: 'Auto-formatted',
            description: 'Documents are automatically formatted to your template',
          ),
        ],
      ),
    );
  }

  // ============ GOOGLE DRIVE TAB ============
  Widget _buildGoogleDriveTab(
    AuthProvider auth,
    TemplateProvider templates,
    UploadProvider uploads,
  ) {
    // Expanded sirf Column ke andar kaam karta hai, SingleChildScrollView ke andar nahi.
    return Column(
      children: [
        // Header section
        Container(
          width: double.infinity,
          color: Colors.black87,
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Tr(
                'Google Drive Integration',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Connected as: ${auth.email ?? "Not connected"}',
                style: const TextStyle(
                  fontSize: 12,
                  color: Colors.grey,
                ),
              ),
              const SizedBox(height: 12),
              const Tr(
                'Select a template before importing files:',
                style: TextStyle(fontSize: 12),
              ),
              const SizedBox(height: 8),
              DropdownButton<int>(
                isExpanded: true,
                value: _selectedTemplateId > 0 ? _selectedTemplateId : null,
                hint: const Tr('Choose a template'),
                items: templates.templates.map((template) {
                  final id = template['id'] is int
                      ? template['id'] as int
                      : int.parse(template['id'].toString());
                  return DropdownMenuItem<int>(
                    value: id,
                    child: Text(template['name']?.toString() ?? 'Unknown'),
                  );
                }).toList(),
                onChanged: (value) {
                  if (value != null) {
                    setState(() {
                      _selectedTemplateId = value;
                    });
                  }
                },
                dropdownColor: const Color(0xFF1A1F2E),
                style: const TextStyle(color: Colors.white),
              ),
            ],
          ),
        ),
        // File browser
        if (_selectedTemplateId > 0)
          Expanded(
            child: GoogleDriveBrowserWidget(
              userId: auth.userId ?? 0,
              templateId: _selectedTemplateId,
              onFileSelected: (fileId, fileName) async {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('Importing $fileName...'),
                    duration: const Duration(seconds: 2),
                  ),
                );
                // Trigger file download from Google Drive
                await uploads.downloadFromGoogleDrive(
                  userId: auth.userId ?? 0,
                  fileId: fileId,
                  filename: fileName,
                  templateId: _selectedTemplateId,
                );
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(
                        uploads.uploadErrorMessage != null
                            ? 'Error: ${uploads.uploadErrorMessage}'
                            : 'File imported successfully!',
                      ),
                      duration: const Duration(seconds: 2),
                    ),
                  );
                }
              },
            ),
          )
        else
          Expanded(
            child: Container(
              color: Colors.black87,
              child: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.folder_open,
                      size: 48,
                      color: Colors.grey.shade600,
                    ),
                    const SizedBox(height: 16),
                    const Tr('Select a template to continue'),
                    const SizedBox(height: 8),
                    Tr(
                      'Templates help format your documents properly',
                      style: TextStyle(
                        color: Colors.grey.shade600,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        if (uploads.isUploading)
          Container(
            width: double.infinity,
            color: Colors.black87,
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const CircularProgressIndicator(),
                const SizedBox(height: 12),
                Text(
                  'Syncing: ${uploads.uploadProgress}%',
                  style: const TextStyle(color: Colors.white),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Future<void> _analyzeWithoutTemplate(AuthProvider auth) async {
    if (auth.isStudent) return;

    // dart:io ka File web par kaam nahi karta.
    // Jab DocumentProvider mein bytes wala method add ho jaye to yahan web support lag sakta hai.
    if (kIsWeb) {
      _showSnack(
        'Analyze without template abhi sirf app mein available hai.',
        isError: true,
      );
      return;
    }

    final confirmed = await confirmAnalyzeWithoutTemplate(context);
    if (!confirmed || !mounted) return;

    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['pdf', 'docx', 'txt'],
    );
    if (result == null ||
        result.files.isEmpty ||
        result.files.first.path == null) {
      return;
    }

    final docs = context.read<DocumentProvider>();
    final response = await docs.uploadDocumentFreeform(
      File(result.files.first.path!),
      auth.userId!,
    );
    if (!mounted) return;
    if (response == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(docs.errorMessage ?? 'Freeform upload failed'),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

    AnalysisNav.open(AnalysisRequest(
      documentId: response['document_id'] as int,
      documentName: (response['filename'] ?? 'Document').toString(),
      templateId: 0,
      templateName: 'AI general analysis — no template applied',
      freeform: true,
    ));
  }

  // ============ MY UPLOADS TAB ============
  Widget _buildMyUploadsTab(AuthProvider auth, UploadProvider uploads) {
    // Pehle yahan FutureBuilder ke andar build() mein loadUserDocuments call ho raha tha,
    // jo notifyListeners se baar baar rebuild + request ka loop bana sakta tha.
    // Ab initState mein ek hi baar load hota hai; pull-to-refresh se dobara load hota hai.
    if (uploads.userDocuments.isEmpty) {
      return RefreshIndicator(
        onRefresh: () => uploads.loadUserDocuments(auth.userId ?? 0),
        child: ListView(
          children: [
            const SizedBox(height: 120),
            Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    Icons.folder_open,
                    size: 48,
                    color: Colors.grey.shade600,
                  ),
                  const SizedBox(height: 16),
                  const Tr('No documents yet'),
                  const SizedBox(height: 8),
                  Tr(
                    'Start uploading documents from any source',
                    style: TextStyle(color: Colors.grey.shade600),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () => uploads.loadUserDocuments(auth.userId ?? 0),
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: uploads.userDocuments.length,
        itemBuilder: (context, index) {
          final doc = uploads.userDocuments[index];
          return _buildDocumentCard(doc);
        },
      ),
    );
  }

  // userDocuments ki items DocumentSyncStatus objects hain, Map nahi.
  Widget _buildDocumentCard(DocumentSyncStatus doc) {
    final statusColor = doc.status == 'completed'
        ? Colors.green
        : doc.status == 'failed'
            ? Colors.red
            : Colors.orange;

    final sourceIcon = doc.source == 'google_drive'
        ? Icons.cloud
        : doc.source == 'mobile'
            ? Icons.phone_android
            : Icons.folder;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Icon(sourceIcon, color: Colors.grey),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    doc.filename,
                    style: const TextStyle(fontWeight: FontWeight.w600),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 4,
                        ),
                        decoration: BoxDecoration(
                          color: statusColor.withOpacity(0.2),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          doc.status,
                          style: TextStyle(
                            fontSize: 11,
                            color: statusColor,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        doc.createdAt.toString().split('.').first,
                        style:
                            const TextStyle(fontSize: 11, color: Colors.grey),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            PopupMenuButton(
              itemBuilder: (context) => [
                const PopupMenuItem(
                  child: Tr('View Details'),
                ),
                const PopupMenuItem(
                  child: Tr('Download'),
                ),
                const PopupMenuItem(
                  child: Tr('Share'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFeatureCard({
    required IconData icon,
    required String title,
    required String description,
  }) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.grey.shade700),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(icon, color: Colors.indigo.shade300),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                Text(
                  description,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey.shade400,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}