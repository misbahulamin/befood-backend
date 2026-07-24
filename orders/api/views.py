from datetime import datetime, timedelta

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.api.permissions import IsOrderOwnerOrAdmin, IsVerifiedCustomer
from orders.filters import OrderFilter
from orders.models import Order, OrderDelivery
from orders.services.meal_off import (
    MealOffError,
    customer_meal_off,
    get_meal_off_settings,
    update_meal_off_settings,
)
from orders.services.order_delivery import DeliveryError, mark_delivery
from orders.services.order_service import get_current_package
from orders.services.order_status import OrderStatusError, change_order_status
from user_management.api.permissions import IsVerifiedAdmin
from user_management.services.admin_access import is_verified_admin

from .serializers import (
    AdminOrderDetailSerializer,
    AdminOrderListSerializer,
    MarkDeliverySerializer,
    MealOffRequestSerializer,
    MealOffSettingsSerializer,
    OrderCancelSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderDeliverySerializer,
    OrderListSerializer,
    TodayBoardDeliverySerializer,
)

CANCELLABLE_STATUSES = {Order.OrderStatus.PENDING, Order.OrderStatus.CONFIRMED}


def _parse_service_date(raw_value):
    today = timezone.localdate()
    if not raw_value:
        return today, None
    try:
        return datetime.strptime(raw_value, '%Y-%m-%d').date(), None
    except ValueError:
        return None, Response(
            {'service_date': ['Invalid date. Use YYYY-MM-DD.']},
            status=status.HTTP_400_BAD_REQUEST,
        )


