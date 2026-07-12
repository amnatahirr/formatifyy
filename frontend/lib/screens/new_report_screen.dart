// import 'dart:convert';
// import 'dart:io';
// import 'package:flutter/material.dart';
// import 'package:file_picker/file_picker.dart';
// import 'package:frontend/screens/qr_upload_service.dart';
// import 'package:http/http.dart' as dio;
// import 'package:provider/provider.dart';
// import 'package:http/http.dart' as http;
// import '../providers/auth_provider.dart';
// import '../providers/document_provider.dart';
// import '../providers/template_provider.dart';
// import '../config/api_config.dart';
// import 'analyze_screen.dart';
// import 'package:url_launcher/url_launcher.dart';

// class NewReportScreen extends StatefulWidget {
//   final Map<String, dynamic>? selectedTemplate;

//   const NewReportScreen({Key? key, this.selectedTemplate}) : super(key: key);

//   @override
//   State<NewReportScreen> createState() => _NewReportScreenState();
// }

// class _NewReportScreenState extends State<NewReportScreen> {
//   bool _isGoogleDriveConnected = false;
//   final TextEditingController _titleController = TextEditingController();
//   final TextEditingController _contentController = TextEditingController();
//   Map<String, dynamic>? _selectedTemplate;
//   bool _isProcessing = false;
//   File? _selectedFile;
//   bool _autoFormatDetection = true;
//   bool _secureProcessing = true;
//   bool _preserveFormatting = true;
//   int _selectedUploadOption = 1; // 1 = file, 2 = paste, 3 = google drive
//   String _googleEmail = '';

//   @override
//   void initState() {
//     super.initState();
//     _loadTemplatesAndDocuments();
//     if (widget.selectedTemplate != null) {
//       _selectedTemplate = widget.selectedTemplate;
//     }
//   }

//   void _loadTemplatesAndDocuments() {
//     Future.microtask(() {
//       final auth = context.read<AuthProvider>();
//       if (auth.userId != null) {
//         context.read<TemplateProvider>().fetchUserTemplates(auth.userId!);
//         context.read<DocumentProvider>().fetchDocuments(auth.userId!);
//       }
//     });
//   }

//   Future<void> _selectFile() async {
//     final result = await FilePicker.platform.pickFiles(
//       type: FileType.custom,
//       allowedExtensions: ['doc', 'docx', 'pdf', 'txt'],
//     );

//     if (result != null && result.files.single.path != null) {
//       setState(() {
//         _selectedFile = File(result.files.single.path!);
//       });
//     }
//   }

//   Future<void> _createReport() async {
//     if (_titleController.text.isEmpty) {
//       _showError('Please enter a document title');
//       return;
//     }

//     if (_contentController.text.isEmpty) {
//       _showError('Please paste or type your content');
//       return;
//     }

//     if (_selectedTemplate == null) {
//       _showError('Please select a template');
//       return;
//     }

//     setState(() => _isProcessing = true);

//     try {
//       final auth = context.read<AuthProvider>();

//       // Create report and get document ID
//       final response = await _createReportAndGetId(
//         _titleController.text,
//         _contentController.text,
//         _selectedTemplate!['id'],
//         auth.userId!,
//       );

//       if (response != null) {
//         _showSuccess('Report created successfully!');
//         _titleController.clear();
//         _contentController.clear();
//         setState(() => _selectedTemplate = null);

//         // Navigate to analyze screen
//         if (mounted) {
//           Navigator.push(
//             context,
//             MaterialPageRoute(
//               builder: (context) => AnalyzeScreen(
//                 documentId: response['document_id'],
//                 documentName: response['filename'],
//                 templateId: _selectedTemplate!['id'],
//                 templateName: _selectedTemplate!['name'] ?? 'Unknown Template',
//               ),
//             ),
//           );
//         }
//       } else {
//         _showError('Failed to create report');
//       }
//     } catch (e) {
//       _showError('Error: $e');
//     } finally {
//       setState(() => _isProcessing = false);
//     }
//   }

//   Future<Map<String, dynamic>?> _createReportAndGetId(
//     String title,
//     String content,
//     int templateId,
//     int userId,
//   ) async {
//     try {
//       final response = await http.post(
//         Uri.parse(
//           '${ApiConfig.getBaseUrl()}/documents/create-report?user_id=$userId&template_id=$templateId',
//         ),
//         headers: {'Content-Type': 'application/json'},
//         body: jsonEncode({
//           'title': title,
//           'content': content,
//           'template_id': templateId,
//         }),
//       );

//       if (response.statusCode == 200) {
//         final data = jsonDecode(response.body);
//         return {
//           'document_id': data['document_id'],
//           'filename': data['filename'],
//         };
//       } else {
//         debugPrint('[v0] Create report failed: ${response.body}');
//         return null;
//       }
//     } catch (e) {
//       debugPrint('[v0] Create report error: $e');
//       return null;
//     }
//   }

//   Future<void> _uploadFile() async {
//     if (_selectedFile == null) {
//       _showError('Please select a file');
//       return;
//     }

//     if (_selectedTemplate == null) {
//       _showError('Please select a template');
//       return;
//     }

//     setState(() => _isProcessing = true);

//     try {
//       final auth = context.read<AuthProvider>();
//       final docProvider = context.read<DocumentProvider>();

//       // Upload document and get response with document ID
//       final response = await _uploadDocumentAndGetId(
//         _selectedFile!,
//         _selectedTemplate!['id'],
//         auth.userId!,
//       );

//       if (response != null) {
//         _showSuccess('File uploaded successfully!');
//         setState(() => _selectedFile = null);

//         // Navigate to analyze screen
//         if (mounted) {
//           Navigator.push(
//             context,
//             MaterialPageRoute(
//               builder: (context) => AnalyzeScreen(
//                 documentId: response['document_id'],
//                 documentName: response['filename'],
//                 templateId: _selectedTemplate!['id'],
//                 templateName: _selectedTemplate!['name'] ?? 'Unknown Template',
//               ),
//             ),
//           );
//         }
//       } else {
//         _showError(docProvider.errorMessage ?? 'Failed to upload file');
//       }
//     } catch (e) {
//       _showError('Error: $e');
//     } finally {
//       setState(() => _isProcessing = false);
//     }
//   }

//   Future<Map<String, dynamic>?> _uploadDocumentAndGetId(
//     File file,
//     int templateId,
//     int userId,
//   ) async {
//     try {
//       final uri = Uri.parse(
//         '${ApiConfig.getBaseUrl()}/documents/upload?template_id=$templateId&user_id=$userId',
//       );

//       var request = http.MultipartRequest('POST', uri);
//       request.files.add(await http.MultipartFile.fromPath('file', file.path));

