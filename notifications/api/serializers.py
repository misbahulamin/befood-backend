from rest_framework import serializers
from notifications.models import NotificationTemplate, Notification, NotificationPreference, PushLog
from user_management.models import DeviceToken


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = "__all__"

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = "__all__"

class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = "__all__"

class PushLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushLog
        fields = "__all__"


class DeviceTokenRegisterSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255, trim_whitespace=True)
    platform = serializers.ChoiceField(choices=DeviceToken.Platform.choices)
    device_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    app_version = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')

    def validate_token(self, value):
        token = (value or '').strip()
        if not token:
            raise serializers.ValidationError('Token is required.')
        if len(token) < 10:
            raise serializers.ValidationError('Token must be at least 10 characters.')
        return token


class DeviceTokenRemoveSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=255, trim_whitespace=True)

    def validate_token(self, value):
        token = (value or '').strip()
        if not token:
            raise serializers.ValidationError('Token is required.')
        if len(token) < 10:
            raise serializers.ValidationError('Token must be at least 10 characters.')
        return token


class DeviceTokenSuccessResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
