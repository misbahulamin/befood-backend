from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from notices.models import Notice
from notices.services import compute_lifecycle_status


def _raise_drf(exc: DjangoValidationError) -> None:
    if hasattr(exc, 'message_dict'):
        raise serializers.ValidationError(exc.message_dict) from exc
    raise serializers.ValidationError({'detail': list(exc.messages)}) from exc


class PublicNoticeSerializer(serializers.ModelSerializer):
    """Lean bilingual payload for unauthenticated website visitors."""

    class Meta:
        model = Notice
        fields = (
            'public_id',
            'title_en',
            'title_bn',
            'body_en',
            'body_bn',
            'severity',
            'publish_at',
            'publish_until',
            'sort_order',
        )
        read_only_fields = fields


class NoticeAdminSerializer(serializers.ModelSerializer):
    """Full admin payload including publish controls and lifecycle status."""

    lifecycle_status = serializers.SerializerMethodField()

    class Meta:
        model = Notice
        fields = (
            'public_id',
            'title_en',
            'title_bn',
            'body_en',
            'body_bn',
            'severity',
            'is_published',
            'publish_at',
            'publish_until',
            'sort_order',
            'lifecycle_status',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'public_id',
            'lifecycle_status',
            'created_at',
            'updated_at',
        )

    def get_lifecycle_status(self, obj):
        return compute_lifecycle_status(obj)

    def create(self, validated_data):
        notice = Notice(**validated_data)
        try:
            notice.full_clean()
        except DjangoValidationError as exc:
            _raise_drf(exc)
        notice.save()
        return notice

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            _raise_drf(exc)
        instance.save()
        return instance
