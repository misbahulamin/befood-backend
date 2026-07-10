from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from orders.api.permissions import IsOrderOwnerOrAdmin, IsVerifiedCustomer
from orders.filters import OrderFilter
from orders.models import Order
from orders.services.order_service import get_current_package
from orders.services.order_status import OrderStatusError, change_order_status

from .serializers import (
    OrderCancelSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
)

CANCELLABLE_STATUSES = {Order.OrderStatus.PENDING, Order.OrderStatus.CONFIRMED}


@extend_schema_view(
    create=extend_schema(
        tags=['Order Management'],
        summary='Create meal order',
        request=OrderCreateSerializer,
        responses={
            201: OrderDetailSerializer,
            400: OpenApiResponse(description='Validation error or month lock error'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
        },
        examples=[
            OpenApiExample(
                'Create order',
                value={'meal_id': 1, 'customer_note': 'Please deliver after 1 PM'},
                request_only=True,
            )
        ],
    ),
    retrieve=extend_schema(
        tags=['Order Management'],
        summary='Retrieve order detail',
        responses={
            200: OrderDetailSerializer,
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Not allowed to view this order'),
            404: OpenApiResponse(description='Order not found'),
        },
    ),
)
class MealOrderViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Order.objects.select_related('customer', 'customer__user', 'meal')
    filter_backends = [DjangoFilterBackend]
    filterset_class = OrderFilter

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        if self.action == 'retrieve':
            return OrderDetailSerializer
        if self.action == 'cancel':
            return OrderCancelSerializer
        return OrderListSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsVerifiedCustomer()]
        if self.action in {'retrieve', 'my_orders', 'cancel', 'current_package'}:
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return queryset
        if hasattr(user, 'customer_profile'):
            return queryset.filter(customer=user.customer_profile)
        return queryset.none()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        output = OrderDetailSerializer(order, context={'request': request})
        return Response(output.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=['Order Management'],
        summary='List my orders',
        parameters=[
            OpenApiParameter(name='order_status', type=str, description='Filter by order status'),
            OpenApiParameter(name='order_month', type=str, description='Filter by YYYY-MM'),
            OpenApiParameter(name='meal_type', type=str, description='Filter by meal type snapshot'),
        ],
        responses={200: OrderListSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='my-orders')
    def my_orders(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = OrderListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(
        tags=['Order Management'],
        summary='Get current month package',
        responses={
            200: OpenApiResponse(description='Current package or null'),
            401: OpenApiResponse(description='Authentication required'),
        },
    )
    @action(detail=False, methods=['get'], url_path='current-package')
    def current_package(self, request):
        profile = getattr(request.user, 'customer_profile', None)
        if profile is None:
            return Response(
                {
                    'current_package': None,
                    'message': 'No active meal package found for this month.',
                }
            )

        order = get_current_package(profile)
        if order is None:
            return Response(
                {
                    'current_package': None,
                    'message': 'No active meal package found for this month.',
                }
            )

        return Response(
            {
                'current_package': OrderDetailSerializer(order, context={'request': request}).data,
                'message': None,
            }
        )

    @extend_schema(
        tags=['Order Management'],
        summary='Cancel order',
        request=OrderCancelSerializer,
        responses={
            200: OrderDetailSerializer,
            400: OpenApiResponse(description='Order cannot be cancelled'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Not allowed to cancel this order'),
            404: OpenApiResponse(description='Order not found'),
        },
    )
    @action(detail=True, methods=['post'], url_path='cancel', permission_classes=[IsAuthenticated, IsOrderOwnerOrAdmin])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.customer.user_id != request.user.id and not request.user.is_superuser:
            return Response({'detail': 'You do not have permission to cancel this order.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if order.order_status not in CANCELLABLE_STATUSES:
            return Response(
                {'order_status': ['Only pending or confirmed orders can be cancelled.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.localdate()
        if today > order.order_start_date:
            return Response(
                {'order_start_date': ['Order can only be cancelled on or before the start date.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            change_order_status(
                order,
                Order.OrderStatus.CANCELLED,
                changed_by=request.user,
                note=serializer.validated_data.get('note', ''),
            )
        except OrderStatusError as exc:
            return Response({'order_status': [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)

        order.refresh_from_db()
        return Response(OrderDetailSerializer(order, context={'request': request}).data)
