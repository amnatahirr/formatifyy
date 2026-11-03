import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/models/app_notification.dart';

void main() {
  group('AppNotification.fromJson', () {
    test('parses standard shape with entity_type and entity_id', () {
      final json = {
        'id': 1,
        'type': 'test',
        'title': 'Test Title',
        'body': 'Test Body',
        'entity_type': 'document',
        'entity_id': 123,
        'payload': {'key': 'value'},
        'is_read': false,
        'created_at': '2024-01-01T00:00:00Z',
        'read_at': null,
      };

      final notification = AppNotification.fromJson(json);

      expect(notification.id, 1);
      expect(notification.type, 'test');
      expect(notification.title, 'Test Title');
      expect(notification.body, 'Test Body');
      expect(notification.entityType, 'document');
      expect(notification.entityId, 123);
      expect(notification.payload, {'key': 'value'});
      expect(notification.isRead, false);
      expect(notification.createdAt, '2024-01-01T00:00:00Z');
      expect(notification.readAt, null);
    });

    test('parses shape with related_type and related_id', () {
      final json = {
        'id': 2,
        'type': 'test',
        'title': 'Test Title',
        'body': 'Test Body',
        'related_type': 'comment',
        'related_id': 456,
        'payload': {'key': 'value'},
        'is_read': true,
        'created_at': '2024-01-01T00:00:00Z',
        'read_at': '2024-01-02T00:00:00Z',
      };

      final notification = AppNotification.fromJson(json);

      expect(notification.id, 2);
      expect(notification.entityType, 'comment');
      expect(notification.entityId, 456);
      expect(notification.isRead, true);
      expect(notification.readAt, '2024-01-02T00:00:00Z');
    });

    test('handles payload_json as JSON string', () {
      final json = {
        'id': 3,
        'type': 'test',
        'title': 'Test Title',
        'body': 'Test Body',
        'payload_json': '{"screen": "analyze", "document_id": 789}',
        'is_read': false,
        'created_at': '2024-01-01T00:00:00Z',
      };

      final notification = AppNotification.fromJson(json);

      expect(notification.payload, {'screen': 'analyze', 'document_id': 789});
    });

    test('handles payload_json as Map', () {
      final json = {
        'id': 4,
        'type': 'test',
        'title': 'Test Title',
        'body': 'Test Body',
        'payload_json': {'screen': 'collaboration', 'project_id': 999},
        'is_read': false,
        'created_at': '2024-01-01T00:00:00Z',
      };

      final notification = AppNotification.fromJson(json);

      expect(notification.payload, {'screen': 'collaboration', 'project_id': 999});
    });

    test('handles missing fields without throwing', () {
      final json = {
        'id': 5,
        'type': 'test',
        'title': 'Test Title',
        'body': 'Test Body',
        'is_read': false,
        'created_at': '2024-01-01T00:00:00Z',
      };

      final notification = AppNotification.fromJson(json);

      expect(notification.entityType, null);
      expect(notification.entityId, null);
      expect(notification.payload, null);
    });

    test('handles null payload_json string', () {
      final json = {
        'id': 6,
        'type': 'test',
        'title': 'Test Title',
        'body': 'Test Body',
        'payload_json': null,
        'is_read': false,
        'created_at': '2024-01-01T00:00:00Z',
      };

      final notification = AppNotification.fromJson(json);

      expect(notification.payload, null);
    });

    test('handles empty payload_json string', () {
      final json = {
        'id': 7,
        'type': 'test',
        'title': 'Test Title',
        'body': 'Test Body',
        'payload_json': '',
        'is_read': false,
        'created_at': '2024-01-01T00:00:00Z',
      };

      final notification = AppNotification.fromJson(json);

      expect(notification.payload, null);
    });

    test('handles invalid payload_json string gracefully', () {
      final json = {
        'id': 8,
        'type': 'test',
        'title': 'Test Title',
        'body': 'Test Body',
        'payload_json': 'not valid json',
        'is_read': false,
        'created_at': '2024-01-01T00:00:00Z',
      };

      final notification = AppNotification.fromJson(json);

      expect(notification.payload, null);
    });

    test('handles related_id as string', () {
      final json = {
        'id': 9,
        'type': 'test',
        'title': 'Test Title',
        'body': 'Test Body',
        'related_id': '789',
        'is_read': false,
        'created_at': '2024-01-01T00:00:00Z',
      };

      final notification = AppNotification.fromJson(json);

      expect(notification.entityId, 789);
    });

    test('prioritizes entity_type over related_type when both present', () {
      final json = {
        'id': 10,
        'type': 'test',
        'title': 'Test Title',
        'body': 'Test Body',
        'entity_type': 'document',
        'related_type': 'comment',
        'is_read': false,
        'created_at': '2024-01-01T00:00:00Z',
      };

      final notification = AppNotification.fromJson(json);

      expect(notification.entityType, 'document');
    });

    test('prioritizes entity_id over related_id when both present', () {
      final json = {
        'id': 11,
        'type': 'test',
        'title': 'Test Title',
        'body': 'Test Body',
        'entity_id': 123,
        'related_id': 456,
        'is_read': false,
        'created_at': '2024-01-01T00:00:00Z',
      };

      final notification = AppNotification.fromJson(json);

      expect(notification.entityId, 123);
    });
  });

  group('AppNotification.toJson', () {
    test('serializes to standard shape', () {
      final notification = AppNotification(
        id: 1,
        type: 'test',
        title: 'Test Title',
        body: 'Test Body',
        entityType: 'document',
        entityId: 123,
        payload: {'key': 'value'},
        isRead: false,
        createdAt: '2024-01-01T00:00:00Z',
        readAt: null,
      );

      final json = notification.toJson();

      expect(json['id'], 1);
      expect(json['type'], 'test');
      expect(json['title'], 'Test Title');
      expect(json['body'], 'Test Body');
      expect(json['entity_type'], 'document');
      expect(json['entity_id'], 123);
      expect(json['payload'], {'key': 'value'});
      expect(json['is_read'], false);
      expect(json['created_at'], '2024-01-01T00:00:00Z');
      expect(json['read_at'], null);
    });
  });
}
