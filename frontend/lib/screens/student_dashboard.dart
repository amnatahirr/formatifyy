import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:frontend/providers/qr_service.dart';
import 'package:frontend/widgets/qr_dialog.dart';
import 'package:provider/provider.dart';
import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:share_plus/share_plus.dart';
import 'package:open_file_plus/open_file_plus.dart';
import '../providers/auth_provider.dart';
import '../providers/document_provider.dart';
import '../providers/template_provider.dart';
import '../providers/collaboration_provider.dart';
import 'new_report_screen.dart';
import 'analyze_screen.dart';
import '../widgets/export_dialog.dart';
import '../widgets/collaboration/project_card.dart';
import 'collaboration/project_dashboard_screen.dart';
import 'collaboration/project_detail_screen.dart';
import 'student_meeting_notes_screen.dart';
import 'student/supervisor_selection_screen.dart';
import 'student/my_supervisor_screen.dart';
import 'student/fyp_milestones_screen.dart';
import 'student/plagiarism_report_screen.dart';
import 'student/status_tracker_screen.dart';
import '../widgets/notifications_panel.dart';
import '../widgets/student/mobile_status_summary_card.dart';
import '../utils/responsive.dart';
import 'mobile_companion_screen.dart';

/// Mobile bottom-nav → existing `_selectedIndex` targets.
/// Notifications has no desktop sidebar entry; uses [kNotificationsTabIndex].
const int kNotificationsTabIndex = 13;

class _MobileNavItem {
  final int tabIndex;
  final IconData icon;
  final String label;

  const _MobileNavItem(this.tabIndex, this.icon, this.label);
}

const List<_MobileNavItem> _kMobileNavItems = [
  _MobileNavItem(0, Icons.dashboard_outlined, 'Dashboard'),
  _MobileNavItem(8, Icons.checklist_outlined, 'Milestones'),
  _MobileNavItem(kNotificationsTabIndex, Icons.notifications_outlined, 'Notifications'),
  _MobileNavItem(2, Icons.folder_outlined, 'Reports'),
];

class StudentDashboard extends StatefulWidget {
  final int initialIndex;
  final int? initialProjectId;
  final int initialProjectTab;

  const StudentDashboard({
    Key? key,
    this.initialIndex = 0,
    this.initialProjectId,
    this.initialProjectTab = 0,
  }) : super(key: key);

  @override
  State<StudentDashboard> createState() => _StudentDashboardState();
}