def _today_board_queryset(request):
    service_date, error = _parse_service_date(request.query_params.get('service_date'))
    if error is not None:
        return None, error

    qs = OrderDelivery.objects.select_related(
        'order',
        'order__customer__user',
    ).filter(
        order__order_status__in={
            Order.OrderStatus.CONFIRMED,
            Order.OrderStatus.ACTIVE,
        }
    )

    week_of_month = request.query_params.get('week_of_month')
    if week_of_month:
        try:
            week_number = int(week_of_month)
        except ValueError:
            return None, Response(
                {'week_of_month': ['Must be an integer ISO week number.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        month_start = service_date.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)
        qs = qs.filter(service_date__gte=month_start, service_date__lte=month_end)
        matching_ids = [
            d.pk
            for d in qs.only('id', 'service_date')
            if d.service_date.isocalendar().week == week_number
        ]
        qs = OrderDelivery.objects.select_related(
            'order',
            'order__customer__user',
        ).filter(pk__in=matching_ids)
    else:
        qs = qs.filter(service_date=service_date)

    meal_period = request.query_params.get('meal_period')
    if meal_period:
        qs = qs.filter(meal_period=meal_period)
    delivery_status = request.query_params.get('status')
    if delivery_status:
        qs = qs.filter(status=delivery_status)

    return qs.order_by('service_date', 'meal_period', 'order_id'), None


def _mark_order_delivery(request, order, delivery_id):
    try:
        delivery = order.deliveries.get(public_id=delivery_id)
    except (OrderDelivery.DoesNotExist, ValueError):
        return Response({'detail': 'Delivery not found for this order.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = MarkDeliverySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        updated = mark_delivery(
            delivery,
            to_status=serializer.validated_data['status'],
            marked_by=request.user,
            note=serializer.validated_data.get('note', ''),
        )
    except DeliveryError as exc:
        message = str(exc)
        code = status.HTTP_409_CONFLICT if 'already' in message.lower() else status.HTTP_400_BAD_REQUEST
        return Response({'detail': message}, status=code)

    return Response(OrderDeliverySerializer(updated).data)


class AdminDeliveryActionsMixin:
    """Shared admin ops on /orders/ and /api/v1/web/orders/."""

    @extend_schema(
        tags=['Admin Order Management'],
        summary='Mark a delivery slot delivered or skipped',
        request=MarkDeliverySerializer,
        responses={
            200: OrderDeliverySerializer,
            400: OpenApiResponse(description='Invalid mark'),
            403: OpenApiResponse(description='Admin required'),
            404: OpenApiResponse(description='Not found'),
            409: OpenApiResponse(description='Conflict / already terminal'),
        },
    )
    @action(
        detail=True,
        methods=['post'],
        url_path=r'deliveries/(?P<delivery_id>[^/.]+)/mark',
        permission_classes=[IsVerifiedAdmin],
    )
    def mark_delivery(self, request, public_id=None, delivery_id=None):
        order = self.get_object()
        return _mark_order_delivery(request, order, delivery_id)

    @extend_schema(
        tags=['Admin Order Management'],
        summary='Today / week kitchen delivery board',
        parameters=[
            OpenApiParameter(name='service_date', type=str, description='YYYY-MM-DD (default: today)'),
            OpenApiParameter(name='week_of_month', type=int, description='ISO week number to filter'),
            OpenApiParameter(name='meal_period', type=str, description='lunch|dinner'),
            OpenApiParameter(name='status', type=str, description='scheduled|delivered|skipped|missed'),
        ],
        responses={200: TodayBoardDeliverySerializer(many=True)},
    )
    @action(
        detail=False,
        methods=['get'],
        url_path='today-board',
        permission_classes=[IsVerifiedAdmin],
    )
    def today_board(self, request):
        qs, error = _today_board_queryset(request)
        if error is not None:
            return error
        serializer = TodayBoardDeliverySerializer(qs, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        tags=['Order Management'],
        summary='List orders',
        description=(
            'Customers receive only their own orders. '
            'Verified admins receive all orders (same filters as the web admin list).'
        ),
        parameters=[
            OpenApiParameter(name='order_status', type=str, description='Filter by order status'),
            OpenApiParameter(name='order_month', type=str, description='Filter by YYYY-MM'),
            OpenApiParameter(name='meal_type', type=str, description='Filter by meal type snapshot'),
            OpenApiParameter(name='activity', type=str, description='active|inactive'),
        ],
        responses={200: OrderListSerializer(many=True)},
    ),
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
                value={'meal_public_id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee', 'customer_note': 'Please deliver after 1 PM'},
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
    AdminDeliveryActionsMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Order.objects.select_related('customer', 'customer__user', 'meal').prefetch_related(
        'deliveries'
    )
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    filter_backends = [DjangoFilterBackend]
    filterset_class = OrderFilter

    def get_serializer_class(self):
        user = self.request.user
        admin_viewer = bool(user and user.is_authenticated and is_verified_admin(user))
        if self.action == 'create':
            return OrderCreateSerializer
        if self.action == 'retrieve':
            return AdminOrderDetailSerializer if admin_viewer else OrderDetailSerializer
        if self.action == 'cancel':
            return OrderCancelSerializer
        if self.action == 'mark_delivery':
            return MarkDeliverySerializer
        if self.action == 'meal_off':
            return MealOffRequestSerializer
        if self.action == 'today_board':
            return TodayBoardDeliverySerializer
        if self.action == 'list' and admin_viewer:
            return AdminOrderListSerializer
        return OrderListSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsVerifiedCustomer()]
        if self.action in {'today_board', 'mark_delivery'}:
            return [IsVerifiedAdmin()]
        if self.action == 'meal_off':
            return [IsVerifiedCustomer()]
        if self.action in {'list', 'retrieve', 'my_orders', 'cancel', 'current_package'}:
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if is_verified_admin(user) or user.is_superuser:
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
    def cancel(self, request, public_id=None):
        order = self.get_object()
        if (
            order.customer.user_id != request.user.id
            and not request.user.is_superuser
            and not is_verified_admin(request.user)
        ):
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

    @extend_schema(
        tags=['Order Management'],
        summary='Meal-off a delivery slot',
        description=(
            'Customer opts out of a scheduled lunch/dinner before the cook-prep deadline. '
            'Lunch default: previous day 23:59. Dinner default: same day 14:00. No refund.'
        ),
        request=MealOffRequestSerializer,
        responses={
            200: OrderDeliverySerializer,
            400: OpenApiResponse(description='Deadline passed or invalid state'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
            404: OpenApiResponse(description='Order or delivery not found'),
            409: OpenApiResponse(description='Already terminal'),
        },
        examples=[
            OpenApiExample(
                'Meal-off success',
                value={'note': 'Out of town'},
                request_only=True,
            ),
            OpenApiExample(
                'Deadline passed',
                value={'detail': 'Meal-off deadline has passed for this slot.'},
                response_only=True,
                status_codes=['400'],
            ),
        ],
    )
    @action(
        detail=True,
        methods=['post'],
        url_path=r'deliveries/(?P<delivery_id>[^/.]+)/meal-off',
        permission_classes=[IsVerifiedCustomer],
    )
    def meal_off(self, request, public_id=None, delivery_id=None):
        order = self.get_object()
        profile = getattr(request.user, 'customer_profile', None)
        if profile is None or order.customer_id != profile.pk:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            delivery = order.deliveries.get(public_id=delivery_id)
        except (OrderDelivery.DoesNotExist, ValueError):
            return Response({'detail': 'Delivery not found for this order.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = MealOffRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = customer_meal_off(
                delivery,
                user=request.user,
                note=serializer.validated_data.get('note', ''),
            )
        except MealOffError as exc:
            message = str(exc)
            if 'not found' in message.lower():
                return Response({'detail': message}, status=status.HTTP_404_NOT_FOUND)
            code = (
                status.HTTP_409_CONFLICT
                if 'already' in message.lower()
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({'detail': message}, status=code)

        return Response(OrderDeliverySerializer(updated).data)


class MealOffSettingsView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=['Admin Order Management'],
        summary='Get meal-off deadline settings',
        responses={200: MealOffSettingsSerializer},
    )
    def get(self, request):
        settings_obj = get_meal_off_settings()
        return Response(MealOffSettingsSerializer(settings_obj).data)

    @extend_schema(
        tags=['Admin Order Management'],
        summary='Update meal-off deadline settings',
        request=MealOffSettingsSerializer,
        responses={
            200: MealOffSettingsSerializer,
            400: OpenApiResponse(description='Validation error'),
            403: OpenApiResponse(description='Admin required'),
        },
    )
    def patch(self, request):
        settings_obj = get_meal_off_settings()
        serializer = MealOffSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = update_meal_off_settings(
            timezone_name=serializer.validated_data.get('timezone'),
            lunch_off_time=serializer.validated_data.get('lunch_off_time'),
            dinner_off_time=serializer.validated_data.get('dinner_off_time'),
        )
        return Response(MealOffSettingsSerializer(updated).data)


@extend_schema_view(
    list=extend_schema(
        tags=['Admin Order Management'],
        summary='List all meal orders',
        parameters=[
            OpenApiParameter(name='order_status', type=str),
            OpenApiParameter(name='order_month', type=str, description='YYYY-MM'),
            OpenApiParameter(name='meal_type', type=str, description='daily|weekly|half_monthly|monthly|...'),
            OpenApiParameter(name='activity', type=str, description='active|inactive'),
            OpenApiParameter(name='created_after', type=str),
            OpenApiParameter(name='created_before', type=str),
            OpenApiParameter(name='start_date', type=str),
            OpenApiParameter(name='end_date', type=str),
        ],
        responses={200: AdminOrderListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Admin Order Management'],
        summary='Retrieve order detail with deliveries',
        responses={200: AdminOrderDetailSerializer},
    ),
)
class AdminOrderViewSet(
    AdminDeliveryActionsMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsVerifiedAdmin]
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    filter_backends = [DjangoFilterBackend]
    filterset_class = OrderFilter
    queryset = Order.objects.select_related(
        'customer',
        'customer__user',
        'meal',
    ).prefetch_related('deliveries')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AdminOrderDetailSerializer
        if self.action == 'mark_delivery':
            return MarkDeliverySerializer
        if self.action == 'today_board':
            return TodayBoardDeliverySerializer
        return AdminOrderListSerializer
