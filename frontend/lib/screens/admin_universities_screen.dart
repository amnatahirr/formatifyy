import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/admin_models.dart';
import '../providers/auth_provider.dart';
import '../services/admin_api_service.dart';
import '../widgets/admin/admin_ui.dart';

class AdminUniversitiesScreen extends StatefulWidget {
  const AdminUniversitiesScreen({super.key});

  @override
  State<AdminUniversitiesScreen> createState() => _AdminUniversitiesScreenState();
}

class _AdminUniversitiesScreenState extends State<AdminUniversitiesScreen> {
  final AdminApiService _api = AdminApiService();
  bool _loading = true;
  String? _error;
  List<AdminUniversityModel> _universities = const [];

  @override
  void initState() {
    super.initState();
    _loadUniversities();
  }

  Future<void> _loadUniversities() async {
    final userId = context.read<AuthProvider>().userId;
    if (userId == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final universities = await _api.fetchUniversities(userId);
      if (mounted) setState(() => _universities = universities);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AdminPage(
      onRefresh: _loadUniversities,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const AdminPageHeader(
            title: 'Universities',
            subtitle: 'Registered institutions and active student accounts',
          ),
          const SizedBox(height: 24),
          if (_loading)
            const AdminLoadingView()
          else if (_error != null)
            AdminErrorView(message: _error!, onRetry: _loadUniversities)
          else if (_universities.isEmpty)
            const AdminEmptyView(message: 'No universities are registered in the system yet.')
          else
            LayoutBuilder(
              builder: (context, constraints) {
                final columns = constraints.maxWidth >= 1100 ? 3 : constraints.maxWidth >= 760 ? 2 : 1;
                return GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: columns,
                    crossAxisSpacing: 18,
                    mainAxisSpacing: 18,
                    childAspectRatio: 1.7,
                  ),
                  itemCount: _universities.length,
                  itemBuilder: (context, index) {
                    final university = _universities[index];
                    return Container(
                      padding: const EdgeInsets.all(20),
                      decoration: adminCardDecoration(),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Container(
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                  color: AdminColors.primary.withOpacity(0.14),
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: const Icon(Icons.school_rounded, color: AdminColors.primary),
                              ),
                              const Spacer(),
                              Text(
                                '${university.studentCount} students',
                                style: const TextStyle(color: AdminColors.primary, fontWeight: FontWeight.w600, fontSize: 12),
                              ),
                            ],
                          ),
                          const SizedBox(height: 16),
                          Text(
                            university.name,
                            style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: Colors.white),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            university.country.isEmpty ? 'Country not specified' : university.country,
                            style: TextStyle(fontSize: 13, color: Colors.white.withOpacity(0.65)),
                          ),
                          const Spacer(),
                          Text(
                            '${university.userCount} total accounts',
                            style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(0.55)),
                          ),
                        ],
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