class _StudentDashboardState extends State<StudentDashboard> {
  late int _selectedIndex;
  int? _activeProjectId;
  int _projectDetailTab = 0;
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
    _selectedIndex = widget.initialIndex.clamp(0, kNotificationsTabIndex);
    _activeProjectId = widget.initialProjectId;
    _projectDetailTab = widget.initialProjectTab;
    _loadInitialData();
  }

  void _loadInitialData() {
    Future.microtask(() {
      final auth = context.read<AuthProvider>();
      if (auth.userId != null) {
        context.read<CollaborationProvider>().setActiveUserId(auth.userId!);
        context.read<TemplateProvider>().fetchUserTemplates(auth.userId!);
        context.read<DocumentProvider>().fetchDocuments(auth.userId!);
        context.read<CollaborationProvider>().fetchProjects();
        //Start auto-refresh polling every 30 seconds
        _refreshTimer = Timer.periodic(const Duration(seconds: 10), (_) {
          final a = context.read<AuthProvider>();
          if (a.userId != null) {
            context.read<CollaborationProvider>().setActiveUserId(a.userId!);
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
    final compact = isCompact(context);

    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      body: compact
          ? Column(
              children: [
                _buildTopBar(compact: true),
                Expanded(child: _buildBody()),
              ],
            )
          : Row(
              children: [
                _buildSidebar(),
                Expanded(
                  child: Column(
                    children: [
                      _buildTopBar(compact: false),
                      Expanded(child: _buildBody()),
                    ],
                  ),
                ),
              ],
            ),
      bottomNavigationBar: compact ? _buildMobileBottomNav() : null,
    );
  }

  Widget _buildMobileBottomNav() {
    final selectedNav = _kMobileNavItems.indexWhere(
      (item) => item.tabIndex == _selectedIndex,
    );

    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        border: Border(
          top: BorderSide(color: Colors.white.withOpacity(0.1)),
        ),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 64,
          child: Row(
            children: [
              for (var i = 0; i < _kMobileNavItems.length; i++)
                Expanded(
                  child: _buildMobileNavButton(
                    item: _kMobileNavItems[i],
                    selected: selectedNav == i,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMobileNavButton({
    required _MobileNavItem item,
    required bool selected,
  }) {
    final color = selected
        ? const Color(0xFF3B82F6)
        : Colors.white.withOpacity(0.55);

    return InkWell(
      onTap: () {
        setState(() {
          _selectedIndex = item.tabIndex;
          _activeProjectId = null;
        });
      },
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(item.icon, size: 22, color: color),
          const SizedBox(height: 4),
          Text(
            item.label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: 10,
              fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
              color: color,
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
                  Icons.people_outline,
                  'Collaboration',
                ),
                _buildSidebarItem(
                  4,
                  Icons.auto_awesome,
                  'AI Tools',
                ),
                _buildSidebarItem(
                  5,
                  Icons.layers,
                  'Templates',
                ),
                _buildSidebarItem(
                  6,
                  Icons.school_outlined,
                  'Choose Supervisor',
                ),
                _buildSidebarItem(
                  7,
                  Icons.badge_outlined,
                  'My Supervisor',
                ),
                _buildSidebarItem(
                  8,
                  Icons.checklist_outlined,
                  'Milestones',
                ),
                _buildSidebarItem(
                  9,
                  Icons.sticky_note_2_outlined,
                  'Meeting Notes',
                ),
                _buildSidebarItem(
                  10,
                  Icons.policy_outlined,
                  'Plagiarism Report',
                ),
                _buildSidebarItem(
                  11,
                  Icons.track_changes_outlined,
                  'Status Tracker',
                ),
                _buildSidebarItem(
                  12,
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
          setState(() {
            _selectedIndex = index;
            _activeProjectId = null;
          });
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

  Widget _buildTopBar({required bool compact}) {
    final titles = [
      'Dashboard',
      'New Report',
      'My Reports',
      'Collaboration',
      'AI Tools',
      'Templates',
      'Choose Supervisor',
      'My Supervisor',
      'Milestones',
      'Meeting Notes',
      'Plagiarism Report',
      'Status Tracker',
      'Settings',
      'Notifications',
    ];
    final descriptions = [
      'Here\'s your report overview.',
      'Choose a template and start formatting your report. Upload from local files, Google Drive, or paste content directly.',
      'Manage and view all your uploaded reports',
      'Create projects, invite teammates, and track shared work.',
      'Powerful AI-powered tools to enhance your reports',
      'Choose from pre-built academic report templates',
      'Request an FYP supervisor for your group',
      'Track your supervisor assignment status',
      'View your FYP milestone checklist',
      'Read-only meeting notes from your FYP supervisor',
      'View plagiarism score and matched sources from your submission',
      'Track final submission review status and supervisor decisions',
      'Manage your account settings and preferences',
      'Updates from your supervisor and FYP workflow',
    ];

    final showingProject = _activeProjectId != null;
    final projectName = context.watch<CollaborationProvider>().currentProject?['name'] as String?;
    final title = showingProject
        ? (projectName ?? 'Project')
        : titles[_selectedIndex];
    final description = showingProject
        ? 'Shared project workspace'
        : (_selectedIndex == 0
            ? 'Welcome back, ${context.watch<AuthProvider>().currentUser ?? "User"}. ${descriptions[_selectedIndex]}'
            : descriptions[_selectedIndex]);

    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        border: Border(
          bottom: BorderSide(
            color: Colors.white.withOpacity(0.1),
          ),
        ),
      ),
      padding: EdgeInsets.fromLTRB(
        compact ? 16 : 32,
        compact ? 12 : 20,
        compact ? 16 : 32,
        compact ? 16 : 20,
      ),
      child: SafeArea(
        bottom: false,
        minimum: EdgeInsets.only(top: compact ? 8 : 0),
        child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: compact ? 20 : 28,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
                if (!compact || _selectedIndex == 0)
                  Text(
                    description,
                    maxLines: compact ? 1 : 3,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 13,
                      color: Colors.white.withOpacity(0.6),
                      fontWeight: FontWeight.w400,
                    ),
                  ),
              ],
            ),
          ),
          if (!compact)
            Row(
              children: [
                const NotificationsPanelButton(),
                const SizedBox(width: 12),
                GestureDetector(
                  onTap: () {
                    setState(() {
                      _selectedIndex = 1;
                      _activeProjectId = null;
                    });
                  },
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: const Color(0xFF3B82F6),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: const Row(
                      children: [
                        Icon(Icons.add, size: 18, color: Colors.white),
                        SizedBox(width: 6),
                        Text(
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
            )
          else
            IconButton(
              tooltip: 'Sign out',
              onPressed: () => _logout(context),
              icon: Icon(Icons.logout_rounded, color: Colors.white.withOpacity(0.75)),
            ),
        ],
      ),
      ),
    );
  }

  Widget _buildBody() {
    if (_activeProjectId != null) {
      return ProjectDetailScreen(
        key: ValueKey('project-$_activeProjectId-$_projectDetailTab'),
        projectId: _activeProjectId!,
        initialTab: _projectDetailTab,
        embedded: true,
        onBack: () => setState(() => _activeProjectId = null),
      );
    }

    if (_selectedIndex == 2) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final auth = context.read<AuthProvider>();
        if (auth.userId != null) {
          context.read<DocumentProvider>().fetchDocuments(auth.userId!);
        }
      });
    }
    switch (_selectedIndex) {
      case 0:
        return _buildDashboardContent();
      case 1:
        return _buildNewReportPage();
      case 2:
        return _buildMyReportsPage();
      case 3:
        return ProjectDashboardScreen(
          embedded: true,
          onOpenProject: _openProjectById,
        );
      case 4:
        return _buildAIToolsPage();
      case 5:
        return _buildTemplatesPage();
      case 6:
        return const SupervisorSelectionScreen();
      case 7:
        return MySupervisorScreen(
          onChooseSupervisor: () => setState(() {
            _selectedIndex = 6;
            _activeProjectId = null;
          }),
        );
      case 8:
        return FypMilestonesScreen(
          onChooseSupervisor: () => setState(() {
            _selectedIndex = 6;
            _activeProjectId = null;
          }),
          onOpenMySupervisor: () => setState(() {
            _selectedIndex = 7;
            _activeProjectId = null;
          }),
        );
      case 9:
        return const StudentMeetingNotesScreen();
      case 10:
        return PlagiarismReportScreen(
          onChooseSupervisor: () => setState(() {
            _selectedIndex = 6;
            _activeProjectId = null;
          }),
          onOpenMySupervisor: () => setState(() {
            _selectedIndex = 7;
            _activeProjectId = null;
          }),
          onOpenNewReport: () => setState(() {
            _selectedIndex = 1;
            _activeProjectId = null;
          }),
        );
      case 11:
        return StatusTrackerScreen(
          onChooseSupervisor: () => setState(() {
            _selectedIndex = 6;
            _activeProjectId = null;
          }),
          onOpenMySupervisor: () => setState(() {
            _selectedIndex = 7;
            _activeProjectId = null;
          }),
          onUploadNewVersion: () => setState(() {
            _selectedIndex = 1;
            _activeProjectId = null;
          }),
        );
      case 12:
        return _buildSettingsPage();
      case kNotificationsTabIndex:
        return const StudentNotificationsPage();
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _buildDashboardContent() {
    final compact = isCompact(context);
    return Consumer<DocumentProvider>(
      builder: (context, docProvider, _) {
        final totalReports = docProvider.documents.length;
        final completedCount = docProvider.documents.where((d) => d['status'] == 'formatted').length;
        final draftCount = docProvider.documents.where((d) => d['status'] == 'uploaded' || d['status'] == 'processing').length;

        return SingleChildScrollView(
          padding: EdgeInsets.all(compact ? 16 : 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (compact) ...[
                const MobileStatusSummaryCard(),
                const SizedBox(height: 16),
                _buildSendFromPhoneCard(),
                const SizedBox(height: 20),
              ],
              _buildStatsRow(compact: compact, totalReports: totalReports, draftCount: draftCount, completedCount: completedCount),
              const SizedBox(height: 28),
              if (compact) ...[
                _buildRecentReportsSection(docProvider.documents),
                const SizedBox(height: 24),
                _buildAIToolsSection(compact: true),
                const SizedBox(height: 24),
                _buildSharedProjectsSection(),
                const SizedBox(height: 24),
                _buildQuickActionsSection(compact: true),
              ] else ...[
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      flex: 2,
                      child: _buildRecentReportsSection(docProvider.documents),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: _buildAIToolsSection(compact: false),
                    ),
                  ],
                ),
                const SizedBox(height: 32),
                _buildSharedProjectsSection(),
                const SizedBox(height: 32),
                _buildQuickActionsSection(compact: false),
              ],
            ],
          ),
        );
      },
    );
  }

  /// Mobile-only entry to Quick Access (Scan QR / Camera / Gallery).
  /// Navigates to [MobileCompanionScreen] — not rebuilt here.
  Widget _buildSendFromPhoneCard() {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () {
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => const MobileCompanionScreen(),
            ),
          );
        },
        borderRadius: BorderRadius.circular(12),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: const Color(0xFF161B22),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.white.withOpacity(0.1)),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFF6366F1).withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(
                  Icons.qr_code_scanner_rounded,
                  color: Color(0xFF6366F1),
                  size: 22,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Send Document from Phone',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Scan QR, camera, or gallery upload',
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.5),
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.chevron_right,
                color: Colors.white.withOpacity(0.35),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatsRow({
    required bool compact,
    required int totalReports,
    required int draftCount,
    required int completedCount,
  }) {
    final cards = [
      _buildStatCard(
        title: 'Total Reports',
        value: totalReports.toString(),
        change: '+12%',
        icon: Icons.description,
        changeColor: const Color(0xFF10B981),
        compact: compact,
      ),
      _buildStatCard(
        title: 'Active Drafts',
        value: draftCount.toString(),
        change: 'In Progress',
        icon: Icons.history,
        changeColor: const Color(0xFFD97706),
        compact: compact,
      ),
      _buildStatCard(
        title: 'Completed',
        value: completedCount.toString(),
        change: '+8%',
        icon: Icons.check_circle,
        changeColor: const Color(0xFF10B981),
        compact: compact,
      ),
      _buildStatCard(
        title: 'AI Suggestions Used',
        value: (totalReports * 5).toString(),
        change: 'AI',
        icon: Icons.auto_awesome,
        changeColor: const Color(0xFF8B5CF6),
        compact: compact,
      ),
    ];

    // Phones (~360–430px): 2×2 grid so labels/badges never overflow card edges.
    if (compact) {
      return LayoutBuilder(
        builder: (context, constraints) {
          final gap = 10.0;
          final cardWidth = (constraints.maxWidth - gap) / 2;
          return Wrap(
            spacing: gap,
            runSpacing: gap,
            children: cards
                .map(
                  (card) => SizedBox(
                    width: cardWidth,
                    child: card,
                  ),
                )
                .toList(),
          );
        },
      );
    }

    return Row(
      children: [
        for (var i = 0; i < cards.length; i++) ...[
          if (i > 0) const SizedBox(width: 16),
          Expanded(child: cards[i]),
        ],
      ],
    );
  }

  Widget _buildStatCard({
    required String title,
    required String value,
    required String change,
    required IconData icon,
    required Color changeColor,
    bool compact = false,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Colors.white.withOpacity(0.1),
        ),
      ),
      padding: EdgeInsets.all(compact ? 12 : 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: EdgeInsets.all(compact ? 8 : 10),
                decoration: BoxDecoration(
                  color: changeColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  icon,
                  color: changeColor,
                  size: compact ? 16 : 20,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  change,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.right,
                  style: TextStyle(
                    fontSize: compact ? 10 : 12,
                    fontWeight: FontWeight.w600,
                    color: changeColor,
                  ),
                ),
              ),
            ],
          ),
          SizedBox(height: compact ? 10 : 16),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: compact ? 22 : 32,
              fontWeight: FontWeight.w700,
              color: Colors.white,
            ),
          ),
          SizedBox(height: compact ? 2 : 4),
          Text(
            title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: compact ? 11 : 13,
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
                  setState(() {
                    _selectedIndex = 2;
                    _activeProjectId = null;
                  });
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

  Widget _buildAIToolsSection({bool compact = false}) {
    final tools = [
      (
        'Auto Format',
        'Format to academic standards',
        Icons.auto_awesome,
        const Color(0xFF3B82F6),
      ),
      (
        'Citation Helper',
        'APA, MLA, Chicago citations',
        Icons.format_quote,
        const Color(0xFF8B5CF6),
      ),
      (
        'Grammar Check',
        'Academic writing suggestions',
        Icons.check_circle_outline,
        const Color(0xFF10B981),
      ),
    ];

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
        const SizedBox(height: 14),
        if (compact)
          Container(
            decoration: BoxDecoration(
              color: const Color(0xFF161B22),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: Colors.white.withOpacity(0.1)),
            ),
            child: Column(
              children: [
                for (var i = 0; i < tools.length; i++) ...[
                  if (i > 0)
                    Divider(
                      height: 1,
                      color: Colors.white.withOpacity(0.06),
                    ),
                  _buildAIToolTile(
                    tools[i].$1,
                    tools[i].$2,
                    tools[i].$3,
                    tools[i].$4,
                  ),
                ],
              ],
            ),
          )
        else
          ...[
            for (var i = 0; i < tools.length; i++) ...[
              if (i > 0) const SizedBox(height: 12),
              _buildAIToolCard(
                tools[i].$1,
                tools[i].$2,
                tools[i].$3,
                tools[i].$4,
              ),
            ],
          ],
      ],
    );
  }

  Widget _buildAIToolTile(
    String title,
    String description,
    IconData icon,
    Color color,
  ) {
    return InkWell(
      onTap: () => setState(() {
        _selectedIndex = 1;
        _activeProjectId = null;
      }),
      borderRadius: BorderRadius.circular(14),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: color.withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: color, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    description,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.white.withOpacity(0.5),
                    ),
                  ),
                ],
              ),
            ),
            Icon(
              Icons.chevron_right_rounded,
              color: Colors.white.withOpacity(0.3),
              size: 20,
            ),
          ],
        ),
      ),
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

  void _openCollaborationHub() {
    setState(() {
      _selectedIndex = 3;
      _activeProjectId = null;
    });
  }

  void _openProjectById(int projectId, {int tab = 0}) {
    setState(() {
      _selectedIndex = 3;
      _activeProjectId = projectId;
      _projectDetailTab = tab;
    });
  }

  void _openProject(Map<String, dynamic> p, {int tab = 0}) {
    final id = p['id'] as int?;
    if (id == null) return;
    _openProjectById(id, tab: tab);
  }

  Widget _buildSharedProjectsSection() {
    return Consumer<CollaborationProvider>(
      builder: (context, vc, _) {
        final projects = vc.projects;
        final recent = projects.take(3).toList();

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Text(
                  'Recent collaborations',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(width: 8),
                if (projects.isNotEmpty)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: const Color(0xFF10B981).withOpacity(0.15),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      '${projects.length}',
                      style: const TextStyle(
                        color: Color(0xFF10B981),
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                const Spacer(),
                TextButton(
                  onPressed: _openCollaborationHub,
                  style: TextButton.styleFrom(
                    foregroundColor: const Color(0xFF6366F1),
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                  ),
                  child: const Text('View all'),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (vc.loading && projects.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              )
            else if (projects.isEmpty)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: const Color(0xFF161B22),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.white.withOpacity(0.1)),
                ),
                child: Column(
                  children: [
                    Icon(Icons.people_outline, size: 32, color: Colors.white.withOpacity(0.3)),
                    const SizedBox(height: 8),
                    Text(
                      'No collaborations yet',
                      style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 13),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Create or join a project from Collaboration',
                      style: TextStyle(color: Colors.white.withOpacity(0.35), fontSize: 12),
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton(
                      onPressed: _openCollaborationHub,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: const Color(0xFF10B981),
                        side: const BorderSide(color: Color(0xFF10B981)),
                      ),
                      child: const Text('Open Collaboration'),
                    ),
                  ],
                ),
              )
            else
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: recent
                    .map(
                      (p) => ProjectCard(
                        project: p,
                        onTap: () => _openProject(p),
                      ),
                    )
                    .toList(),
              ),
          ],
        );
      },
    );
  }

  Widget _buildQuickActionsSection({bool compact = false}) {
    final actions = [
      (
        'New Report',
        'Start or use a template',
        Icons.description_outlined,
        const Color(0xFF3B82F6),
        () => setState(() {
              _selectedIndex = 1;
              _activeProjectId = null;
            }),
      ),
      (
        'Import',
        'Upload a document',
        Icons.upload_file_outlined,
        const Color(0xFF8B5CF6),
        () => setState(() {
              _selectedIndex = 1;
              _activeProjectId = null;
            }),
      ),
      (
        'Templates',
        'Browse formats',
        Icons.layers_outlined,
        const Color(0xFF06B6D4),
        () => setState(() {
              _selectedIndex = 5;
              _activeProjectId = null;
            }),
      ),
      (
        'Collaborate',
        'Work with team',
        Icons.people_outline,
        const Color(0xFF10B981),
        _openCollaborationHub,
      ),
    ];

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
        const SizedBox(height: 14),
        if (compact)
          LayoutBuilder(
            builder: (context, constraints) {
              const gap = 10.0;
              final width = (constraints.maxWidth - gap) / 2;
              return Wrap(
                spacing: gap,
                runSpacing: gap,
                children: actions
                    .map(
                      (a) => SizedBox(
                        width: width,
                        child: _buildQuickActionCard(
                          a.$1,
                          a.$2,
                          a.$3,
                          a.$4,
                          onTap: a.$5,
                          compact: true,
                        ),
                      ),
                    )
                    .toList(),
              );
            },
          )
        else
          Row(
            children: [
              for (var i = 0; i < actions.length; i++) ...[
                if (i > 0) const SizedBox(width: 16),
                Expanded(
                  child: _buildQuickActionCard(
                    actions[i].$1,
                    actions[i].$2,
                    actions[i].$3,
                    actions[i].$4,
                    onTap: actions[i].$5,
                  ),
                ),
              ],
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
    bool compact = false,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        child: Container(
          decoration: BoxDecoration(
            color: const Color(0xFF161B22),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: Colors.white.withOpacity(0.1),
            ),
          ),
          padding: EdgeInsets.all(compact ? 14 : 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: EdgeInsets.all(compact ? 8 : 10),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: color, size: compact ? 18 : 20),
              ),
              SizedBox(height: compact ? 10 : 12),
              Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: compact ? 13 : 13,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                description,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: compact ? 11 : 11,
                  fontWeight: FontWeight.w400,
                  color: Colors.white.withOpacity(0.5),
                  height: 1.35,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildNewReportPage() {
    return NewReportScreen(
      selectedTemplate: _selectedTemplate,
      embedded: true,
    );
  }

  void _openAnalyzeScreen(Map<String, dynamic> doc) {
    final docId = doc['id'] as int?;
    final templateId = doc['template_id'] as int?;
    if (docId == null || templateId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Cannot analyze — document info is missing'),
          backgroundColor: Color(0xFFEF4444),
        ),
      );
      return;
    }

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => AnalyzeScreen(
          documentId: docId,
          documentName: doc['filename'] as String? ?? 'Document',
          templateId: templateId,
          templateName: doc['template_name'] as String? ?? 'Template',
        ),
      ),
    ).then((_) {
      final auth = context.read<AuthProvider>();
      if (auth.userId != null) {
        context.read<DocumentProvider>().fetchDocuments(auth.userId!);
      }
    });
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
        
        final compact = isCompact(context);

        return RefreshIndicator(
          onRefresh: () => docProvider.fetchDocuments(auth.userId!),
          color: const Color(0xFF3B82F6),
          backgroundColor: const Color(0xFF161B22),
          child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: EdgeInsets.fromLTRB(
            compact ? 16 : 32,
            compact ? 12 : 32,
            compact ? 16 : 32,
            compact ? 100 : 32,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Search, Filter, Sort Bar
              if (compact) ...[
                Container(
                  decoration: BoxDecoration(
                    color: const Color(0xFF161B22),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: Colors.white.withOpacity(0.1)),
                  ),
                  padding: const EdgeInsets.symmetric(horizontal: 12),
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
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: _buildReportsMenuButton(
                        icon: Icons.filter_list,
                        label: 'Filter',
                        items: const [
                          PopupMenuItem(value: 'all', child: Text('All Reports')),
                          PopupMenuItem(value: 'completed', child: Text('Completed')),
                          PopupMenuItem(value: 'in_progress', child: Text('In Progress')),
                          PopupMenuItem(value: 'draft', child: Text('Drafts')),
                        ],
                        onSelected: (value) {
                          setState(() {
                            _selectedFilter = value;
                            _currentPage = 1;
                          });
                        },
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _buildReportsMenuButton(
                        icon: Icons.swap_vert,
                        label: 'Sort',
                        items: const [
                          PopupMenuItem(value: 'recent', child: Text('Most Recent')),
                          PopupMenuItem(value: 'name', child: Text('Name A-Z')),
                        ],
                        onSelected: (value) {
                          setState(() {
                            _sortBy = value;
                            _currentPage = 1;
                          });
                        },
                      ),
                    ),
                  ],
                ),
              ] else
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
              const SizedBox(height: 20),
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
              SizedBox(height: compact ? 20 : 32),
              // Grid / list of Reports
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
              else if (compact)
                Column(
                  children: [
                    for (final doc in paginatedDocs)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: _buildMobileReportCard(doc),
                      ),
                  ],
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
                                        flex: 2,
                                        child: ElevatedButton.icon(
                                          onPressed: () => _openAnalyzeScreen(doc),
                                          icon: const Icon(Icons.analytics_outlined, size: 14),
                                          label: const Text(
                                            'Analyze',
                                            style: TextStyle(
                                              fontSize: 12,
                                              fontWeight: FontWeight.w600,
                                            ),
                                          ),
                                          style: ElevatedButton.styleFrom(
                                            backgroundColor: const Color(0xFF10B981),
                                            foregroundColor: Colors.white,
                                            padding: const EdgeInsets.symmetric(vertical: 8),
                                            shape: RoundedRectangleBorder(
                                              borderRadius: BorderRadius.circular(6),
                                            ),
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: 6),
                                      Expanded(
                                        child: OutlinedButton(
                                          onPressed: () {
                                            _showEditDialog(doc, auth.userId!);
                                          },
                                          style: OutlinedButton.styleFrom(
                                            foregroundColor: const Color(0xFF3B82F6),
                                            side: const BorderSide(color: Color(0xFF3B82F6)),
                                            padding: const EdgeInsets.symmetric(vertical: 8),
                                            shape: RoundedRectangleBorder(
                                              borderRadius: BorderRadius.circular(6),
                                            ),
                                          ),
                                          child: const Text(
                                            'Edit',
                                            style: TextStyle(
                                              fontSize: 11,
                                              fontWeight: FontWeight.w600,
                                            ),
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: 4),
                                      IconButton(
                                        onPressed: () {
                                          _handleDownload(doc);
                                        },
                                        icon: const Icon(Icons.download, size: 16),
                                        tooltip: 'Download',
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
                                          if (value == 'analyze') {
                                            _openAnalyzeScreen(doc);
                                          } else if (value == 'preview') {
                                            _showPreview(doc);
                                          } else if (value == 'download') {
                                            _handleDownload(doc);
                                          } else if (value == 'share') {
                                            _handleShare(doc);
                                          } else if (value == 'delete') {
                                            _handleDelete(doc);
                                          }
                                        },
                                        itemBuilder: (context) => const [
                                          PopupMenuItem(
                                            value: 'analyze',
                                            child: Row(
                                              children: [
                                                Icon(Icons.analytics_outlined, size: 16, color: Color(0xFF10B981)),
                                                SizedBox(width: 8),
                                                Text('Analyze'),
                                              ],
                                            ),
                                          ),
                                          PopupMenuItem(
                                            value: 'preview',
                                            child: Row(
                                              children: [
                                                Icon(Icons.preview, size: 16),
                                                SizedBox(width: 8),
                                                Text('Preview'),
                                              ],
                                            ),
                                          ),
                                          PopupMenuItem(
                                            value: 'download',
                                            child: Row(
                                              children: [
                                                Icon(Icons.download, size: 16),
                                                SizedBox(width: 8),
                                                Text('Download'),
                                              ],
                                            ),
                                          ),
                                          PopupMenuItem(
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
        ),
        );
      },
    );
  }

  Widget _buildReportsMenuButton({
    required IconData icon,
    required String label,
    required List<PopupMenuEntry<String>> items,
    required ValueChanged<String> onSelected,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white.withOpacity(0.1)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
      child: PopupMenuButton<String>(
        onSelected: onSelected,
        itemBuilder: (_) => items,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: Colors.white.withOpacity(0.6), size: 18),
            const SizedBox(width: 8),
            Text(
              label,
              style: TextStyle(
                color: Colors.white.withOpacity(0.7),
                fontSize: 13,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMobileReportCard(Map<String, dynamic> doc) {
    final status = doc['status'] ?? 'draft';
    final statusColor = _getStatusColor(status);
    final statusLabel = _getStatusLabel(status);
    final iconColor = _getIconColor(status);

    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withOpacity(0.1)),
      ),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: iconColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.description_outlined, color: iconColor, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      doc['filename'] ?? 'Untitled',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      doc['template_name'] ?? 'No template',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.white.withOpacity(0.5),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  statusLabel,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    color: statusColor,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            'Modified ${_getTimeAgo(doc['created_at'] ?? DateTime.now())}',
            style: TextStyle(
              fontSize: 11,
              color: Colors.white.withOpacity(0.45),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            height: 40,
            child: ElevatedButton.icon(
              onPressed: () => _handleDownload(doc),
              icon: const Icon(Icons.download_rounded, size: 18),
              label: const Text(
                'Download',
                style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF3B82F6),
                foregroundColor: Colors.white,
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
              ),
            ),
          ),
        ],
      ),
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
        return const Color(0xFF10B981);
      case 'processing':
        return const Color(0xFFEAB308);
      case 'uploaded':
      case 'pending':
        return const Color(0xFF6366F1);
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
      case 'uploaded':
      case 'pending':
        return 'Ready to Analyze';
      case 'draft':
        return 'Draft';
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
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () => _logout(context),
                  icon: const Icon(Icons.logout_rounded),
                  label: const Text('Sign Out'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.white,
                    side: BorderSide(color: Colors.white.withOpacity(0.2)),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
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
                              _activeProjectId = null;
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
  // Mobile Reports: only PDF / Word → save to phone files.
  if (isCompact(context)) {
    _showMobileDownloadSheet(doc);
    return;
  }

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

  void _showMobileDownloadSheet(Map<String, dynamic> doc) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: const Color(0xFF161B22),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
      ),
      builder: (sheetContext) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Center(
                  child: Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(999),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                const Text(
                  'Download as',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  'File will be saved to your phone',
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.5),
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 16),
                _mobileDownloadOption(
                  icon: Icons.picture_as_pdf_rounded,
                  color: const Color(0xFFDC2626),
                  title: 'PDF',
                  subtitle: 'Best for viewing and sharing',
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _downloadToPhone(doc, 'pdf');
                  },
                ),
                const SizedBox(height: 10),
                _mobileDownloadOption(
                  icon: Icons.description_rounded,
                  color: const Color(0xFF2563EB),
                  title: 'Word',
                  subtitle: 'Editable .docx document',
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _downloadToPhone(doc, 'docx');
                  },
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _mobileDownloadOption({
    required IconData icon,
    required Color color,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
  }) {
    return Material(
      color: const Color(0xFF0D1117),
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.white.withOpacity(0.1)),
          ),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: color.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: color, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: TextStyle(
                        color: Colors.white.withOpacity(0.5),
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.download_rounded,
                color: Colors.white.withOpacity(0.35),
                size: 20,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _downloadToPhone(Map<String, dynamic> doc, String format) async {
    final docProvider = context.read<DocumentProvider>();
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please sign in again to download'),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

    final label = format == 'pdf' ? 'PDF' : 'Word';
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(
        child: CircularProgressIndicator(color: Color(0xFF3B82F6)),
      ),
    );

    try {
      final success = await docProvider.downloadFormattedDocument(
        doc['id'] as int,
        userId,
        format: format,
      );
      if (!mounted) return;
      Navigator.of(context, rootNavigator: true).pop(); // close loading

      final path = docProvider.lastDownloadedPath;
      if (!success || path == null || path.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Download failed: ${docProvider.errorMessage ?? 'Unknown error'}',
            ),
            backgroundColor: Colors.red,
          ),
        );
        return;
      }

      final where = Platform.isAndroid ? 'Downloads' : 'Files';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('$label saved to $where'),
          backgroundColor: const Color(0xFF10B981),
          action: SnackBarAction(
            label: 'Open',
            textColor: Colors.white,
            onPressed: () => OpenFile.open(path),
          ),
        ),
      );

      // iOS: also open share sheet so user can save to Files app.
      if (Platform.isIOS) {
        await SharePlus.instance.share(
          ShareParams(
            files: [XFile(path)],
            subject: path.split(Platform.pathSeparator).last,
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      Navigator.of(context, rootNavigator: true).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Download error: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  /// Mobile-only: save via [downloadFormattedDocument], then share with share_plus
  /// (same SharePlus.instance.share / ShareParams pattern as MobileQrDownloadScreen).
  void _handleShare(Map<String, dynamic> doc) {
    showDialog(
      context: context,
      builder: (dialogContext) => ExportDialog(
        onExport: (format, {bool applyBullets = true, bool autoDetect = true}) async {
          final docProvider = context.read<DocumentProvider>();
          final userId = context.read<AuthProvider>().userId;
          if (userId == null) return;

          try {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Preparing $format for share...'),
                backgroundColor: const Color(0xFF3B82F6),
              ),
            );

            final success = await docProvider.downloadFormattedDocument(
              doc['id'],
              userId,
              format: format,
              applyBullets: applyBullets,
              autoDetectBullets: autoDetect,
            );

            final path = docProvider.lastDownloadedPath;
            if (!success || path == null || path.isEmpty) {
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      'Share failed: ${docProvider.errorMessage ?? 'Could not save file'}',
                    ),
                    backgroundColor: Colors.red,
                  ),
                );
              }
              return;
            }

            final fileName = path.split(Platform.pathSeparator).last;
            await SharePlus.instance.share(
              ShareParams(
                files: [XFile(path)],
                subject: fileName,
              ),
            );
          } catch (e) {
            if (mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('Share error: $e'),
                  backgroundColor: Colors.red,
                ),
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