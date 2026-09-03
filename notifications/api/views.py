"""Customer notification inbox APIs (list, unread count, mark read)."""

from __future__ import annotations

from rest_framework import generics, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import (
    Notification,
    NotificationPreference,
    NotificationTemplate,
    PushLog,
)
from notifications.api.serializers import (
    InboxNotificationSerializer,
    NotificationPreferenceSerializer,
    NotificationSerializer,
    NotificationTemplateSerializer,
    PushLogSerializer,
    UnreadCountSerializer,
)


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated]


class NotificationViewSet(viewsets.ModelViewSet):
    """Legacy viewset — scoped to the authenticated user only."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return NotificationPreference.objects.filter(user=self.request.user)


class PushLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PushLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PushLog.objects.filter(notification__user=self.request.user)


class NotificationInboxListView(generics.ListAPIView):
    """Paginated inbox for the authenticated customer."""

    permission_classes = [IsAuthenticated]
    serializer_class = InboxNotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')


class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response(UnreadCountSerializer({'count': count}).data)


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read'])
        return Response(InboxNotificationSerializer(notification).data)


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True
        )
        return Response({'updated': updated})
