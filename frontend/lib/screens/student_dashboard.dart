import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:frontend/providers/qr_service.dart';
import 'package:frontend/widgets/qr_dialog.dart';
import 'package:provider/provider.dart';
import 'dart:io';
import 'package:file_picker/file_picker.dart';
import '../providers/auth_provider.dart';
import '../providers/document_provider.dart';
import '../providers/template_provider.dart';
import 'new_report_screen.dart';
import '../widgets/export_dialog.dart';

class StudentDashboard extends StatefulWidget {
  const StudentDashboard({Key? key}) : super(key: key);

  @override
  State<StudentDashboard> createState() => _StudentDashboardState();
}

class _StudentDashboardState extends State<StudentDashboard> {
  int _selectedIndex = 0;
  Map<String, dynamic>? _selectedTemplate;
  String _searchQuery = '';
  String _selectedFilter = 'all';
  String _sortBy = 'recent';
  int _currentPage = 1;
  int _itemsPerPage = 9;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _loadInitialData();
  }

  void _loadInitialData() {
    Future.microtask(() {
      final auth = context.read<AuthProvider>();
      if (auth.userId != null) {
        context.read<TemplateProvider>().fetchUserTemplates(auth.userId!);
        context.read<DocumentProvider>().fetchDocuments(auth.userId!);
        //Start auto-refresh polling every 30 seconds
        _refreshTimer = Timer.periodic(const Duration(seconds: 10), (_) {
          final a = context.read<AuthProvider>();
          if (a.userId != null) {
            context.read<DocumentProvider>().fetchDocuments(a.userId!);
          }
        });
      }
    });
  }

  @override
  void dispose() {
   _refreshTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      body: Row(
        children: [
          _buildSidebar(),
          Expanded(
            child: Column(
              children: [
                _buildTopBar(),
                Expanded(child: _buildBody()),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSidebar() {
    return Container(
      width: 200,
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        border: Border(
          right: BorderSide(
            color: Colors.white.withOpacity(0.1),
          ),
        ),
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF3B82F6),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: const Icon(
                    Icons.description,
                    color: Colors.white,
                    size: 20,
                  ),
                ),
                const SizedBox(width: 12),
                const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'FORMATIFY',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
                    ),
                    Text(
                      'Academic Edition',
                      style: TextStyle(
                        fontSize: 10,
                        color: Colors.white,
                        fontWeight: FontWeight.w400,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(vertical: 8),
              children: [
                _buildSidebarItem(
                  0,
                  Icons.dashboard,
                  'Dashboard',
                ),
                _buildSidebarItem(
                  1,
                  Icons.add_circle_outline,
                  'New Report',
                ),
                _buildSidebarItem(
                  2,
                  Icons.folder,
                  'My Reports',
                ),
                _buildSidebarItem(
                  3,
                  Icons.auto_awesome,
                  'AI Tools',
                ),
                _buildSidebarItem(
                  4,
                  Icons.layers,
                  'Templates',
                ),
                _buildSidebarItem(
                  5,
                  Icons.settings,
                  'Settings',
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Container(
              decoration: BoxDecoration(
                color: const Color(0xFF0D1117),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: Colors.white.withOpacity(0.1),
                ),
              ),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Consumer<AuthProvider>(
                  builder: (context, auth, _) {
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 32,
                          height: 32,
                          decoration: BoxDecoration(
                            color: const Color(0xFF3B82F6),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Center(
                            child: Text(
                              (auth.currentUser?.isNotEmpty ?? false)
                                  ? auth.currentUser![0].toUpperCase()
                                  : 'U',
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 12),
                        Text(
                          auth.currentUser ?? 'User',
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                        ),
                        Text(
                          'Student',
                          style: TextStyle(
                            fontSize: 11,
                            color: Colors.white.withOpacity(0.6),
                            fontWeight: FontWeight.w400,
                          ),
                        ),
                        const SizedBox(height: 12),
                        SizedBox(
                          width: double.infinity,
                          height: 32,
                          child: ElevatedButton.icon(
                            onPressed: () => _logout(context),
                            icon: const Icon(Icons.logout, size: 14),
                            label: const Text(
                              'Logout',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF3B82F6),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(6),
                              ),
                            ),
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSidebarItem(int index, IconData icon, String label) {
    final isSelected = _selectedIndex == index;
    return Container(
      color: isSelected ? const Color(0xFF3B82F6).withOpacity(0.15) : Colors.transparent,
      child: InkWell(
        onTap: () {
          setState(() => _selectedIndex = index);
        },
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Icon(
                icon,
                size: 20,
                color: isSelected
                    ? const Color(0xFF3B82F6)
                    : Colors.white.withOpacity(0.6),
              ),
              const SizedBox(width: 12),
              Text(
                label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                  color: isSelected
                      ? const Color(0xFF3B82F6)
                      : Colors.white.withOpacity(0.7),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTopBar() {
    final titles = ['Dashboard', 'New Report', 'My Reports', 'AI Tools', 'Templates', 'Settings'];
    final descriptions = [
      'Here\'s your report overview.',
      'Choose a template and start formatting your report. Upload from local files, Google Drive, or paste content directly.',
      'Manage and view all your uploaded reports',
      'Powerful AI-powered tools to enhance your reports',
      'Choose from pre-built academic report templates',
      'Manage your account settings and preferences',
    ];

    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        border: Border(
          bottom: BorderSide(
            color: Colors.white.withOpacity(0.1),
          ),
        ),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 20),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                titles[_selectedIndex],
                style: const TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                ),
              ),
              Consumer<AuthProvider>(
                builder: (context, auth, _) {
                  return Text(
                    _selectedIndex == 0 ? 'Welcome back, ${auth.currentUser ?? "User"}. ${descriptions[_selectedIndex]}' : descriptions[_selectedIndex],
                    style: TextStyle(
                      fontSize: 13,
                      color: Colors.white.withOpacity(0.6),
                      fontWeight: FontWeight.w400,
                    ),
                  );
                },
              ),
            ],
          ),
          Row(
            children: [
              Container(
                decoration: BoxDecoration(
                  color: const Color(0xFF0D1117),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(
                    color: Colors.white.withOpacity(0.1),
                  ),
                ),
                child: IconButton(
                  icon: const Icon(Icons.notifications_outlined),
                  onPressed: () {},
                  color: Colors.white.withOpacity(0.6),
                  tooltip: 'Notifications',
                ),
              ),
              const SizedBox(width: 12),
              GestureDetector(
                onTap: () {
                  setState(() => _selectedIndex = 1);
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF3B82F6),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.add, size: 18, color: Colors.white),
                      const SizedBox(width: 6),
                      const Text(
                        'New Report',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildBody() {
    switch (_selectedIndex) {
      case 0:
        return _buildDashboardContent();
      case 1:
        return _buildNewReportPage();
      case 2:
        return _buildMyReportsPage();
      case 3:
        return _buildAIToolsPage();
      case 4:
        return _buildTemplatesPage();
      case 5:
        return _buildSettingsPage();
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _buildDashboardContent() {
    return Consumer<DocumentProvider>(
      builder: (context, docProvider, _) {
        final totalReports = docProvider.documents.length;
        final completedCount = docProvider.documents.where((d) => d['status'] == 'formatted').length;
        final draftCount = docProvider.documents.where((d) => d['status'] == 'uploaded' || d['status'] == 'processing').length;

        return SingleChildScrollView(
          padding: const EdgeInsets.all(32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: _buildStatCard(
                      title: 'Total Reports',
                      value: totalReports.toString(),
                      change: '+12%',
                      icon: Icons.description,
                      changeColor: const Color(0xFF10B981),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: _buildStatCard(
                      title: 'Active Drafts',
                      value: draftCount.toString(),
                      change: 'In Progress',
                      icon: Icons.history,
                      changeColor: const Color(0xFFD97706),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: _buildStatCard(
                      title: 'Completed',
                      value: completedCount.toString(),
                      change: '+8%',
                      icon: Icons.check_circle,
                      changeColor: const Color(0xFF10B981),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: _buildStatCard(
                      title: 'AI Suggestions Used',
                      value: (totalReports * 5).toString(),
                      change: 'AI',
                      icon: Icons.auto_awesome,
                      changeColor: const Color(0xFF8B5CF6),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 32),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    flex: 2,
                    child: _buildRecentReportsSection(docProvider.documents),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: _buildAIToolsSection(),
                  ),
                ],
              ),
              const SizedBox(height: 32),
              _buildQuickActionsSection(),
            ],
          ),
        );
      },
    );
  }

  Widget _buildStatCard({
    required String title,
    required String value,
    required String change,
    required IconData icon,
    required Color changeColor,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Colors.white.withOpacity(0.1),
        ),
      ),
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: changeColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  icon,
                  color: changeColor,
                  size: 20,
                ),
              ),
              Text(
                change,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: changeColor,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            value,
            style: const TextStyle(
              fontSize: 32,
              fontWeight: FontWeight.w700,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            title,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w400,
              color: Colors.white.withOpacity(0.6),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecentReportsSection(List<Map<String, dynamic>> documents) {
    final recentDocs = documents.take(4).toList();

    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Colors.white.withOpacity(0.1),
        ),
      ),
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Recent Reports',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                ),
              ),
              GestureDetector(
                onTap: () {
                  setState(() => _selectedIndex = 2);
                },
                child: Text(
                  'View All',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: const Color(0xFF3B82F6),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (recentDocs.isEmpty)
            Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 24),
                child: Text(
                  'No reports yet',
                  style: TextStyle(
                    fontSize: 13,
                    color: Colors.white.withOpacity(0.5),
                  ),
                ),
              ),
            )
          else
            ...recentDocs.asMap().entries.map((entry) {
              final doc = entry.value;
              final isLast = entry.key == recentDocs.length - 1;
              final status = doc['status'] ?? 'uploaded';
              final statusLabel = status == 'formatted' ? 'Complete' : status == 'processing' ? 'Processing' : 'Draft';
              final statusColor = status == 'formatted' ? const Color(0xFF10B981) : status == 'processing' ? const Color(0xFFD97706) : const Color(0xFF3B82F6);
              
              return Column(
                children: [
                  _buildReportItem(
                    doc['filename'] ?? 'Untitled Report',
                    'Last edited ${_getTimeAgo(doc['created_at'] ?? DateTime.now())}',
                    statusLabel,
                    statusColor,
                    Icons.description,
                    statusColor,
                  ),
                  if (!isLast) const SizedBox(height: 12),
                ],
              );
            }).toList(),
        ],
      ),
    );
  }

  Widget _buildReportItem(
    String title,
    String subtitle,
    String status,
    Color statusColor,
    IconData icon,
    Color iconColor,
  ) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: iconColor.withOpacity(0.15),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, color: iconColor, size: 18),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                ),
              ),
              Text(
                subtitle,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w400,
                  color: Colors.white.withOpacity(0.5),
                ),
              ),
            ],
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: statusColor.withOpacity(0.15),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(
            status,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: statusColor,
            ),
          ),
        ),
        const SizedBox(width: 8),
        Icon(
          Icons.more_vert,
          size: 16,
          color: Colors.white.withOpacity(0.4),
        ),
      ],
    );
  }

  Widget _buildAIToolsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'AI Formatting Tools',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 16),
        _buildAIToolCard(
          'Auto Format',
          'Automatically format your report according to academic standards',
          Icons.auto_awesome,
          const Color(0xFF3B82F6),
        ),
        const SizedBox(height: 12),
        _buildAIToolCard(
          'Citation Helper',
          'Generate and format citations in APA, MLA, or Chicago style',
          Icons.format_quote,
          const Color(0xFF8B5CF6),
        ),
        const SizedBox(height: 12),
        _buildAIToolCard(
          'Grammar Check',
          'AI-powered grammar and style suggestions for academic writing',
          Icons.check_circle,
          const Color(0xFF10B981),
        ),
      ],
    );
  }

  Widget _buildAIToolCard(
    String title,
    String description,
    IconData icon,
    Color color,
  ) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Colors.white.withOpacity(0.1),
        ),
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
                  color: color.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: color, size: 18),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            description,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w400,
              color: Colors.white.withOpacity(0.6),
              height: 1.4,
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            height: 32,
            child: ElevatedButton(
              onPressed: () {},
              style: ElevatedButton.styleFrom(
                backgroundColor: color,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(6),
                ),
              ),
              child: Text(
                'Use Tool',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuickActionsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Quick Actions',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: _buildQuickActionCard(
                'Create New Report',
                'Start from scratch or use a template',
                Icons.description,
                const Color(0xFF3B82F6),
                onTap: () => setState(() => _selectedIndex = 1),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: _buildQuickActionCard(
                'Import Document',
                'Upload existing files to format',
                Icons.upload_file,
                const Color(0xFF8B5CF6),
                onTap: () => setState(() => _selectedIndex = 1),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: _buildQuickActionCard(
                'Browse Templates',
                'Explore academic report templates',
                Icons.layers,
                const Color(0xFF06B6D4),
                onTap: () => setState(() => _selectedIndex = 4),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: _buildQuickActionCard(
                'Collaborate',
                'Share and work with team members',
                Icons.people,
                const Color(0xFF10B981),
                onTap: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Collaboration feature coming soon'),
                      backgroundColor: Color(0xFFD97706),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildQuickActionCard(
    String title,
    String description,
    IconData icon,
    Color color, {
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        child: Container(
          decoration: BoxDecoration(
            color: const Color(0xFF161B22),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: Colors.white.withOpacity(0.1),
            ),
          ),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: color, size: 20),
              ),
              const SizedBox(height: 12),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                description,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w400,
                  color: Colors.white.withOpacity(0.5),
                  height: 1.4,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildNewReportPage() {
    return NewReportScreen(selectedTemplate: _selectedTemplate);
  }

  Widget _buildMyReportsPage() {
    final auth = context.read<AuthProvider>();
    return Consumer<DocumentProvider>(
      builder: (context, docProvider, _) {
        // Apply search filter
        List<Map<String, dynamic>> filteredDocs = docProvider.documents
            .where((d) => (d['filename'] ?? '')
                .toLowerCase()
                .contains(_searchQuery.toLowerCase()))
            .toList();
        
        // Apply status filter
        if (_selectedFilter == 'completed') {
          filteredDocs = filteredDocs.where((d) => d['status'] == 'completed').toList();
        } else if (_selectedFilter == 'in_progress') {
          filteredDocs = filteredDocs.where((d) => d['status'] == 'processing').toList();
        } else if (_selectedFilter == 'draft') {
          filteredDocs = filteredDocs.where((d) => d['status'] == 'draft').toList();
        }
        
        // Apply sorting
        if (_sortBy == 'recent') {
          filteredDocs.sort((a, b) {
            final dateA = DateTime.tryParse(a['created_at'] ?? '') ?? DateTime.now();
            final dateB = DateTime.tryParse(b['created_at'] ?? '') ?? DateTime.now();
            return dateB.compareTo(dateA);
          });
        } else if (_sortBy == 'name') {
          filteredDocs.sort((a, b) => 
              (a['filename'] ?? '').compareTo(b['filename'] ?? ''));
        }
        
        // Calculate pagination
        int totalPages = (filteredDocs.length / _itemsPerPage).ceil();
        int startIndex = (_currentPage - 1) * _itemsPerPage;
        int endIndex = startIndex + _itemsPerPage;
        List<Map<String, dynamic>> paginatedDocs = filteredDocs
            .sublist(startIndex, endIndex > filteredDocs.length ? filteredDocs.length : endIndex);
        
        return RefreshIndicator(
          onRefresh: () => docProvider.fetchDocuments(auth.userId!),
          color: const Color(0xFF3B82F6),
          backgroundColor: const Color(0xFF161B22),
          child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Search, Filter, Sort Bar
              Row(
                children: [
                  Expanded(
                    flex: 2,
                    child: Container(
                      decoration: BoxDecoration(
                        color: const Color(0xFF161B22),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: Colors.white.withOpacity(0.1),
                        ),
                      ),
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: TextField(
                        onChanged: (value) {
                          setState(() {
                            _searchQuery = value;
                            _currentPage = 1;
                          });
                        },
                        style: const TextStyle(color: Colors.white),
                        decoration: InputDecoration(
                          hintText: 'Search reports...',
                          hintStyle: TextStyle(
                            color: Colors.white.withOpacity(0.4),
                            fontSize: 13,
                          ),
                          border: InputBorder.none,
                          prefixIcon: Icon(
                            Icons.search,
                            color: Colors.white.withOpacity(0.5),
                            size: 20,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Container(
                    decoration: BoxDecoration(
                      color: const Color(0xFF161B22),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: Colors.white.withOpacity(0.1),
                      ),
                    ),
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: PopupMenuButton<String>(
                      onSelected: (value) {
                        setState(() {
                          _selectedFilter = value;
                          _currentPage = 1;
                        });
                      },
                      itemBuilder: (context) => [
                        const PopupMenuItem(value: 'all', child: Text('All Reports')),
                        const PopupMenuItem(value: 'completed', child: Text('Completed')),
                        const PopupMenuItem(value: 'in_progress', child: Text('In Progress')),
                        const PopupMenuItem(value: 'draft', child: Text('Drafts')),
                      ],
                      child: Row(
                        children: [
                          Icon(Icons.filter_list, color: Colors.white.withOpacity(0.6), size: 18),
                          const SizedBox(width: 8),
                          Text(
                            'Filter',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.7),
                              fontSize: 13,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Container(
                    decoration: BoxDecoration(
                      color: const Color(0xFF161B22),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: Colors.white.withOpacity(0.1),
                      ),
                    ),
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: PopupMenuButton<String>(
                      onSelected: (value) {
                        setState(() {
                          _sortBy = value;
                          _currentPage = 1;
                        });
                      },
                      itemBuilder: (context) => [
                        const PopupMenuItem(value: 'recent', child: Text('Most Recent')),
                        const PopupMenuItem(value: 'name', child: Text('Name A-Z')),
                      ],
                      child: Row(
                        children: [
                          Icon(Icons.swap_vert, color: Colors.white.withOpacity(0.6), size: 18),
                          const SizedBox(width: 8),
                          Text(
                            'Sort',
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.7),
                              fontSize: 13,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              // Tabs
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    _buildTabButton('All Reports', 'all'),
                    _buildTabButton('Completed', 'completed'),
                    _buildTabButton('In Progress', 'in_progress'),
                    _buildTabButton('Drafts', 'draft'),
                  ],
                ),
              ),
              const SizedBox(height: 32),
              // Grid of Reports
              if (docProvider.isLoading)
                const Center(child: CircularProgressIndicator())
              else if (paginatedDocs.isEmpty)
                Center(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 48),
                    child: Column(
                      children: [
                        Icon(
                          Icons.folder_open,
                          size: 48,
                          color: Colors.white.withOpacity(0.3),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'No reports found',
                          style: TextStyle(
                            fontSize: 14,
                            color: Colors.white.withOpacity(0.5),
                          ),
                        ),
                      ],
                    ),
                  ),
                )
              else
                GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 3,
                    crossAxisSpacing: 24,
                    mainAxisSpacing: 24,
                    childAspectRatio: 0.85,
                  ),
                  itemCount: paginatedDocs.length,
                  itemBuilder: (context, index) {
                    final doc = paginatedDocs[index];
                    final status = doc['status'] ?? 'draft';
                    final statusColor = _getStatusColor(status);
                    final statusLabel = _getStatusLabel(status);
                    final iconColor = _getIconColor(status);

                    return Container(
                      decoration: BoxDecoration(
                        color: const Color(0xFF161B22),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: Colors.white.withOpacity(0.1),
                        ),
                      ),
                      child: Column(
                        children: [
                          // Top Section with Icon and Status Badge
                          Container(
                            height: 140,
                            decoration: BoxDecoration(
                              color: iconColor.withOpacity(0.15),
                              borderRadius: const BorderRadius.only(
                                topLeft: Radius.circular(12),
                                topRight: Radius.circular(12),
                              ),
                            ),
                            child: Stack(
                              children: [
                                Center(
                                  child: Icon(
                                    Icons.description,
                                    size: 48,
                                    color: iconColor,
                                  ),
                                ),
                                Positioned(
                                  top: 12,
                                  right: 12,
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 10,
                                      vertical: 6,
                                    ),
                                    decoration: BoxDecoration(
                                      color: statusColor.withOpacity(0.8),
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: Text(
                                      statusLabel,
                                      style: const TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.w600,
                                        color: Colors.white,
                                      ),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          // Bottom Section with Details
                          Expanded(
                            child: Padding(
                              padding: const EdgeInsets.all(16),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    doc['filename'] ?? 'Untitled',
                                    style: const TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w600,
                                      color: Colors.white,
                                    ),
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  const SizedBox(height: 6),
                                  Text(
                                    doc['template_name'] ?? 'No template',
                                    style: TextStyle(
                                      fontSize: 11,
                                      color: Colors.white.withOpacity(0.6),
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    'Modified ${_getTimeAgo(doc['created_at'] ?? DateTime.now())}',
                                    style: TextStyle(
                                      fontSize: 10,
                                      color: Colors.white.withOpacity(0.5),
                                    ),
                                  ),
                                  const Spacer(),
                                  // Action Buttons
                                  Row(
                                    children: [
                          Expanded(
                            child: ElevatedButton(
                              onPressed: () {
                                _showEditDialog(doc, auth.userId!);
                              },
                              style: ElevatedButton.styleFrom(
                                backgroundColor: const Color(0xFF3B82F6),
                                padding: const EdgeInsets.symmetric(vertical: 8),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(6),
                                ),
                              ),
                              child: const Text(
                                'Edit',
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                          ),
                                      const SizedBox(width: 8),
                                      IconButton(
                                        onPressed: () {
                                          _handleDownload(doc);
                                        },
                                        icon: const Icon(Icons.download, size: 16),
                                        color: Colors.white.withOpacity(0.6),
                                        padding: EdgeInsets.zero,
                                        constraints: const BoxConstraints(
                                          minWidth: 24,
                                          minHeight: 24,
                                        ),
                                      ),
                                      const SizedBox(width: 4),
                                      PopupMenuButton<String>(
                                        onSelected: (value) {
                                          if (value == 'preview') {
                                            _showPreview(doc);
                                          } else if (value == 'download') {
                                            _handleDownload(doc);
                                          } else if (value == 'delete') {
                                            _handleDelete(doc);
                                          }
                                        },
                                        itemBuilder: (context) => [
                                          const PopupMenuItem(
                                            value: 'preview',
                                            child: Row(
                                              children: [
                                                Icon(Icons.preview, size: 16),
                                                SizedBox(width: 8),
                                                Text('Preview'),
                                              ],
                                            ),
                                          ),
                                          const PopupMenuItem(
                                            value: 'download',
                                            child: Row(
                                              children: [
                                                Icon(Icons.download, size: 16),
                                                SizedBox(width: 8),
                                                Text('Download'),
                                              ],
                                            ),
                                          ),
                                          const PopupMenuItem(
                                            value: 'delete',
                                            child: Row(
                                              children: [
                                                Icon(Icons.delete, size: 16, color: Colors.red),
                                                SizedBox(width: 8),
                                                Text('Delete', style: TextStyle(color: Colors.red)),
                                              ],
                                            ),
                                          ),
                                        ],
                                        child: Icon(
                                          Icons.more_vert,
                                          size: 16,
                                          color: Colors.white.withOpacity(0.6),
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              const SizedBox(height: 40),
              // Pagination
              if (filteredDocs.isNotEmpty)
                Center(
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      IconButton(
                        icon: const Icon(Icons.chevron_left),
                        color: Colors.white.withOpacity(0.6),
                        onPressed: _currentPage > 1
                            ? () => setState(() => _currentPage--)
                            : null,
                      ),
                      for (int i = 1; i <= totalPages && i <= 3; i++)
                        GestureDetector(
                          onTap: () => setState(() => _currentPage = i),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 4),
                            child: Container(
                              width: 32,
                              height: 32,
                              decoration: BoxDecoration(
                                color: i == _currentPage
                                    ? const Color(0xFF3B82F6)
                                    : const Color(0xFF161B22),
                                borderRadius: BorderRadius.circular(6),
                                border: Border.all(
                                  color: Colors.white.withOpacity(0.1),
                                ),
                              ),
                              child: Center(
                                child: Text(
                                  '$i',
                                  style: TextStyle(
                                    color: i == _currentPage ? Colors.white : Colors.white.withOpacity(0.6),
                                    fontWeight: FontWeight.w600,
                                    fontSize: 13,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                      if (totalPages > 3)
                        Text(
                          '...',
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.6),
                            fontSize: 13,
                          ),
                        ),
                      if (totalPages > 3)
                        GestureDetector(
                          onTap: () => setState(() => _currentPage = totalPages),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 4),
                            child: Container(
                              width: 32,
                              height: 32,
                              decoration: BoxDecoration(
                                color: totalPages == _currentPage
                                    ? const Color(0xFF3B82F6)
                                    : const Color(0xFF161B22),
                                borderRadius: BorderRadius.circular(6),
                                border: Border.all(
                                  color: Colors.white.withOpacity(0.1),
                                ),
                              ),
                              child: Center(
                                child: Text(
                                  '$totalPages',
                                  style: TextStyle(
                                    color: totalPages == _currentPage ? Colors.white : Colors.white.withOpacity(0.6),
                                    fontWeight: FontWeight.w600,
                                    fontSize: 13,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                      IconButton(
                        icon: const Icon(Icons.chevron_right),
                        color: Colors.white.withOpacity(0.6),
                        onPressed: _currentPage < totalPages
                            ? () => setState(() => _currentPage++)
                            : null,
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),     // close SingleChildScrollView
        );     // close RefreshIndicator  ← return statement ends here
      },
    );
  }

  Widget _buildTabButton(String label, String value) {
    final isSelected = _selectedFilter == value;
    return GestureDetector(
      onTap: () {
        setState(() {
          _selectedFilter = value;
          _currentPage = 1;
        });
      },
      child: Container(
        margin: const EdgeInsets.only(right: 12),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFF3B82F6) : Colors.transparent,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
            color: isSelected
                ? const Color(0xFF3B82F6)
                : Colors.white.withOpacity(0.1),
          ),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w500,
            color: isSelected ? Colors.white : Colors.white.withOpacity(0.7),
          ),
        ),
      ),
    );
  }

  Color _getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'completed':
      case 'formatted':
      case 'uploaded':
        return const Color(0xFF10B981);
      case 'processing':
        return const Color(0xFFEAB308);
      case 'draft':
        return const Color(0xFFEF4444);
      default:
        return const Color(0xFF10B981);
    }
  }

  String _getStatusLabel(String status) {
    switch (status.toLowerCase()) {
      case 'completed':
      case 'formatted':
        return 'Completed';
      case 'processing':
        return 'In Progress';
      case 'draft':
      case 'uploaded':
        return 'Completed';
      default:
        return 'Formatted';
    }
  }

  Color _getIconColor(String status) {
    switch (status) {
      case 'completed':
        return const Color(0xFF10B981);
      case 'processing':
        return const Color(0xFF10D981);
      case 'draft':
        return const Color(0xFF8B5CF6);
      default:
        return const Color(0xFF3B82F6);
    }
  }

  void _showEditDialog(Map<String, dynamic> doc, int userId) {
    final docProvider = context.read<DocumentProvider>();
    final editController = TextEditingController();
    bool isLoading = true;
    String? editError;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) {
          // Load document content
          if (isLoading) {
            docProvider.getPreview(doc['id'], userId).then((previewData) {
              if (previewData != null) {
                editController.text = previewData['formatted_content'] ?? '';
              }
              setState(() => isLoading = false);
            }).catchError((error) {
              setState(() {
                isLoading = false;
                editError = 'Failed to load document';
              });
            });
          }

          return Dialog(
            backgroundColor: const Color(0xFF0D1117),
            insetPadding: const EdgeInsets.all(32),
            child: Container(
              decoration: BoxDecoration(
                color: const Color(0xFF0D1117),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: Colors.white.withOpacity(0.1),
                ),
              ),
              child: Column(
                children: [
                  // Header
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      border: Border(
                        bottom: BorderSide(
                          color: Colors.white.withOpacity(0.1),
                        ),
                      ),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          'Edit Document',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                        ),
                        GestureDetector(
                          onTap: () => Navigator.pop(context),
                          child: Icon(
                            Icons.close,
                            color: Colors.white.withOpacity(0.6),
                          ),
                        ),
                      ],
                    ),
                  ),
                  // Content
                  if (isLoading)
                    Expanded(
                      child: Center(
                        child: CircularProgressIndicator(),
                      ),
                    )
                  else if (editError != null)
                    Expanded(
                      child: Center(
                        child: Text(
                          editError!,
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.6),
                          ),
                        ),
                      ),
                    )
                  else
                    Expanded(
                      child: SingleChildScrollView(
                        padding: const EdgeInsets.all(32),
                        child: TextField(
                          controller: editController,
                          maxLines: null,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 14,
                            height: 1.6,
                          ),
                          decoration: InputDecoration(
                            hintText: 'Edit your document here...',
                            hintStyle: TextStyle(
                              color: Colors.white.withOpacity(0.3),
                              fontSize: 14,
                            ),
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
                              borderSide: const BorderSide(
                                color: Color(0xFF3B82F6),
                              ),
                            ),
                            filled: true,
                            fillColor: const Color(0xFF161B22),
                            contentPadding: const EdgeInsets.all(16),
                          ),
                        ),
                      ),
                    ),
                  // Footer buttons
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      border: Border(
                        top: BorderSide(
                          color: Colors.white.withOpacity(0.1),
                        ),
                      ),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        TextButton(
                          onPressed: () => Navigator.pop(context),
                          child: const Text(
                            'Cancel',
                            style: TextStyle(
                              color: Colors.white,
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        ElevatedButton(
                          onPressed: isLoading || editError != null
                              ? null
                              : () async {
                                  final success = await docProvider.saveDocumentContent(
                                    doc['id'],
                                    editController.text,
                                    userId,
                                  );
                                  if (!mounted) return;
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(
                                      content: Text(
                                        success
                                            ? 'Document saved successfully'
                                            : 'Failed to save document',
                                      ),
                                      backgroundColor: success
                                          ? const Color(0xFF10B981)
                                          : const Color(0xFFEF4444),
                                    ),
                                  );
                                  if (success) Navigator.pop(context);
                                },
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF3B82F6),
                          ),
                          child: const Text(
                            'Save Changes',
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
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
        },
      ),
    );
  }

  void _showPreview(Map<String, dynamic> doc) {
    final auth = context.read<AuthProvider>();
    final docProvider = context.read<DocumentProvider>();
    final isTemplate = doc['formatting_rules'] != null;

    showDialog(
      context: context,
      builder: (context) => Dialog(
        backgroundColor: const Color(0xFF0D1117),
        insetPadding: const EdgeInsets.all(32),
        child: Container(
          decoration: BoxDecoration(
            color: const Color(0xFF0D1117),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: Colors.white.withOpacity(0.1),
            ),
          ),
          child: Column(
            children: [
              // Header
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  border: Border(
                    bottom: BorderSide(
                      color: Colors.white.withOpacity(0.1),
                    ),
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          isTemplate ? 'Template Preview' : 'Document Preview',
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                        ),
                        if (isTemplate)
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Text(
                              doc['name'] ?? 'Template',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.white.withOpacity(0.6),
                              ),
                            ),
                          ),
                      ],
                    ),
                    GestureDetector(
                      onTap: () => Navigator.pop(context),
                      child: Icon(
                        Icons.close,
                        color: Colors.white.withOpacity(0.6),
                      ),
                    ),
                  ],
                ),
              ),
              // Content
              Expanded(
                child: isTemplate
                    ? _buildTemplatePreviewContent(doc)
                    : FutureBuilder<Map<String, dynamic>?>(
                        future: docProvider.getPreview(doc['id'], auth.userId!),
                        builder: (context, snapshot) {
                          if (snapshot.connectionState == ConnectionState.waiting) {
                            return const Center(
                              child: CircularProgressIndicator(),
                            );
                          }

                          if (snapshot.hasError || !snapshot.hasData) {
                            return Center(
                              child: Text(
                                'Failed to load preview',
                                style: TextStyle(
                                  color: Colors.white.withOpacity(0.6),
                                ),
                              ),
                            );
                          }

                          final previewData = snapshot.data!;
                          final content = previewData['formatted_content'] ?? '';
                          final formattingRules = previewData['formatting_rules'] ?? {};
                          final formattedLines = previewData['formatted_lines'] ?? [];

                          final pageSize = formattingRules['page_size'] ?? 'A4';

                          return SingleChildScrollView(
                            padding: const EdgeInsets.all(32),
                            child: Container(
                              decoration: BoxDecoration(
                                color: Colors.white,
                                borderRadius: BorderRadius.circular(8),
                                boxShadow: [
                                  BoxShadow(
                                    color: Colors.black.withOpacity(0.2),
                                    blurRadius: 8,
                                  ),
                                ],
                              ),
                              padding: const EdgeInsets.all(40),
                              width: pageSize == 'A4' ? 600 : 612,
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  // Show formatted content with template styles
                                  if (formattedLines.isNotEmpty)
                                    Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: formattedLines.map<Widget>((lineData) {
                                        final lineType = lineData['type'] ?? 'paragraph';
                                        final lineText = lineData['text'] ?? '';
                                        
                                        return _buildStyledLine(
                                          lineText,
                                          lineType,
                                          formattingRules,
                                        );
                                      }).toList(),
                                    )
                                  else
                                    Text(
                                      content,
                                      style: TextStyle(
                                        fontSize: (formattingRules['body_size'] ?? 11).toDouble(),
                                        color: Colors.black87,
                                        height: (formattingRules['line_spacing'] ?? 1.5).toDouble(),
                                        fontFamily: formattingRules['body_font'] ?? 'Calibri',
                                      ),
                                    ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
              ),
              // Footer buttons
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  border: Border(
                    top: BorderSide(
                      color: Colors.white.withOpacity(0.1),
                    ),
                  ),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text(
                        'Close',
                        style: TextStyle(
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTemplatePreviewContent(Map<String, dynamic> template) {
    final formattingRules = template['formatting_rules'] ?? {};
    final pageSize = formattingRules['page_size'] ?? 'A4';

    // Sample content to show template formatting
    final sampleContent = [
      {'text': 'Sample Heading 1', 'type': 'heading1'},
      {'text': 'This is a sample paragraph showing how your documents will be formatted using this template.', 'type': 'paragraph'},
      {'text': 'Sample Heading 2', 'type': 'heading2'},
      {'text': 'Key Points:', 'type': 'heading3'},
      {'text': 'First point to demonstrate bullet formatting', 'type': 'bullet'},
      {'text': 'Second point with consistent spacing', 'type': 'bullet'},
      {'text': 'Third point showing style application', 'type': 'bullet'},
      {'text': 'Conclusion paragraph showing body text formatting with proper line spacing and font selection.', 'type': 'paragraph'},
    ];

    return SingleChildScrollView(
      padding: const EdgeInsets.all(32),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(8),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.2),
              blurRadius: 8,
            ),
          ],
        ),
        padding: const EdgeInsets.all(40),
        width: pageSize == 'A4' ? 600 : 612,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: sampleContent.map<Widget>((lineData) {
            return _buildStyledLine(
              lineData['text'] ?? '',
              lineData['type'] ?? 'paragraph',
              formattingRules,
            );
          }).toList(),
        ),
      ),
    );
  }

  Widget _buildAIToolsPage() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          GridView.count(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisCount: 2,
            crossAxisSpacing: 16,
            mainAxisSpacing: 16,
            childAspectRatio: 1.2,
            children: [
              _buildAIToolCard(
                'Auto Format',
                'Automatically format your report according to academic standards',
                Icons.auto_awesome,
                const Color(0xFF3B82F6),
              ),
              _buildAIToolCard(
                'Citation Helper',
                'Generate and format citations in APA, MLA, or Chicago style',
                Icons.format_quote,
                const Color(0xFF8B5CF6),
              ),
              _buildAIToolCard(
                'Grammar Check',
                'AI-powered grammar and style suggestions for academic writing',
                Icons.check_circle,
                const Color(0xFF10B981),
              ),
              _buildAIToolCard(
                'Plagiarism Detector',
                'Check your content against millions of sources',
                Icons.search,
                const Color(0xFFD97706),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildTemplatesPage() {
    final templateColors = [
      const Color(0xFF3B82F6), // Blue
      const Color(0xFFA855F7), // Purple
      const Color(0xFF10B981), // Green
      const Color(0xFFEF4444), // Red
      const Color(0xFFFF6B35), // Orange
      const Color(0xFFEC4899), // Pink
      const Color(0xFF06B6D4), // Cyan
    ];

    return Consumer<TemplateProvider>(
      builder: (context, templateProvider, _) {
        return SingleChildScrollView(
          padding: const EdgeInsets.all(32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header with title and request button
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  ElevatedButton.icon(
                    onPressed: () {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Request Template feature coming soon')),
                      );
                    },
                    icon: const Icon(Icons.add, size: 18),
                    label: const Text('Request Template'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF3B82F6),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 32),

              // Search and filters row
              Row(
                children: [
                  Expanded(
                    flex: 2,
                    child: TextField(
                      onChanged: (value) {
                        setState(() => _searchQuery = value);
                      },
                      style: const TextStyle(color: Colors.white),
                      decoration: InputDecoration(
                        hintText: 'Search universities or template names...',
                        hintStyle: TextStyle(color: Colors.white.withOpacity(0.4)),
                        prefixIcon: Icon(Icons.search, color: Colors.white.withOpacity(0.4)),
                        filled: true,
                        fillColor: const Color(0xFF1A1F26),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                          borderSide: BorderSide(color: Colors.white.withOpacity(0.1)),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                          borderSide: BorderSide(color: Colors.white.withOpacity(0.1)),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    decoration: BoxDecoration(
                      color: const Color(0xFF161B22),
                      border: Border.all(color: Colors.white.withOpacity(0.1)),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: DropdownButton<String>(
                      value: _selectedFilter,
                      underline: const SizedBox(),
                      dropdownColor: const Color(0xFF161B22),
                      style: const TextStyle(color: Colors.white),
                      onChanged: (value) {
                        if (value != null) {
                          setState(() => _selectedFilter = value);
                        }
                      },
                      items: [
                        const DropdownMenuItem(value: 'all', child: Text('All Categories')),
                        const DropdownMenuItem(value: 'engineering', child: Text('Engineering')),
                        const DropdownMenuItem(value: 'sciences', child: Text('Sciences')),
                        const DropdownMenuItem(value: 'business', child: Text('Business')),
                        const DropdownMenuItem(value: 'humanities', child: Text('Humanities')),
                      ],
                    ),
                  ),
                  const SizedBox(width: 16),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    decoration: BoxDecoration(
                      color: const Color(0xFF161B22),
                      border: Border.all(color: Colors.white.withOpacity(0.1)),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: DropdownButton<String>(
                      value: _sortBy,
                      underline: const SizedBox(),
                      dropdownColor: const Color(0xFF161B22),
                      style: const TextStyle(color: Colors.white),
                      onChanged: (value) {
                        if (value != null) {
                          setState(() => _sortBy = value);
                        }
                      },
                      items: [
                        const DropdownMenuItem(value: 'popular', child: Text('Most Popular')),
                        const DropdownMenuItem(value: 'recent', child: Text('Most Recent')),
                        const DropdownMenuItem(value: 'name', child: Text('Name (A-Z)')),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 32),

              // Currently using template section
              if (_selectedTemplate != null)
                Container(
                  decoration: BoxDecoration(
                    color: const Color(0xFF1A2847),
                    border: Border.all(color: const Color(0xFF3B82F6).withOpacity(0.3)),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  padding: const EdgeInsets.all(20),
                  child: Row(
                    children: [
                      Container(
                        width: 60,
                        height: 60,
                        decoration: BoxDecoration(
                          color: const Color(0xFF3B82F6),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(Icons.description, color: Colors.white),
                      ),
                      const SizedBox(width: 20),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Currently Using: ${_selectedTemplate!['name'] ?? 'Selected Template'}',
                              style: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w600,
                                color: Colors.white,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'This template is applied to your current document. You can switch templates anytime.',
                              style: TextStyle(
                                fontSize: 13,
                                color: Colors.white.withOpacity(0.6),
                              ),
                            ),
                          ],
                        ),
                      ),
                      ElevatedButton(
                        onPressed: () => _showPreview(_selectedTemplate!),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF3B82F6),
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(6),
                          ),
                        ),
                        child: const Text('View Details'),
                      ),
                    ],
                  ),
                )
              else
                Container(
                  decoration: BoxDecoration(
                    color: const Color(0xFF1A2847),
                    border: Border.all(color: Colors.white.withOpacity(0.2)),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  padding: const EdgeInsets.all(20),
                  child: Row(
                    children: [
                      Container(
                        width: 60,
                        height: 60,
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Icon(Icons.description, color: Colors.white.withOpacity(0.5)),
                      ),
                      const SizedBox(width: 20),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'No Template Selected',
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w600,
                                color: Colors.white.withOpacity(0.7),
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Select a template below to get started with your document formatting.',
                              style: TextStyle(
                                fontSize: 13,
                                color: Colors.white.withOpacity(0.5),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              const SizedBox(height: 48),

              // Popular Templates section
              const Text(
                'Popular Templates',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 20),
              if (templateProvider.isLoading)
                const Center(child: CircularProgressIndicator())
              else if (templateProvider.templates.isEmpty)
                Center(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 48),
                    child: Text(
                      'No templates available',
                      style: TextStyle(
                        fontSize: 14,
                        color: Colors.white.withOpacity(0.5),
                      ),
                    ),
                  ),
                )
              else
                GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 3,
                    crossAxisSpacing: 20,
                    mainAxisSpacing: 20,
                  ),
                  itemCount: templateProvider.templates.length < 3 ? templateProvider.templates.length : 3,
                  itemBuilder: (context, index) {
                    final template = templateProvider.templates[index];
                    final color = templateColors[index % templateColors.length];
                    return _buildTemplateCardNew(template, color, index == 0);
                  },
                ),
              const SizedBox(height: 48),

              // All Templates section
              const Text(
                'All Templates',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 20),
              GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 3,
                  crossAxisSpacing: 20,
                  mainAxisSpacing: 20,
                ),
                itemCount: templateProvider.templates.length,
                itemBuilder: (context, index) {
                  final template = templateProvider.templates[index];
                  final color = templateColors[index % templateColors.length];
                  return _buildTemplateCardNew(template, color, false);
                },
              ),
              const SizedBox(height: 48),

              // Request custom template section
              Center(
                child: Container(
                  decoration: BoxDecoration(
                    color: const Color(0xFF1A1F26),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.white.withOpacity(0.1)),
                  ),
                  padding: const EdgeInsets.all(40),
                  child: Column(
                    children: [
                      const Icon(Icons.help_outline, color: Color(0xFF3B82F6), size: 48),
                      const SizedBox(height: 16),
                      const Text(
                        'Can\'t find your university template?',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Request a custom template and we\'ll add it within 48 hours',
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.white.withOpacity(0.6),
                        ),
                      ),
                      const SizedBox(height: 24),
                      ElevatedButton(
                        onPressed: () {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Custom template request submitted')),
                          );
                        },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF3B82F6),
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                        child: const Text('Request Custom Template'),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 32),
            ],
          ),
        );
      },
    );
  }

  Widget _buildSettingsPage() {
    return Consumer<AuthProvider>(
      builder: (context, auth, _) {
        return SingleChildScrollView(
          padding: const EdgeInsets.all(32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              
              Container(
                decoration: BoxDecoration(
                  color: const Color(0xFF161B22),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: Colors.white.withOpacity(0.1),
                  ),
                ),
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Account Information',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 16),
                    _buildSettingsItem('Username', auth.currentUser ?? 'N/A'),
                    const SizedBox(height: 12),
                    _buildSettingsItem('Email', auth.email ?? 'N/A'),
                    const SizedBox(height: 12),
                    _buildSettingsItem('Account Type', 'Student'),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              Container(
                decoration: BoxDecoration(
                  color: const Color(0xFF161B22),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: Colors.white.withOpacity(0.1),
                  ),
                ),
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Preferences',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Email Notifications',
                          style: TextStyle(
                            fontSize: 13,
                            color: Colors.white,
                          ),
                        ),
                        Switch(
                          value: true,
                          onChanged: (value) {},
                          activeColor: const Color(0xFF3B82F6),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'Dark Mode',
                          style: TextStyle(
                            fontSize: 13,
                            color: Colors.white,
                          ),
                        ),
                        Switch(
                          value: true,
                          onChanged: (value) {},
                          activeColor: const Color(0xFF3B82F6),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildTemplateCardNew(Map<String, dynamic> template, Color cardColor, bool isPopular) {
    final templateNames = {
      'mit_engineering': 'MIT Engineering',
      'stanford_cs': 'Stanford CS',
      'harvard_business': 'Harvard Business',
      'oxford_sciences': 'Oxford Sciences',
      'cambridge_arts': 'Cambridge Arts',
      'generic': 'Generic Template',
      'berkeley_engineering': 'UC Berkeley Engineering',
      'yale_law': 'Yale Law',
      'imperial_medicine': 'Imperial Medicine',
    };

    final templateDescriptions = {
      'mit_engineering': 'Standard format for engineering FYP reports with IEEE citation style',
      'stanford_cs': 'CS department template with ACM citation format and code blocks',
      'harvard_business': 'MBA thesis format with Harvard citation and executive summary',
      'oxford_sciences': 'Natural sciences format with APA citation and lab report structure',
      'cambridge_arts': 'Humanities template with MLA citation and footnote support',
      'generic': 'Universal format suitable for most academic institutions',
      'berkeley_engineering': 'Engineering thesis format with technical documentation style',
      'yale_law': 'Legal research format with Bluebook citation style',
      'imperial_medicine': 'Medical research format with Vancouver citation style',
    };

    final templateDetails = {
      'mit_engineering': [
        'IEEE Citation Style',
        '1-inch margins, Times New Roman 12pt',
        'Double-spaced numbered sections',
      ],
      'stanford_cs': [
        'ACM Citation Style',
        'Code syntax highlighting support',
        '1.5 spacing, Helvetica 11pt',
      ],
      'harvard_business': [
        'Harvard Citation Style',
        'Executive summary template',
        '1.5 spacing, Calibri 11pt',
      ],
      'oxford_sciences': [
        'APA Citation Style',
        'Lab report sections included',
        'Single-spaced with formatted equations',
      ],
      'cambridge_arts': [
        'MLA Citation Style',
        'Footnotes and endnote support',
        'Customizable formatting',
      ],
      'generic': [
        'Flexible citation styles',
        'Customizable formatting',
        'Works for most institutions',
      ],
      'berkeley_engineering': [
        'IEEE Citation Style',
        'Technical diagram support',
        'Technical documentation structure',
      ],
      'yale_law': [
        'Bluebook Citation Style',
        'Legal document structure',
        'Legal formatting conventions',
      ],
      'imperial_medicine': [
        'Vancouver Citation Style',
        'Clinical trial structure',
        'Medical formatting standards',
      ],
    };

    final templateKey = template['name']?.toLowerCase().replaceAll(' ', '_') ?? 'generic';
    final displayName = templateNames[templateKey] ?? template['name'] ?? 'Template';
    final description = templateDescriptions[templateKey] ?? 'Academic report template';
    final details = templateDetails[templateKey] ?? ['Standard formatting', 'Citation support'];

    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withOpacity(0.1)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Colored header
          Container(
            width: double.infinity,
            height: 140,
            decoration: BoxDecoration(
              color: cardColor,
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [cardColor, cardColor.withOpacity(0.8)],
              ),
            ),
            child: Stack(
              children: [
                // Template title in header
                Padding(
                  padding: const EdgeInsets.all(20),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      displayName,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ),
                // Status badge
                if (isPopular)
                  Positioned(
                    top: 12,
                    right: 12,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: Colors.white.withOpacity(0.4)),
                      ),
                      child: const Text(
                        'Popular',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),

          // Content section
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Title
                  Text(
                    '$displayName Template',
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 6),

                  // Description
                  Text(
                    description,
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.white.withOpacity(0.6),
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 12),

                  // Details list
                  ...details.map((detail) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      children: [
                        Text(
                          '• ',
                          style: TextStyle(
                            fontSize: 11,
                            color: Colors.white.withOpacity(0.5),
                          ),
                        ),
                        Expanded(
                          child: Text(
                            detail,
                            style: TextStyle(
                              fontSize: 11,
                              color: Colors.white.withOpacity(0.5),
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  )).toList(),

                  const Spacer(),

                  // Action buttons
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () => _showPreview(template),
                          style: OutlinedButton.styleFrom(
                            side: BorderSide(color: Colors.white.withOpacity(0.2)),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(6),
                            ),
                          ),
                          child: const Text(
                            'Preview',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: ElevatedButton(
                          onPressed: () {
                            setState(() {
                              _selectedTemplate = template;
                              _selectedIndex = 1; // Switch to New Report tab
                            });
                            Navigator.pop(context);
                          },
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.white.withOpacity(0.1),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(6),
                            ),
                          ),
                          child: const Text(
                            'Select Template',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showUploadDialog(Map<String, dynamic> template) {
    showDialog(
      context: context,
      builder: (context) => _buildUploadDialog(template),
    );
  }

  Widget _buildUploadDialog(Map<String, dynamic> template) {
    return Dialog(
      backgroundColor: const Color(0xFF161B22),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Container(
        width: 400,
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Upload Document',
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Using template: ${template['name']}',
              style: TextStyle(
                fontSize: 12,
                color: Colors.white.withOpacity(0.6),
              ),
            ),
            const SizedBox(height: 24),
            // Tab-like buttons for choosing upload method
            Container(
              decoration: BoxDecoration(
                color: const Color(0xFF0D1117),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: GestureDetector(
                      onTap: () => _pickFile(template),
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        decoration: BoxDecoration(
                          color: const Color(0xFF3B82F6),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: const Center(
                          child: Text(
                            'Upload File',
                            style: TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w600,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: GestureDetector(
                      onTap: () {
                        Navigator.pop(context);
                        _showPasteContentDialog(template);
                      },
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        decoration: BoxDecoration(
                          color: Colors.transparent,
                          border: Border.all(
                            color: Colors.white.withOpacity(0.2),
                          ),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Center(
                          child: Text(
                            'Paste Text',
                            style: TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w600,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            Text(
              'Supported formats: PDF, DOCX, DOC, TXT',
              style: TextStyle(
                fontSize: 11,
                color: Colors.white.withOpacity(0.5),
              ),
            ),
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: Text(
                    'Cancel',
                    style: TextStyle(
                      color: Colors.white.withOpacity(0.6),
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _pickFile(Map<String, dynamic> template) async {
    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf', 'docx', 'doc', 'txt'],
      );

      if (result != null && result.files.single.path != null) {
        final file = File(result.files.single.path!);
        final auth = context.read<AuthProvider>();
        final docProvider = context.read<DocumentProvider>();

        if (!mounted) return;
        Navigator.pop(context);

        // Show loading dialog
        showDialog(
          context: context,
          barrierDismissible: false,
          builder: (context) => Dialog(
            backgroundColor: const Color(0xFF161B22),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const CircularProgressIndicator(),
                  const SizedBox(height: 16),
                  const Text(
                    'Uploading document...',
                    style: TextStyle(color: Colors.white),
                  ),
                ],
              ),
            ),
          ),
        );

        final success = await docProvider.uploadDocument(
          file,
          template['id'] ?? 1,
          auth.userId ?? 1,
        );

        if (mounted) {
          Navigator.pop(context); // Close loading dialog

          if (success) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Document uploaded successfully!'),
                backgroundColor: Color(0xFF10B981),
              ),
            );
            // Refresh documents
            if (auth.userId != null) {
              docProvider.fetchDocuments(auth.userId!);
            }
          } else {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Upload failed: ${docProvider.errorMessage}'),
                backgroundColor: const Color(0xFFEF4444),
              ),
            );
          }
        }
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error: $e'),
          backgroundColor: const Color(0xFFEF4444),
        ),
      );
    }
  }

  void _showPasteContentDialog(Map<String, dynamic> template) {
    final textController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) => Dialog(
        backgroundColor: const Color(0xFF161B22),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        child: Container(
          width: 500,
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Paste Your Content',
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Paste your document text below',
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.white.withOpacity(0.6),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: textController,
                maxLines: 8,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: 'Paste your document content here...',
                  hintStyle: TextStyle(
                    color: Colors.white.withOpacity(0.4),
                  ),
                  filled: true,
                  fillColor: const Color(0xFF0D1117),
                  contentPadding: const EdgeInsets.all(12),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(6),
                    borderSide: BorderSide(
                      color: Colors.white.withOpacity(0.2),
                    ),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(6),
                    borderSide: BorderSide(
                      color: Colors.white.withOpacity(0.2),
                    ),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(6),
                    borderSide: const BorderSide(
                      color: Color(0xFF3B82F6),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: Text(
                      'Cancel',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.6),
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  ElevatedButton(
                    onPressed: () => _uploadPastedContent(template, textController.text),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF3B82F6),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(6),
                      ),
                    ),
                    child: const Text(
                      'Upload',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _uploadPastedContent(Map<String, dynamic> template, String content) async {
    if (content.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please paste some content'),
          backgroundColor: Color(0xFFEF4444),
        ),
      );
      return;
    }

    final auth = context.read<AuthProvider>();
    final docProvider = context.read<DocumentProvider>();

    if (!mounted) return;
    Navigator.pop(context); // Close paste dialog

    // Show loading dialog
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => Dialog(
        backgroundColor: const Color(0xFF161B22),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(),
              const SizedBox(height: 16),
              const Text(
                'Processing content...',
                style: TextStyle(color: Colors.white),
              ),
            ],
          ),
        ),
      ),
    );

    final success = await docProvider.uploadPastedContent(
      content,
      template['id'] ?? 1,
      auth.userId ?? 1,
    );

    if (mounted) {
      Navigator.pop(context); // Close loading dialog

      if (success) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Content uploaded successfully!'),
            backgroundColor: Color(0xFF10B981),
          ),
        );
        // Refresh documents
        if (auth.userId != null) {
          docProvider.fetchDocuments(auth.userId!);
        }
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Upload failed: ${docProvider.errorMessage}'),
            backgroundColor: const Color(0xFFEF4444),
          ),
        );
      }
    }
  }

  Widget _buildSettingsItem(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: Colors.white.withOpacity(0.6),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w500,
            color: Colors.white,
          ),
        ),
      ],
    );
  }

   String _getTimeAgo(dynamic dateTime) {
    DateTime parsedDateTime;
    
    if (dateTime is String) {
      // Backend sends UTC timestamps with 'Z' suffix — parse and convert to local time
      final parsed = DateTime.tryParse(dateTime);
      parsedDateTime = parsed != null
          ? (parsed.isUtc ? parsed.toLocal() : parsed)
          : DateTime.now();
    } else if (dateTime is DateTime) {
      parsedDateTime = dateTime.isUtc ? dateTime.toLocal() : dateTime;
    } else {
      return 'Unknown time';
    }

    final now = DateTime.now();
    final difference = now.difference(parsedDateTime);

    if (difference.inDays > 7) {
      return '${(difference.inDays / 7).toStringAsFixed(0)} weeks ago';
    } else if (difference.inDays > 0) {
      return '${difference.inDays} day${difference.inDays > 1 ? 's' : ''} ago';
    } else if (difference.inHours > 0) {
      return '${difference.inHours} hour${difference.inHours > 1 ? 's' : ''} ago';
    } else if (difference.inMinutes > 0) {
      return '${difference.inMinutes} minute${difference.inMinutes > 1 ? 's' : ''} ago';
    } else if (difference.inSeconds > 0) {
      return '${difference.inSeconds} second${difference.inSeconds > 1 ? 's' : ''} ago';
    } else {
      return 'just now';
    }
  }

void _handleDownload(Map<String, dynamic> doc) {
  showDialog(
    context: context,
    builder: (dialogContext) => ExportDialog(
      onExport: (format, {bool applyBullets = true, bool autoDetect = true}) async {
        final docProvider = context.read<DocumentProvider>();
         final authProvider = Provider.of<AuthProvider>(context, listen: false);
            final userId = authProvider.userId;
        try {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Downloading document as $format...'),
              backgroundColor: const Color(0xFF3B82F6),
            ),
          );

          final success = await docProvider.downloadFormattedDocument(
            doc['id'],
            userId!,
            format: format,
            applyBullets: applyBullets,
            autoDetectBullets: autoDetect,
          );

          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(success
                    ? 'Document downloaded as $format successfully!'
                    : 'Download failed: ${docProvider.errorMessage}'),
                backgroundColor: success ? Colors.green : Colors.red,
              ),
            );
          }
        } catch (e) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Error: $e'),
                backgroundColor: Colors.red,
              ),
            );
          }
        }
      },

    onQRCode: () async {
  try {
    final result = await QRService.generateQr(doc['id']);

    final qrBase64 = result['qr_base64'];
    if (qrBase64 == null || qrBase64.isEmpty) throw "QR data missing";

    if (!mounted) return;

    showDialog(
      context: context,
      useRootNavigator: true,
      builder: (_) => Dialog(
        child: Container(
          padding: const EdgeInsets.all(20),
          child: Image.memory(
            base64Decode(qrBase64),
            width: 250,
            height: 250,
            errorBuilder: (_, __, ___) => const Text('Failed to load QR'),
          ),
        ),
      ),
    );
  } catch (e) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Failed to generate QR: $e")),
      );
    }
  }
},


    ),
  );
}


  void _handleDelete(Map<String, dynamic> doc) {
    showDialog(
      context: context,
      builder: (context) => Dialog(
        backgroundColor: const Color(0xFF161B22),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        child: Container(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Delete Report',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                'Are you sure you want to delete "${doc['filename']}"? This action cannot be undone.',
                style: TextStyle(
                  fontSize: 13,
                  color: Colors.white.withOpacity(0.6),
                ),
              ),
              const SizedBox(height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: Text(
                      'Cancel',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.6),
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  ElevatedButton(
                    onPressed: () {
                      Navigator.pop(context);
                      _performDelete(doc);
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFEF4444),
                    ),
                    child: const Text(
                      'Delete',
                      style: TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _performDelete(Map<String, dynamic> doc) async {
    try {
      final auth = context.read<AuthProvider>();
      final docProvider = context.read<DocumentProvider>();

      // Show loading dialog
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (context) => Dialog(
          backgroundColor: const Color(0xFF161B22),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const CircularProgressIndicator(),
                const SizedBox(height: 16),
                const Text(
                  'Deleting document...',
                  style: TextStyle(color: Colors.white),
                ),
              ],
            ),
          ),
        ),
      );

      final success = await docProvider.deleteDocument(
        doc['id'],
        auth.userId ?? 1,
      );

      if (mounted) {
        Navigator.pop(context); // Close loading dialog

        if (success) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Document deleted successfully'),
              backgroundColor: Color(0xFF10B981),
              duration: Duration(seconds: 2),
            ),
          );
          // Force rebuild to refresh the list
          setState(() {});
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Delete failed: ${docProvider.errorMessage}'),
              backgroundColor: const Color(0xFFEF4444),
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: $e'),
            backgroundColor: const Color(0xFFEF4444),
          ),
        );
      }
    }
  }

  Widget _buildStyledLine(
    String text,
    String lineType,
    Map<String, dynamic> formattingRules,
  ) {
    TextStyle style;
    EdgeInsets padding = EdgeInsets.zero;
    
    switch (lineType) {
      case 'heading1':
        style = TextStyle(
          fontSize: double.parse(
            (formattingRules['heading1_size'] ?? 18).toString(),
          ),
          fontWeight: (formattingRules['heading1_bold'] ?? true)
              ? FontWeight.bold
              : FontWeight.normal,
          fontStyle: (formattingRules['heading1_italic'] ?? false)
              ? FontStyle.italic
              : FontStyle.normal,
          decoration: (formattingRules['heading1_underline'] ?? false)
              ? TextDecoration.underline
              : TextDecoration.none,
          color: _parseColor(formattingRules['heading1_color'] ?? '#000000'),
          fontFamily: _parseFontFamily(
            formattingRules['heading1_font'] ?? 'Times New Roman',
          ),
        );
        padding = const EdgeInsets.only(top: 12, bottom: 8);
        break;
      
      case 'heading2':
        style = TextStyle(
          fontSize: double.parse(
            (formattingRules['heading2_size'] ?? 16).toString(),
          ),
          fontWeight: (formattingRules['heading2_bold'] ?? true)
              ? FontWeight.bold
              : FontWeight.normal,
          fontStyle: (formattingRules['heading2_italic'] ?? false)
              ? FontStyle.italic
              : FontStyle.normal,
          decoration: (formattingRules['heading2_underline'] ?? false)
              ? TextDecoration.underline
              : TextDecoration.none,
          color: _parseColor(formattingRules['heading2_color'] ?? '#000000'),
          fontFamily: _parseFontFamily(
            formattingRules['heading2_font'] ?? 'Times New Roman',
          ),
        );
        padding = const EdgeInsets.only(top: 10, bottom: 6);
        break;
      
      case 'heading3':
        style = TextStyle(
          fontSize: double.parse(
            (formattingRules['heading3_size'] ?? 14).toString(),
          ),
          fontWeight: (formattingRules['heading3_bold'] ?? true)
              ? FontWeight.bold
              : FontWeight.normal,
          fontStyle: (formattingRules['heading3_italic'] ?? false)
              ? FontStyle.italic
              : FontStyle.normal,
          decoration: (formattingRules['heading3_underline'] ?? false)
              ? TextDecoration.underline
              : TextDecoration.none,
          color: _parseColor(formattingRules['heading3_color'] ?? '#000000'),
          fontFamily: _parseFontFamily(
            formattingRules['heading3_font'] ?? 'Times New Roman',
          ),
        );
        padding = const EdgeInsets.only(top: 8, bottom: 4);
        break;
      
      case 'bullet':
        style = TextStyle(
          fontSize: double.parse(
            (formattingRules['bullet_size'] ?? 12).toString(),
          ),
          color: _parseColor(formattingRules['bullet_color'] ?? '#000000'),
          fontFamily: _parseFontFamily(
            formattingRules['bullet_font'] ?? 'Times New Roman',
          ),
          height: double.parse(
            (formattingRules['line_spacing'] ?? 1.5).toString(),
          ),
        );
        return Padding(
          padding: const EdgeInsets.only(left: 24),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('• ', style: TextStyle(fontSize: 12)),
              Expanded(
                child: Text(text, style: style),
              ),
            ],
          ),
        );
      
      case 'numbered':
        style = TextStyle(
          fontSize: double.parse(
            (formattingRules['numbered_size'] ?? 12).toString(),
          ),
          color: _parseColor(formattingRules['numbered_color'] ?? '#000000'),
          fontFamily: _parseFontFamily(
            formattingRules['numbered_font'] ?? 'Times New Roman',
          ),
          height: double.parse(
            (formattingRules['line_spacing'] ?? 1.5).toString(),
          ),
        );
        return Padding(
          padding: const EdgeInsets.only(left: 24),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(width: 20),
              Expanded(
                child: Text(text, style: style),
              ),
            ],
          ),
        );
      
      default: // paragraph
        style = TextStyle(
          fontSize: double.parse(
            (formattingRules['body_size'] ?? 12).toString(),
          ),
          color: _parseColor(formattingRules['body_color'] ?? '#000000'),
          fontFamily: _parseFontFamily(
            formattingRules['body_font'] ?? 'Times New Roman',
          ),
          height: double.parse(
            (formattingRules['line_spacing'] ?? 1.5).toString(),
          ),
        );
        padding = const EdgeInsets.only(bottom: 6);
    }
    
    return Padding(
      padding: padding,
      child: Text(text, style: style),
    );
  }

  String _parseFontFamily(dynamic font) {
    if (font == null) return 'Times New Roman';
    final fontStr = font.toString().toLowerCase();
    if (fontStr.contains('arial')) return 'Arial';
    if (fontStr.contains('georgia')) return 'Georgia';
    if (fontStr.contains('courier')) return 'Courier New';
    if (fontStr.contains('verdana')) return 'Verdana';
    if (fontStr.contains('calibri')) return 'Calibri';
    if (fontStr.contains('garamond')) return 'Garamond';
    return 'Times New Roman';
  }

  Color _parseColor(String colorString) {
    try {
      if (colorString.startsWith('#')) {
        return Color(int.parse(colorString.replaceFirst('#', '0xff')));
      }
      return Colors.black;
    } catch (e) {
      return Colors.black;
    }
  }

  void _logout(BuildContext context) {
    context.read<AuthProvider>().logout();
  }
}

