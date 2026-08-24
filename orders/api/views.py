from datetime import datetime, timedelta

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from meals.models import MealCategory
from orders.api.permissions import IsOrderOwnerOrAdmin, IsVerifiedCustomer
from orders.filters import OrderFilter
from orders.models import MealDemandSnapshot, Order, OrderDelivery
from orders.services.meal_demand import (
    build_kitchen_requirement,
    demand_to_dict,
    get_demand,
    resolve_default_kitchen_slot,
)
from orders.services.meal_off import (
    MealOffError,
    customer_meal_off,
    customer_meal_on,
    get_meal_off_settings,
    meal_off_business_now,
    update_meal_off_settings,
)
from orders.services.order_delivery import DeliveryError, mark_delivery
from orders.services.subscription_parent import live_delivery_q
from orders.services.order_service import SUBSCRIBE_REQUIRED_ERROR, get_current_package
from orders.services.subscription_service import (
    SUBSCRIBE_REQUIRED_CODE,
    ensure_subscription_deliveries,
)
from orders.api.subscription_serializers import CustomerSubscriptionDetailSerializer
from orders.services.order_status import OrderStatusError, change_order_status
from orders.services.order_wallet_settings import (
    get_order_wallet_settings,
    update_order_wallet_settings,
)
from orders.services.orderable_months import build_orderable_months_for_meal
from user_management.api.permissions import IsVerifiedAdmin
from user_management.services.admin_access import is_verified_admin