//       var response = await request.send();
//       final responseBody = await response.stream.bytesToString();

//       if (response.statusCode == 200) {
//         final data = jsonDecode(responseBody);
//         return {
//           'document_id': data['document_id'],
//           'filename': data['filename'],
//         };
//       } else {
//         debugPrint('[v0] Upload failed: $responseBody');
//         return null;
//       }
//     } catch (e) {
//       debugPrint('[v0] Upload error: $e');
//       return null;
//     }
//   }

//   // Inside _NewReportScreenState

//   bool _isFetchingDriveFiles = false;
//   List<Map<String, dynamic>> _driveFiles = [];

//   // Show Google Drive connection dialog
//   void _showGoogleDriveOptions() async {
//     final auth = context.read<AuthProvider>();
//     String email = '';

//     await showDialog(
//       context: context,
//       builder: (context) => AlertDialog(
//         backgroundColor: const Color(0xFF161B22),
//         title: const Text(
//           'Connect Google Drive',
//           style: TextStyle(color: Colors.white),
//         ),
//         content: Column(
//           mainAxisSize: MainAxisSize.min,
//           children: [
//             Text(
//               'Enter your Google email to authorize access:',
//               style: TextStyle(
//                 fontSize: 13,
//                 color: Colors.white.withOpacity(0.8),
//               ),
//             ),
//             const SizedBox(height: 16),
//             TextField(
//               style: const TextStyle(color: Colors.white),
//               decoration: InputDecoration(
//                 hintText: 'example@gmail.com',
//                 hintStyle: TextStyle(color: Colors.white.withOpacity(0.4)),
//                 filled: true,
//                 fillColor: const Color(0xFF0D1117),
//                 border: OutlineInputBorder(
//                   borderRadius: BorderRadius.circular(6),
//                 ),
//               ),
//               onChanged: (value) => email = value,
//             ),
//           ],
//         ),
//         actions: [
//           TextButton(
//             onPressed: () => Navigator.pop(context),
//             child: const Text(
//               'Cancel',
//               style: TextStyle(color: Colors.white70),
//             ),
//           ),
//           ElevatedButton(
//             onPressed: () async {
//               Navigator.pop(context);
//               await _connectGoogleDrive();
//             },
//             child: const Text('Connect via OAuth'),
//             style: ElevatedButton.styleFrom(
//               backgroundColor: const Color(0xFF10B981),
//             ),
//           ),
//         ],
//       ),
//     );
//   }

//   Future<void> _connectGoogleDrive() async {
//     try {
//       final auth = context.read<AuthProvider>();

//       // Use connectGoogleDrive() to link Drive to existing logged-in user
//       // This passes user_id to backend so tokens are stored for the correct user
//       final success = await auth.connectGoogleDrive();

//       if (success) {
//         _showSuccess('Google Drive connected successfully!');
//         setState(() => _isGoogleDriveConnected = true);
//       } else {
//         _showError(auth.errorMessage ?? 'Failed to connect Google Drive');
//       }
//     } catch (e) {
//       _showError('Error connecting Google Drive: $e');
//     }
//   }

//   // ========================================
//   // FIXED: Fetch files with user_id parameter
//   // ========================================
//   Future<void> _fetchGoogleDriveFiles(int userId) async {
//     try {
//       setState(() {
//         _isFetchingDriveFiles = true;
//         _driveFiles = [];
//       });

//       // FIXED: Added user_id query parameter to the request
//       final response = await http.get(
//         Uri.parse(
//           'http://localhost:8000/api/uploads/google-drive/files?user_id=$userId',
//         ),
//       );

//       if (response.statusCode != 200) {
//         final errorData = jsonDecode(response.body);
//         _showError(
//           'Failed to fetch files: ${errorData['detail'] ?? 'Unknown error'}',
//         );
//         return;
//       }

//       final data = jsonDecode(response.body);
//       final files = List<Map<String, dynamic>>.from(data['files'] ?? []);
//       setState(() => _driveFiles = files);

//       if (files.isEmpty) {
//         _showError('No files found in Google Drive');
//         return;
//       }

//       if (!mounted) return;

//       // Show file selection dialog using Dialog instead of AlertDialog to avoid IntrinsicWidth issues
//       showDialog(
//         context: context,
//         builder: (context) => Dialog(
//           backgroundColor: const Color(0xFF161B22),
//           shape: RoundedRectangleBorder(
//             borderRadius: BorderRadius.circular(12),
//           ),
//           child: Container(
//             width: 450,
//             height: 400,
//             padding: const EdgeInsets.all(20),
//             child: Column(
//               crossAxisAlignment: CrossAxisAlignment.start,
//               children: [
//                 const Text(
//                   'Select File from Google Drive',
//                   style: TextStyle(
//                     color: Colors.white,
//                     fontSize: 18,
//                     fontWeight: FontWeight.bold,
//                   ),
//                 ),
//                 const SizedBox(height: 16),
//                 Expanded(
//                   child: _isFetchingDriveFiles
//                       ? const Center(child: CircularProgressIndicator())
//                       : _driveFiles.isEmpty
//                       ? const Center(
//                           child: Text(
//                             'No files found',
//                             style: TextStyle(color: Colors.white70),
//                           ),
//                         )
//                       : ListView.builder(
//                           itemCount: _driveFiles.length,
//                           itemBuilder: (context, index) {
//                             final file = _driveFiles[index];
//                             return ListTile(
//                               leading: Icon(
//                                 _getFileIcon(file['mimeType'] ?? ''),
//                                 color: Colors.white70,
//                               ),
//                               title: Text(
//                                 file['name'] ?? 'Unknown',
//                                 style: const TextStyle(color: Colors.white),
//                                 overflow: TextOverflow.ellipsis,
//                               ),
//                               subtitle: Text(
//                                 file['mimeType'] ?? '',
//                                 style: TextStyle(
//                                   color: Colors.white.withOpacity(0.5),
//                                   fontSize: 11,
//                                 ),
//                               ),
//                               onTap: () {
//                                 Navigator.pop(context);
//                                 _importFromGoogleDrive(
//                                   userId,
//                                   file['id'],
//                                   file['name'] ?? 'GoogleDrive_File',
//                                 );
//                               },
//                             );
//                           },
//                         ),
//                 ),
//                 const SizedBox(height: 12),
//                 Align(
//                   alignment: Alignment.centerRight,
//                   child: TextButton(
//                     onPressed: () => Navigator.pop(context),
//                     child: const Text('Cancel'),
//                   ),
//                 ),
//               ],
//             ),
//           ),
//         ),
//       );
//     } catch (e) {
//       _showError('Error fetching files: $e');
//     } finally {
//       setState(() => _isFetchingDriveFiles = false);
//     }
//   }