class TemplatesPanel extends StatelessWidget {
  const TemplatesPanel({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Templates',
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                  letterSpacing: 0.5,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Select a template to apply formatting to your documents',
                style: TextStyle(
                  fontSize: 14,
                  color: Colors.white.withOpacity(0.6),
                  fontWeight: FontWeight.w400,
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          Expanded(
            child: Consumer<TemplateProvider>(
              builder: (context, templateProvider, _) {
                if (templateProvider.isLoading) {
                  return const Center(
                    child: CircularProgressIndicator(
                      color: Color(0xFF6366F1),
                    ),
                  );
                }

                if (templateProvider.errorMessage != null) {
                  return Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.error_outline, size: 48, color: Colors.white.withOpacity(0.3)),
                        const SizedBox(height: 16),
                        Text(
                          'Error: ${templateProvider.errorMessage}',
                          style: TextStyle(color: Colors.white.withOpacity(0.6)),
                        ),
                      ],
                    ),
                  );
                }

                if (templateProvider.templates.isEmpty) {
                  return Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.layers_clear, size: 48, color: Colors.white.withOpacity(0.3)),
                        const SizedBox(height: 16),
                        Text(
                          'No templates available yet',
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.6),
                            fontSize: 15,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  );
                }

                return ListView.builder(
                  itemCount: templateProvider.templates.length,
                  itemBuilder: (context, index) {
                    final template = templateProvider.templates[index];
                    final isSelected = templateProvider.selectedTemplate?['id'] == template['id'];
                    
                    return Container(
                      margin: const EdgeInsets.only(bottom: 16),
                      decoration: BoxDecoration(
                        color: isSelected
                            ? const Color(0xFF6366F1).withOpacity(0.15)
                            : const Color(0xFF1A1F2E),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: isSelected
                              ? const Color(0xFF6366F1).withOpacity(0.4)
                              : Colors.white.withOpacity(0.1),
                          width: 1.5,
                        ),
                      ),
                      child: Padding(
                        padding: const EdgeInsets.all(20),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          Container(
                                            padding: const EdgeInsets.all(8),
                                            decoration: BoxDecoration(
                                              color: const Color(0xFF6366F1).withOpacity(0.2),
                                              borderRadius: BorderRadius.circular(6),
                                            ),
                                            child: const Icon(
                                              Icons.layers,
                                              color: Color(0xFF6366F1),
                                              size: 16,
                                            ),
                                          ),
                                          const SizedBox(width: 12),
                                          Expanded(
                                            child: Text(
                                              template['name'] ?? 'Unnamed Template',
                                              style: const TextStyle(
                                                fontSize: 17,
                                                fontWeight: FontWeight.w600,
                                                color: Colors.white,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                      if (isSelected)
                                        Padding(
                                          padding: const EdgeInsets.only(top: 8, left: 20),
                                          child: Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                            decoration: BoxDecoration(
                                              color: const Color(0xFF10B981).withOpacity(0.15),
                                              borderRadius: BorderRadius.circular(6),
                                            ),
                                            child: Row(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                const Icon(
                                                  Icons.check_circle,
                                                  size: 14,
                                                  color: Color(0xFF10B981),
                                                ),
                                                const SizedBox(width: 4),
                                                Text(
                                                  'Selected',
                                                  style: TextStyle(
                                                    fontSize: 12,
                                                    color: Colors.white.withOpacity(0.8),
                                                    fontWeight: FontWeight.w500,
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ),
                                        ),
                                    ],
                                  ),
                                ),
                                SizedBox(
                                  height: 40,
                                  child: ElevatedButton(
                                    onPressed: isSelected
                                        ? null
                                        : () {
                                            templateProvider.selectTemplate(template);
                                            ScaffoldMessenger.of(context).showSnackBar(
                                              SnackBar(
                                                content: Text('Template "${template['name']}" selected!'),
                                                backgroundColor: const Color(0xFF10B981),
                                                duration: const Duration(seconds: 2),
                                                behavior: SnackBarBehavior.floating,
                                                margin: const EdgeInsets.all(16),
                                              ),
                                            );
                                          },
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: isSelected
                                          ? const Color(0xFF10B981).withOpacity(0.2)
                                          : const Color(0xFF6366F1),
                                      foregroundColor: isSelected ? const Color(0xFF10B981) : Colors.white,
                                    ),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(isSelected ? Icons.check : Icons.add, size: 18),
                                        const SizedBox(width: 6),
                                        Text(isSelected ? 'Selected' : 'Select'),
                                      ],
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class SettingsPanel extends StatelessWidget {
  const SettingsPanel({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(32.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Settings',
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                  letterSpacing: 0.5,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Manage your account settings and preferences',
                style: TextStyle(
                  fontSize: 14,
                  color: Colors.white.withOpacity(0.6),
                  fontWeight: FontWeight.w400,
                ),
              ),
            ],
          ),
          const SizedBox(height: 32),
          Consumer<AuthProvider>(
            builder: (context, auth, _) {
              return Container(
                decoration: BoxDecoration(
                  color: const Color(0xFF1A1F2E),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.white.withOpacity(0.1)),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(24.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: const Color(0xFF6366F1).withOpacity(0.2),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: const Icon(
                              Icons.account_circle,
                              color: Color(0xFF6366F1),
                              size: 24,
                            ),
                          ),
                          const SizedBox(width: 12),
                          const Text(
                            'Account Settings',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: Colors.white,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 24),
                      _buildSettingField(
                        'Email Address',
                        auth.userEmail ?? 'user@university.edu',
                        Icons.email,
                      ),
                      const SizedBox(height: 16),
                      _buildSettingField(
                        'Username',
                        auth.currentUser ?? 'User',
                        Icons.person,
                      ),
                      const SizedBox(height: 16),
                      _buildSettingField(
                        'Role',
                        auth.userRole != null
                            ? auth.userRole![0].toUpperCase() + auth.userRole!.substring(1)
                            : 'Unknown',
                        Icons.shield,
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildSettingField(String label, String value, IconData icon) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0F1419).withOpacity(0.5),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withOpacity(0.08)),
      ),
      child: Row(
        children: [
          Icon(icon, color: const Color(0xFF6366F1), size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.white.withOpacity(0.6),
                    fontWeight: FontWeight.w500,
                    letterSpacing: 0.5,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  value,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
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