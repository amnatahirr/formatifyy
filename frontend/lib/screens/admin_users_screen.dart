import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';

import '../config/api_config.dart';
import '../providers/auth_provider.dart';

class AdminUsersScreen extends StatefulWidget {
  const AdminUsersScreen({super.key});

  @override
  State<AdminUsersScreen> createState() => _AdminUsersScreenState();
}

class _AdminUsersScreenState extends State<AdminUsersScreen> {
  late String baseUrl;
  List<Map<String, dynamic>> _allUsers = [];
  List<Map<String, dynamic>> _pagedUsers = [];
  bool _isLoading = false;
  String _searchQuery = '';
  int _currentPage = 1;
  final int _itemsPerPage = 10;

  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    baseUrl = ApiConfig.getBaseUrl();
    _loadUsers();
  }

  Future<void> _loadUsers() async {
    setState(() => _isLoading = true);
    try {
      final auth = context.read<AuthProvider>();
      if (auth.userId == null) return;
      final response = await http.get(
        Uri.parse('$baseUrl/admin/users?user_id=${auth.userId}'),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        _allUsers = List<Map<String, dynamic>>.from(data['users'] ?? []);
        _applyFiltersAndPagination();
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error loading users: $e')),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _applyFiltersAndPagination() {
    final query = _searchQuery.trim().toLowerCase();
    final filtered = _allUsers.where((u) {
      if (query.isEmpty) return true;
      final username = (u['username'] ?? '').toString().toLowerCase();
      final email = (u['email'] ?? '').toString().toLowerCase();
      return username.contains(query) || email.contains(query);
    }).toList();

    final totalPages = (filtered.length / _itemsPerPage).ceil();
    if (_currentPage > totalPages && totalPages > 0) _currentPage = totalPages;
    if (_currentPage < 1) _currentPage = 1;

    final start = (_currentPage - 1) * _itemsPerPage;
    final end = (start + _itemsPerPage) > filtered.length ? filtered.length : (start + _itemsPerPage);
    _pagedUsers = start < filtered.length ? filtered.sublist(start, end) : [];
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final totalPages = (_allUsers.length / _itemsPerPage).ceil();
    return Container(
      color: const Color(0xFF0F1419),
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Students',
            style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700, color: Colors.white),
          ),
          const SizedBox(height: 6),
          Text(
            'All registered student emails and accounts.',
            style: TextStyle(color: Colors.white.withOpacity(0.6)),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchController,
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(
                    hintText: 'Search by username or email',
                    border: OutlineInputBorder(),
                  ),
                  onChanged: (value) {
                    _searchQuery = value;
                    _currentPage = 1;
                    _applyFiltersAndPagination();
                  },
                ),
              ),
              const SizedBox(width: 12),
              ElevatedButton.icon(
                onPressed: _loadUsers,
                icon: const Icon(Icons.refresh),
                label: const Text('Refresh'),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _pagedUsers.isEmpty
                    ? const Center(
                        child: Text('No student users found', style: TextStyle(color: Colors.white70)),
                      )
                    : ListView.separated(
                        itemCount: _pagedUsers.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 10),
                        itemBuilder: (context, index) {
                          final u = _pagedUsers[index];
                          return Container(
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: const Color(0xFF1A1F2E),
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(color: const Color(0xFF2D3748)),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.school, color: Color(0xFF6366F1)),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        (u['username'] ?? '').toString(),
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                      Text(
                                        (u['email'] ?? '').toString(),
                                        style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 12),
                                      ),
                                    ],
                                  ),
                                ),
                                Text(
                                  (u['university_name'] ?? 'N/A').toString(),
                                  style: TextStyle(color: Colors.white.withOpacity(0.7)),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
          ),
          if (totalPages > 1)
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: _currentPage > 1
                      ? () {
                          _currentPage--;
                          _applyFiltersAndPagination();
                        }
                      : null,
                  child: const Text('Prev'),
                ),
                Text('$_currentPage / $totalPages', style: const TextStyle(color: Colors.white70)),
                TextButton(
                  onPressed: _currentPage < totalPages
                      ? () {
                          _currentPage++;
                          _applyFiltersAndPagination();
                        }
                      : null,
                  child: const Text('Next'),
                ),
              ],
            ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }
}