//   // Helper function to get file icon based on mime type
//   IconData _getFileIcon(String mimeType) {
//     if (mimeType.contains('pdf')) return Icons.picture_as_pdf;
//     if (mimeType.contains('document') || mimeType.contains('word'))
//       return Icons.description;
//     if (mimeType.contains('spreadsheet') || mimeType.contains('excel'))
//       return Icons.table_chart;
//     if (mimeType.contains('presentation')) return Icons.slideshow;
//     if (mimeType.contains('image')) return Icons.image;
//     return Icons.insert_drive_file;
//   }

//   // Download and import selected file from Google Drive
//   Future<void> _importFromGoogleDrive(
//     int userId,
//     String fileId,
//     String filename,
//   ) async {
//     if (_selectedTemplate == null) {
//       _showError('Please select a template first');
//       return;
//     }

//     try {
//       setState(() => _isProcessing = true);
//       final response = await http.post(
//         Uri.parse(
//           'http://localhost:8000/api/uploads/download-from-google-drive?user_id=$userId&file_id=$fileId&filename=$filename&template_id=${_selectedTemplate!['id']}',
//         ),
//       );

//       if (response.statusCode == 200) {
//         _showSuccess('File imported successfully!');
//         // Refresh documents list
//         final auth = context.read<AuthProvider>();
//         if (auth.userId != null) {
//           context.read<DocumentProvider>().fetchDocuments(auth.userId!);
//         }
//       } else {
//         final data = jsonDecode(response.body);
//         _showError(
//           'Failed to import file: ${data['detail'] ?? 'Unknown error'}',
//         );
//       }
//     } catch (e) {
//       _showError('Error: $e');
//     } finally {
//       setState(() => _isProcessing = false);
//     }
//   }

//   void _showError(String message) {
//     ScaffoldMessenger.of(context).showSnackBar(
//       SnackBar(content: Text(message), backgroundColor: Colors.red),
//     );
//   }

//   void _showSuccess(String message) {
//     ScaffoldMessenger.of(context).showSnackBar(
//       SnackBar(content: Text(message), backgroundColor: Colors.green),
//     );
//   }

//   @override
//   void dispose() {
//     _titleController.dispose();
//     _contentController.dispose();
//     super.dispose();
//   }

//   @override
//   Widget build(BuildContext context) {
//     return Scaffold(
//       backgroundColor: const Color(0xFF0D1117),
//       body: SingleChildScrollView(
//         padding: const EdgeInsets.all(32),
//         child: Column(
//           crossAxisAlignment: CrossAxisAlignment.start,
//           children: [
//             // Title
//             const Text(
//               'Create New Report',
//               style: TextStyle(
//                 fontSize: 28,
//                 fontWeight: FontWeight.w700,
//                 color: Colors.white,
//               ),
//             ),
//             const SizedBox(height: 8),
//             Text(
//               'Choose how you want to upload your content',
//               style: TextStyle(
//                 fontSize: 14,
//                 color: Colors.white.withOpacity(0.6),
//               ),
//             ),
//             const SizedBox(height: 32),
//             // Option Selection Buttons
//             Row(
//               children: [
//                 _buildOptionButton(
//                   index: 1,
//                   icon: Icons.upload_file,
//                   label: 'Upload File',
//                   color: const Color(0xFF3B82F6),
//                 ),
//                 const SizedBox(width: 16),
//                 _buildOptionButton(
//                   index: 2,
//                   icon: Icons.edit,
//                   label: 'Paste Content',
//                   color: const Color(0xFF8B5CF6),
//                 ),
//                 const SizedBox(width: 16),
//                 _buildOptionButton(
//                   index: 3,
//                   icon: Icons.cloud,
//                   label: 'Google Drive',
//                   color: const Color(0xFF10B981),
//                 ),
//                 const SizedBox(width: 16),
//                 _buildOptionButton(
//                   index: 4,
//                   icon: Icons.qr_code,
//                   label: 'Upload from Phone',
//                   color: const Color(0xFFF59E0B),
//                 ),
//               ],
//             ),
//             const SizedBox(height: 32),
//             // Content based on selected option
//             if (_selectedUploadOption == 1)
//               _buildFileUploadContent()
//             else if (_selectedUploadOption == 2)
//               _buildPasteContentUI()
//             else if (_selectedUploadOption == 3)
//               _buildGoogleDriveUI()
//             else if (_selectedUploadOption == 4)
//               _buildUploadFromPhoneUI(),
//           ],
//         ),
//       ),
//     );
//   }

//   Widget _buildUploadFromPhoneUI() {
//     final auth = context.watch<AuthProvider>();

//     return Row(
//       children: [
//         Expanded(
//           child: Container(
//             padding: const EdgeInsets.all(24),
//             decoration: BoxDecoration(
//               color: const Color(0xFF161B22),
//               borderRadius: BorderRadius.circular(12),
//               border: Border.all(color: Colors.white.withOpacity(0.1)),
//             ),
//             child: Column(
//               crossAxisAlignment: CrossAxisAlignment.start,
//               children: [
//                 Row(
//                   children: [
//                     Container(
//                       padding: const EdgeInsets.all(10),
//                       decoration: BoxDecoration(
//                         color: const Color(0xFFF59E0B).withOpacity(0.2),
//                         borderRadius: BorderRadius.circular(8),
//                       ),
//                       child: const Icon(
//                         Icons.qr_code,
//                         color: Color(0xFFF59E0B),
//                       ),
//                     ),
//                     const SizedBox(width: 12),
//                     const Text(
//                       'Upload from Phone',
//                       style: TextStyle(
//                         fontSize: 16,
//                         fontWeight: FontWeight.w600,
//                         color: Colors.white,
//                       ),
//                     ),
//                   ],
//                 ),
//                 const SizedBox(height: 24),
//                 Text(
//                   'Scan QR code using your phone to upload a document.',
//                   style: TextStyle(color: Colors.white.withOpacity(0.6)),
//                 ),
//                 const SizedBox(height: 24),
//                 SizedBox(
//                   width: double.infinity,
//                   height: 48,
//                   child: ElevatedButton.icon(
//                     icon: const Icon(Icons.qr_code),
//                     label: const Text('Generate QR Code'),
//                     onPressed:
//                         (_selectedTemplate != null && auth.userId != null)
//                         ? () => _handleUploadFromPhone(auth.userId!)
//                         : null,
//                     style: ElevatedButton.styleFrom(
//                       backgroundColor: const Color(0xFFF59E0B),
//                     ),
//                   ),
//                 ),
//                 if (_selectedTemplate == null)
//                   Padding(
//                     padding: const EdgeInsets.only(top: 8),
//                     child: Text(
//                       'Please select a template first',
//                       style: TextStyle(color: Colors.orange.withOpacity(0.8)),
//                     ),
//                   ),
//               ],
//             ),
//           ),
//         ),
//         const SizedBox(width: 24),
//         Expanded(child: _buildTemplateSelector()),
//       ],
//     );
//   }

