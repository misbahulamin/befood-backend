from datetime import date

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.api.admin_test_meal_serializers import (
    AdminTestMealAnalyticsSerializer,
    AdminTestMealOrderSerializer,
    AdminTestMealRecordPaymentSerializer,
)
from orders.models import TestMealOrder
from orders.services.test_meal import (
    TestMealError,
    TestMealValidationError,
    admin_test_meal_queryset,
    build_test_meal_analytics,
    conversion_flags_for_order,
    correct_test_meal_payment,
    record_test_meal_payment,
    serialize_admin_test_meal_order,
)
from user_management.api.permissions import IsVerifiedAdmin

ADMIN_TEST_MEAL_TAG = 'Admin Test Meals'


class AdminTestMealPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _parse_date(value: str | None) -> date | None:
    if not value or not str(value).strip():
        return None
    return date.fromisoformat(str(value).strip())


def _admin_test_meal_error_response(exc: TestMealError) -> Response:
    payload = {
        'detail': str(exc),
        'error_code': getattr(exc, 'code', 'TEST_MEAL_ERROR'),
    }
    if isinstance(exc, TestMealValidationError):
        return Response(payload, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    return Response(payload, status=status.HTTP_400_BAD_REQUEST)


def _apply_converted_filter(qs, raw_value: str | None):
    """Filter by ``has_subscribed_after_test`` using per-order conversion flags."""
    value = (raw_value or '').strip().lower()
    if value not in ('true', 'false', '1', '0', 'yes', 'no'):
        return qs
    want = value in ('true', '1', 'yes')
    matched_ids = [
        order.pk
        for order in qs
        if conversion_flags_for_order(order)['has_subscribed_after_test'] == want
    ]
    return qs.filter(pk__in=matched_ids)


def _filter_admin_test_meals(request):
    qs = admin_test_meal_queryset()

    service_date = request.query_params.get('service_date')
    date_from = request.query_params.get('date_from') or request.query_params.get('from')
    date_to = request.query_params.get('date_to') or request.query_params.get('to')
    meal_period = (request.query_params.get('meal_period') or '').strip()
    order_status = (request.query_params.get('order_status') or '').strip()
    payment_status = (request.query_params.get('payment_status') or '').strip()
    search = (request.query_params.get('search') or request.query_params.get('q') or '').strip()
    package_public_id = (request.query_params.get('package_public_id') or '').strip()
    zone_public_id = (request.query_params.get('zone_public_id') or '').strip()
    converted = request.query_params.get('converted')

    if service_date:
        qs = qs.filter(service_date=_parse_date(service_date))
    else:
        if date_from:
            qs = qs.filter(service_date__gte=_parse_date(date_from))
        if date_to:
            qs = qs.filter(service_date__lte=_parse_date(date_to))

    if meal_period in TestMealOrder.MealPeriod.values:
        qs = qs.filter(meal_period=meal_period)

    if order_status in TestMealOrder.OrderStatus.values:
        qs = qs.filter(order_status=order_status)

    if payment_status in TestMealOrder.PaymentStatus.values:
        qs = qs.filter(payment_status=payment_status)

    if package_public_id:
        qs = qs.filter(package__public_id=package_public_id)

    if zone_public_id:
        qs = qs.filter(
            deliveries__logistics_zone__public_id=zone_public_id
        ).distinct()

    if search:
        qs = qs.filter(
            Q(customer__user__first_name__icontains=search)
            | Q(customer__user__last_name__icontains=search)
            | Q(customer__user__email__icontains=search)
            | Q(customer__phone__icontains=search)
            | Q(public_id__icontains=search)
        )

    if converted is not None:
        qs = _apply_converted_filter(qs, converted)

    return qs


class AdminTestMealListView(APIView):
    permission_classes = [IsVerifiedAdmin]
    pagination_class = AdminTestMealPagination

    @extend_schema(
        tags=[ADMIN_TEST_MEAL_TAG],
        summary='List Test Meal orders (admin)',
        description='Verified-admin cross-customer Test Meal directory with filters.',
        parameters=[
            OpenApiParameter(name='service_date', type=str, description='YYYY-MM-DD'),
            OpenApiParameter(name='date_from', type=str, description='YYYY-MM-DD'),
            OpenApiParameter(name='date_to', type=str, description='YYYY-MM-DD'),
            OpenApiParameter(name='from', type=str, description='Alias of date_from'),
            OpenApiParameter(name='to', type=str, description='Alias of date_to'),
            OpenApiParameter(name='meal_period', type=str, enum=['lunch', 'dinner']),
            OpenApiParameter(
                name='order_status',
                type=str,
                enum=TestMealOrder.OrderStatus.values,
            ),
            OpenApiParameter(
                name='payment_status',
                type=str,
                enum=TestMealOrder.PaymentStatus.values,
            ),
            OpenApiParameter(name='search', type=str, description='Customer name/phone/email/id'),
            OpenApiParameter(name='q', type=str, description='Alias of search'),
            OpenApiParameter(name='package_public_id', type=str),
            OpenApiParameter(name='zone_public_id', type=str),
            OpenApiParameter(
                name='converted',
                type=str,
                enum=['true', 'false'],
                description='Filter by has_subscribed_after_test.',
            ),
            OpenApiParameter(name='page', type=int),
            OpenApiParameter(name='page_size', type=int),
        ],
        responses={
            200: AdminTestMealOrderSerializer(many=True),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified admin required'),
        },
    )
    def get(self, request):
        try:
            qs = _filter_admin_test_meals(request)
        except ValueError:
            return Response(
                {'detail': 'Invalid date filter.', 'error_code': 'INVALID_DATE'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        results = [serialize_admin_test_meal_order(row) for row in page]
        return paginator.get_paginated_response(results)


class AdminTestMealDetailView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ADMIN_TEST_MEAL_TAG],
        summary='Test Meal order detail (admin)',
        responses={
            200: AdminTestMealOrderSerializer,
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified admin required'),
            404: OpenApiResponse(description='Not found'),
        },
    )
    def get(self, request, public_id):
        order = admin_test_meal_queryset().filter(public_id=public_id).first()
        if order is None:
            return Response(
                {'detail': 'Test Meal order not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(serialize_admin_test_meal_order(order))


class AdminTestMealRecordPaymentView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ADMIN_TEST_MEAL_TAG],
        summary='Record or correct a Test Meal payment (admin)',
        description=(
            'Records a manual payment (defaulting amount to the order total). When '
            'payment_status is supplied, applies a payment correction/refund instead.'
        ),
        request=AdminTestMealRecordPaymentSerializer,
        responses={
            200: AdminTestMealOrderSerializer,
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified admin required'),
            404: OpenApiResponse(description='Not found'),
            422: OpenApiResponse(description='Invalid payment state / status'),
        },
    )
    def post(self, request, public_id):
        order = admin_test_meal_queryset().filter(public_id=public_id).first()
        if order is None:
            return Response(
                {'detail': 'Test Meal order not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AdminTestMealRecordPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            if 'payment_status' in data:
                correct_test_meal_payment(
                    order,
                    actor=request.user,
                    payment_status=data['payment_status'],
                    amount=data.get('amount'),
                    collected_at=data.get('collected_at'),
                    notes=data.get('notes', ''),
                )
            else:
                record_test_meal_payment(
                    order,
                    actor=request.user,
                    amount=data.get('amount'),
                    collected_at=data.get('collected_at'),
                    notes=data.get('notes', ''),
                )
        except TestMealError as exc:
            return _admin_test_meal_error_response(exc)

        refreshed = admin_test_meal_queryset().filter(pk=order.pk).first()
        return Response(serialize_admin_test_meal_order(refreshed))


class AdminTestMealAnalyticsView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ADMIN_TEST_MEAL_TAG],
        summary='Test Meal analytics (admin)',
        parameters=[
            OpenApiParameter(name='date_from', type=str, description='YYYY-MM-DD'),
            OpenApiParameter(name='date_to', type=str, description='YYYY-MM-DD'),
            OpenApiParameter(name='from', type=str, description='Alias of date_from'),
            OpenApiParameter(name='to', type=str, description='Alias of date_to'),
        ],
        responses={
            200: AdminTestMealAnalyticsSerializer,
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified admin required'),
        },
    )
    def get(self, request):
        date_from = request.query_params.get('date_from') or request.query_params.get('from')
        date_to = request.query_params.get('date_to') or request.query_params.get('to')
        try:
            payload = build_test_meal_analytics(
                date_from=_parse_date(date_from),
                date_to=_parse_date(date_to),
            )
        except ValueError:
            return Response(
                {'detail': 'Invalid date filter.', 'error_code': 'INVALID_DATE'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(payload)
