NOTIFICATIONS_TAG = 'Notifications'
ADMIN_NOTIFICATIONS_TAG = 'Admin Notifications'

DEVICE_TOKEN_REGISTER_SUCCESS = {
    'success': True,
    'message': 'Device registered successfully',
}

DEVICE_TOKEN_REMOVE_SUCCESS = {
    'success': True,
    'message': 'Device deactivated successfully',
}

DEVICE_TOKEN_REGISTER_REQUEST = {
    'token': 'fcm_example_token_string_from_flutter',
    'platform': 'android',
    'device_name': 'Pixel 8',
    'app_version': '1.2.0',
}

DEVICE_TOKEN_REMOVE_REQUEST = {
    'token': 'fcm_example_token_string_from_flutter',
}

PUSH_CAMPAIGN_SEND_REQUEST = {
    'title': 'Special Offer',
    'body': '20% discount today',
    'notification_type': 'promotion',
    'data': {
        'screen': 'promotion_detail',
        'entity_type': 'promotion',
        'entity_id': 'summer-sale',
    },
    'target': {'type': 'all', 'confirm_broadcast': True},
}

PUSH_CAMPAIGN_ACCEPTED_EXAMPLE = {
    'public_id': '550e8400-e29b-41d4-a716-446655440000',
    'status': 'processing',
    'total_targets': 5000,
    'total_sent': 0,
    'total_failed': 0,
    'total_skipped': 0,
    'created_by_email': 'admin@example.com',
    'created_at': '2026-09-02T10:00:00Z',
}

PUSH_CAMPAIGN_DUPLICATE_EXAMPLE = {
    'detail': 'Duplicate campaign detected within deduplication window.',
    'public_id': '550e8400-e29b-41d4-a716-446655440000',
}
