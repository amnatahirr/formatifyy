import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';

enum AnalysisStatus { processing, completed, failed }

class AnalysisJob {
  AnalysisJob({required this.documentId, required this.name, this.onOpen});
  final int documentId;
  final String name;
  final VoidCallback? onOpen;
  AnalysisStatus status = AnalysisStatus.processing;
  String? error;
  Map<String, dynamic>? result;
  final Completer<Map<String, dynamic>> completer = Completer();
}

class AnalysisJobProvider extends ChangeNotifier {
  final Map<int, AnalysisJob> _jobs = {};
  final Map<int, Timer> _timers = {};

  /// Set from main.dart: MaterialApp(scaffoldMessengerKey: ...)
  GlobalKey<ScaffoldMessengerState>? messengerKey;

  /// Doc whose AnalyzeScreen is currently open (no snackbar for it).
  int? activeDocId;
  List<AnalysisJob> get jobs => _jobs.values.toList().reversed.toList();

void openJob(AnalysisJob job) {
  if (activeDocId == job.documentId) return; // screen pehle se khuli hai
  final open = job.onOpen;
  if (open == null) {
    debugPrint('[AnalysisJob] onOpen is null for doc ${job.documentId}');
    return;
  }
  // snackbar band hone ke baad route push karo
  WidgetsBinding.instance.addPostFrameCallback((_) => open());
}

void dismissJob(int documentId) {
  final j = _jobs[documentId];
  if (j == null || j.status == AnalysisStatus.processing) return;
  _jobs.remove(documentId);
  notifyListeners();
}

  AnalysisJob? jobFor(int id) => _jobs[id];
  int get runningCount =>
      _jobs.values.where((j) => j.status == AnalysisStatus.processing).length;

  Future<Map<String, dynamic>> startOrAttach({
    required int documentId,
    required int userId,
    required String name,
    bool freeform = false,
    bool force = false,
    VoidCallback? onOpen,
  }) async {
    final existing = _jobs[documentId];
    if (existing != null && !force) {
      if (existing.status == AnalysisStatus.completed) return existing.result!;
      if (existing.status == AnalysisStatus.processing) {
        return existing.completer.future; // re-attach to running job
      }
    }
    _timers.remove(documentId)?.cancel();

    final job = AnalysisJob(documentId: documentId, name: name, onOpen: onOpen);
    job.completer.future.catchError((_) => <String, dynamic>{}); // no unhandled error
    _jobs[documentId] = job;
    notifyListeners();

    final base = ApiConfig.getBaseUrl();
    try {
      final resp = await http.post(
        Uri.parse('$base/documents/analyze-start/$documentId'
            '?user_id=$userId&freeform=$freeform'),
        headers: ApiConfig.getHeaders(),
      );
      if (resp.statusCode != 200) {
        throw Exception('Could not start analysis (${resp.statusCode}): ${resp.body}');
      }
      _poll(job, userId, base);
    } catch (e) {
      _fail(job, e.toString());
    }
    return job.completer.future;
  }

  void _poll(AnalysisJob job, int userId, String base) {
    var busy = false;
    _timers[job.documentId] =
        Timer.periodic(const Duration(seconds: 3), (t) async {
      if (busy) return;
      busy = true;
      try {
        final s = await http.get(Uri.parse(
            '$base/documents/analyze-status/${job.documentId}?user_id=$userId'));
        if (s.statusCode != 200) return;
        final st = jsonDecode(s.body) as Map<String, dynamic>;
        if (st['status'] == 'completed') {
          final r = await http.get(Uri.parse(
              '$base/documents/analyze-result/${job.documentId}?user_id=$userId'));
          if (r.statusCode != 200) return; // retry next tick
          t.cancel();
          _complete(job, jsonDecode(r.body) as Map<String, dynamic>);
        } else if (st['status'] == 'failed') {
          t.cancel();
          _fail(job, st['error']?.toString() ?? 'Analysis failed');
        }
      } catch (_) {
        // transient network error — keep polling
      } finally {
        busy = false;
      }
    });
  }

  void _complete(AnalysisJob job, Map<String, dynamic> data) {
    job.status = AnalysisStatus.completed;
    job.result = data;
    if (!job.completer.isCompleted) job.completer.complete(data);
    notifyListeners();

    if (activeDocId != job.documentId) {
      messengerKey?.currentState?.showSnackBar(SnackBar(
        content: Text('Analysis complete: ${job.name}'),
        backgroundColor: const Color(0xFF10B981),
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 8),
        action: job.onOpen == null
    ? null
    : SnackBarAction(
        label: 'VIEW',
        textColor: Colors.white,
        onPressed: () => openJob(job),
      ),
      ));
    }
  }

  void _fail(AnalysisJob job, String msg) {
    job.status = AnalysisStatus.failed;
    job.error = msg;
    if (!job.completer.isCompleted) job.completer.completeError(Exception(msg));
    notifyListeners();
    if (activeDocId != job.documentId) {
      messengerKey?.currentState?.showSnackBar(SnackBar(
        content: Text('Analysis failed: ${job.name}'),
        backgroundColor: const Color(0xFFEF4444),
        behavior: SnackBarBehavior.floating,
      ));
    }
  }
}