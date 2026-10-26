import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:record/record.dart';
import '../../config/api_config.dart';

import '../tr.dart';
class VoiceTemplateButton extends StatefulWidget {
  final bool enabled;
  final String baseUrl;
  final int userId;
  final String spacingUnit;
  final Map<String, dynamic> Function() currentRules;
  final void Function(Map<String, dynamic> patch) onPatchReady;

  const VoiceTemplateButton({
    super.key,
    required this.enabled,
    required this.baseUrl,
    required this.userId,
    required this.spacingUnit,
    required this.currentRules,
    required this.onPatchReady,
  });

  @override
  State<VoiceTemplateButton> createState() => _VoiceTemplateButtonState();
}

class _VoiceTemplateButtonState extends State<VoiceTemplateButton> {
  final _recorder = AudioRecorder();
  bool _recording = false;
  bool _busy = false;

  // Stream-based recording: audio memory mein jama hota hai
  final BytesBuilder _pcm = BytesBuilder();
  StreamSubscription<Uint8List>? _sub;

  @override
  void dispose() {
    _sub?.cancel();
    _recorder.dispose();
    super.dispose();
  }

  void _snack(String m) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  Uint8List _wav(Uint8List pcm, int rate) {
    final b = BytesBuilder();
    void i32(int v) =>
        b.add(Uint8List(4)..buffer.asByteData().setUint32(0, v, Endian.little));
    void i16(int v) =>
        b.add(Uint8List(2)..buffer.asByteData().setUint16(0, v, Endian.little));
    b.add('RIFF'.codeUnits);
    i32(36 + pcm.length);
    b.add('WAVEfmt '.codeUnits);
    i32(16);
    i16(1);
    i16(1);
    i32(rate);
    i32(rate * 2);
    i16(2);
    i16(16);
    b.add('data'.codeUnits);
    i32(pcm.length);
    b.add(pcm);
    return b.toBytes();
  }

  Future<void> _toggle() async {
    if (_busy) return;
    if (_recording) {
      await _stopAndSend();
      return;
    }

    try {
      if (!await _recorder.hasPermission()) {
        _snack('Microphone permission nahi mili');
        return;
      }
      debugPrint('[VOICE] startStream');
      _pcm.clear();
      final stream = await _recorder.startStream(const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
      ));
      _sub = stream.listen((d) => _pcm.add(d));
      if (mounted) setState(() => _recording = true);
    } catch (e) {
      debugPrint('[VOICE] start error: $e');
      _snack('Recording start nahi hui: $e');
    }
  }

  Future<void> _stopAndSend() async {
    // UI foran badlo, taake stuck na lage
    setState(() {
      _recording = false;
      _busy = true;
    });

    try {
      debugPrint('[VOICE] stopping...');
      await _sub?.cancel();
      // stop() hang bhi kare to hamara data pehle se jama hai
      try {
        await _recorder.stop().timeout(const Duration(seconds: 2));
      } catch (_) {}

      final pcm = _pcm.takeBytes();
      debugPrint('[VOICE] pcm bytes = ${pcm.length}');
      if (pcm.length < 3200) throw 'Audio bohat chhoti hai, mic data nahi aaya';
      final wav = _wav(pcm, 16000);

      final url =
          '${widget.baseUrl}/admin/templates/voice-patch?user_id=${widget.userId}';
      debugPrint('[VOICE] POST $url');

      final req = http.MultipartRequest('POST', Uri.parse(url));
      final headers = Map<String, String>.from(ApiConfig.getHeaders());
      headers.remove('Content-Type');
      req.headers.addAll(headers);
      req.fields['spacing_unit'] = widget.spacingUnit;
      req.fields['current'] = jsonEncode(widget.currentRules());
      req.files.add(
          http.MultipartFile.fromBytes('audio', wav, filename: 'voice.wav'));

      final res = await http.Response.fromStream(
          await req.send().timeout(const Duration(seconds: 60)));
      debugPrint('[VOICE] status ${res.statusCode}: ${res.body}');
      if (res.statusCode != 200) throw 'Server ${res.statusCode}: ${res.body}';

      final body = jsonDecode(res.body) as Map<String, dynamic>;
      final patch = Map<String, dynamic>.from(body['patch'] ?? {});
      if (!mounted) return;

      final ok = await _confirm(
        transcript: (body['transcript'] ?? '').toString(),
        patch: patch,
        unclear: (body['unclear'] ?? '').toString(),
      );
      if (ok == true && patch.isNotEmpty) widget.onPatchReady(patch);
    } catch (e) {
      debugPrint('[VOICE] error: $e');
      if (mounted) _snack('Voice error: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<bool?> _confirm({
    required String transcript,
    required Map<String, dynamic> patch,
    required String unclear,
  }) {
    return showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Tr('Voice command'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('tanscript: "$transcript"',
                  style: const TextStyle(fontStyle: FontStyle.italic)),
              const SizedBox(height: 12),
              if (patch.isEmpty) const Tr('Koi change samajh nahi aaya.'),
              ...patch.entries.map((e) => Text('• ${e.key}: ${e.value}')),
              if (unclear.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text('Samajh nahi aaya: $unclear',
                    style: const TextStyle(color: Colors.orange)),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Tr('Cancel')),
          if (patch.isNotEmpty)
            ElevatedButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Tr('Apply to form')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: widget.enabled && !_busy ? _toggle : null,
      icon: _busy
          ? const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2))
          : Icon(_recording ? Icons.stop_circle : Icons.mic,
              color: _recording ? Colors.red : null),
      label: Text(_busy
          ? 'Processing...'
          : _recording
              ? 'Stop & apply'
              : 'Voice command'),
    );
  }
}