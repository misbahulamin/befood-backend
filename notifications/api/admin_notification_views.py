"""Verified-admin push notification APIs."""

from __future__ import annotations

from django.db import transaction
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.api.admin_notification_serializers import (
    PushCampaignAcceptedSerializer,
    PushCampaignDetailSerializer,
    PushCampaignListSerializer,
    PushCampaignSendSerializer,
)
from notifications.api.openapi import (
    ADMIN_NOTIFICATIONS_TAG,
    PUSH_CAMPAIGN_SEND_REQUEST,
)
from notifications.models import PushCampaign
from notifications.services.notification_sender import (
    BroadcastConfirmationRequiredError,
    DuplicateCampaignError,
    create_campaign,
    enqueue_dispatch,
)
from user_management.api.permissions import IsVerifiedAdmin


class AdminPushCampaignPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _client_ip(request) -> str | None:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@extend_schema(
    tags=[ADMIN_NOTIFICATIONS_TAG],
    summary='Send push notification campaign',
    description=(
        'Verified admin only. Creates a push campaign and returns immediately with '
        '`202 Accepted` while FCM dispatch runs asynchronously.'
    ),
    request=PushCampaignSendSerializer,
    responses={
        202: PushCampaignAcceptedSerializer,
        409: PushCampaignAcceptedSerializer,
    },
    examples=[
        OpenApiExample(
            'Send promotion campaign',
            value=PUSH_CAMPAIGN_SEND_REQUEST,
            request_only=True,
        ),
    ],
)
class AdminPushCampaignSendView(APIView):
    permission_classes = [IsVerifiedAdmin]

    def post(self, request):
        serializer = PushCampaignSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        idempotency_key = (request.headers.get('Idempotency-Key') or '').strip()

        try:
            campaign, is_new = create_campaign(
                created_by=request.user,
                title=data['title'],
                body=data['body'],
                notification_type=data['notification_type'],
                data=data.get('data') or {},
                target=data['target'],
                ip_address=_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                idempotency_key=idempotency_key,
            )
        except DuplicateCampaignError as exc:
            payload = PushCampaignAcceptedSerializer(exc.campaign).data
            return Response(payload, status=status.HTTP_409_CONFLICT)
        except BroadcastConfirmationRequiredError as exc:
            raise ValidationError(
                {
                    'target': [
                        f'Broadcast confirmation required for {exc.eligible_count} eligible users. '
                        'Set confirm_broadcast to true.'
                    ]
                }
            ) from exc

        if is_new:
            transaction.on_commit(lambda campaign_id=campaign.id: enqueue_dispatch(campaign_id))

        return Response(
            PushCampaignAcceptedSerializer(campaign).data,
            status=status.HTTP_202_ACCEPTED,
        )


@extend_schema_view(
    list=extend_schema(
        tags=[ADMIN_NOTIFICATIONS_TAG],
        summary='List push notification campaigns',
        parameters=[
            OpenApiParameter(name='status', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='notification_type', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='created_from', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='created_to', type=str, location=OpenApiParameter.QUERY),
        ],
    ),
    retrieve=extend_schema(
        tags=[ADMIN_NOTIFICATIONS_TAG],
        summary='Get push campaign detail',
    ),
)
class AdminPushCampaignViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsVerifiedAdmin]
    lookup_field = 'public_id'
    pagination_class = AdminPushCampaignPagination

    def get_queryset(self):
        queryset = PushCampaign.objects.select_related('created_by').prefetch_related(
            'recipients__user',
            'recipients__device',
        )
        params = self.request.query_params

        status_filter = params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        notification_type = params.get('notification_type')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        created_from = parse_datetime(params.get('created_from') or '')
        if created_from:
            queryset = queryset.filter(created_at__gte=created_from)

        created_to = parse_datetime(params.get('created_to') or '')
        if created_to:
            queryset = queryset.filter(created_at__lte=created_to)

        return queryset.order_by('-created_at', '-id')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PushCampaignDetailSerializer
        return PushCampaignListSerializer