//   Widget _buildOptionButton({
//     required int index,
//     required IconData icon,
//     required String label,
//     required Color color,
//   }) {
//     final isSelected = _selectedUploadOption == index;

//     return Expanded(
//       child: GestureDetector(
//         onTap: () => setState(() => _selectedUploadOption = index),
//         child: Container(
//           decoration: BoxDecoration(
//             color: isSelected
//                 ? color.withOpacity(0.2)
//                 : const Color(0xFF161B22),
//             borderRadius: BorderRadius.circular(12),
//             border: Border.all(
//               color: isSelected ? color : Colors.white.withOpacity(0.1),
//               width: isSelected ? 2 : 1,
//             ),
//           ),
//           padding: const EdgeInsets.all(20),
//           child: Column(
//             mainAxisAlignment: MainAxisAlignment.center,
//             children: [
//               Icon(icon, size: 32, color: color),
//               const SizedBox(height: 12),
//               Text(
//                 label,
//                 style: const TextStyle(
//                   fontSize: 14,
//                   fontWeight: FontWeight.w600,
//                   color: Colors.white,
//                 ),
//               ),
//             ],
//           ),
//         ),
//       ),
//     );
//   }

//   Future<void> _handleUploadFromPhone(int userId) async {
//     try {
//       final result = await QRUploadService.generateUploadQr(
//         userId,
//         _selectedTemplate!['id'],
//       );

//       final qrBase64 = result['qr_base64'];
//       final uploadUrl = result['upload_url'];

//       if (qrBase64 == null || uploadUrl == null) {
//         throw Exception('Invalid QR response from server');
//       }

//       showDialog(
//         context: context,
//         builder: (_) => Dialog(
//           backgroundColor: Colors.white,
//           child: Padding(
//             padding: const EdgeInsets.all(20),
//             child: Column(
//               mainAxisSize: MainAxisSize.min,
//               children: [
//                 const Text(
//                   'Scan to Upload from Phone',
//                   style: TextStyle(fontWeight: FontWeight.bold),
//                 ),
//                 const SizedBox(height: 16),
//                 Image.memory(base64Decode(qrBase64), width: 250, height: 250),
//                 const SizedBox(height: 12),
//                 SelectableText(uploadUrl, style: const TextStyle(fontSize: 12)),
//               ],
//             ),
//           ),
//         ),
//       );
//     } catch (e) {
//       _showError('Failed to generate QR: $e');
//     }
//   }

//   Widget _buildFileUploadContent() {
//     return Row(
//       crossAxisAlignment: CrossAxisAlignment.start,
//       children: [
//         // File Upload Section
//         Expanded(
//           child: Container(
//             decoration: BoxDecoration(
//               color: const Color(0xFF161B22),
//               borderRadius: BorderRadius.circular(12),
//               border: Border.all(color: Colors.white.withOpacity(0.1)),
//             ),
//             padding: const EdgeInsets.all(24),
//             child: Column(
//               crossAxisAlignment: CrossAxisAlignment.start,
//               children: [
//                 // Header
//                 Row(
//                   children: [
//                     Container(
//                       padding: const EdgeInsets.all(10),
//                       decoration: BoxDecoration(
//                         color: const Color(0xFF3B82F6).withOpacity(0.2),
//                         borderRadius: BorderRadius.circular(8),
//                       ),
//                       child: const Icon(
//                         Icons.upload_file,
//                         color: Color(0xFF3B82F6),
//                         size: 20,
//                       ),
//                     ),
//                     const SizedBox(width: 12),
//                     const Text(
//                       'Upload File',
//                       style: TextStyle(
//                         fontSize: 16,
//                         fontWeight: FontWeight.w600,
//                         color: Colors.white,
//                       ),
//                     ),
//                   ],
//                 ),
//                 const SizedBox(height: 24),
//                 // File Selection Area
//                 if (_selectedFile == null)
//                   GestureDetector(
//                     onTap: _selectFile,
//                     child: Container(
//                       decoration: BoxDecoration(
//                         color: const Color(0xFF0D1117),
//                         borderRadius: BorderRadius.circular(8),
//                         border: Border.all(
//                           color: Colors.white.withOpacity(0.2),
//                           strokeAlign: BorderSide.strokeAlignOutside,
//                         ),
//                       ),
//                       padding: const EdgeInsets.symmetric(
//                         vertical: 40,
//                         horizontal: 24,
//                       ),
//                       child: Column(
//                         mainAxisAlignment: MainAxisAlignment.center,
//                         children: [
//                           Icon(
//                             Icons.cloud_upload,
//                             size: 48,
//                             color: Colors.white.withOpacity(0.4),
//                           ),
//                           const SizedBox(height: 16),
//                           Text(
//                             'Click to upload or drag files',
//                             style: TextStyle(
//                               fontSize: 14,
//                               fontWeight: FontWeight.w500,
//                               color: Colors.white,
//                             ),
//                           ),
//                           const SizedBox(height: 6),
//                           Text(
//                             'Supported: DOC, DOCX, PDF, TXT',
//                             style: TextStyle(
//                               fontSize: 12,
//                               color: Colors.white.withOpacity(0.4),
//                             ),
//                           ),
//                         ],
//                       ),
//                     ),
//                   )
//                 else
//                   Container(
//                     decoration: BoxDecoration(
//                       color: const Color(0xFF0D1117),
//                       borderRadius: BorderRadius.circular(8),
//                       border: Border.all(
//                         color: const Color(0xFF10B981).withOpacity(0.5),
//                       ),
//                     ),
//                     padding: const EdgeInsets.all(16),
//                     child: Row(
//                       children: [
//                         const Icon(
//                           Icons.check_circle,
//                           color: Color(0xFF10B981),
//                           size: 24,
//                         ),
//                         const SizedBox(width: 12),
//                         Expanded(
//                           child: Column(
//                             crossAxisAlignment: CrossAxisAlignment.start,
//                             children: [
//                               Text(
//                                 'File selected',
//                                 style: TextStyle(
//                                   fontSize: 12,
//                                   color: Colors.white.withOpacity(0.6),
//                                 ),
//                               ),
//                               const SizedBox(height: 4),
//                               Text(
//                                 _selectedFile!.path.split('/').last,
//                                 style: const TextStyle(
//                                   fontSize: 14,
//                                   fontWeight: FontWeight.w600,
//                                   color: Colors.white,
//                                 ),
//                                 overflow: TextOverflow.ellipsis,
//                               ),
//                             ],
//                           ),
//                         ),
//                         GestureDetector(
//                           onTap: () => setState(() => _selectedFile = null),
//                           child: Icon(
//                             Icons.close,
//                             color: Colors.white.withOpacity(0.4),
//                           ),
//                         ),
//                       ],
//                     ),
//                   ),
//                 const SizedBox(height: 24),
//                 // Upload Button
//                 SizedBox(
//                   width: double.infinity,
//                   height: 48,
//                   child: ElevatedButton.icon(
//                     onPressed:
//                         (_selectedFile != null &&
//                             _selectedTemplate != null &&
//                             !_isProcessing)
//                         ? _uploadFile
//                         : null,
//                     icon: _isProcessing
//                         ? const SizedBox(
//                             height: 20,
//                             width: 20,
//                             child: CircularProgressIndicator(
//                               strokeWidth: 2,
//                               valueColor: AlwaysStoppedAnimation<Color>(
//                                 Colors.white,
//                               ),
//                             ),
//                           )
//                         : const Icon(Icons.upload),
//                     label: Text(
//                       _isProcessing ? 'Processing...' : 'Upload & Process',
//                     ),
//                     style: ElevatedButton.styleFrom(
//                       backgroundColor: const Color(0xFF3B82F6),
//                       foregroundColor: Colors.white,
//                       shape: RoundedRectangleBorder(
//                         borderRadius: BorderRadius.circular(8),
//                       ),
//                     ),
//                   ),
//                 ),
//               ],
//             ),
//           ),
//         ),
//         const SizedBox(width: 24),
//         // Template Selection Section
//         Expanded(child: _buildTemplateSelector()),
//       ],
//     );
//   }

