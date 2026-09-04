from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from support.api.serializers import (
    CustomerConversationSerializer,
    SupportMessageCreateSerializer,
    SupportMessageSerializer,
)
from support.models import SupportMessage
from support.services.conversations import get_or_create_conversation
from support.services.messages import EmptyMessageError, mark_read_by_customer, post_message
from support.services.notifications import schedule_offline_notifications
from user_management.api.permissions import HasCustomerProfile


class SupportMessagePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


class CustomerInboxView(APIView):
    permission_classes = [HasCustomerProfile]

    @extend_schema(
        summary='Customer support inbox',
        responses={200: CustomerConversationSerializer},
        parameters=[
            OpenApiParameter('page', int, required=False),
            OpenApiParameter('page_size', int, required=False),
        ],
        tags=['Support'],
    )
    def get(self, request):
        conversation = get_or_create_conversation(request.user.customer_profile)
        mark_read_by_customer(conversation)
        messages_qs = SupportMessage.objects.filter(conversation=conversation).order_by(
            'created_at', 'id'
        )
        paginator = SupportMessagePagination()
        page = paginator.paginate_queryset(messages_qs, request, view=self)
        return Response(
            {
                'conversation': CustomerConversationSerializer(conversation).data,
                'messages': SupportMessageSerializer(page, many=True).data,
                'pagination': {
                    'count': paginator.page.paginator.count,
                    'next': paginator.get_next_link(),
                    'previous': paginator.get_previous_link(),
                    'page_size': paginator.get_page_size(request),
                },
            }
        )


class CustomerMessageCreateView(APIView):
    permission_classes = [HasCustomerProfile]

    @extend_schema(
        summary='Send support message (REST fallback)',
        request=SupportMessageCreateSerializer,
        responses={201: SupportMessageSerializer},
        tags=['Support'],
    )
    def post(self, request):
        serializer = SupportMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = get_or_create_conversation(request.user.customer_profile)
        try:
            message = post_message(
                conversation=conversation,
                sender_type=SupportMessage.SenderType.CUSTOMER,
                sender_user=request.user,
                body=serializer.validated_data['message'],
            )
        except EmptyMessageError as exc:
            return Response(
                {'message': [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        schedule_offline_notifications(message)
        return Response(SupportMessageSerializer(message).data, status=status.HTTP_201_CREATED)
