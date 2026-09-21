from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from delivery_schedules.models import DeliverySchedule


def _raise_drf(exc: DjangoValidationError) -> None:
    if hasattr(exc, 'message_dict'):
        raise serializers.ValidationError(exc.message_dict) from exc
    raise serializers.ValidationError({'detail': list(exc.messages)}) from exc


class DeliveryScheduleAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliverySchedule
        fields = (
            'public_id',
            'name',
            'start_time',
            'end_time',
            'is_active',
            'sort_order',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'public_id',
            'created_at',
            'updated_at',
        )

    def validate_name(self, value):
        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError('Name is required.')
        qs = DeliverySchedule.objects.filter(name__iexact=name)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                'A delivery schedule with this name already exists.'
            )
        return name

    def validate(self, attrs):
        start_time = attrs.get('start_time', getattr(self.instance, 'start_time', None))
        end_time = attrs.get('end_time', getattr(self.instance, 'end_time', None))
        if start_time is not None and end_time is not None and start_time >= end_time:
            raise serializers.ValidationError(
                {
                    'end_time': (
                        'End time must be after start time (same-day windows only).'
                    )
                }
            )
        return attrs

    def create(self, validated_data):
        instance = DeliverySchedule(**validated_data)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            _raise_drf(exc)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            _raise_drf(exc)
        instance.save()
        return instance


class PublicDeliveryScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliverySchedule
        fields = (
            'public_id',
            'name',
            'start_time',
            'end_time',
            'sort_order',
        )
        read_only_fields = fields
