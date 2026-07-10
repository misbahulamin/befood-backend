from rest_framework import serializers
from notifications.models import NotificationTemplate, Notification, NotificationPreference, PushLog

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