//   Widget _buildPasteContentUI() {
//     return Row(
//       crossAxisAlignment: CrossAxisAlignment.start,
//       children: [
//         // Content Input Section
//         Expanded(
//           flex: 2,
//           child: Container(
//             decoration: BoxDecoration(
//               color: const Color(0xFF161B22),
//               borderRadius: BorderRadius.circular(12),
//               border: Border.all(color: Colors.white.withOpacity(0.1)),
//             ),
//             padding: const EdgeInsets.all(24),
//             child: Column(
//               crossAxisAlignment: CrossAxisAlignment.start,
//               children: [
//                 // Header
//                 Row(
//                   children: [
//                     Container(
//                       padding: const EdgeInsets.all(10),
//                       decoration: BoxDecoration(
//                         color: const Color(0xFF8B5CF6).withOpacity(0.2),
//                         borderRadius: BorderRadius.circular(8),
//                       ),
//                       child: const Icon(
//                         Icons.edit,
//                         color: Color(0xFF8B5CF6),
//                         size: 20,
//                       ),
//                     ),
//                     const SizedBox(width: 12),
//                     const Text(
//                       'Paste Content',
//                       style: TextStyle(
//                         fontSize: 16,
//                         fontWeight: FontWeight.w600,
//                         color: Colors.white,
//                       ),
//                     ),
//                   ],
//                 ),
//                 const SizedBox(height: 24),
//                 // Title Field
//                 TextField(
//                   controller: _titleController,
//                   style: const TextStyle(color: Colors.white),
//                   decoration: InputDecoration(
//                     labelText: 'Document Title',
//                     labelStyle: TextStyle(color: Colors.white.withOpacity(0.6)),
//                     filled: true,
//                     fillColor: const Color(0xFF0D1117),
//                     border: OutlineInputBorder(
//                       borderRadius: BorderRadius.circular(8),
//                       borderSide: BorderSide(
//                         color: Colors.white.withOpacity(0.1),
//                       ),
//                     ),
//                     enabledBorder: OutlineInputBorder(
//                       borderRadius: BorderRadius.circular(8),
//                       borderSide: BorderSide(
//                         color: Colors.white.withOpacity(0.1),
//                       ),
//                     ),
//                     focusedBorder: OutlineInputBorder(
//                       borderRadius: BorderRadius.circular(8),
//                       borderSide: const BorderSide(color: Color(0xFF8B5CF6)),
//                     ),
//                   ),
//                 ),
//                 const SizedBox(height: 16),
//                 // Content Field
//                 TextField(
//                   controller: _contentController,
//                   style: const TextStyle(color: Colors.white),
//                   maxLines: 10,
//                   decoration: InputDecoration(
//                     labelText: 'Paste your content here...',
//                     alignLabelWithHint: true,
//                     labelStyle: TextStyle(color: Colors.white.withOpacity(0.6)),
//                     filled: true,
//                     fillColor: const Color(0xFF0D1117),
//                     border: OutlineInputBorder(
//                       borderRadius: BorderRadius.circular(8),
//                       borderSide: BorderSide(
//                         color: Colors.white.withOpacity(0.1),
//                       ),
//                     ),
//                     enabledBorder: OutlineInputBorder(
//                       borderRadius: BorderRadius.circular(8),
//                       borderSide: BorderSide(
//                         color: Colors.white.withOpacity(0.1),
//                       ),
//                     ),
//                     focusedBorder: OutlineInputBorder(
//                       borderRadius: BorderRadius.circular(8),
//                       borderSide: const BorderSide(color: Color(0xFF8B5CF6)),
//                     ),
//                   ),
//                 ),
//                 const SizedBox(height: 24),
//                 // Create Button
//                 SizedBox(
//                   width: double.infinity,
//                   height: 48,
//                   child: ElevatedButton.icon(
//                     onPressed:
//                         (_titleController.text.isNotEmpty &&
//                             _contentController.text.isNotEmpty &&
//                             _selectedTemplate != null &&
//                             !_isProcessing)
//                         ? _createReport
//                         : null,
//                     icon: _isProcessing
//                         ? const SizedBox(
//                             height: 20,
//                             width: 20,
//                             child: CircularProgressIndicator(
//                               strokeWidth: 2,
//                               valueColor: AlwaysStoppedAnimation<Color>(
//                                 Colors.white,
//                               ),
//                             ),
//                           )
//                         : const Icon(Icons.auto_fix_high),
//                     label: Text(
//                       _isProcessing ? 'Processing...' : 'Create Report',
//                     ),
//                     style: ElevatedButton.styleFrom(
//                       backgroundColor: const Color(0xFF8B5CF6),
//                       foregroundColor: Colors.white,
//                       shape: RoundedRectangleBorder(
//                         borderRadius: BorderRadius.circular(8),
//                       ),
//                     ),
//                   ),
//                 ),
//               ],
//             ),
//           ),
//         ),
//         const SizedBox(width: 24),
//         // Template Selection Section
//         Expanded(child: _buildTemplateSelector()),
//       ],
//     );
//   }

