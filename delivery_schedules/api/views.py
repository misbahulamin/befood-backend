from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters, mixins, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from user_management.api.permissions import IsVerifiedAdmin

from delivery_schedules.filters import DeliveryScheduleFilter
from delivery_schedules.models import DeliverySchedule
from delivery_schedules.services import (
    delete_delivery_schedule,
    get_public_delivery_schedules,
)

from .serializers import (
    DeliveryScheduleAdminSerializer,
    PublicDeliveryScheduleSerializer,
)


class AdminDeliverySchedulePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


@extend_schema_view(
    list=extend_schema(
        tags=['Public Delivery Schedules'],
        summary='List active delivery schedules',
        description=(
            'Unauthenticated. Returns active delivery time windows ordered by '
            'sort_order ascending. Times are Asia/Dhaka wall-clock values.'
        ),
        responses={200: PublicDeliveryScheduleSerializer(many=True)},
    ),
)
class PublicDeliveryScheduleViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Public catalog of active delivery time windows."""

    serializer_class = PublicDeliveryScheduleSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = None
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        return get_public_delivery_schedules()


@extend_schema_view(
    list=extend_schema(
        tags=['Admin Delivery Schedules'],
        summary='List delivery schedules',
        description=(
            'Verified admin only. Returns all delivery schedules including inactive. '
            'Filter by is_active or search name.'
        ),
        parameters=[
            OpenApiParameter(
                name='is_active',
                type=bool,
                location=OpenApiParameter.QUERY,
                description='Filter by is_active.',
            ),
            OpenApiParameter(
                name='search',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Case-insensitive search on name.',
            ),
            OpenApiParameter(
                name='page',
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page_size',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Page size (default 50, max 200).',
            ),
            OpenApiParameter(
                name='ordering',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Order by sort_order, name, start_time, created_at, updated_at.',
            ),
        ],
        responses={200: DeliveryScheduleAdminSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Admin Delivery Schedules'],
        summary='Retrieve delivery schedule',
        responses={200: DeliveryScheduleAdminSerializer},
    ),
    create=extend_schema(
        tags=['Admin Delivery Schedules'],
        summary='Create delivery schedule',
        request=DeliveryScheduleAdminSerializer,
        responses={201: DeliveryScheduleAdminSerializer},
    ),
    partial_update=extend_schema(
        tags=['Admin Delivery Schedules'],
        summary='Update delivery schedule',
        request=DeliveryScheduleAdminSerializer,
        responses={200: DeliveryScheduleAdminSerializer},
    ),
    destroy=extend_schema(
        tags=['Admin Delivery Schedules'],
        summary='Delete delivery schedule',
        description='Hard-deletes the schedule.',
        responses={204: None},
    ),
)
class DeliveryScheduleAdminViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Verified-admin CRUD for delivery schedules."""

    serializer_class = DeliveryScheduleAdminSerializer
    permission_classes = [IsVerifiedAdmin]
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = DeliveryScheduleFilter
    ordering_fields = [
        'sort_order',
        'name',
        'start_time',
        'end_time',
        'created_at',
        'updated_at',
    ]
    ordering = ['sort_order', 'name']
    pagination_class = AdminDeliverySchedulePagination
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return DeliverySchedule.objects.all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        delete_delivery_schedule(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
