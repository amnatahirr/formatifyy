import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../config/api_config.dart';
import '../config/dev_user_config.dart';

typedef VcEventHandler = void Function(Map<String, dynamic> event);

class CollaborationSocket {
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  int? _projectId;

  /// Connects using user id from --dart-define=USER_ID (member1 → 1, member2 → 2)
  void connect({
    required int projectId,
    required VcEventHandler onEvent,
    void Function(Object error)? onError,
    int? userId,
  }) {
    disconnect();
    _projectId = projectId;
    final uid = userId ?? DevUserConfig.backendUserId;
    final wsBase = ApiConfig.getWsBaseUrl();
    final uri = Uri.parse('$wsBase/api/vc/ws/projects/$projectId?user_id=$uid');
    _channel = WebSocketChannel.connect(uri);
    _subscription = _channel!.stream.listen(
      (data) {
        try {
          final decoded = jsonDecode(data as String) as Map<String, dynamic>;
          onEvent(decoded);
        } catch (_) {}
      },
      onError: onError,
    );
  }

  void ping() {
    _channel?.sink.add('ping');
  }

  void disconnect() {
    _subscription?.cancel();
    _subscription = null;
    _channel?.sink.close();
    _channel = null;
    _projectId = null;
  }

  bool get isConnected => _channel != null;
  int? get projectId => _projectId;
}
