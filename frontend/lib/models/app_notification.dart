import 'dart:convert';

class AppNotification {
  final int id;
  final String type;
  final String title;
  final String body;
  final String? entityType;
  final int? entityId;
  final Map<String, dynamic>? payload;
  final bool isRead;
  final String createdAt;
  final String? readAt;

  AppNotification({
    required this.id,
    required this.type,
    required this.title,
    required this.body,
    this.entityType,
    this.entityId,
    this.payload,
    required this.isRead,
    required this.createdAt,
    this.readAt,
  });

  factory AppNotification.fromJson(Map<String, dynamic> json) {
    // Handle both entity_type and related_type
    final entityType = json['entity_type'] as String? ?? json['related_type'] as String?;
    // Handle both entity_id and related_id
    final entityId = json['entity_id'] as int? ?? _asInt(json['related_id']);
    // Handle both payload and payload_json (can be string or map)
    final payload = _parsePayload(json['payload'] ?? json['payload_json']);

    return AppNotification(
      id: json['id'] as int,
      type: json['type'] as String,
      title: json['title'] as String,
      body: json['body'] as String,
      entityType: entityType,
      entityId: entityId,
      payload: payload,
      isRead: json['is_read'] as bool? ?? false,
      createdAt: json['created_at'] as String,
      readAt: json['read_at'] as String?,
    );
  }

  static int? _asInt(dynamic value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value == null) return null;
    return int.tryParse(value.toString());
  }

  static Map<String, dynamic>? _parsePayload(dynamic value) {
    if (value == null) return null;
    if (value is Map<String, dynamic>) return value;
    if (value is Map) return Map<String, dynamic>.from(value);
    if (value is String) {
      try {
        final decoded = value as String;
        if (decoded.isEmpty) return null;
        return Map<String, dynamic>.from(
          (jsonDecode(decoded) as Map),
        );
      } catch (_) {
        return null;
      }
    }
    return null;
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'type': type,
      'title': title,
      'body': body,
      'entity_type': entityType,
      'entity_id': entityId,
      'payload': payload,
      'is_read': isRead,
      'created_at': createdAt,
      'read_at': readAt,
    };
  }
}
