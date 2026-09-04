from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from support.api.serializers import (
    AdminConversationDetailSerializer,
    AdminConversationListSerializer,
    AdminReplySerializer,
    AdminStatusSerializer,
    SupportMessageSerializer,
)
from support.models import SupportMessage
from support.services.conversations import (
    apply_admin_conversation_filters,
    admin_conversations_queryset,
    update_conversation_status,
)
from support.services.messages import EmptyMessageError, mark_read_by_admin, post_message
from support.services.notifications import schedule_offline_notifications
from user_management.api.permissions import IsVerifiedAdmin


class AdminSupportPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminSupportMessagePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


@extend_schema_view(
    list=extend_schema(
        summary='List support conversations',
        parameters=[
            OpenApiParameter('status', str, required=False),
            OpenApiParameter('has_unread', bool, required=False),
            OpenApiParameter('q', str, required=False),
            OpenApiParameter('page', int, required=False),
            OpenApiParameter('page_size', int, required=False),
        ],
        tags=['Admin Support'],
    ),
    retrieve=extend_schema(summary='Support conversation detail', tags=['Admin Support']),
)
class AdminSupportConversationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsVerifiedAdmin]
    pagination_class = AdminSupportPagination
    lookup_field = 'public_id'
    serializer_class = AdminConversationListSerializer

    def get_queryset(self):
        qs = admin_conversations_queryset()
        params = self.request.query_params
        status_value = params.get('status') or None
        q = params.get('q') or None
        has_unread_raw = params.get('has_unread')
        has_unread = None
        if has_unread_raw is not None:
            normalized = str(has_unread_raw).strip().lower()
            if normalized in ('1', 'true', 'yes'):
                has_unread = True
            elif normalized in ('0', 'false', 'no'):
                has_unread = False
            else:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({'has_unread': ['Must be true or false.']})
        if status_value and status_value not in ('open', 'closed', 'archived'):
            from rest_framework.exceptions import ValidationError

            raise ValidationError({'status': ['Invalid status.']})
        unknown = set(params.keys()) - {
            'status',
            'has_unread',
            'q',
            'page',
            'page_size',
        }
        if unknown:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({'detail': f'Unsupported filters: {sorted(unknown)}'})
        return apply_admin_conversation_filters(
            qs,
            status=status_value,
            has_unread=has_unread,
            q=q,
        )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AdminConversationDetailSerializer
        return AdminConversationListSerializer

    def retrieve(self, request, *args, **kwargs):
        conversation = self.get_object()
        mark_read_by_admin(conversation)
        messages_qs = SupportMessage.objects.filter(conversation=conversation).order_by(
            'created_at', 'id'
        )
        paginator = AdminSupportMessagePagination()
        page = paginator.paginate_queryset(messages_qs, request, view=self)
        return Response(
            {
                'conversation': AdminConversationDetailSerializer(conversation).data,
                'messages': SupportMessageSerializer(page, many=True).data,
                'pagination': {
                    'count': paginator.page.paginator.count,
                    'next': paginator.get_next_link(),
                    'previous': paginator.get_previous_link(),
                    'page_size': paginator.get_page_size(request),
                },
            }
        )

    @extend_schema(
        summary='Admin reply to conversation',
        request=AdminReplySerializer,
        responses={201: SupportMessageSerializer},
        tags=['Admin Support'],
    )
    @action(detail=True, methods=['post'], url_path='reply')
    def reply(self, request, public_id=None):
        conversation = self.get_object()
        serializer = AdminReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = post_message(
                conversation=conversation,
                sender_type=SupportMessage.SenderType.ADMIN,
                sender_user=request.user,
                body=serializer.validated_data['message'],
            )
        except EmptyMessageError as exc:
            return Response({'message': [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        schedule_offline_notifications(message)
        return Response(SupportMessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary='Update conversation status',
        request=AdminStatusSerializer,
        responses={200: AdminConversationDetailSerializer},
        tags=['Admin Support'],
    )
    @action(detail=True, methods=['patch'], url_path='status')
    def set_status(self, request, public_id=None):
        conversation = self.get_object()
        serializer = AdminStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = update_conversation_status(
            conversation,
            status=serializer.validated_data['status'],
        )
        return Response(AdminConversationDetailSerializer(conversation).data)
