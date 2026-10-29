import 'dart:async';
import 'dart:convert';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:frontend/providers/qr_service.dart';
import 'package:frontend/widgets/qr_dialog.dart';
import 'package:provider/provider.dart';
import 'dart:io';
import '../widgets/analysis_jobs_sidebar_item.dart';
import '../utils/analysis_nav.dart';
import 'package:file_picker/file_picker.dart';
import 'package:share_plus/share_plus.dart';
import 'package:open_file_plus/open_file_plus.dart';
import '../config/dev_user_config.dart';
import '../providers/auth_provider.dart';
import '../providers/document_provider.dart';
import '../providers/template_provider.dart';
import '../providers/collaboration_provider.dart';
import '../providers/fyp_provider.dart';
import '../utils/logout_confirm.dart';
import '../theme/app_theme.dart';
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
import '../widgets/student/desktop_semester_deadline_card.dart';
import '../utils/responsive.dart';
import 'mobile_companion_screen.dart';
import '../widgets/document_preview_panel.dart'; 
import '../providers/lang_provider.dart';
import '../widgets/tr.dart';

/// Mobile bottom-nav → existing `_selectedIndex` targets.
/// Notifications has no desktop sidebar entry; uses [kNotificationsTabIndex].
const int kNotificationsTabIndex = 13;

class _MobileNavItem {
  final int tabIndex;
  final IconData icon;
  final String label;

  const _MobileNavItem(this.tabIndex, this.icon, this.label);
}

const List<_MobileNavItem> _kMobileNavItemsCore = [
  _MobileNavItem(0, Icons.dashboard_outlined, 'Dashboard'),
  _MobileNavItem(kNotificationsTabIndex, Icons.notifications_outlined, 'Notifications'),
  _MobileNavItem(2, Icons.folder_outlined, 'Reports'),
];

const List<_MobileNavItem> _kMobileNavItemsFyp = [
  _MobileNavItem(0, Icons.dashboard_outlined, 'Dashboard'),
  _MobileNavItem(8, Icons.checklist_outlined, 'Milestones'),
  _MobileNavItem(kNotificationsTabIndex, Icons.notifications_outlined, 'Notifications'),
  _MobileNavItem(2, Icons.folder_outlined, 'Reports'),
];