//   Widget _buildGoogleDriveUI() {
//     final auth = context.watch<AuthProvider>();
//     final userId = auth.userId;

//     return Row(
//       crossAxisAlignment: CrossAxisAlignment.start,
//       children: [
//         // Google Drive Section
//         Expanded(
//           child: Container(
//             decoration: BoxDecoration(
//               color: const Color(0xFF161B22),
//               borderRadius: BorderRadius.circular(12),
//               border: Border.all(color: Colors.white.withOpacity(0.1)),
//             ),
//             padding: const EdgeInsets.all(24),
//             child: Column(
//               crossAxisAlignment: CrossAxisAlignment.start,
//               children: [
//                 // Header
//                 Row(
//                   children: [
//                     Container(
//                       padding: const EdgeInsets.all(10),
//                       decoration: BoxDecoration(
//                         color: const Color(0xFF10B981).withOpacity(0.2),
//                         borderRadius: BorderRadius.circular(8),
//                       ),
//                       child: const Icon(
//                         Icons.cloud,
//                         color: Color(0xFF10B981),
//                         size: 20,
//                       ),
//                     ),
//                     const SizedBox(width: 12),
//                     const Text(
//                       'Google Drive',
//                       style: TextStyle(
//                         fontSize: 16,
//                         fontWeight: FontWeight.w600,
//                         color: Colors.white,
//                       ),
//                     ),
//                   ],
//                 ),
//                 const SizedBox(height: 24),
//                 // Connection Status
//                 Container(
//                   decoration: BoxDecoration(
//                     color: const Color(0xFF0D1117),
//                     borderRadius: BorderRadius.circular(8),
//                     border: Border.all(
//                       color: _isGoogleDriveConnected
//                           ? const Color(0xFF10B981).withOpacity(0.5)
//                           : Colors.white.withOpacity(0.1),
//                     ),
//                   ),
//                   padding: const EdgeInsets.all(16),
//                   child: Column(
//                     children: [
//                       Icon(
//                         _isGoogleDriveConnected
//                             ? Icons.check_circle
//                             : Icons.cloud_off,
//                         size: 48,
//                         color: _isGoogleDriveConnected
//                             ? const Color(0xFF10B981)
//                             : Colors.white.withOpacity(0.4),
//                       ),
//                       const SizedBox(height: 12),
//                       Text(
//                         _isGoogleDriveConnected
//                             ? 'Connected to Google Drive'
//                             : 'Not connected',
//                         style: TextStyle(
//                           fontSize: 14,
//                           fontWeight: FontWeight.w500,
//                           color: _isGoogleDriveConnected
//                               ? const Color(0xFF10B981)
//                               : Colors.white.withOpacity(0.6),
//                         ),
//                       ),
//                     ],
//                   ),
//                 ),
//                 const SizedBox(height: 16),
//                 // Connect Button
//                 if (!_isGoogleDriveConnected)
//                   SizedBox(
//                     width: double.infinity,
//                     height: 48,
//                     child: ElevatedButton.icon(
//                       onPressed: _showGoogleDriveOptions,
//                       icon: const Icon(Icons.link),
//                       label: const Text('Connect Google Drive'),
//                       style: ElevatedButton.styleFrom(
//                         backgroundColor: const Color(0xFF10B981),
//                         foregroundColor: Colors.white,
//                         shape: RoundedRectangleBorder(
//                           borderRadius: BorderRadius.circular(8),
//                         ),
//                       ),
//                     ),
//                   )
//                 else
//                   SizedBox(
//                     width: double.infinity,
//                     height: 48,
//                     child: ElevatedButton.icon(
//                       onPressed:
//                           (_selectedTemplate != null &&
//                               userId != null &&
//                               !_isFetchingDriveFiles)
//                           ? () => _fetchGoogleDriveFiles(userId)
//                           : null,
//                       icon: _isFetchingDriveFiles
//                           ? const SizedBox(
//                               height: 20,
//                               width: 20,
//                               child: CircularProgressIndicator(
//                                 strokeWidth: 2,
//                                 valueColor: AlwaysStoppedAnimation<Color>(
//                                   Colors.white,
//                                 ),
//                               ),
//                             )
//                           : const Icon(Icons.folder_open),
//                       label: Text(
//                         _isFetchingDriveFiles
//                             ? 'Loading...'
//                             : 'Upload Document from Drive',
//                       ),
//                       style: ElevatedButton.styleFrom(
//                         backgroundColor: const Color(0xFF10B981),
//                         foregroundColor: Colors.white,
//                         shape: RoundedRectangleBorder(
//                           borderRadius: BorderRadius.circular(8),
//                         ),
//                       ),
//                     ),
//                   ),
//                 if (_selectedTemplate == null && _isGoogleDriveConnected)
//                   Padding(
//                     padding: const EdgeInsets.only(top: 8),
//                     child: Text(
//                       'Please select a template first',
//                       style: TextStyle(
//                         fontSize: 12,
//                         color: Colors.orange.withOpacity(0.8),
//                       ),
//                     ),
//                   ),
//               ],
//             ),
//           ),
//         ),
//         const SizedBox(width: 24),
//         // Template Selection Section
//         Expanded(child: _buildTemplateSelector()),
//       ],
//     );
//   }

//   Widget _buildTemplateSelector() {
//     return Container(
//       decoration: BoxDecoration(
//         color: const Color(0xFF161B22),
//         borderRadius: BorderRadius.circular(12),
//         border: Border.all(color: Colors.white.withOpacity(0.1)),
//       ),
//       padding: const EdgeInsets.all(24),
//       child: Column(
//         crossAxisAlignment: CrossAxisAlignment.start,
//         children: [
//           // Header
//           Row(
//             children: [
//               Container(
//                 padding: const EdgeInsets.all(10),
//                 decoration: BoxDecoration(
//                   color: const Color(0xFFF59E0B).withOpacity(0.2),
//                   borderRadius: BorderRadius.circular(8),
//                 ),
//                 child: const Icon(
//                   Icons.description,
//                   color: Color(0xFFF59E0B),
//                   size: 20,
//                 ),
//               ),
//               const SizedBox(width: 12),
//               const Text(
//                 'Select Template',
//                 style: TextStyle(
//                   fontSize: 16,
//                   fontWeight: FontWeight.w600,
//                   color: Colors.white,
//                 ),
//               ),
//             ],
//           ),
//           const SizedBox(height: 24),
//           // Template List
//           Consumer<TemplateProvider>(
//             builder: (context, templateProvider, child) {
//               if (templateProvider.isLoading) {
//                 return const Center(
//                   child: Padding(
//                     padding: EdgeInsets.all(32),
//                     child: CircularProgressIndicator(),
//                   ),
//                 );
//               }

