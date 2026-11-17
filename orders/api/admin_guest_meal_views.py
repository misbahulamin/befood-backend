from datetime import date

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.api.admin_guest_meal_serializers import (
    AdminGuestMealListResponseSerializer,
    AdminGuestMealOrderSerializer,
)
from orders.models import GuestMealOrder
from orders.services.guest_meal import (
    admin_guest_meal_queryset,
    serialize_admin_guest_meal_order,
    summarize_admin_guest_meals,
)
from user_management.api.permissions import IsVerifiedAdmin

ADMIN_GUEST_MEAL_TAG = 'Admin Guest Meals'


class AdminGuestMealPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _parse_date(value: str | None) -> date | None:
    if not value or not str(value).strip():
        return None
    return date.fromisoformat(str(value).strip())


def _filter_admin_guest_meals(request):
    qs = admin_guest_meal_queryset()

    service_date = request.query_params.get('service_date')
    date_from = request.query_params.get('date_from') or request.query_params.get('from')
    date_to = request.query_params.get('date_to') or request.query_params.get('to')
    meal_period = (request.query_params.get('meal_period') or '').strip()
    status_value = (request.query_params.get('status') or '').strip()
    search = (request.query_params.get('search') or request.query_params.get('q') or '').strip()
    package_public_id = (request.query_params.get('package_public_id') or '').strip()
    zone_public_id = (request.query_params.get('zone_public_id') or '').strip()

    if service_date:
        qs = qs.filter(service_date=_parse_date(service_date))
    else:
        if date_from:
            qs = qs.filter(service_date__gte=_parse_date(date_from))
        if date_to:
            qs = qs.filter(service_date__lte=_parse_date(date_to))

    if meal_period in GuestMealOrder.MealPeriod.values:
        qs = qs.filter(meal_period=meal_period)

    if status_value in GuestMealOrder.Status.values:
        qs = qs.filter(status=status_value)

    if package_public_id:
        qs = qs.filter(subscription__meal__public_id=package_public_id)

    if zone_public_id:
        qs = qs.filter(delivery__logistics_zone__public_id=zone_public_id)

    if search:
        qs = qs.filter(
            Q(customer__user__first_name__icontains=search)
            | Q(customer__user__last_name__icontains=search)
            | Q(customer__user__email__icontains=search)
            | Q(customer__phone__icontains=search)
            | Q(public_id__icontains=search)
        )

    return qs


class AdminGuestMealListView(APIView):
    permission_classes = [IsVerifiedAdmin]
    pagination_class = AdminGuestMealPagination

    @extend_schema(
        tags=[ADMIN_GUEST_MEAL_TAG],
        summary='List guest meal orders (admin)',
        description=(
            'Verified-admin cross-customer Guest Meal directory. '
            'Summary metrics keep order_count distinct from box_quantity.'
        ),
        parameters=[
            OpenApiParameter(name='service_date', type=str, description='YYYY-MM-DD'),
            OpenApiParameter(name='date_from', type=str, description='YYYY-MM-DD'),
            OpenApiParameter(name='date_to', type=str, description='YYYY-MM-DD'),
            OpenApiParameter(name='meal_period', type=str, enum=['lunch', 'dinner']),
            OpenApiParameter(
                name='status',
                type=str,
                enum=['scheduled', 'delivered', 'cancelled'],
            ),
            OpenApiParameter(name='search', type=str, description='Customer name/phone/email/id'),
            OpenApiParameter(name='package_public_id', type=str),
            OpenApiParameter(name='zone_public_id', type=str),
            OpenApiParameter(name='page', type=int),
            OpenApiParameter(name='page_size', type=int),
        ],
        responses={
            200: AdminGuestMealListResponseSerializer,
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified admin required'),
        },
    )
    def get(self, request):
        try:
            qs = _filter_admin_guest_meals(request)
        except ValueError:
            return Response(
                {'detail': 'Invalid date filter.', 'error_code': 'INVALID_DATE'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        summary = summarize_admin_guest_meals(qs)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        results = [serialize_admin_guest_meal_order(row) for row in page]
        response = paginator.get_paginated_response(results)
        response.data['summary'] = summary
        return response


class AdminGuestMealDetailView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ADMIN_GUEST_MEAL_TAG],
        summary='Guest meal order detail (admin)',
        responses={
            200: AdminGuestMealOrderSerializer,
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified admin required'),
            404: OpenApiResponse(description='Not found'),
        },
    )
    def get(self, request, public_id):
        order = (
            admin_guest_meal_queryset()
            .filter(public_id=public_id)
            .first()
        )
        if order is None:
            return Response(
                {'detail': 'Guest meal order not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(serialize_admin_guest_meal_order(order))