List<_MobileNavItem> get _mobileNavItems =>
    DevUserConfig.hasFypModule ? _kMobileNavItemsFyp : _kMobileNavItemsCore;

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
  AppPalette _p = AppPalette.dark;
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
  AnalysisRequest? _activeAnalysis;
  void _onAnalysisRequest() {
  if (!mounted) return;
  final req = AnalysisNav.request.value;
  setState(() {
    _activeAnalysis = req;
    if (req != null) _selectedIndex = 2;
  });
  if (req == null) {
    final uid = context.read<AuthProvider>().userId;
    if (uid != null) context.read<DocumentProvider>().fetchDocuments(uid);
  }
}
@override
void initState() {
  super.initState();
  _selectedIndex = widget.initialIndex.clamp(0, kNotificationsTabIndex);
  _activeProjectId = widget.initialProjectId;
  _projectDetailTab = widget.initialProjectTab;

  final pending = AnalysisNav.request.value;
  if (pending != null) {
    _activeAnalysis = pending;
    _selectedIndex = 2;
  }

  AnalysisNav.attach(this);
  AnalysisNav.request.addListener(_onAnalysisRequest);
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
        final email = (auth.userEmail ?? auth.email ?? '').trim();
        if (DevUserConfig.hasFypModule && email.isNotEmpty) {
          context.read<FypProvider>().fetchAssignmentStatus(
                userId: auth.userId!,
                email: email,
              );
        }
        //Start auto-refresh polling every 30 seconds
        _refreshTimer = Timer.periodic(Duration(seconds: 10), (_) {
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
    AnalysisNav.detach(this);
AnalysisNav.request.removeListener(_onAnalysisRequest);
   _refreshTimer?.cancel();
    super.dispose();
  }

  /// Dark-only card chrome; light keeps prior radius/border/no extra shadow.
  BoxDecoration _cardDeco({Color? color, double lightRadius = 12}) =>
      BoxDecoration(
        color: color ?? _p.surface,
        borderRadius: BorderRadius.circular(
          _p.isDark ? _p.cardRadius : lightRadius,
        ),
        border: Border.all(color: _p.isDark ? _p.borderStrong : _p.border),
        boxShadow: _p.isDark ? _p.cardShadow : null,
      );

  @override
  Widget build(BuildContext context) {
    final compact = isCompact(context);
    _p = context.watch<ThemeProvider>().palette;

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: _p.ambientGlowBackdrop(
        child: compact
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
      ),
      bottomNavigationBar: compact ? _buildMobileBottomNav() : null,
    );
  }

  Widget _buildMobileBottomNav() {
    final items = _mobileNavItems;
    final selectedNav = items.indexWhere(
      (item) => item.tabIndex == _selectedIndex,
    );

    return Container(
      decoration: BoxDecoration(
        color: _p.isDark ? _p.topBarBg : _p.surface,
        border: Border(
          top: BorderSide(color: _p.isDark ? _p.borderStrong : _p.border),
        ),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 64,
          child: Row(
            children: [
              for (var i = 0; i < items.length; i++)
                Expanded(
                  child: _buildMobileNavButton(
                    item: items[i],
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
        ? _p.accent
        : _p.iconMuted;

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
          SizedBox(height: 4),
          Tr(
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
        color: _p.sidebarBg,
        border: Border(
          right: BorderSide(
            color: _p.isDark ? _p.borderStrong : _p.border,
          ),
        ),
      ),
      child: Column(
        children: [
          Padding(
            padding: EdgeInsets.all(20),
            child: Row(
              children: [
                Container(
                  padding: EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: _p.accent,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Icon(
                    Icons.description,
                    color: Colors.white,
                    size: 20,
                  ),
                ),
                SizedBox(width: 12),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Tr(
                      'FORMATIFY',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: _p.textPrimary,
                      ),
                    ),
                    Tr(
                      'Academic Edition',
                      style: TextStyle(
                        fontSize: 10,
                        color: _p.textPrimary,
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
              padding: EdgeInsets.symmetric(vertical: 8),
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
                const AnalysisJobsSidebarItem(),
                _buildSidebarItem(
                  3,
                  Icons.people_outline,
                  'Collaboration',
                ),
                _buildSidebarItem(
                  5,
                  Icons.layers,
                  'Templates',
                ),
                if (DevUserConfig.hasFypModule) ...[
                  Consumer<FypProvider>(
                    builder: (context, fyp, _) {
                      if (!fyp.canChooseSupervisor) {
                        return const SizedBox.shrink();
                      }
                      return _buildSidebarItem(
                        6,
                        Icons.school_outlined,
                        'ChooseSupervisor',
                      );
                    },
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
                ],
                _buildSidebarItem(
                  12,
                  Icons.settings,
                  'Settings',
                ),
              ],
            ),
          ),
          Padding(
            padding: EdgeInsets.all(16),
            child: Container(
              decoration: BoxDecoration(
                color: _p.surfaceAlt,
                borderRadius: BorderRadius.circular(
                  _p.isDark ? _p.cardRadius : 8,
                ),
                border: Border.all(
                  color: _p.isDark ? _p.borderStrong : _p.border,
                ),
                boxShadow: _p.isDark ? _p.cardShadow : null,
              ),
              child: Padding(
                padding: EdgeInsets.all(12),
                child: Consumer<AuthProvider>(
                  builder: (context, auth, _) {
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          width: 32,
                          height: 32,
                          decoration: BoxDecoration(
                            color: _p.accent,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Center(
                            child: Text(
                              (auth.currentUser?.isNotEmpty ?? false)
                                  ? auth.currentUser![0].toUpperCase()
                                  : 'U',
                              style: TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ),
                        SizedBox(height: 12),
                        Text(
                          auth.currentUser ?? 'User',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: _p.textPrimary,
                          ),
                        ),
                        Text(
                          DevUserConfig.displayRoleLabel(auth.userRole),
                          style: TextStyle(
                            fontSize: 11,
                            color: _p.textSecondary,
                            fontWeight: FontWeight.w400,
                          ),
                        ),
                        SizedBox(height: 12),
                        SizedBox(
                          width: double.infinity,
                          height: 32,
                          child: ElevatedButton.icon(
                            onPressed: () => _logout(context),
                            icon: Icon(Icons.logout, size: 14, color: Colors.white),
                            label: Tr(
                              'Logout',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: Colors.white,
                              ),
                            ),
                            style: ElevatedButton.styleFrom(
                              foregroundColor: Colors.white,
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
    margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
    decoration: BoxDecoration(
      color: isSelected ? _p.accentSoft : Colors.transparent,
      borderRadius: BorderRadius.circular(10),
      border: isSelected
          ? Border.all(color: _p.accent, width: 1.5)
          : null,
    ),
    child: InkWell(
      borderRadius: BorderRadius.circular(10),
      onTap: () {
        AnalysisNav.request.value = null;

        setState(() {
          _selectedIndex = index;
          _activeProjectId = null;
          _activeAnalysis = null;
        });
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 12,
        ),
        child: Row(
          children: [
            Icon(
              icon,
              size: 20,
              color: isSelected ? _p.accent : _p.textSecondary,
            ),
            const SizedBox(width: 12),

            Expanded(
              child: Tr(
                label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight:
                      isSelected ? FontWeight.w600 : FontWeight.w400,
                  color: isSelected ? _p.accent : _p.textSecondary,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
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

    // Soften university/FYP wording for core-only orgs.
    if (!DevUserConfig.hasFypModule) {
      descriptions[5] = 'Choose from pre-built report templates';
      descriptions[13] = 'Updates and account notifications';
    }
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
        color: _p.topBarBg,
        border: Border(
          bottom: BorderSide(
            color: _p.isDark ? _p.borderStrong : _p.border,
          ),
        ),
        boxShadow: _p.cardShadow,
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
                Tr(
                  title,
                  style: TextStyle(
                    fontSize: compact ? 20 : 28,
                    fontWeight: FontWeight.w700,
                    color: _p.textPrimary,
                  ),
                ),
                if (!compact || _selectedIndex == 0)
                  Tr(
                    description,
                    maxLines: compact ? 1 : 3,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 13,
                      color: _p.textSecondary,
                      fontWeight: FontWeight.w400,
                    ),
                  ),
              ],
            ),
          ),
          if (!compact)
            Row(
              children: [
                NotificationsPanelButton(),
                SizedBox(width: 12),
                GestureDetector(
                  onTap: () {
                    setState(() {
                      _selectedIndex = 1;
                      _activeProjectId = null;
                    });
                  },
                  child: Container(
                    padding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: _p.accent,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.add, size: 18, color: Colors.white),
                        SizedBox(width: 6),
                        Tr(
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
              icon: Icon(Icons.logout_rounded, color: _p.textSecondary),
            ),
        ],
      ),
      ),
    );
  }

  Widget _buildBody() {
    if (_activeAnalysis != null) {
    final r = _activeAnalysis!;
    return AnalyzeScreen(
      key: ValueKey('analysis-${r.documentId}-${r.freeform}'),
      documentId: r.documentId,
      documentName: r.documentName,
      templateId: r.templateId,
      templateName: r.templateName,
      freeformAnalysis: r.freeform,
      embedded: true,
    );
  }
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
        // AI Tools tab removed — bounce back to Dashboard.
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (!mounted) return;
          if (_selectedIndex == 4) {
            setState(() {
              _selectedIndex = 0;
              _activeProjectId = null;
            });
          }
        });
        return _buildDashboardContent();
      case 5:
        WidgetsBinding.instance.addPostFrameCallback((_) {
          final auth = context.read<AuthProvider>();
          if (auth.userId != null) {
            context.read<TemplateProvider>().fetchUserTemplates(auth.userId!);
          }
        });
        return _buildTemplatesPage();
      case 6:
      case 7:
      case 8:
      case 9:
      case 10:
      case 11:
        if (!DevUserConfig.hasFypModule) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (!mounted) return;
            if (_selectedIndex >= 6 && _selectedIndex <= 11) {
              setState(() {
                _selectedIndex = 0;
                _activeProjectId = null;
              });
            }
          });
          return _buildDashboardContent();
        }
        switch (_selectedIndex) {
          case 6:
            // After choosing (pending/accepted), leave this screen permanently.
            if (context.watch<FypProvider>().hasChosenSupervisor) {
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (!mounted) return;
                if (_selectedIndex == 6) {
                  setState(() {
                    _selectedIndex = 7;
                    _activeProjectId = null;
                  });
                }
              });
              return MySupervisorScreen(
                onChooseSupervisor: () => setState(() {
                  _selectedIndex = 6;
                  _activeProjectId = null;
                }),
              );
            }
            return SupervisorSelectionScreen(
              onRequestSubmitted: () => setState(() {
                _selectedIndex = 7;
                _activeProjectId = null;
              }),
            );
          case 7:
            return MySupervisorScreen(
              onChooseSupervisor: context.watch<FypProvider>().canChooseSupervisor
                  ? () => setState(() {
                        _selectedIndex = 6;
                        _activeProjectId = null;
                      })
                  : null,
            );
          case 8:
            return FypMilestonesScreen(
              onChooseSupervisor: context.watch<FypProvider>().canChooseSupervisor
                  ? () => setState(() {
                        _selectedIndex = 6;
                        _activeProjectId = null;
                      })
                  : null,
              onOpenMySupervisor: () => setState(() {
                _selectedIndex = 7;
                _activeProjectId = null;
              }),
            );
          case 9:
            return const StudentMeetingNotesScreen();
          case 10:
            return PlagiarismReportScreen(
              onChooseSupervisor: context.watch<FypProvider>().canChooseSupervisor
                  ? () => setState(() {
                        _selectedIndex = 6;
                        _activeProjectId = null;
                      })
                  : null,
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
              onChooseSupervisor: context.watch<FypProvider>().canChooseSupervisor
                  ? () => setState(() {
                        _selectedIndex = 6;
                        _activeProjectId = null;
                      })
                  : null,
              onOpenMySupervisor: () => setState(() {
                _selectedIndex = 7;
                _activeProjectId = null;
              }),
              onUploadNewVersion: () => setState(() {
                _selectedIndex = 1;
                _activeProjectId = null;
              }),
            );
          default:
            return const SizedBox.shrink();
        }
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
                if (DevUserConfig.hasFypModule) ...[
                  const MobileStatusSummaryCard(),
                  SizedBox(height: 16),
                ],
                _buildSendFromPhoneCard(),
                SizedBox(height: 20),
              ] else ...[
                if (DevUserConfig.hasFypModule) ...[
                  const DesktopSemesterDeadlineCard(),
                  SizedBox(height: 20),
                ],
              ],
              _buildStatsRow(compact: compact, totalReports: totalReports, draftCount: draftCount, completedCount: completedCount),
              SizedBox(height: 28),
              if (compact) ...[
                _buildRecentReportsSection(docProvider.documents),
                SizedBox(height: 24),
                _buildAIToolsSection(compact: true),
                SizedBox(height: 24),
                _buildSharedProjectsSection(),
                SizedBox(height: 24),
                _buildQuickActionsSection(compact: true),
              ] else ...[
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      flex: 2,
                      child: _buildRecentReportsSection(docProvider.documents),
                    ),
                    SizedBox(width: 16),
                    Expanded(
                      child: _buildAIToolsSection(compact: false),
                    ),
                  ],
                ),
                SizedBox(height: 32),
                _buildSharedProjectsSection(),
                SizedBox(height: 32),
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
        borderRadius: BorderRadius.circular(
          _p.isDark ? _p.cardRadius : 12,
        ),
        child: Container(
          width: double.infinity,
          padding: EdgeInsets.all(16),
          decoration: _cardDeco(),
          child: Row(
            children: [
              Container(
                padding: EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: _p.accentSoft,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(
                  Icons.qr_code_scanner_rounded,
                  color: _p.accent,
                  size: 22,
                ),
              ),
              SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Tr(
                      'Send Document from Phone',
                      style: TextStyle(
                        color: _p.textPrimary,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    SizedBox(height: 4),
                    Tr(
                      'Scan QR, camera, or gallery upload',
                      style: TextStyle(
                        color: _p.textSecondary,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.chevron_right,
                color: _p.textMuted,
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
        changeColor: Color(0xFF10B981),
        compact: compact,
      ),
      _buildStatCard(
        title: 'Active Drafts',
        value: draftCount.toString(),
        change: 'In Progress',
        icon: Icons.history,
        changeColor: Color(0xFFD97706),
        compact: compact,
      ),
      _buildStatCard(
        title: 'Completed',
        value: completedCount.toString(),
        change: '+8%',
        icon: Icons.check_circle,
        changeColor: Color(0xFF10B981),
        compact: compact,
      ),
      _buildStatCard(
        title: 'AI Suggestions Used',
        value: (totalReports * 5).toString(),
        change: 'AI',
        icon: Icons.auto_awesome,
        changeColor: Color(0xFF8B5CF6),
        compact: compact,
      ),
    ];

    // Phones (~360–430px): 2×2 grid so labels/badges never overflow card edges.
    if (compact) {
      return LayoutBuilder(
        builder: (context, constraints) {
          final gap = 16.0;
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
          if (i > 0) SizedBox(width: 24),
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
      decoration: _cardDeco(),
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
              SizedBox(width: 8),
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
              color: _p.textPrimary,
            ),
          ),
          SizedBox(height: compact ? 2 : 4),
          Tr(
            title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: compact ? 11 : 13,
              fontWeight: FontWeight.w400,
              color: _p.textSecondary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecentReportsSection(List<Map<String, dynamic>> documents) {
    final recentDocs = documents.take(4).toList();

    return Container(
      decoration: _cardDeco(),
      padding: EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Tr(
                'Recent Reports',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: _p.textPrimary,
                ),
              ),
              GestureDetector(
                onTap: () {
                  setState(() {
                    _selectedIndex = 2;
                    _activeProjectId = null;
                  });
                },
                child: Tr(
                  'View All',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: _p.accent,
                  ),
                ),
              ),
            ],
          ),
          SizedBox(height: 16),
          if (recentDocs.isEmpty)
            Center(
              child: Padding(
                padding: EdgeInsets.symmetric(vertical: 24),
                child: Tr(
                  'No reports yet',
                  style: TextStyle(
                    fontSize: 13,
                    color: _p.textSecondary,
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
              final statusColor = status == 'formatted' ? Color(0xFF10B981) : status == 'processing' ? Color(0xFFD97706) : _p.accent;
              
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
                  if (!isLast) SizedBox(height: 12),
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
          padding: EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: iconColor.withOpacity(0.15),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, color: iconColor, size: 18),
        ),
        SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Tr(
                title,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: _p.textPrimary,
                ),
              ),
              Tr(
                subtitle,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w400,
                  color: _p.textSecondary,
                ),
              ),
            ],
          ),
        ),
        Container(
          padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: statusColor.withOpacity(0.15),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Tr(
            status,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: statusColor,
            ),
          ),
        ),
        SizedBox(width: 8),
        Icon(
          Icons.more_vert,
          size: 16,
          color: _p.textMuted,
        ),
      ],
    );
  }

  Widget _buildAIToolsSection({bool compact = false}) {
    final tools = [
      (
        'Auto Format',
        DevUserConfig.hasFypModule
            ? 'Format to academic standards'
            : 'Format to your org template',
        Icons.auto_awesome,
        _p.accent,
      ),
      (
        'Citation Helper',
        'APA, MLA, Chicago citations',
        Icons.format_quote,
        Color(0xFF8B5CF6),
      ),
      (
        'Grammar Check',
        'Academic writing suggestions',
        Icons.check_circle_outline,
        Color(0xFF10B981),
      ),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Tr(
          'AI Formatting Tools',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: _p.textPrimary,
          ),
        ),
        SizedBox(height: 14),
        if (compact)
          Container(
            decoration: _cardDeco(lightRadius: 14),
            child: Column(
              children: [
                for (var i = 0; i < tools.length; i++) ...[
                  if (i > 0)
                    Divider(
                      height: 1,
                      color: _p.border,
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
              if (i > 0) SizedBox(height: 12),
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
      borderRadius: BorderRadius.circular(
        _p.isDark ? _p.cardRadius : 14,
      ),
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: 14, vertical: 12),
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
            SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Tr(
                    title,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: _p.textPrimary,
                    ),
                  ),
                  SizedBox(height: 2),
                  Tr(
                    description,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 12,
                      color: _p.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
            Icon(
              Icons.chevron_right_rounded,
              color: _p.textMuted,
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
      decoration: _cardDeco(),
      padding: EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: color, size: 18),
              ),
              SizedBox(width: 12),
              Expanded(
                child: Tr(
                  title,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: _p.textPrimary,
                  ),
                ),
              ),
            ],
          ),
          SizedBox(height: 8),
          Tr(
            description,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w400,
              color: _p.textSecondary,
              height: 1.4,
            ),
          ),
          SizedBox(height: 12),
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
              child: Tr(
                'Use Tool',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: _p.textPrimary,
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
                Tr(
                  'Recent collaborations',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: _p.textPrimary,
                  ),
                ),
                SizedBox(width: 8),
                if (projects.isNotEmpty)
                  Container(
                    padding: EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: Color(0xFF10B981).withOpacity(0.15),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      '${projects.length}',
                      style: TextStyle(
                        color: Color(0xFF10B981),
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                Spacer(),
                TextButton(
                  onPressed: _openCollaborationHub,
                  style: TextButton.styleFrom(
                    foregroundColor: Color(0xFF6366F1),
                    padding: EdgeInsets.symmetric(horizontal: 8),
                  ),
                  child: Tr('View all'),
                ),
              ],
            ),
            SizedBox(height: 16),
            if (vc.loading && projects.isEmpty)
              Center(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              )
            else if (projects.isEmpty)
              Container(
                width: double.infinity,
                padding: EdgeInsets.all(24),
                decoration: _cardDeco(),
                child: Column(
                  children: [
                    Icon(Icons.people_outline, size: 32, color: _p.textMuted),
                    SizedBox(height: 8),
                    Tr(
                      'No collaborations yet',
                      style: TextStyle(color: _p.textSecondary, fontSize: 13),
                    ),
                    SizedBox(height: 4),
                    Tr(
                      'Create or join a project from Collaboration',
                      style: TextStyle(color: _p.textMuted, fontSize: 12),
                    ),
                    SizedBox(height: 12),
                    OutlinedButton(
                      onPressed: _openCollaborationHub,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Color(0xFF10B981),
                        side: BorderSide(color: Color(0xFF10B981)),
                      ),
                      child: Tr('Open Collaboration'),
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
        _p.accent,
        () => setState(() {
              _selectedIndex = 1;
              _activeProjectId = null;
            }),
      ),
      (
        'Import',
        'Upload a document',
        Icons.upload_file_outlined,
        Color(0xFF8B5CF6),
        () => setState(() {
              _selectedIndex = 1;
              _activeProjectId = null;
            }),
      ),
      (
        'Templates',
        'Browse formats',
        Icons.layers_outlined,
        Color(0xFF06B6D4),
        () => setState(() {
              _selectedIndex = 5;
              _activeProjectId = null;
            }),
      ),
      (
        'Collaborate',
        'Work with team',
        Icons.people_outline,
        Color(0xFF10B981),
        _openCollaborationHub,
      ),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Tr(
          'Quick Actions',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: _p.textPrimary,
          ),
        ),
        SizedBox(height: 14),
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
                if (i > 0) SizedBox(width: 16),
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
          decoration: _cardDeco(lightRadius: 14),
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
              Tr(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: compact ? 13 : 13,
                  fontWeight: FontWeight.w600,
                  color: _p.textPrimary,
                ),
              ),
              SizedBox(height: 4),
              Tr(
                description,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: compact ? 11 : 11,
                  fontWeight: FontWeight.w400,
                  color: _p.textSecondary,
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
      SnackBar(
        content: Tr('Cannot analyze — document info is missing'),
        backgroundColor: Color(0xFFEF4444),
      ),
    );
    return;
  }

  AnalysisNav.open(AnalysisRequest(
    documentId: docId,
    documentName: doc['filename'] as String? ?? 'Document',
    templateId: templateId,
    templateName: doc['template_name'] as String? ?? 'Template',
  ));
}

Widget _buildMyReportsPage() {
    final auth = context.read<AuthProvider>();
    return Consumer<DocumentProvider>(
      builder: (context, docProvider, _) {
        // Apply search
        List<Map<String, dynamic>> filteredDocs = docProvider.documents
            .where((d) => (d['filename'] ?? '')
                .toLowerCase()
                .contains(_searchQuery.toLowerCase()))
            .toList();

        // Sort by recent or name
        if (_sortBy == 'name') {
          filteredDocs.sort((a, b) =>
              (a['filename'] ?? '').compareTo(b['filename'] ?? ''));
        } else {
          filteredDocs.sort((a, b) {
            final dateA = DateTime.tryParse(a['created_at'] ?? '') ?? DateTime.now();
            final dateB = DateTime.tryParse(b['created_at'] ?? '') ?? DateTime.now();
            return dateB.compareTo(dateA);
          });
        }

        // Calculate pagination
        int totalPages = (filteredDocs.length / _itemsPerPage).ceil();
        if (totalPages < 1) totalPages = 1;
        int startIndex = (_currentPage - 1) * _itemsPerPage;
        int endIndex = startIndex + _itemsPerPage;
        List<Map<String, dynamic>> paginatedDocs = filteredDocs.sublist(
            startIndex, endIndex > filteredDocs.length ? filteredDocs.length : endIndex);

        final compact = isCompact(context);

        return RefreshIndicator(
          onRefresh: () => docProvider.fetchDocuments(auth.userId!),
          color: _p.accent,
          backgroundColor: _p.surface,
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
                // Search + Sort only
                if (compact) ...[
                  Container(
                    decoration: BoxDecoration(
                      color: _p.surface,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: _p.border),
                    ),
                    padding: EdgeInsets.symmetric(horizontal: 12),
                    child: TextField(
                      onChanged: (value) {
                        setState(() {
                          _searchQuery = value;
                          _currentPage = 1;
                        });
                      },
                      style: TextStyle(color: _p.textPrimary),
                      decoration: InputDecoration(
                        hintText: 'Search reports...',
                        hintStyle: TextStyle(
                          color: _p.textMuted,
                          fontSize: 13,
                        ),
                        border: InputBorder.none,
                        prefixIcon: Icon(
                          Icons.search,
                          color: _p.textSecondary,
                          size: 20,
                        ),
                      ),
                    ),
                  ),
                  SizedBox(height: 10),
                  _buildReportsMenuButton(
                    icon: Icons.swap_vert,
                    label: _sortBy == 'name' ? 'Name A-Z' : 'Most Recent',
                    items: const [
                      PopupMenuItem(value: 'recent', child: Tr('Most Recent')),
                      PopupMenuItem(value: 'name', child: Tr('Name A-Z')),
                    ],
                    onSelected: (value) {
                      setState(() {
                        _sortBy = value;
                        _currentPage = 1;
                      });
                    },
                  ),
                ] else
                  Row(
                    children: [
                      Expanded(
                        flex: 2,
                        child: Container(
                          decoration: BoxDecoration(
                            color: _p.surface,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: _p.border,
                            ),
                          ),
                          padding: EdgeInsets.symmetric(horizontal: 16),
                          child: TextField(
                            onChanged: (value) {
                              setState(() {
                                _searchQuery = value;
                                _currentPage = 1;
                              });
                            },
                            style: TextStyle(color: _p.textPrimary),
                            decoration: InputDecoration(
                              hintText: 'Search reports...',
                              hintStyle: TextStyle(
                                color: _p.textMuted,
                                fontSize: 13,
                              ),
                              border: InputBorder.none,
                              prefixIcon: Icon(
                                Icons.search,
                                color: _p.textSecondary,
                                size: 20,
                              ),
                            ),
                          ),
                        ),
                      ),
                      SizedBox(width: 12),
                      Container(
                        decoration: BoxDecoration(
                          color: _p.surface,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: _p.border,
                          ),
                        ),
                        padding: EdgeInsets.symmetric(horizontal: 12),
                        child: PopupMenuButton<String>(
                          onSelected: (value) {
                            setState(() {
                              _sortBy = value;
                              _currentPage = 1;
                            });
                          },
                          itemBuilder: (context) => [
                            const PopupMenuItem(value: 'recent', child: Tr('Most Recent')),
                            const PopupMenuItem(value: 'name', child: Tr('Name A-Z')),
                          ],
                          child: Row(
                            children: [
                              Icon(Icons.swap_vert, color: _p.textSecondary, size: 18),
                              SizedBox(width: 8),
                              Tr(
                                _sortBy == 'name' ? 'Name A-Z' : 'Most Recent',
                                style: TextStyle(
                                  color: _p.textSecondary,
                                  fontSize: 13,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                SizedBox(height: compact ? 20 : 28),
                // Grid / list of Reports
                if (docProvider.isLoading)
                  Center(child: CircularProgressIndicator())
                else if (paginatedDocs.isEmpty)
                  Center(
                    child: Padding(
                      padding: EdgeInsets.symmetric(vertical: 48),
                      child: Column(
                        children: [
                          Icon(
                            Icons.folder_open,
                            size: 48,
                            color: _p.textMuted,
                          ),
                          SizedBox(height: 16),
                          Tr(
                            'No reports found',
                            style: TextStyle(
                              fontSize: 14,
                              color: _p.textSecondary,
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
                          padding: EdgeInsets.only(bottom: 10),
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
                      // Taller cards so Unformatted / Formatted actions fit cleanly.
                      childAspectRatio: 0.72,
                    ),
                    itemCount: paginatedDocs.length,
                    itemBuilder: (context, index) {
                      final doc = paginatedDocs[index];
                      final status = doc['status'] ?? 'draft';
                      final statusColor = _getStatusColor(status);
                      final statusLabel = _getStatusLabel(status);
                      final iconColor = _getIconColor(status);
                      final hasFormatted = doc['has_formatted'] == true;

                      return Container(
                        decoration: _cardDeco(),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(
                            _p.isDark ? _p.cardRadius : 12,
                          ),
                          child: Column(
                            children: [
                              // Top Section with Icon and Status Badge
                              Container(
                                height: 140,
                                decoration: BoxDecoration(
                                  color: iconColor.withOpacity(0.15),
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
                                        padding: EdgeInsets.symmetric(
                                          horizontal: 10,
                                          vertical: 6,
                                        ),
                                        decoration: BoxDecoration(
                                          color: statusColor.withOpacity(0.8),
                                          borderRadius: BorderRadius.circular(6),
                                        ),
                                        child: Tr(
                                          statusLabel,
                                          style: TextStyle(
                                            fontSize: 10,
                                            fontWeight: FontWeight.w600,
                                            color: _p.textPrimary,
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
                                  padding: EdgeInsets.all(16),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        doc['filename'] ?? 'Untitled',
                                        style: TextStyle(
                                          fontSize: 14,
                                          fontWeight: FontWeight.w600,
                                          color: _p.textPrimary,
                                        ),
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                      SizedBox(height: 6),
                                      Text(
                                        doc['template_name'] ?? 'No template',
                                        style: TextStyle(
                                          fontSize: 11,
                                          color: _p.textSecondary,
                                        ),
                                      ),
                                      SizedBox(height: 8),
                                      Text(
                                        'Modified ${_getTimeAgo(doc['created_at'] ?? DateTime.now())}',
                                        style: TextStyle(
                                          fontSize: 10,
                                          color: _p.textSecondary,
                                        ),
                                      ),
                                      if (hasFormatted) ...[
                                        SizedBox(height: 6),
                                        Container(
                                          padding: EdgeInsets.symmetric(
                                              horizontal: 8, vertical: 3),
                                          decoration: BoxDecoration(
                                            color: Color(0xFF10B981).withOpacity(0.12),
                                            borderRadius: BorderRadius.circular(6),
                                          ),
                                          child: Tr(
                                            'Both versions ready to download',
                                            style: TextStyle(
                                              fontSize: 10,
                                              fontWeight: FontWeight.w600,
                                              color: Color(0xFF059669),
                                            ),
                                          ),
                                        ),
                                      ],
                                      Spacer(),
                                      // "Download" label so users know these buttons export files
                                      Padding(
                                        padding: EdgeInsets.only(bottom: 6),
                                        child: Row(
                                          children: [
                                            Icon(
                                              Icons.download_rounded,
                                              size: 13,
                                              color: _p.textSecondary,
                                            ),
                                            SizedBox(width: 4),
                                            Tr(
                                              'Download',
                                              style: TextStyle(
                                                fontSize: 11,
                                                fontWeight: FontWeight.w600,
                                                color: _p.textSecondary,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                      // Version download buttons + actions menu
                                      Row(
                                        children: [
                                          Expanded(
                                            child: Tooltip(
                                              message:
                                                  'Download original file (unformatted)',
                                              child: OutlinedButton.icon(
                                                onPressed: () => _handleDownloadVersion(
                                                  doc,
                                                  version: 'unformatted',
                                                ),
                                                icon: Icon(
                                                  Icons.file_download_outlined,
                                                  size: 14,
                                                ),
                                                label: Tr(
                                                  'Unformatted',
                                                  style: TextStyle(
                                                    fontSize: 10,
                                                    fontWeight: FontWeight.w700,
                                                  ),
                                                ),
                                                style: OutlinedButton.styleFrom(
                                                  foregroundColor: _p.textPrimary,
                                                  side: BorderSide(color: _p.border),
                                                  padding: EdgeInsets.symmetric(
                                                    vertical: 8,
                                                    horizontal: 4,
                                                  ),
                                                  shape: RoundedRectangleBorder(
                                                    borderRadius:
                                                        BorderRadius.circular(6),
                                                  ),
                                                ),
                                              ),
                                            ),
                                          ),
                                          SizedBox(width: 6),
                                          Expanded(
                                            child: Tooltip(
                                              message: hasFormatted
                                                  ? 'Download formatted file'
                                                  : 'Not available yet - open Analyze and save the formatted document',
                                              child: OutlinedButton.icon(
                                                onPressed: hasFormatted
                                                    ? () => _handleDownloadVersion(
                                                          doc,
                                                          version: 'formatted',
                                                        )
                                                    : () => _showFormattedMissingHint(),
                                                icon: Icon(
                                                  Icons.file_download_outlined,
                                                  size: 14,
                                                ),
                                                label: Tr(
                                                  'Formatted',
                                                  style: TextStyle(
                                                    fontSize: 10,
                                                    fontWeight: FontWeight.w700,
                                                  ),
                                                ),
                                                style: OutlinedButton.styleFrom(
                                                  foregroundColor: hasFormatted
                                                      ? _p.accent
                                                      : _p.textMuted,
                                                  side: BorderSide(
                                                    color: hasFormatted
                                                        ? _p.accent
                                                        : _p.border,
                                                  ),
                                                  padding: EdgeInsets.symmetric(
                                                    vertical: 8,
                                                    horizontal: 4,
                                                  ),
                                                  shape: RoundedRectangleBorder(
                                                    borderRadius:
                                                        BorderRadius.circular(6),
                                                  ),
                                                ),
                                              ),
                                            ),
                                          ),
                                          SizedBox(width: 4),
                                          PopupMenuButton<String>(
                                            onSelected: (value) {
                                              if (value == 'analyze') {
                                                _openAnalyzeScreen(doc);
                                              } else if (value == 'preview') {
                                                _showPreview(doc);
                                              } else if (value == 'rename') {
                                                _showRenameDialog(doc);
                                              } else if (value == 'edit') {
                                                _showEditDialog(doc, auth.userId!);
                                              } else if (value == 'send' &&
                                                  DevUserConfig.hasFypModule) {
                                                _sendReportToSupervisor(doc);
                                              } else if (value == 'delete') {
                                                _handleDelete(doc);
                                              }
                                            },
                                            itemBuilder: (context) => [
                                              const PopupMenuItem(
                                                value: 'analyze',
                                                child: Row(
                                                  children: [
                                                    Icon(Icons.analytics_outlined,
                                                        size: 16,
                                                        color: Color(0xFF10B981)),
                                                    SizedBox(width: 8),
                                                    Tr('Analyze'),
                                                  ],
                                                ),
                                              ),
                                              if (DevUserConfig.hasFypModule)
                                                const PopupMenuItem(
                                                  value: 'send',
                                                  child: Row(
                                                    children: [
                                                      Icon(Icons.send_rounded,
                                                          size: 16,
                                                          color: Color(0xFF10B981)),
                                                      SizedBox(width: 8),
                                                      Tr('Send to Supervisor'),
                                                    ],
                                                  ),
                                                ),
                                              const PopupMenuItem(
                                                value: 'preview',
                                                child: Row(
                                                  children: [
                                                    Icon(Icons.preview, size: 16),
                                                    SizedBox(width: 8),
                                                    Tr('Preview'),
                                                  ],
                                                ),
                                              ),
                                              const PopupMenuItem(
                                                value: 'rename',
                                                child: Row(
                                                  children: [
                                                    Icon(
                                                        Icons
                                                            .drive_file_rename_outline,
                                                        size: 16),
                                                    SizedBox(width: 8),
                                                    Tr('Rename'),
                                                  ],
                                                ),
                                              ),
                                              const PopupMenuItem(
                                                value: 'edit',
                                                child: Row(
                                                  children: [
                                                    Icon(Icons.edit_outlined,
                                                        size: 16),
                                                    SizedBox(width: 8),
                                                    Tr('Edit'),
                                                  ],
                                                ),
                                              ),
                                              const PopupMenuItem(
                                                value: 'delete',
                                                child: Row(
                                                  children: [
                                                    Icon(Icons.delete,
                                                        size: 16, color: Colors.red),
                                                    SizedBox(width: 8),
                                                    Tr('Delete',
                                                        style: TextStyle(
                                                            color: Colors.red)),
                                                  ],
                                                ),
                                              ),
                                            ],
                                            child: Icon(
                                              Icons.more_vert,
                                              size: 16,
                                              color: _p.textSecondary,
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
                        ),
                      );
                    },
                  ),
                SizedBox(height: 40),
                // Pagination
                if (filteredDocs.isNotEmpty)
                  Center(
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        IconButton(
                          icon: Icon(Icons.chevron_left),
                          color: _p.textSecondary,
                          onPressed: _currentPage > 1
                              ? () => setState(() => _currentPage--)
                              : null,
                        ),
                        for (int i = 1; i <= totalPages && i <= 3; i++)
                          GestureDetector(
                            onTap: () => setState(() => _currentPage = i),
                            child: Padding(
                              padding: EdgeInsets.symmetric(horizontal: 4),
                              child: Container(
                                width: 32,
                                height: 32,
                                decoration: BoxDecoration(
                                  color: i == _currentPage ? _p.accent : _p.surface,
                                  borderRadius: BorderRadius.circular(6),
                                  border: Border.all(
                                    color: _p.border,
                                  ),
                                ),
                                child: Center(
                                  child: Text(
                                    '$i',
                                    style: TextStyle(
                                      color: i == _currentPage
                                          ? Colors.white
                                          : _p.textSecondary,
                                      fontWeight: FontWeight.w600,
                                      fontSize: 13,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        if (totalPages > 3)
                          Tr(
                            '...',
                            style: TextStyle(
                              color: _p.textSecondary,
                              fontSize: 13,
                            ),
                          ),
                        if (totalPages > 3)
                          GestureDetector(
                            onTap: () => setState(() => _currentPage = totalPages),
                            child: Padding(
                              padding: EdgeInsets.symmetric(horizontal: 4),
                              child: Container(
                                width: 32,
                                height: 32,
                                decoration: BoxDecoration(
                                  color: totalPages == _currentPage
                                      ? _p.accent
                                      : _p.surface,
                                  borderRadius: BorderRadius.circular(6),
                                  border: Border.all(
                                    color: _p.border,
                                  ),
                                ),
                                child: Center(
                                  child: Text(
                                    '$totalPages',
                                    style: TextStyle(
                                      color: totalPages == _currentPage
                                          ? Colors.white
                                          : _p.textSecondary,
                                      fontWeight: FontWeight.w600,
                                      fontSize: 13,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        IconButton(
                          icon: Icon(Icons.chevron_right),
                          color: _p.textSecondary,
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

  Future<void> _sendReportToSupervisor(Map<String, dynamic> doc) async {
    final auth = context.read<AuthProvider>();
    final fyp = context.read<FypProvider>();
    final docs = context.read<DocumentProvider>();

    final userId = auth.userId;
    final email = (auth.userEmail ?? auth.email ?? '').trim();
    if (userId == null || email.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Tr('Please sign in again to send'),
          backgroundColor: Color(0xFFEF4444),
        ),
      );
      return;
    }

    var groupId = fyp.fypGroupId;
    if (groupId == null) {
      await fyp.fetchAssignmentStatus(userId: userId, email: email);
      groupId = fyp.fypGroupId;
    }
    if (groupId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Tr(
            'No accepted supervisor yet. Choose a supervisor and wait for acceptance first.',
          ),
          backgroundColor: Color(0xFFEF4444),
        ),
      );
      return;
    }

    final docId = doc['id'];
    if (docId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Tr('Invalid document'),
          backgroundColor: Color(0xFFEF4444),
        ),
      );
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _p.surface,
        title: Tr(
          'Send to Supervisor?',
          style: TextStyle(color: _p.textPrimary),
        ),
        content: Text(
          'Send "${doc['filename'] ?? 'this report'}" for supervisor review?',
          style: TextStyle(color: _p.textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Tr('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(
              backgroundColor: Color(0xFF10B981),
              foregroundColor: Colors.white,
            ),
            child: Tr('Send'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => Center(
        child: CircularProgressIndicator(color: Color(0xFF10B981)),
      ),
    );

    final result = await docs.submitFinalSubmission(
      userId: userId,
      groupId: groupId,
      title: (doc['filename'] ?? 'Report').toString(),
      filename: (doc['filename'] ?? 'document.docx').toString(),
      studentContactEmail: email,
      sourceDocumentId: docId is int ? docId : int.tryParse(docId.toString()),
      analysisReport: docs.analysisReportFor(
        docId is int ? docId : int.tryParse(docId.toString()) ?? -1,
      ),
    );

    if (!mounted) return;
    Navigator.of(context, rootNavigator: true).pop();

    if (result != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Tr('Sent to supervisor for review'),
          backgroundColor: Color(0xFF10B981),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(docs.errorMessage ?? 'Failed to send'),
          backgroundColor: Color(0xFFEF4444),
        ),
      );
    }
  }

  Widget _buildReportsMenuButton({
    required IconData icon,
    required String label,
    required List<PopupMenuEntry<String>> items,
    required ValueChanged<String> onSelected,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: _p.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: _p.border),
      ),
      padding: EdgeInsets.symmetric(horizontal: 12, vertical: 2),
      child: PopupMenuButton<String>(
        onSelected: onSelected,
        itemBuilder: (_) => items,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: _p.textSecondary, size: 18),
            SizedBox(width: 8),
            Tr(
              label,
              style: TextStyle(
                color: _p.textSecondary,
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
      decoration: _cardDeco(lightRadius: 14),
      padding: EdgeInsets.all(14),
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
              SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      doc['filename'] ?? 'Untitled',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: _p.textPrimary,
                      ),
                    ),
                    SizedBox(height: 3),
                    Text(
                      doc['template_name'] ?? 'No template',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 12,
                        color: _p.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              SizedBox(width: 8),
              Container(
                padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Tr(
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
          SizedBox(height: 10),
          Text(
            'Modified ${_getTimeAgo(doc['created_at'] ?? DateTime.now())}',
            style: TextStyle(
              fontSize: 11,
              color: _p.textMuted,
            ),
          ),
          SizedBox(height: 12),
          if (doc['has_formatted'] == true)
            Padding(
              padding: EdgeInsets.only(bottom: 10),
              child: Container(
                width: double.infinity,
                padding: EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: Color(0xFF10B981).withOpacity(0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Tr(
                  'Formatted + Unformatted available',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF059669),
                  ),
                ),
              ),
            ),
          if (DevUserConfig.hasFypModule)
            SizedBox(
              width: double.infinity,
              height: 42,
              child: ElevatedButton.icon(
                onPressed: () => _sendReportToSupervisor(doc),
                icon: Icon(Icons.send_rounded, size: 16),
                label: Tr(
                  'Send to Supervisor',
                  style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Color(0xFF10B981),
                  foregroundColor: Colors.white,
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
              ),
            ),
          if (DevUserConfig.hasFypModule) SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: () => _showRenameDialog(doc),
              icon: Icon(Icons.drive_file_rename_outline, size: 16),
              label: Tr('Rename', style: TextStyle(fontSize: 12)),
              style: TextButton.styleFrom(
                foregroundColor: _p.textSecondary,
                padding: EdgeInsets.zero,
                minimumSize: Size(0, 32),
              ),
            ),
          ),
          Row(
            children: [
              Expanded(
                child: SizedBox(
                  height: 40,
                  child: OutlinedButton(
                    onPressed: () => _handleDownloadVersion(
                      doc,
                      version: 'unformatted',
                    ),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: _p.textPrimary,
                      side: BorderSide(color: _p.border),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                    child: Tr(
                      'Unformatted',
                      style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12),
                    ),
                  ),
                ),
              ),
              SizedBox(width: 8),
              Expanded(
                child: SizedBox(
                  height: 40,
                  child: OutlinedButton(
                    onPressed: doc['has_formatted'] == true
                        ? () => _handleDownloadVersion(
                              doc,
                              version: 'formatted',
                            )
                        : () => _showFormattedMissingHint(),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: doc['has_formatted'] == true
                          ? _p.accent
                          : _p.textMuted,
                      side: BorderSide(
                        color: doc['has_formatted'] == true
                            ? _p.accent
                            : _p.border,
                      ),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                    child: Tr(
                      'Formatted',
                      style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Color _getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'completed':
      case 'formatted':
        return Color(0xFF10B981);
      case 'processing':
        return Color(0xFFEAB308);
      case 'uploaded':
      case 'pending':
        return Color(0xFF6366F1);
      case 'draft':
        return Color(0xFFEF4444);
      default:
        return Color(0xFF10B981);
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
        return Color(0xFF10B981);
      case 'processing':
        return Color(0xFF10D981);
      case 'draft':
        return Color(0xFF8B5CF6);
      default:
        return _p.accent;
    }
  }

  Future<void> _showRenameDialog(Map<String, dynamic> doc) async {
    final userId = context.read<AuthProvider>().userId;
    final docProvider = context.read<DocumentProvider>();
    final docId = doc['id'];
    if (userId == null || docId is! int) return;

    final oldName = (doc['filename'] ?? '').toString();
    const known = ['.docx', '.pdf', '.txt', '.doc'];
    final lower = oldName.toLowerCase();
    final ext = known.firstWhere((e) => lower.endsWith(e), orElse: () => '');
    final stem = oldName.substring(0, oldName.length - ext.length);
    final controller = TextEditingController(text: stem);

    final entered = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _p.surface,
        title: Tr('Rename Report', style: TextStyle(color: _p.textPrimary)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: controller,
              autofocus: true,
              style: TextStyle(color: _p.textPrimary),
              decoration: InputDecoration(
                hintText: 'Report name',
                hintStyle: TextStyle(color: _p.textMuted),
                suffixText: ext,
              ),
              onSubmitted: (v) => Navigator.pop(ctx, v.trim()),
            ),
            if (ext.isNotEmpty) ...[
              SizedBox(height: 8),
              Text(
                'The $ext extension is kept automatically.',
                style: TextStyle(fontSize: 11, color: _p.textSecondary),
              ),
            ],
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Tr('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, controller.text.trim()),
            child: Tr('Save'),
          ),
        ],
      ),
    );

    if (entered == null || entered.isEmpty || !mounted) return;
    final saved = await docProvider.renameDocument(docId, userId, '$entered$ext');
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(saved != null
            ? 'Report renamed'
            : (docProvider.errorMessage ?? 'Rename failed')),
        backgroundColor: saved != null ? Color(0xFF10B981) : Color(0xFFEF4444),
      ),
    );
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
            backgroundColor: _p.surfaceAlt,
            insetPadding: EdgeInsets.all(32),
            child: Container(
              decoration: BoxDecoration(
                color: _p.surfaceAlt,
                borderRadius: BorderRadius.circular(
                  _p.isDark ? _p.cardRadius : 12,
                ),
                border: Border.all(
                  color: _p.isDark ? _p.borderStrong : _p.border,
                ),
                boxShadow: _p.isDark ? _p.cardShadow : null,
              ),
              child: Column(
                children: [
                  // Header
                  Container(
                    padding: EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      border: Border(
                        bottom: BorderSide(
                          color: _p.border,
                        ),
                      ),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Tr(
                          'Edit Document',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w600,
                            color: _p.textPrimary,
                          ),
                        ),
                        GestureDetector(
                          onTap: () => Navigator.pop(context),
                          child: Icon(
                            Icons.close,
                            color: _p.textSecondary,
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
                            color: _p.textSecondary,
                          ),
                        ),
                      ),
                    )
                  else
                    Expanded(
                      child: SingleChildScrollView(
                        padding: EdgeInsets.all(32),
                        child: TextField(
                          controller: editController,
                          maxLines: null,
                          style: TextStyle(
                            color: _p.textPrimary,
                            fontSize: 14,
                            height: 1.6,
                          ),
                          decoration: InputDecoration(
                            hintText: 'Edit your document here...',
                            hintStyle: TextStyle(
                              color: _p.textMuted,
                              fontSize: 14,
                            ),
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
                              borderSide: BorderSide(
                                color: _p.accent,
                              ),
                            ),
                            filled: true,
                            fillColor: _p.surface,
                            contentPadding: EdgeInsets.all(16),
                          ),
                        ),
                      ),
                    ),
                  // Footer buttons
                  Container(
                    padding: EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      border: Border(
                        top: BorderSide(
                          color: _p.border,
                        ),
                      ),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        TextButton(
                          onPressed: () => Navigator.pop(context),
                          child: Tr(
                            'Cancel',
                            style: TextStyle(
                              color: _p.textPrimary,
                            ),
                          ),
                        ),
                        SizedBox(width: 12),
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
                                      content: Tr(
                                        success
                                            ? 'Document saved successfully'
                                            : 'Failed to save document',
                                      ),
                                      backgroundColor: success
                                          ? Color(0xFF10B981)
                                          : Color(0xFFEF4444),
                                    ),
                                  );
                                  if (success) Navigator.pop(context);
                                },
                          style: ElevatedButton.styleFrom(),
                          child: Tr(
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
        backgroundColor: _p.surfaceAlt,
        insetPadding: EdgeInsets.all(24),
        child: Container(
          width: MediaQuery.of(context).size.width * 0.85,
          height: MediaQuery.of(context).size.height * 0.85,
          decoration: BoxDecoration(
            color: _p.surfaceAlt,
            borderRadius: BorderRadius.circular(
              _p.isDark ? _p.cardRadius : 12,
            ),
            border: Border.all(
              color: _p.isDark ? _p.borderStrong : _p.border,
            ),
            boxShadow: _p.isDark ? _p.cardShadow : null,
          ),
          child: Column(
            children: [
              // Header
              Container(
                padding: EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                decoration: BoxDecoration(
                  border: Border(
                    bottom: BorderSide(
                      color: _p.border,
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
                          isTemplate ? 'Template Preview' : (doc['filename'] ?? 'Document Preview'),
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                            color: _p.textPrimary,
                          ),
                        ),
                        if (isTemplate)
                          Padding(
                            padding: EdgeInsets.only(top: 2),
                            child: Text(
                              doc['name'] ?? 'Template',
                              style: TextStyle(
                                fontSize: 12,
                                color: _p.textSecondary,
                              ),
                            ),
                          ),
                      ],
                    ),
                    IconButton(
                      icon: Icon(Icons.close, color: _p.textSecondary),
                      onPressed: () => Navigator.pop(context),
                    ),
                  ],
                ),
              ),
              // Content - Word-like DocumentPreviewPanel Integration
              Expanded(
                child: isTemplate
                    ? DocumentPreviewPanel(
                        blocks: [
                          {'type': 'heading', 'level': 1, 'text': 'Sample Heading 1'},
                          {
                            'type': 'paragraph',
                            'text': 'This is a sample paragraph showing how your documents will be formatted using this template with all applied styles, font selections, and correct margins.'
                          },
                          {'type': 'heading', 'level': 2, 'text': 'Sample Heading 2'},
                          {'type': 'list_item', 'list_style': 'bullet', 'text': 'First point to demonstrate bullet formatting'},
                          {'type': 'list_item', 'list_style': 'bullet', 'text': 'Second point with consistent spacing'},
                          {
                            'type': 'paragraph',
                            'text': 'Conclusion paragraph showing body text formatting with proper line spacing and font selection.'
                          },
                        ],
                        issues: const [],
                        imageBaseUrl: '',
                        documentId: 0,
                        appliedFixes: const {},
                        ignoredIssueIds: const {},
                        onApplyFix: (_, __) {},
                        onIgnoreIssue: (_) {},
                        defaultFont: doc['formatting_rules']?['body_font'] ?? 'Times New Roman',
                        bodyPt: (doc['formatting_rules']?['body_size'] ?? 12).toDouble(),
                      )
                    : FutureBuilder<Map<String, dynamic>?>(
                        future: docProvider.getPreview(doc['id'], auth.userId!),
                        builder: (context, snapshot) {
                          if (snapshot.connectionState == ConnectionState.waiting) {
                            return Center(
                              child: CircularProgressIndicator(color: _p.accent),
                            );
                          }

                          if (snapshot.hasError || !snapshot.hasData) {
                            return Center(
                              child: Tr(
                                'Failed to load preview or document empty',
                                style: TextStyle(color: _p.textSecondary),
                              ),
                            );
                          }

                          final previewData = snapshot.data!;
                          final rawLines = previewData['formatted_lines'] ?? previewData['blocks'];
                          
                          // Normalize content into standard block maps expected by DocumentPreviewPanel
                          List<Map<String, dynamic>> blocks = [];
                          if (rawLines is List) {
                            blocks = rawLines.map<Map<String, dynamic>>((line) {
                              if (line is Map) {
                                return Map<String, dynamic>.from(line);
                              }
                              return {
                                'type': 'paragraph',
                                'text': line.toString(),
                              };
                            }).toList();
                          }

                          if (blocks.isEmpty) {
                            blocks = [
                              {
                                'type': 'paragraph',
                                'text': previewData['formatted_content'] ?? 'No content available.',
                              }
                            ];
                          }

                          return DocumentPreviewPanel(
                            blocks: blocks,
                            issues: const [],
                            imageBaseUrl: '',
                            documentId: doc['id'] ?? 0,
                            appliedFixes: const {},
                            ignoredIssueIds: const {},
                            onApplyFix: (_, __) {},
                            onIgnoreIssue: (_) {},
                            onBlocksChanged: (updatedBlocks) {
                              // Optional: handle block updates live if needed
                            },
                          );
                        },
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
      padding: EdgeInsets.all(32),
      child: Container(
        decoration: BoxDecoration(
          // Document page is always white so template text stays readable
          color: Colors.white,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: _p.border),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.12),
              blurRadius: 8,
            ),
          ],
        ),
        padding: EdgeInsets.all(40),
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

  Widget _buildTemplatesPage() {
    final templateColors = [
      _p.accent, // Blue
      Color(0xFFA855F7), // Purple
      Color(0xFF10B981), // Green
      Color(0xFFEF4444), // Red
      Color(0xFFFF6B35), // Orange
      Color(0xFFEC4899), // Pink
      Color(0xFF06B6D4), // Cyan
    ];

    return Consumer<TemplateProvider>(
      builder: (context, templateProvider, _) {
        return SingleChildScrollView(
          padding: EdgeInsets.all(32),
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
                        SnackBar(content: Tr('Request Template feature coming soon')),
                      );
                    },
                    icon: Icon(Icons.add, size: 18),
                    label: Tr('Request Template'),
                    style: ElevatedButton.styleFrom(
                      foregroundColor: Colors.white,
                      padding: EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                  ),
                ],
              ),
              SizedBox(height: 32),

              // Search and filters row
              Row(
                children: [
                  Expanded(
                    flex: 2,
                    child: TextField(
                      onChanged: (value) {
                        setState(() => _searchQuery = value);
                      },
                      style: TextStyle(color: _p.textPrimary),
                      decoration: InputDecoration(
                        hintText: 'Search universities or template names...',
                        hintStyle: TextStyle(color: _p.textMuted),
                        prefixIcon: Icon(Icons.search, color: _p.textMuted),
                        filled: true,
                        fillColor: _p.surface,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                          borderSide: BorderSide(color: _p.border),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                          borderSide: BorderSide(color: _p.border),
                        ),
                      ),
                    ),
                  ),
                  SizedBox(width: 16),
                  Container(
                    padding: EdgeInsets.symmetric(horizontal: 16),
                    decoration: BoxDecoration(
                      color: _p.surface,
                      border: Border.all(color: _p.border),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: DropdownButton<String>(
                      value: _selectedFilter,
                      underline: SizedBox(),
                      dropdownColor: _p.surface,
                      style: TextStyle(color: _p.textPrimary),
                      onChanged: (value) {
                        if (value != null) {
                          setState(() => _selectedFilter = value);
                        }
                      },
                      items: [
                        const DropdownMenuItem(value: 'all', child: Tr('All Categories')),
                        const DropdownMenuItem(value: 'engineering', child: Tr('Engineering')),
                        const DropdownMenuItem(value: 'sciences', child: Tr('Sciences')),
                        const DropdownMenuItem(value: 'business', child: Tr('Business')),
                        const DropdownMenuItem(value: 'humanities', child: Tr('Humanities')),
                      ],
                    ),
                  ),
                  SizedBox(width: 16),
                  Container(
                    padding: EdgeInsets.symmetric(horizontal: 16),
                    decoration: BoxDecoration(
                      color: _p.surface,
                      border: Border.all(color: _p.border),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: DropdownButton<String>(
                      value: _sortBy,
                      underline: SizedBox(),
                      dropdownColor: _p.surface,
                      style: TextStyle(color: _p.textPrimary),
                      onChanged: (value) {
                        if (value != null) {
                          setState(() => _sortBy = value);
                        }
                      },
                      items: [
                        const DropdownMenuItem(value: 'popular', child: Tr('Most Popular')),
                        const DropdownMenuItem(value: 'recent', child: Tr('Most Recent')),
                        const DropdownMenuItem(value: 'name', child: Tr('Name (A-Z)')),
                      ],
                    ),
                  ),
                ],
              ),
              SizedBox(height: 32),

              // Currently using template section
              if (_selectedTemplate != null)
                Container(
                  decoration: BoxDecoration(
                    color: _p.isDark
                        ? _p.surfaceElevated
                        : const Color(0xFF1A2847),
                    border: Border.all(color: _p.accent.withOpacity(0.3)),
                    borderRadius: BorderRadius.circular(
                      _p.isDark ? _p.cardRadius : 12,
                    ),
                    boxShadow: _p.isDark ? _p.cardShadow : null,
                  ),
                  padding: EdgeInsets.all(20),
                  child: Row(
                    children: [
                      Container(
                        width: 60,
                        height: 60,
                        decoration: BoxDecoration(
                          color: _p.accent,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Icon(Icons.description, color: Colors.white),
                      ),
                      SizedBox(width: 20),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Currently Using: ${_selectedTemplate!['name'] ?? 'Selected Template'}',
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w600,
                                color: _p.textPrimary,
                              ),
                            ),
                            SizedBox(height: 4),
                            Tr(
                              'This template is applied to your current document. You can switch templates anytime.',
                              style: TextStyle(
                                fontSize: 13,
                                color: _p.textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      ElevatedButton(
                        onPressed: () => _showPreview(_selectedTemplate!),
                        style: ElevatedButton.styleFrom(
                          foregroundColor: Colors.white,
                          padding: EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(6),
                          ),
                        ),
                        child: Tr('View Details'),
                      ),
                    ],
                  ),
                )
              else
                Container(
                  decoration: BoxDecoration(
                    color: _p.surface,
                    border: Border.all(color: _p.borderStrong),
                    borderRadius: BorderRadius.circular(
                      _p.isDark ? _p.cardRadius : 12,
                    ),
                    boxShadow: _p.cardShadow,
                  ),
                  padding: EdgeInsets.all(20),
                  child: Row(
                    children: [
                      Container(
                        width: 60,
                        height: 60,
                        decoration: BoxDecoration(
                          color: _p.accentSoft,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Icon(Icons.description, color: _p.accent),
                      ),
                      SizedBox(width: 20),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Tr(
                              'No Template Selected',
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w600,
                                color: _p.textPrimary,
                              ),
                            ),
                            SizedBox(height: 4),
                            Tr(
                              'Select a template below to get started with your document formatting.',
                              style: TextStyle(
                                fontSize: 13,
                                color: _p.textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              SizedBox(height: 48),

              // Templates from database only
              Tr(
                'Available Templates',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: _p.textPrimary,
                ),
              ),
              SizedBox(height: 8),
              Tr(
                DevUserConfig.hasFypModule
                    ? 'Loaded from your university database'
                    : 'Templates configured for your organization',
                style: TextStyle(
                  fontSize: 13,
                  color: _p.textSecondary,
                ),
              ),
              SizedBox(height: 20),
              if (templateProvider.isLoading)
                Center(child: CircularProgressIndicator())
              else if (templateProvider.errorMessage != null)
                Center(
                  child: Padding(
                    padding: EdgeInsets.symmetric(vertical: 48),
                    child: Column(
                      children: [
                        Text(
                          templateProvider.errorMessage!,
                          style: TextStyle(
                            fontSize: 14,
                            color: _p.textSecondary,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        SizedBox(height: 12),
                        TextButton(
                          onPressed: () {
                            final userId = context.read<AuthProvider>().userId;
                            if (userId != null) {
                              templateProvider.fetchUserTemplates(userId);
                            }
                          },
                          child: Tr('Retry'),
                        ),
                      ],
                    ),
                  ),
                )
              else if (templateProvider.templates.isEmpty)
                Center(
                  child: Padding(
                    padding: EdgeInsets.symmetric(vertical: 48),
                    child: Tr(
                      'No templates yet. Ask your admin to add templates in Template Manager.',
                      style: TextStyle(
                        fontSize: 14,
                        color: _p.textSecondary,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),
                )
              else
                GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: isCompact(context) ? 1 : 3,
                    crossAxisSpacing: 20,
                    mainAxisSpacing: 20,
                    childAspectRatio: isCompact(context) ? 1.35 : 0.85,
                  ),
                  itemCount: templateProvider.templates.length,
                  itemBuilder: (context, index) {
                    final template = templateProvider.templates[index];
                    final color = templateColors[index % templateColors.length];
                    return _buildTemplateCardNew(template, color);
                  },
                ),
              SizedBox(height: 48),

              // Request custom template section
              Center(
                child: Container(
                  decoration: _cardDeco(),
                  padding: EdgeInsets.all(40),
                  child: Column(
                    children: [
                      Container(
                        width: 56,
                        height: 56,
                        decoration: BoxDecoration(
                          color: _p.accent.withValues(alpha: 0.12),
                          shape: BoxShape.circle,
                        ),
                        child: Icon(Icons.help_outline, color: _p.accent, size: 28),
                      ),
                      SizedBox(height: 16),
                      Tr(
                        DevUserConfig.hasFypModule
                            ? 'Can\'t find your university template?'
                            : 'Need a custom template?',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                          color: _p.textPrimary,
                        ),
                      ),
                      SizedBox(height: 8),
                      Tr(
                        'Request a custom template and we\'ll add it within 48 hours',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 14,
                          color: _p.textSecondary,
                        ),
                      ),
                      SizedBox(height: 24),
                      ElevatedButton(
                        onPressed: () {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Tr('Custom template request submitted')),
                          );
                        },
                        style: ElevatedButton.styleFrom(
                          foregroundColor: Colors.white,
                          padding: EdgeInsets.symmetric(horizontal: 32, vertical: 14),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                        child: Tr('Request Custom Template'),
                      ),
                    ],
                  ),
                ),
              ),
              SizedBox(height: 32),
            ],
          ),
        );
      },
    );
  }

 Widget _buildSettingsPage() {
  return Consumer2<AuthProvider, ThemeProvider>(
    builder: (context, auth, theme, _) {
      final lang = context.watch<LangProvider>();

      return SingleChildScrollView(
        padding: EdgeInsets.all(32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              decoration: _cardDeco(),
              padding: EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Tr(
                    'Account Information',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: _p.textPrimary,
                    ),
                  ),
                  SizedBox(height: 16),
                  _buildSettingsItem('Username', auth.currentUser ?? 'N/A'),
                  SizedBox(height: 12),
                  _buildSettingsItem('Email', auth.email ?? 'N/A'),
                  SizedBox(height: 12),
                  _buildSettingsItem(
                    'Account Type',
                    DevUserConfig.displayRoleLabel(auth.userRole),
                  ),
                ],
              ),
            ),
            SizedBox(height: 24),
            Container(
              decoration: _cardDeco(),
              padding: EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Tr(
                    'Preferences',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: _p.textPrimary,
                    ),
                  ),
                  SizedBox(height: 16),

                  // ---------- NEW: Language ----------
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Tr(
                        'Language',
                        style: TextStyle(fontSize: 13, color: _p.textPrimary),
                      ),
                      DropdownButton<String>(
                        value: lang.code,
                        dropdownColor: _p.surface,
                        underline: SizedBox(),
                        style: TextStyle(fontSize: 13, color: _p.textPrimary),
                        items: kLanguages
                            .map((l) => DropdownMenuItem(
                                  value: l.code,
                                  child: Text(l.name), // plain Text, translate nahi hona
                                ))
                            .toList(),
                        onChanged: (v) {
                          if (v != null) {
                            context.read<LangProvider>().setLang(v);
                          }
                        },
                      ),
                    ],
                  ),
                  SizedBox(height: 12),
                  // -----------------------------------

                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Tr(
                        'Email Notifications',
                        style: TextStyle(fontSize: 13, color: _p.textPrimary),
                      ),
                      Switch(
                        value: true,
                        onChanged: (value) {},
                        activeColor: _p.accent,
                      ),
                    ],
                  ),
                  SizedBox(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Tr(
                            'Dark Mode',
                            style: TextStyle(fontSize: 13, color: _p.textPrimary),
                          ),
                          SizedBox(height: 2),
                          Tr(
                            theme.isDarkMode ? 'On' : 'Off — Light Mode',
                            style: TextStyle(fontSize: 11, color: _p.textSecondary),
                          ),
                        ],
                      ),
                      Switch(
                        value: theme.isDarkMode,
                        onChanged: (value) => theme.setDarkMode(value),
                        activeColor: _p.accent,
                      ),
                    ],
                  ),
                ],
              ),
            ),
            SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () => _logout(context),
                icon: Icon(Icons.logout_rounded),
                label: Tr('Sign Out'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: _p.textPrimary,
                  side: BorderSide(color: _p.borderStrong),
                  padding: EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
          ],
        ),
      );
    },
  );
}

  Widget _buildTemplateCardNew(Map<String, dynamic> template, Color cardColor) {
    final displayName = (template['name'] ?? 'Template').toString();
    final description = (template['description'] ?? '').toString().trim();
    final sections = List<dynamic>.from(template['required_sections'] ?? const []);
    final rules = Map<String, dynamic>.from(
      (template['formatting_rules'] is Map)
          ? Map<String, dynamic>.from(template['formatting_rules'] as Map)
          : const {},
    );

    final details = <String>[];
    if (sections.isNotEmpty) {
      details.add('${sections.length} required section${sections.length == 1 ? '' : 's'}');
    }
    final bodyFont = (rules['body_font'] ?? '').toString().trim();
    final bodySize = rules['body_size'];
    if (bodyFont.isNotEmpty || bodySize != null) {
      details.add(
        [
          if (bodyFont.isNotEmpty) bodyFont,
          if (bodySize != null) '${bodySize}pt',
        ].join(' · '),
      );
    }
    final pageSize = (rules['page_size'] ?? '').toString().trim();
    if (pageSize.isNotEmpty) {
      details.add('Page size: $pageSize');
    }
    if (details.isEmpty) {
      details.add('University formatting template');
    }

    return Container(
      decoration: _cardDeco(),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(
          _p.isDark ? _p.cardRadius : 12,
        ),
        child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: double.infinity,
            height: 120,
            decoration: BoxDecoration(
              // Dark: purple-system header. Light: keep multi-color cardColor variety.
              gradient: _p.isDark
                  ? LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [
                        _p.accentAlt.withOpacity(0.55),
                        _p.accent.withOpacity(0.35),
                        _p.surfaceElevated,
                      ],
                    )
                  : LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [cardColor, cardColor.withOpacity(0.8)],
                    ),
              color: _p.isDark ? null : cardColor,
            ),
            padding: EdgeInsets.all(20),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(
                displayName,
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: _p.textPrimary,
                ),
              ),
            ),
          ),
          Expanded(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    displayName,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: _p.textPrimary,
                    ),
                  ),
                  SizedBox(height: 6),
                  Text(
                    description.isEmpty
                        ? 'No description provided'
                        : description,
                    style: TextStyle(
                      fontSize: 12,
                      color: _p.textSecondary,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  SizedBox(height: 12),
                  ...details.take(3).map(
                    (detail) => Padding(
                      padding: EdgeInsets.only(bottom: 6),
                      child: Row(
                        children: [
                          Tr(
                            '• ',
                            style: TextStyle(
                              fontSize: 11,
                              color: _p.textSecondary,
                            ),
                          ),
                          Expanded(
                            child: Text(
                              detail,
                              style: TextStyle(
                                fontSize: 11,
                                color: _p.textSecondary,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  Spacer(),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () => _showPreview(template),
                          style: OutlinedButton.styleFrom(
                            side: BorderSide(color: _p.borderStrong),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(6),
                            ),
                          ),
                          child: Tr(
                            'Preview',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: _p.textPrimary,
                            ),
                          ),
                        ),
                      ),
                      SizedBox(width: 8),
                      Expanded(
                        child: ElevatedButton(
                          onPressed: () {
                            setState(() {
                              _selectedTemplate = template;
                              _selectedIndex = 1;
                              _activeProjectId = null;
                            });
                          },
                          // No opaque backgroundColor — theme gradient CTA.
                          // Sits in card body (surface), below header — not on gradient.
                          style: ElevatedButton.styleFrom(
                            foregroundColor: Colors.white,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(6),
                            ),
                          ),
                          child: Tr(
                            'Select',
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
      backgroundColor: _p.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(
          _p.isDark ? _p.cardRadius : 12,
        ),
      ),
      child: Container(
        width: 400,
        padding: EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Tr(
              'Upload Document',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: _p.textPrimary,
              ),
            ),
            SizedBox(height: 8),
            Text(
              'Using template: ${template['name']}',
              style: TextStyle(
                fontSize: 12,
                color: _p.textSecondary,
              ),
            ),
            SizedBox(height: 24),
            // Tab-like buttons for choosing upload method
            Container(
              decoration: BoxDecoration(
                color: _p.surfaceAlt,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: GestureDetector(
                      onTap: () => _pickFile(template),
                      child: Container(
                        padding: EdgeInsets.symmetric(vertical: 12),
                        decoration: BoxDecoration(
                          color: _p.accent,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Center(
                          child: Tr(
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
                  SizedBox(width: 8),
                  Expanded(
                    child: GestureDetector(
                      onTap: () {
                        Navigator.pop(context);
                        _showPasteContentDialog(template);
                      },
                      child: Container(
                        padding: EdgeInsets.symmetric(vertical: 12),
                        decoration: BoxDecoration(
                          color: Colors.transparent,
                          border: Border.all(
                            color: _p.borderStrong,
                          ),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Center(
                          child: Tr(
                            'Paste Text',
                            style: TextStyle(
                              color: _p.textPrimary,
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
            SizedBox(height: 20),
            Tr(
              'Supported formats: PDF, DOCX, DOC, TXT',
              style: TextStyle(
                fontSize: 11,
                color: _p.textSecondary,
              ),
            ),
            SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: Tr(
                    'Cancel',
                    style: TextStyle(
                      color: _p.textSecondary,
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
            backgroundColor: _p.surface,
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const CircularProgressIndicator(),
                  SizedBox(height: 16),
                  Tr(
                    'Uploading document...',
                    style: TextStyle(color: _p.textPrimary),
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
              SnackBar(
                content: Tr('Document uploaded successfully!'),
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
                backgroundColor: Color(0xFFEF4444),
              ),
            );
          }
        }
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error: $e'),
          backgroundColor: Color(0xFFEF4444),
        ),
      );
    }
  }

  void _showPasteContentDialog(Map<String, dynamic> template) {
    final textController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) => Dialog(
        backgroundColor: _p.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(
            _p.isDark ? _p.cardRadius : 12,
          ),
        ),
        child: Container(
          width: 500,
          padding: EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Tr(
                'Paste Your Content',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: _p.textPrimary,
                ),
              ),
              SizedBox(height: 8),
              Tr(
                'Paste your document text below',
                style: TextStyle(
                  fontSize: 12,
                  color: _p.textSecondary,
                ),
              ),
              SizedBox(height: 16),
              TextField(
                controller: textController,
                maxLines: 8,
                style: TextStyle(color: _p.textPrimary),
                decoration: InputDecoration(
                  hintText: 'Paste your document content here...',
                  hintStyle: TextStyle(
                    color: _p.textMuted,
                  ),
                  filled: true,
                  fillColor: _p.surface,
                  contentPadding: EdgeInsets.all(12),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(6),
                    borderSide: BorderSide(
                      color: _p.borderStrong,
                    ),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(6),
                    borderSide: BorderSide(
                      color: _p.borderStrong,
                    ),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(6),
                    borderSide: BorderSide(
                      color: _p.accent,
                    ),
                  ),
                ),
              ),
              SizedBox(height: 20),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: Tr(
                      'Cancel',
                      style: TextStyle(
                        color: _p.textSecondary,
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  SizedBox(width: 12),
                  ElevatedButton(
                    onPressed: () => _uploadPastedContent(template, textController.text),
                    style: ElevatedButton.styleFrom(
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(6),
                      ),
                    ),
                    child: Tr(
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
        SnackBar(
          content: Tr('Please paste some content'),
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
        backgroundColor: _p.surface,
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(),
              SizedBox(height: 16),
              Tr(
                'Processing content...',
                style: TextStyle(color: _p.textPrimary),
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
          SnackBar(
            content: Tr('Content uploaded successfully!'),
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
            backgroundColor: Color(0xFFEF4444),
          ),
        );
      }
    }
  }

  Widget _buildSettingsItem(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Tr(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: _p.textSecondary,
          ),
        ),
        SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w500,
            color: _p.textPrimary,
          ),
        ),
      ],
    );
  }

 String _getTimeAgo(dynamic dateTime) {
  if (dateTime == null) return 'just now';

  DateTime parsedDateTime;

  if (dateTime is Timestamp) {
    // 1. Firebase Timestamp handling
    parsedDateTime = dateTime.toDate().toLocal();
  } else if (dateTime is String) {
    // 2. String handling (Ensures string is parsed as UTC if not specified)
    String dateStr = dateTime.trim();
    if (!dateStr.endsWith('Z') && !dateStr.contains('+')) {
      dateStr += 'Z'; // Force UTC parsing if missing
    }
    final parsed = DateTime.tryParse(dateStr);
    parsedDateTime = parsed != null ? parsed.toLocal() : DateTime.now();
  } else if (dateTime is DateTime) {
    // 3. DateTime object handling
    parsedDateTime = dateTime.isUtc ? dateTime.toLocal() : dateTime;
  } else {
    return 'just now';
  }

  final now = DateTime.now();
  final difference = now.difference(parsedDateTime);

  // Future timestamp prevention (Server latency check)
  if (difference.isNegative || difference.inSeconds < 30) {
    return 'just now';
  } else if (difference.inDays >= 7) {
    final weeks = (difference.inDays / 7).floor();
    return '$weeks week${weeks > 1 ? 's' : ''} ago';
  } else if (difference.inDays > 0) {
    return '${difference.inDays} day${difference.inDays > 1 ? 's' : ''} ago';
  } else if (difference.inHours > 0) {
    return '${difference.inHours} hour${difference.inHours > 1 ? 's' : ''} ago';
  } else if (difference.inMinutes > 0) {
    return '${difference.inMinutes} minute${difference.inMinutes > 1 ? 's' : ''} ago';
  } else {
    return '${difference.inSeconds} second${difference.inSeconds > 1 ? 's' : ''} ago';
  }
}
  void _showFormattedMissingHint() {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Tr(
          'No formatted version yet. Open Analyze, apply fixes, then tap Save Formatted Document.',
        ),
        backgroundColor: _p.accent,
      ),
    );
  }

  /// Access Unformatted (original upload) or Formatted (saved) from My Reports.
  void _handleDownloadVersion(
    Map<String, dynamic> doc, {
    required String version,
  }) {
    final isFormatted = version == 'formatted';
    if (isFormatted && doc['has_formatted'] != true) {
      _showFormattedMissingHint();
      return;
    }

    if (!isFormatted) {
      _downloadOriginalReport(doc);
      return;
    }

    // Formatted: let user pick PDF / Word (same as before).
    if (isCompact(context)) {
      _showMobileDownloadSheet(doc, savedFormattedOnly: true);
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
                content: Text('Downloading formatted document as $format...'),
                backgroundColor: _p.accent,
              ),
            );

            final success = await docProvider.downloadSavedFormattedDocument(
              doc['id'],
              userId!,
              format: format,
            );

            if (mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text(
                    success
                        ? 'Formatted document downloaded as $format!'
                        : 'Download failed: ${docProvider.errorMessage}',
                  ),
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
                  padding: EdgeInsets.all(20),
                  child: Image.memory(
                    base64Decode(qrBase64),
                    width: 250,
                    height: 250,
                    errorBuilder: (_, __, ___) => Tr('Failed to load QR'),
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

  Future<void> _downloadOriginalReport(Map<String, dynamic> doc) async {
    final docProvider = context.read<DocumentProvider>();
    final authProvider = Provider.of<AuthProvider>(context, listen: false);
    final userId = authProvider.userId;
    if (userId == null) return;

    if (isCompact(context)) {
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (_) => Center(
          child: CircularProgressIndicator(color: _p.accent),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Tr('Downloading unformatted report...'),
          backgroundColor: _p.accent,
        ),
      );
    }

    final success = await docProvider.downloadOriginalDocument(doc['id'], userId);
    if (!mounted) return;

    if (isCompact(context)) {
      Navigator.of(context, rootNavigator: true).pop();
    }

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
        content: Text('Unformatted report saved to $where'),
        backgroundColor: Color(0xFF10B981),
        action: isCompact(context)
            ? SnackBarAction(
                label: 'Open',
                textColor: Colors.white,
                onPressed: () => OpenFile.open(path),
              )
            : null,
      ),
    );

    if (isCompact(context) && Platform.isIOS) {
      await SharePlus.instance.share(
        ShareParams(
          files: [XFile(path)],
          subject: path.split(Platform.pathSeparator).last,
        ),
      );
    }
  }

  /// Kept for any remaining call sites that still expect a single Download action.
  void _handleDownload(Map<String, dynamic> doc) {
    _handleDownloadVersion(doc, version: 'formatted');
  }

  void _showMobileDownloadSheet(
    Map<String, dynamic> doc, {
    bool savedFormattedOnly = false,
  }) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: _p.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
      ),
      builder: (sheetContext) {
        return SafeArea(
          child: Padding(
            padding: EdgeInsets.fromLTRB(20, 12, 20, 20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Center(
                  child: Container(
                    width: 40,
                    height: 4,
                    decoration: BoxDecoration(
                      color: _p.borderStrong,
                      borderRadius: BorderRadius.circular(999),
                    ),
                  ),
                ),
                SizedBox(height: 16),
                Tr(
                  savedFormattedOnly ? 'Download formatted as' : 'Download as',
                  style: TextStyle(
                    color: _p.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                SizedBox(height: 6),
                Tr(
                  'File will be saved to your phone',
                  style: TextStyle(
                    color: _p.textSecondary,
                    fontSize: 13,
                  ),
                ),
                SizedBox(height: 16),
                _mobileDownloadOption(
                  icon: Icons.picture_as_pdf_rounded,
                  color: Color(0xFFDC2626),
                  title: 'PDF',
                  subtitle: 'Best for viewing and sharing',
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _downloadToPhone(
                      doc,
                      'pdf',
                      useSavedFormatted: savedFormattedOnly,
                    );
                  },
                ),
                SizedBox(height: 10),
                _mobileDownloadOption(
                  icon: Icons.description_rounded,
                  color: Color(0xFF2563EB),
                  title: 'Word',
                  subtitle: 'Editable .docx document',
                  onTap: () {
                    Navigator.pop(sheetContext);
                    _downloadToPhone(
                      doc,
                      'docx',
                      useSavedFormatted: savedFormattedOnly,
                    );
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
      color: _p.surfaceAlt,
      borderRadius: BorderRadius.circular(
        _p.isDark ? _p.cardRadius : 12,
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(
          _p.isDark ? _p.cardRadius : 12,
        ),
        child: Container(
          padding: EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(
              _p.isDark ? _p.cardRadius : 12,
            ),
            border: Border.all(
              color: _p.isDark ? _p.borderStrong : _p.border,
            ),
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
              SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Tr(
                      title,
                      style: TextStyle(
                        color: _p.textPrimary,
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    SizedBox(height: 2),
                    Tr(
                      subtitle,
                      style: TextStyle(
                        color: _p.textSecondary,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.download_rounded,
                color: _p.textMuted,
                size: 20,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _downloadToPhone(
    Map<String, dynamic> doc,
    String format, {
    bool useSavedFormatted = false,
  }) async {
    final docProvider = context.read<DocumentProvider>();
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Tr('Please sign in again to download'),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }

    final label = format == 'pdf' ? 'PDF' : 'Word';
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => Center(
        child: CircularProgressIndicator(color: _p.accent),
      ),
    );

    try {
      final success = useSavedFormatted
          ? await docProvider.downloadSavedFormattedDocument(
              doc['id'] as int,
              userId,
              format: format,
            )
          : await docProvider.downloadFormattedDocument(
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
          backgroundColor: Color(0xFF10B981),
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
                backgroundColor: _p.accent,
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
        backgroundColor: _p.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(
            _p.isDark ? _p.cardRadius : 12,
          ),
        ),
        child: Container(
          padding: EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Tr(
                'Delete Report',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: _p.textPrimary,
                ),
              ),
              SizedBox(height: 12),
              Text(
                'Are you sure you want to delete "${doc['filename']}"? This action cannot be undone.',
                style: TextStyle(
                  fontSize: 13,
                  color: _p.textSecondary,
                ),
              ),
              SizedBox(height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: Tr(
                      'Cancel',
                      style: TextStyle(
                        color: _p.textSecondary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  SizedBox(width: 12),
                  ElevatedButton(
                    onPressed: () {
                      Navigator.pop(context);
                      _performDelete(doc);
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Color(0xFFEF4444),
                    ),
                    child: Tr(
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
          backgroundColor: _p.surface,
          child: Padding(
            padding: EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const CircularProgressIndicator(),
                SizedBox(height: 16),
                Tr(
                  'Deleting document...',
                  style: TextStyle(color: _p.textPrimary),
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
            SnackBar(
              content: Tr('Document deleted successfully'),
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
              backgroundColor: Color(0xFFEF4444),
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
            backgroundColor: Color(0xFFEF4444),
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
        padding = EdgeInsets.only(top: 12, bottom: 8);
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
        padding = EdgeInsets.only(top: 10, bottom: 6);
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
        padding = EdgeInsets.only(top: 8, bottom: 4);
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
          padding: EdgeInsets.only(left: 24),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Tr('• ', style: TextStyle(fontSize: 12)),
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
          padding: EdgeInsets.only(left: 24),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(width: 20),
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
        padding = EdgeInsets.only(bottom: 6);
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

  Future<void> _logout(BuildContext context) => confirmAndLogout(context);
}

class TemplatesPanel extends StatelessWidget {
  const TemplatesPanel({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final p = context.watch<ThemeProvider>().palette;
    return Padding(
      padding: EdgeInsets.all(32.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Tr(
                'Templates',
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w700,
                  color: p.textPrimary,
                  letterSpacing: 0.5,
                ),
              ),
              SizedBox(height: 8),
              Tr(
                'Select a template to apply formatting to your documents',
                style: TextStyle(
                  fontSize: 14,
                  color: p.textSecondary,
                  fontWeight: FontWeight.w400,
                ),
              ),
            ],
          ),
          SizedBox(height: 24),
          Expanded(
            child: Consumer<TemplateProvider>(
              builder: (context, templateProvider, _) {
                if (templateProvider.isLoading) {
                  return Center(
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
                        Icon(Icons.error_outline, size: 48, color: p.textMuted),
                        SizedBox(height: 16),
                        Text(
                          'Error: ${templateProvider.errorMessage}',
                          style: TextStyle(color: p.textSecondary),
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
                        Icon(Icons.layers_clear, size: 48, color: p.textMuted),
                        SizedBox(height: 16),
                        Tr(
                          'No templates available yet',
                          style: TextStyle(
                            color: p.textSecondary,
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
                      margin: EdgeInsets.only(bottom: 16),
                      decoration: BoxDecoration(
                        color: isSelected
                            ? (p.isDark
                                ? p.accentSoft
                                : const Color(0xFF6366F1).withOpacity(0.15))
                            : (p.isDark
                                ? p.surfaceElevated
                                : const Color(0xFF1A1F2E)),
                        borderRadius: BorderRadius.circular(
                          p.isDark ? p.cardRadius : 12,
                        ),
                        border: Border.all(
                          color: isSelected
                              ? (p.isDark
                                  ? p.accent.withOpacity(0.4)
                                  : const Color(0xFF6366F1).withOpacity(0.4))
                              : (p.isDark ? p.borderStrong : p.border),
                          width: 1.5,
                        ),
                        boxShadow: p.isDark ? p.cardShadow : null,
                      ),
                      child: Padding(
                        padding: EdgeInsets.all(20),
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
                                            padding: EdgeInsets.all(8),
                                            decoration: BoxDecoration(
                                              color: p.isDark
                                                  ? p.accentSoft
                                                  : const Color(0xFF6366F1)
                                                      .withOpacity(0.2),
                                              borderRadius:
                                                  BorderRadius.circular(6),
                                            ),
                                            child: Icon(
                                              Icons.layers,
                                              color: p.isDark
                                                  ? p.accent
                                                  : const Color(0xFF6366F1),
                                              size: 16,
                                            ),
                                          ),
                                          SizedBox(width: 12),
                                          Expanded(
                                            child: Text(
                                              template['name'] ?? 'Unnamed Template',
                                              style: TextStyle(
                                                fontSize: 17,
                                                fontWeight: FontWeight.w600,
                                                color: p.textPrimary,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                      if (isSelected)
                                        Padding(
                                          padding: EdgeInsets.only(top: 8, left: 20),
                                          child: Container(
                                            padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                            decoration: BoxDecoration(
                                              color: Color(0xFF10B981).withOpacity(0.15),
                                              borderRadius: BorderRadius.circular(6),
                                            ),
                                            child: Row(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                Icon(
                                                  Icons.check_circle,
                                                  size: 14,
                                                  color: Color(0xFF10B981),
                                                ),
                                                SizedBox(width: 4),
                                                Tr(
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
                                                backgroundColor: Color(0xFF10B981),
                                                duration: Duration(seconds: 2),
                                                behavior: SnackBarBehavior.floating,
                                                margin: EdgeInsets.all(16),
                                              ),
                                            );
                                          },
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: isSelected
                                          ? Color(0xFF10B981).withOpacity(0.2)
                                          : Color(0xFF6366F1),
                                      foregroundColor: isSelected ? Color(0xFF10B981) : Colors.white,
                                    ),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(isSelected ? Icons.check : Icons.add, size: 18),
                                        SizedBox(width: 6),
                                        Tr(isSelected ? 'Selected' : 'Select'),
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
    final p = context.watch<ThemeProvider>().palette;
    return Padding(
      padding: EdgeInsets.all(32.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Tr(
                'Settings',
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w700,
                  color: p.textPrimary,
                  letterSpacing: 0.5,
                ),
              ),
              SizedBox(height: 8),
              Tr(
                'Manage your account settings and preferences',
                style: TextStyle(
                  fontSize: 14,
                  color: p.textSecondary,
                  fontWeight: FontWeight.w400,
                ),
              ),
            ],
          ),
          SizedBox(height: 32),
          Consumer<AuthProvider>(
            builder: (context, auth, _) {
              return Container(
                decoration: BoxDecoration(
                  color: p.isDark
                      ? p.surfaceElevated
                      : const Color(0xFF1A1F2E),
                  borderRadius: BorderRadius.circular(
                    p.isDark ? p.cardRadius : 12,
                  ),
                  border: Border.all(
                    color: p.isDark ? p.borderStrong : p.border,
                  ),
                  boxShadow: p.isDark ? p.cardShadow : null,
                ),
                child: Padding(
                  padding: EdgeInsets.all(24.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: p.isDark
                                  ? p.accentSoft
                                  : const Color(0xFF6366F1).withOpacity(0.2),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Icon(
                              Icons.account_circle,
                              color: p.isDark
                                  ? p.accent
                                  : const Color(0xFF6366F1),
                              size: 24,
                            ),
                          ),
                          SizedBox(width: 12),
                          Tr(
                            'Account Settings',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: p.textPrimary,
                            ),
                          ),
                        ],
                      ),
                      SizedBox(height: 24),
                      _buildSettingField(
                        context,
                        'Email Address',
                        auth.userEmail ?? 'user@university.edu',
                        Icons.email,
                      ),
                      SizedBox(height: 16),
                      _buildSettingField(
                        context,
                        'Username',
                        auth.currentUser ?? 'User',
                        Icons.person,
                      ),
                      SizedBox(height: 16),
                      _buildSettingField(
                        context,
                        'Role',
                        DevUserConfig.displayRoleLabel(auth.userRole),
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

  Widget _buildSettingField(
    BuildContext context,
    String label,
    String value,
    IconData icon,
  ) {
    final p = context.watch<ThemeProvider>().palette;
    return Container(
      padding: EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: p.surfaceAlt,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: p.border),
      ),
      child: Row(
        children: [
          Icon(icon, color: Color(0xFF6366F1), size: 20),
          SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Tr(
                  label,
                  style: TextStyle(
                    fontSize: 12,
                    color: p.textSecondary,
                    fontWeight: FontWeight.w500,
                    letterSpacing: 0.5,
                  ),
                ),
                SizedBox(height: 4),
                Text(
                  value,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: p.textPrimary,
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