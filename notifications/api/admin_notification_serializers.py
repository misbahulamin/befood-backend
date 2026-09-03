"""Serializers for admin push notification APIs."""

from __future__ import annotations

import json

from rest_framework import serializers

from notifications.models import PushCampaign, PushCampaignRecipient

ALLOWED_DATA_KEYS = frozenset({'type', 'screen', 'entity_type', 'entity_id'})
MAX_DATA_BYTES = 4096


_DEFAULT_SCREEN_BY_TYPE = {
    'order': 'my_meal',
    'wallet': 'wallet',
    'delivery': 'delivery_places',
    'promotion': 'offer',
    'system': 'home',
}


class PushCampaignDataSerializer(serializers.Serializer):
    screen = serializers.CharField(required=False, allow_blank=True, max_length=100)
    entity_type = serializers.CharField(required=False, allow_blank=True, max_length=100)
    entity_id = serializers.CharField(required=False, allow_blank=True, max_length=100)


class PushCampaignTargetSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=['user', 'users', 'filter', 'all'])
    user_id = serializers.IntegerField(required=False)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        max_length=500,
    )
    filters = serializers.DictField(required=False, child=serializers.JSONField())
    confirm_broadcast = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        target_type = attrs.get('type')
        if target_type == 'user' and attrs.get('user_id') is None:
            raise serializers.ValidationError('user_id is required for single-user targeting.')
        if target_type == 'users' and not attrs.get('user_ids'):
            raise serializers.ValidationError('user_ids must not be empty.')
        if target_type == 'filter' and attrs.get('filters') is None:
            attrs['filters'] = {}
        return attrs


class PushCampaignSendSerializer(serializers.Serializer):
    title = serializers.CharField(min_length=1, max_length=255)
    body = serializers.CharField(min_length=1, max_length=4000)
    notification_type = serializers.ChoiceField(
        choices=[choice.value for choice in PushCampaign.NotificationType]
    )
    data = PushCampaignDataSerializer(required=False)
    target = PushCampaignTargetSerializer()

    def validate(self, attrs):
        raw_data = self.initial_data.get('data')
        if isinstance(raw_data, dict):
            unknown = set(raw_data.keys()) - ALLOWED_DATA_KEYS
            if unknown:
                raise serializers.ValidationError(
                    {'data': f'Unsupported data key(s): {", ".join(sorted(unknown))}.'}
                )
        nested = attrs.get('data') or {}
        payload = {key: str(val) for key, val in nested.items() if val is not None and val != ''}
        notification_type = attrs.get('notification_type') or ''
        if notification_type and 'type' not in payload:
            payload['type'] = str(notification_type)
        if 'screen' not in payload:
            default_screen = _DEFAULT_SCREEN_BY_TYPE.get(str(notification_type).lower())
            if default_screen:
                payload['screen'] = default_screen
        if len(json.dumps(payload).encode('utf-8')) > MAX_DATA_BYTES:
            raise serializers.ValidationError({'data': 'Data payload exceeds 4 KB.'})
        attrs['data'] = payload
        return attrs


class PushCampaignAcceptedSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model = PushCampaign
        fields = (
            'public_id',
            'status',
            'total_targets',
            'total_sent',
            'total_failed',
            'total_skipped',
            'created_by_email',
            'created_at',
        )


class PushCampaignListSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)

    class Meta:
        model = PushCampaign
        fields = (
            'public_id',
            'title',
            'notification_type',
            'target_type',
            'status',
            'total_targets',
            'total_sent',
            'total_failed',
            'total_skipped',
            'created_by_email',
            'created_at',
        )


class PushCampaignRecipientSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    device_platform = serializers.CharField(source='device.platform', read_only=True, default='')

    class Meta:
        model = PushCampaignRecipient
        fields = (
            'user_email',
            'device_platform',
            'status',
            'firebase_message_id',
            'error_message',
            'sent_at',
        )


class PushCampaignDetailSerializer(PushCampaignListSerializer):
    body = serializers.CharField(read_only=True)
    data = serializers.JSONField(read_only=True)
    target_config = serializers.JSONField(read_only=True)
    error_summary = serializers.CharField(read_only=True)
    ip_address = serializers.IPAddressField(read_only=True)
    user_agent = serializers.CharField(read_only=True)
    recipients = PushCampaignRecipientSerializer(many=True, read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta(PushCampaignListSerializer.Meta):
        fields = PushCampaignListSerializer.Meta.fields + (
            'body',
            'data',
            'target_config',
            'error_summary',
            'ip_address',
            'user_agent',
            'updated_at',
            'recipients',
        )