from .serializers import (
    AdminOrderDetailSerializer,
    AdminOrderListSerializer,
    KitchenTodayRequirementSerializer,
    MarkDeliverySerializer,
    MealDemandHistoryItemSerializer,
    MealOffRequestSerializer,
    MealOffSettingsSerializer,
    MealOnRequestSerializer,
    MealStatisticsResponseSerializer,
    OrderCancelSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderDeliverySerializer,
    OrderListSerializer,
    OrderWalletSettingsSerializer,
    OrderableMonthsQuerySerializer,
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
        'subscription',
        'subscription__customer__user',
    ).filter(live_delivery_q(service_date))

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
            'subscription',
            'subscription__customer__user',
        ).filter(pk__in=matching_ids)
    else:
        qs = qs.filter(service_date=service_date)

    meal_period = request.query_params.get('meal_period')
    if meal_period:
        qs = qs.filter(meal_period=meal_period)
    delivery_status = request.query_params.get('status')
    if delivery_status:
        qs = qs.filter(status=delivery_status)

    return qs.order_by('service_date', 'meal_period', 'id'), None


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
        payload = {'detail': message}
        if getattr(exc, 'code', None):
            payload['error_code'] = exc.code
        if getattr(exc, 'code', None) in {
            'WALLET_INSUFFICIENT_FOR_MEAL',
            'WALLET_FROZEN',
            'MEAL_PAYMENT_IDEMPOTENCY_CONFLICT',
            'MEAL_PAYMENT_FAILED',
            'MEAL_SLOT_PRICE_MISSING',
        }:
            return Response(payload, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        code = status.HTTP_409_CONFLICT if 'already' in message.lower() else status.HTTP_400_BAD_REQUEST
        return Response(payload, status=code)

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
            422: OpenApiResponse(
                description='Wallet insufficient/frozen for meal delivery charge'
            ),
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
        summary='Create meal order (retired)',
        description=(
            'Monthly meal-package create is retired. Clients must POST /api/v1/subscriptions/ '
            'with plan_public_id. This endpoint always returns 409 SUBSCRIBE_REQUIRED and '
            'does not persist an Order.'
        ),
        request=OrderCreateSerializer,
        responses={
            409: OpenApiResponse(description='Subscribe required; monthly order create retired'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
        },
        examples=[
            OpenApiExample(
                'Subscribe required',
                value={
                    'detail': (
                        'Monthly meal orders are retired. Subscribe to a meal plan instead.'
                    ),
                    'error_code': 'SUBSCRIBE_REQUIRED',
                },
                response_only=True,
                status_codes=['409'],
            ),
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
        if self.action == 'meal_on':
            return MealOnRequestSerializer
        if self.action == 'today_board':
            return TodayBoardDeliverySerializer
        if self.action == 'list' and admin_viewer:
            return AdminOrderListSerializer
        return OrderListSerializer

    def get_permissions(self):
        if self.action in {'create', 'orderable_months'}:
            return [IsVerifiedCustomer()]
        if self.action in {'today_board', 'mark_delivery'}:
            return [IsVerifiedAdmin()]
        if self.action in {'meal_off', 'meal_on'}:
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
        return Response(
            {
                'detail': SUBSCRIBE_REQUIRED_ERROR,
                'error_code': SUBSCRIBE_REQUIRED_CODE,
            },
            status=status.HTTP_409_CONFLICT,
        )

    @extend_schema(
        tags=['Order Management'],
        summary='List orderable meal months for a package',
        description=(
            'Retired. The 13-month Order Now picker is no longer the purchase path. '
            'List plans at GET /api/v1/subscription-plans/ and subscribe instead.'
        ),
        parameters=[
            OpenApiParameter(
                name='meal_public_id',
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description='Meal package public UUID',
            ),
        ],
        responses={
            409: OpenApiResponse(description='Subscribe required; orderable-months retired'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
        },
        examples=[
            OpenApiExample(
                'Orderable months',
                value={
                    'meal_public_id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
                    'meal_name': 'Regular Monthly',
                    'months': [
                        {
                            'year': 2026,
                            'month': 7,
                            'order_month': '2026-07',
                            'label': 'July 2026',
                            'is_current': True,
                            'is_published': True,
                            'has_order': False,
                        },
                        {
                            'year': 2026,
                            'month': 8,
                            'order_month': '2026-08',
                            'label': 'August 2026',
                            'is_current': False,
                            'is_published': False,
                            'has_order': False,
                        },
                    ],
                },
                response_only=True,
            ),
        ],
    )
    @action(detail=False, methods=['get'], url_path='orderable-months')
    def orderable_months(self, request):
        return Response(
            {
                'detail': SUBSCRIBE_REQUIRED_ERROR,
                'error_code': SUBSCRIBE_REQUIRED_CODE,
            },
            status=status.HTTP_409_CONFLICT,
        )

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
        summary='Get current meal subscription',
        description=(
            'Returns the caller’s active subscription (same payload as '
            'GET /api/v1/subscriptions/current/). Null when none.'
        ),
        responses={
            200: OpenApiResponse(description='Current package or null'),
            401: OpenApiResponse(description='Authentication required'),
        },
    )
    @action(detail=False, methods=['get'], url_path='current-package')
    def current_package(self, request):
        profile = getattr(request.user, 'customer_profile', None)
        empty = {
            'current_package': None,
            'current_subscription': None,
            'message': 'No active meal subscription.',
        }
        if profile is None:
            return Response(empty)

        subscription = get_current_package(profile)
        if subscription is None:
            return Response(empty)

        ensure_subscription_deliveries(subscription)
        payload = CustomerSubscriptionDetailSerializer(
            subscription, context={'request': request}
        ).data
        return Response(
            {
                'current_package': payload,
                'current_subscription': payload,
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

    @extend_schema(
        tags=['Order Management'],
        summary='Meal-on a customer-skipped delivery slot',
        description=(
            'Customer undoes a prior meal-off and restores the slot to scheduled, '
            'only while still before the same lunch/dinner cook-prep deadline. '
            'Does not charge the wallet.'
        ),
        request=MealOnRequestSerializer,
        responses={
            200: OrderDeliverySerializer,
            400: OpenApiResponse(description='Deadline passed or invalid state'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
            404: OpenApiResponse(description='Order or delivery not found'),
            409: OpenApiResponse(description='Not a customer-skipped slot'),
        },
        examples=[
            OpenApiExample(
                'Meal-on success',
                value={'note': 'Changed plans'},
                request_only=True,
            ),
            OpenApiExample(
                'Deadline passed',
                value={'detail': 'Meal-on deadline has passed for this slot.'},
                response_only=True,
                status_codes=['400'],
            ),
        ],
    )
    @action(
        detail=True,
        methods=['post'],
        url_path=r'deliveries/(?P<delivery_id>[^/.]+)/meal-on',
        permission_classes=[IsVerifiedCustomer],
    )
    def meal_on(self, request, public_id=None, delivery_id=None):
        order = self.get_object()
        profile = getattr(request.user, 'customer_profile', None)
        if profile is None or order.customer_id != profile.pk:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            delivery = order.deliveries.get(public_id=delivery_id)
        except (OrderDelivery.DoesNotExist, ValueError):
            return Response({'detail': 'Delivery not found for this order.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = MealOnRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = customer_meal_on(
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
                if (
                    'cannot be meal-oned' in message.lower()
                    or 'only customer meal-offs' in message.lower()
                )
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


class OrderWalletSettingsView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=['Admin Order Management'],
        summary='Get order wallet minimum balance settings',
        description=(
            'Returns the minimum wallet balance (BDT) a verified customer must have '
            'before placing a meal package order. Eligibility check only — order create '
            'does not debit the wallet.'
        ),
        responses={
            200: OrderWalletSettingsSerializer,
            403: OpenApiResponse(description='Admin required'),
        },
        examples=[
            OpenApiExample(
                'Default settings',
                value={'min_wallet_balance_to_order': '500.00', 'updated_at': '2026-07-29T10:00:00Z'},
                response_only=True,
            ),
        ],
    )
    def get(self, request):
        settings_obj = get_order_wallet_settings()
        return Response(OrderWalletSettingsSerializer(settings_obj).data)

    @extend_schema(
        tags=['Admin Order Management'],
        summary='Update order wallet minimum balance settings',
        description=(
            'Partially update the minimum wallet balance required to place an order. '
            'Amount must be >= 0 with at most 2 decimal places.'
        ),
        request=OrderWalletSettingsSerializer,
        responses={
            200: OrderWalletSettingsSerializer,
            400: OpenApiResponse(description='Validation error (negative or too many decimals)'),
            403: OpenApiResponse(description='Admin required'),
        },
        examples=[
            OpenApiExample(
                'Raise minimum to 600',
                value={'min_wallet_balance_to_order': '600.00'},
                request_only=True,
            ),
            OpenApiExample(
                'Negative rejected',
                value={'min_wallet_balance_to_order': ['Amount must be greater than or equal to zero.']},
                response_only=True,
                status_codes=['400'],
            ),
        ],
    )
    def patch(self, request):
        settings_obj = get_order_wallet_settings()
        serializer = OrderWalletSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = update_order_wallet_settings(
            min_wallet_balance_to_order=serializer.validated_data.get('min_wallet_balance_to_order'),
        )
        return Response(OrderWalletSettingsSerializer(updated).data)


def _parse_demand_service_date(raw_value, *, settings_obj):
    today = meal_off_business_now(settings_obj).date()
    if not raw_value:
        return today, None
    try:
        return datetime.strptime(raw_value, '%Y-%m-%d').date(), None
    except (TypeError, ValueError):
        return None, Response(
            {'detail': 'service_date must be YYYY-MM-DD.'},
            status=status.HTTP_400_BAD_REQUEST,
        )


class MealStatisticsView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=['Admin Order Management'],
        summary='Meal demand statistics for a service date',
        description=(
            'Expected / meal-off / final cooking counts with package breakdown. '
            'confirmation_status is estimated before the meal-off deadline and confirmed after.'
        ),
        parameters=[
            OpenApiParameter(
                name='service_date',
                type=str,
                description='YYYY-MM-DD (default: today in meal-off timezone)',
            ),
            OpenApiParameter(
                name='meal_period',
                type=str,
                description='lunch|dinner (omit for both)',
            ),
            OpenApiParameter(
                name='package_public_id',
                type=str,
                description='Optional meal package UUID filter',
            ),
        ],
        responses={
            200: MealStatisticsResponseSerializer,
            400: OpenApiResponse(description='Invalid filter'),
            403: OpenApiResponse(description='Admin required'),
        },
        examples=[
            OpenApiExample(
                'Dinner statistics',
                value={
                    'service_date': '2026-08-05',
                    'periods': [
                        {
                            'service_date': '2026-08-05',
                            'meal_period': 'dinner',
                            'confirmation_status': 'estimated',
                            'total_customers': 500,
                            'expected_meal_count': 500,
                            'meal_off_count': 50,
                            'final_cooking_count': 450,
                            'remaining_meal_count': 450,
                            'packages': [],
                        }
                    ],
                },
                response_only=True,
            ),
        ],
    )
    def get(self, request):
        settings_obj = get_meal_off_settings()
        service_date, error = _parse_demand_service_date(
            request.query_params.get('service_date'),
            settings_obj=settings_obj,
        )
        if error is not None:
            return error

        meal_period = request.query_params.get('meal_period')
        if meal_period and meal_period not in {
            OrderDelivery.MealPeriod.LUNCH,
            OrderDelivery.MealPeriod.DINNER,
        }:
            return Response(
                {'detail': 'meal_period must be lunch or dinner.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        package_public_id = request.query_params.get('package_public_id')
        if package_public_id:
            if not MealCategory.objects.filter(public_id=package_public_id).exists():
                return Response(
                    {'detail': 'package_public_id not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        periods = (
            [meal_period]
            if meal_period
            else [OrderDelivery.MealPeriod.LUNCH, OrderDelivery.MealPeriod.DINNER]
        )
        period_payloads = []
        for period in periods:
            demand = get_demand(
                service_date,
                period,
                package_public_id=package_public_id,
                settings_obj=settings_obj,
            )
            period_payloads.append(demand_to_dict(demand))

        return Response(
            {
                'service_date': service_date.isoformat(),
                'periods': period_payloads,
            }
        )


class KitchenTodayMealRequirementView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=['Admin Order Management'],
        summary='Kitchen today cooking requirement',
        description=(
            'Lean cooking headcount + ingredient quantities. Defaults to today and lunch '
            'before dinner_off_time, else dinner. Override with service_date / meal_period.'
        ),
        parameters=[
            OpenApiParameter(name='service_date', type=str, description='YYYY-MM-DD override'),
            OpenApiParameter(name='meal_period', type=str, description='lunch|dinner override'),
        ],
        responses={
            200: KitchenTodayRequirementSerializer,
            400: OpenApiResponse(description='Invalid filter'),
            403: OpenApiResponse(description='Admin required'),
        },
        examples=[
            OpenApiExample(
                'Today lunch requirement',
                value={
                    'service_date': '2026-08-05',
                    'meal_period': 'lunch',
                    'confirmation_status': 'confirmed',
                    'expected_meal_count': 500,
                    'meal_off_count': 50,
                    'final_cooking_count': 450,
                    'total_customers': 500,
                    'ingredients_incomplete': False,
                    'ingredients': [
                        {
                            'ingredient_public_id': '11111111-1111-1111-1111-111111111111',
                            'name': 'Rice',
                            'unit': 'kg',
                            'quantity': '135.000000',
                            'kg_per_person': '0.300000',
                            'quantity_available': True,
                        }
                    ],
                },
                response_only=True,
            ),
        ],
    )
    def get(self, request):
        settings_obj = get_meal_off_settings()
        raw_date = request.query_params.get('service_date')
        raw_period = request.query_params.get('meal_period')

        if raw_date or raw_period:
            if raw_date:
                service_date, error = _parse_demand_service_date(
                    raw_date, settings_obj=settings_obj
                )
                if error is not None:
                    return error
            else:
                service_date = meal_off_business_now(settings_obj).date()

            if raw_period:
                if raw_period not in {
                    OrderDelivery.MealPeriod.LUNCH,
                    OrderDelivery.MealPeriod.DINNER,
                }:
                    return Response(
                        {'detail': 'meal_period must be lunch or dinner.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                meal_period = raw_period
            else:
                _, meal_period = resolve_default_kitchen_slot(settings_obj=settings_obj)
        else:
            service_date, meal_period = resolve_default_kitchen_slot(settings_obj=settings_obj)

        payload = build_kitchen_requirement(
            service_date,
            meal_period,
            settings_obj=settings_obj,
        )
        return Response(payload)


class MealDemandHistoryView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=['Admin Order Management'],
        summary='Historical meal demand snapshots',
        description=(
            'Returns frozen MealDemandSnapshot rows (counts + ingredient requirements). '
            'Does not recalculate from live deliveries.'
        ),
        parameters=[
            OpenApiParameter(name='service_date', type=str, description='Exact YYYY-MM-DD'),
            OpenApiParameter(name='date_from', type=str, description='Range start YYYY-MM-DD'),
            OpenApiParameter(name='date_to', type=str, description='Range end YYYY-MM-DD'),
            OpenApiParameter(name='meal_period', type=str, description='lunch|dinner'),
            OpenApiParameter(name='package_public_id', type=str, description='Package UUID'),
        ],
        responses={
            200: MealDemandHistoryItemSerializer(many=True),
            400: OpenApiResponse(description='Invalid filter'),
            403: OpenApiResponse(description='Admin required'),
        },
    )
    def get(self, request):
        qs = MealDemandSnapshot.objects.select_related('package').all()

        service_date = request.query_params.get('service_date')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        meal_period = request.query_params.get('meal_period')
        package_public_id = request.query_params.get('package_public_id')

        def _parse_date(raw, field_name):
            try:
                return datetime.strptime(raw, '%Y-%m-%d').date(), None
            except (TypeError, ValueError):
                return None, Response(
                    {'detail': f'{field_name} must be YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if service_date:
            parsed, error = _parse_date(service_date, 'service_date')
            if error is not None:
                return error
            qs = qs.filter(service_date=parsed)
        if date_from:
            parsed, error = _parse_date(date_from, 'date_from')
            if error is not None:
                return error
            qs = qs.filter(service_date__gte=parsed)
        if date_to:
            parsed, error = _parse_date(date_to, 'date_to')
            if error is not None:
                return error
            qs = qs.filter(service_date__lte=parsed)
        if meal_period:
            if meal_period not in {
                OrderDelivery.MealPeriod.LUNCH,
                OrderDelivery.MealPeriod.DINNER,
            }:
                return Response(
                    {'detail': 'meal_period must be lunch or dinner.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(meal_period=meal_period)
        if package_public_id:
            qs = qs.filter(package__public_id=package_public_id)

        serializer = MealDemandHistoryItemSerializer(qs[:500], many=True)
        return Response(serializer.data)


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
