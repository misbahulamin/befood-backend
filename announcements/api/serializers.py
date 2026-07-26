from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from announcements.models import Announcement
from announcements.services import compute_lifecycle_status
from announcements.utils.banner_image import (
    validate_image_extension,
    validate_image_size,
)


def _raise_drf(exc: DjangoValidationError) -> None:
    if hasattr(exc, 'message_dict'):
        raise serializers.ValidationError(exc.message_dict) from exc
    raise serializers.ValidationError({'detail': list(exc.messages)}) from exc


def _absolute_image_url(obj, request):
    if not obj.image:
        return None
    url = obj.image.url
    return request.build_absolute_uri(url) if request else url


class PublicAnnouncementSerializer(serializers.ModelSerializer):
    """Lean payload for unauthenticated website popups."""

    image = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = (
            'public_id',
            'title',
            'description',
            'type',
            'severity',
            'image',
            'button_text',
            'button_url',
            'publish_at',
            'publish_until',
            'priority',
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_image(self, obj):
        return _absolute_image_url(obj, self.context.get('request'))


class AnnouncementAdminSerializer(serializers.ModelSerializer):
    """Full admin payload including publish controls and lifecycle status."""

    lifecycle_status = serializers.SerializerMethodField()
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Announcement
        fields = (
            'public_id',
            'title',
            'description',
            'type',
            'severity',
            'image',
            'button_text',
            'button_url',
            'is_published',
            'publish_at',
            'publish_until',
            'priority',
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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['image'] = _absolute_image_url(instance, self.context.get('request'))
        return data

    def get_lifecycle_status(self, obj):
        return compute_lifecycle_status(obj)

    def validate_image(self, value):
        if value is None:
            return value
        try:
            validate_image_extension(value.name)
            validate_image_size(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    def create(self, validated_data):
        announcement = Announcement(**validated_data)
        try:
            announcement.full_clean()
        except DjangoValidationError as exc:
            _raise_drf(exc)
        announcement.save()
        return announcement

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            _raise_drf(exc)
        instance.save()
        return instance