//               final templates = templateProvider.templates;

//               if (templates.isEmpty) {
//                 return Container(
//                   padding: const EdgeInsets.all(24),
//                   decoration: BoxDecoration(
//                     color: const Color(0xFF0D1117),
//                     borderRadius: BorderRadius.circular(8),
//                   ),
//                   child: Column(
//                     children: [
//                       Icon(
//                         Icons.folder_off,
//                         size: 32,
//                         color: Colors.white.withOpacity(0.4),
//                       ),
//                       const SizedBox(height: 12),
//                       Text(
//                         'No templates available',
//                         style: TextStyle(color: Colors.white.withOpacity(0.6)),
//                       ),
//                     ],
//                   ),
//                 );
//               }

//               return ListView.separated(
//                 shrinkWrap: true,
//                 physics: const NeverScrollableScrollPhysics(),
//                 itemCount: templates.length,
//                 separatorBuilder: (_, __) => const SizedBox(height: 8),
//                 itemBuilder: (context, index) {
//                   final template = templates[index];
//                   final isSelected = _selectedTemplate?['id'] == template['id'];

//                   return GestureDetector(
//                     onTap: () => setState(() => _selectedTemplate = template),
//                     child: Container(
//                       decoration: BoxDecoration(
//                         color: isSelected
//                             ? const Color(0xFFF59E0B).withOpacity(0.2)
//                             : const Color(0xFF0D1117),
//                         borderRadius: BorderRadius.circular(8),
//                         border: Border.all(
//                           color: isSelected
//                               ? const Color(0xFFF59E0B)
//                               : Colors.white.withOpacity(0.1),
//                         ),
//                       ),
//                       padding: const EdgeInsets.all(12),
//                       child: Row(
//                         children: [
//                           Icon(
//                             isSelected
//                                 ? Icons.radio_button_checked
//                                 : Icons.radio_button_off,
//                             color: isSelected
//                                 ? const Color(0xFFF59E0B)
//                                 : Colors.white.withOpacity(0.4),
//                             size: 20,
//                           ),
//                           const SizedBox(width: 12),
//                           Expanded(
//                             child: Column(
//                               crossAxisAlignment: CrossAxisAlignment.start,
//                               children: [
//                                 Text(
//                                   template['name'] ?? 'Unnamed Template',
//                                   style: const TextStyle(
//                                     fontSize: 14,
//                                     fontWeight: FontWeight.w500,
//                                     color: Colors.white,
//                                   ),
//                                 ),
//                                 if (template['description'] != null)
//                                   Text(
//                                     template['description'],
//                                     style: TextStyle(
//                                       fontSize: 12,
//                                       color: Colors.white.withOpacity(0.5),
//                                     ),
//                                     maxLines: 1,
//                                     overflow: TextOverflow.ellipsis,
//                                   ),
//                               ],
//                             ),
//                           ),
//                         ],
//                       ),
//                     ),
//                   );
//                 },
//               );
//             },
//           ),
//         ],
//       ),
//     );
//   }
// }




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
import '../providers/template_provider.dart';
import '../config/api_config.dart';
import 'analyze_screen.dart';
import 'package:url_launcher/url_launcher.dart';

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
    _loadTemplatesAndDocuments();
    if (widget.selectedTemplate != null) {
      _selectedTemplate = widget.selectedTemplate;
    }
  }

  void _loadTemplatesAndDocuments() {
    Future.microtask(() {
      final auth = context.read<AuthProvider>();
      if (auth.userId != null) {
        context.read<TemplateProvider>().fetchUserTemplates(auth.userId!);
        context.read<DocumentProvider>().fetchDocuments(auth.userId!);
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

      // Create report and get document ID
      final response = await _createReportAndGetId(
        _titleController.text,
        _contentController.text,
        capturedTemplateId,
        auth.userId!,
      );

      if (response != null) {
        _showSuccess('Report created successfully!');

        // Clear fields AFTER capturing template values
        _titleController.clear();
        _contentController.clear();
        setState(() => _selectedTemplate = null);

        // Navigate using the captured (non-null) values
        if (mounted) {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => AnalyzeScreen(
                documentId: response['document_id'],
                documentName: response['filename'],
                templateId: capturedTemplateId,
                templateName: capturedTemplateName,
              ),
            ),
          );
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
      final response = await http.post(
        Uri.parse(
          '${ApiConfig.getBaseUrl()}/documents/create-report?user_id=$userId&template_id=$templateId',
        ),
        headers: {'Content-Type': 'application/json'},
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
          'filename': data['filename'],
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
        setState(() => _selectedFile = null);

        // Navigate to analyze screen
        if (mounted) {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => AnalyzeScreen(
                documentId: response['document_id'],
                documentName: response['filename'],
                templateId: _selectedTemplate!['id'],
                templateName: _selectedTemplate!['name'] ?? 'Unknown Template',
              ),
            ),
          );
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

  bool _isFetchingDriveFiles = false;
  List<Map<String, dynamic>> _driveFiles = [];

  void _showGoogleDriveOptions() async {
    final auth = context.read<AuthProvider>();
    String email = '';

    await showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF161B22),
        title: const Text(
          'Connect Google Drive',
          style: TextStyle(color: Colors.white),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Enter your Google email to authorize access:',
              style: TextStyle(
                fontSize: 13,
                color: Colors.white.withOpacity(0.8),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: 'example@gmail.com',
                hintStyle: TextStyle(color: Colors.white.withOpacity(0.4)),
                filled: true,
                fillColor: const Color(0xFF0D1117),
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
            child: const Text(
              'Cancel',
              style: TextStyle(color: Colors.white70),
            ),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(context);
              await _connectGoogleDrive();
            },
            child: const Text('Connect via OAuth'),
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
          'http://localhost:8000/api/uploads/google-drive/files?user_id=$userId',
        ),
      );

      if (response.statusCode != 200) {
        final errorData = jsonDecode(response.body);
        _showError(
          'Failed to fetch files: ${errorData['detail'] ?? 'Unknown error'}',
        );
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
          backgroundColor: const Color(0xFF161B22),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          child: Container(
            width: 450,
            height: 400,
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Select File from Google Drive',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 16),
                Expanded(
                  child: _isFetchingDriveFiles
                      ? const Center(child: CircularProgressIndicator())
                      : _driveFiles.isEmpty
                      ? const Center(
                          child: Text(
                            'No files found',
                            style: TextStyle(color: Colors.white70),
                          ),
                        )
                      : ListView.builder(
                          itemCount: _driveFiles.length,
                          itemBuilder: (context, index) {
                            final file = _driveFiles[index];
                            return ListTile(
                              leading: Icon(
                                _getFileIcon(file['mimeType'] ?? ''),
                                color: Colors.white70,
                              ),
                              title: Text(
                                file['name'] ?? 'Unknown',
                                style: const TextStyle(color: Colors.white),
                                overflow: TextOverflow.ellipsis,
                              ),
                              subtitle: Text(
                                file['mimeType'] ?? '',
                                style: TextStyle(
                                  color: Colors.white.withOpacity(0.5),
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
                    child: const Text('Cancel'),
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
      setState(() => _isFetchingDriveFiles = false);
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
      final response = await http.post(
        Uri.parse(
          'http://localhost:8000/api/uploads/download-from-google-drive?user_id=$userId&file_id=$fileId&filename=$filename&template_id=${_selectedTemplate!['id']}',
        ),
      );

      if (response.statusCode == 200) {
        _showSuccess('File imported successfully!');
        final auth = context.read<AuthProvider>();
        if (auth.userId != null) {
          context.read<DocumentProvider>().fetchDocuments(auth.userId!);
        }
      } else {
        final data = jsonDecode(response.body);
        _showError(
          'Failed to import file: ${data['detail'] ?? 'Unknown error'}',
        );
      }
    } catch (e) {
      _showError('Error: $e');
    } finally {
      setState(() => _isProcessing = false);
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
    _titleController.dispose();
    _contentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final body = SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            
           
            const SizedBox(height: 32),
            Row(
              children: [
                _buildOptionButton(
                  index: 1,
                  icon: Icons.upload_file,
                  label: 'Upload File',
                  color: const Color(0xFF3B82F6),
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
        color: const Color(0xFF0D1117),
        child: body,
      );
    }

    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      body: body,
    );
  }

  Widget _buildUploadFromPhoneUI() {
    final auth = context.watch<AuthProvider>();

    return Row(
      children: [
        Expanded(
          child: Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: const Color(0xFF161B22),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.white.withOpacity(0.1)),
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
                    const Text(
                      'Upload from Phone',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                Text(
                  'Scan QR code using your phone to upload a document.',
                  style: TextStyle(color: Colors.white.withOpacity(0.6)),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  height: 48,
                  child: ElevatedButton.icon(
                    icon: const Icon(Icons.qr_code),
                    label: const Text('Generate QR Code'),
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
                    child: Text(
                      'Please select a template first',
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
                : const Color(0xFF161B22),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isSelected ? color : Colors.white.withOpacity(0.1),
              width: isSelected ? 2 : 1,
            ),
          ),
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 32, color: color),
              const SizedBox(height: 12),
              Text(
                label,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
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
              const Text(
                'Scan to Upload from Phone',
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
              color: const Color(0xFF161B22),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.white.withOpacity(0.1)),
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
                        color: const Color(0xFF3B82F6).withOpacity(0.2),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(
                        Icons.upload_file,
                        color: Color(0xFF3B82F6),
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 12),
                    const Text(
                      'Upload File',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
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
                        color: const Color(0xFF0D1117),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: Colors.white.withOpacity(0.2),
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
                            color: Colors.white.withOpacity(0.4),
                          ),
                          const SizedBox(height: 16),
                          Text(
                            'Click to upload or drag files',
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w500,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            'Supported: DOC, DOCX, PDF, TXT',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.white.withOpacity(0.4),
                            ),
                          ),
                        ],
                      ),
                    ),
                  )
                else
                  Container(
                    decoration: BoxDecoration(
                      color: const Color(0xFF0D1117),
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
                              Text(
                                'File selected',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.white.withOpacity(0.6),
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                _selectedFile!.path.split('/').last,
                                style: const TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600,
                                  color: Colors.white,
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
                            color: Colors.white.withOpacity(0.4),
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
                      backgroundColor: const Color(0xFF3B82F6),
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
              color: const Color(0xFF161B22),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.white.withOpacity(0.1)),
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
                    const Text(
                      'Paste Content',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                // Title Field
                TextField(
                  controller: _titleController,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    labelText: 'Document Title',
                    labelStyle: TextStyle(color: Colors.white.withOpacity(0.6)),
                    filled: true,
                    fillColor: const Color(0xFF0D1117),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide(
                        color: Colors.white.withOpacity(0.1),
                      ),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide(
                        color: Colors.white.withOpacity(0.1),
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
                  style: const TextStyle(color: Colors.white),
                  maxLines: 10,
                  decoration: InputDecoration(
                    labelText: 'Paste your content here...',
                    alignLabelWithHint: true,
                    labelStyle: TextStyle(color: Colors.white.withOpacity(0.6)),
                    filled: true,
                    fillColor: const Color(0xFF0D1117),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide(
                        color: Colors.white.withOpacity(0.1),
                      ),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide(
                        color: Colors.white.withOpacity(0.1),
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
                    child: Text(
                      'Select a template on the right to enable this button',
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
              color: const Color(0xFF161B22),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.white.withOpacity(0.1)),
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
                    const Text(
                      'Google Drive',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                Container(
                  decoration: BoxDecoration(
                    color: const Color(0xFF0D1117),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: _isGoogleDriveConnected
                          ? const Color(0xFF10B981).withOpacity(0.5)
                          : Colors.white.withOpacity(0.1),
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
                            : Colors.white.withOpacity(0.4),
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
                              : Colors.white.withOpacity(0.6),
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
                      label: const Text('Connect Google Drive'),
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
                    child: Text(
                      'Please select a template first',
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
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.1)),
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
              const Text(
                'Select Template',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
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
                    color: const Color(0xFF0D1117),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Column(
                    children: [
                      Icon(
                        Icons.folder_off,
                        size: 32,
                        color: Colors.white.withOpacity(0.4),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        'No templates available',
                        style: TextStyle(color: Colors.white.withOpacity(0.6)),
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
                            : const Color(0xFF0D1117),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: isSelected
                              ? const Color(0xFFF59E0B)
                              : Colors.white.withOpacity(0.1),
                        ),
                      ),
                      padding: const EdgeInsets.all(12),
                      child: Row(
                        children: [
                          Icon(
                            isSelected
                                ? Icons.radio_button_checked
                                : Icons.radio_button_off,
                            color: isSelected
                                ? const Color(0xFFF59E0B)
                                : Colors.white.withOpacity(0.4),
                            size: 20,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  template['name'] ?? 'Unnamed Template',
                                  style: const TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w500,
                                    color: Colors.white,
                                  ),
                                ),
                                if (template['description'] != null)
                                  Text(
                                    template['description'],
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.white.withOpacity(0.5),
                                    ),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                              ],
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
        ],
      ),
    );
  }
}