from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from notifications.models import NotificationTemplate, Notification, NotificationPreference, PushLog
from .serializers import NotificationTemplateSerializer, NotificationSerializer, NotificationPreferenceSerializer, PushLogSerializer

class NotificationTemplateViewSet(viewsets.ModelViewSet):
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated]

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    queryset = NotificationPreference.objects.all()
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

class PushLogViewSet(viewsets.ModelViewSet):
    queryset = PushLog.objects.all()
    serializer_class = PushLogSerializer
    permission_classes = [IsAuthenticated]
