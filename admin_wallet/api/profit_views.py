"""Admin Profit web API views."""

from datetime import date

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from admin_wallet.api.profit_serializers import (
    AdminProfitDashboardSerializer,
    MealProfitTransactionSerializer,
)
from admin_wallet.services.profit_analytics import dashboard_payload, filter_history
from user_management.api.permissions import IsVerifiedAdmin

ADMIN_PROFIT_TAG = 'Admin Profit'


class AdminProfitPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _parse_optional_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


class AdminProfitDashboardView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ADMIN_PROFIT_TAG],
        operation_id='adminProfitDashboard',
        summary='Admin Profit dashboard aggregates',
        description=(
            'Ledger-only meal profit analytics. Totals are summed from '
            '`MealProfitTransaction` rows (no live delivery scan). '
            'Default chart/range window is the current calendar month by '
            '`service_date`. Optional `start_date` / `end_date` override the '
            'range breakdowns and daily chart. Optional `package`, `customer`, '
            'and `meal_period` scope all aggregates.'
        ),
        parameters=[
            OpenApiParameter('start_date', str, description='YYYY-MM-DD (service_date)'),
            OpenApiParameter('end_date', str, description='YYYY-MM-DD (service_date)'),
            OpenApiParameter('package', str, description='Meal package public_id UUID'),
            OpenApiParameter('customer', str, description='Customer public_id UUID'),
            OpenApiParameter('meal_period', str, enum=['lunch', 'dinner']),
        ],
        responses={200: AdminProfitDashboardSerializer},
    )
    def get(self, request):
        try:
            start_date = _parse_optional_date(request.query_params.get('start_date'))
            end_date = _parse_optional_date(request.query_params.get('end_date'))
        except ValueError:
            return Response(
                {
                    'success': False,
                    'message': 'Invalid date; use YYYY-MM-DD.',
                    'errors': {},
                    'error_code': 'INVALID_DATE',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        meal_period = request.query_params.get('meal_period') or None
        if meal_period and meal_period not in ('lunch', 'dinner'):
            return Response(
                {
                    'success': False,
                    'message': 'meal_period must be lunch or dinner.',
                    'errors': {'meal_period': ['Invalid value.']},
                    'error_code': 'INVALID_FILTER',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        payload = dashboard_payload(
            start_date=start_date,
            end_date=end_date,
            package_public_id=request.query_params.get('package') or None,
            customer_public_id=request.query_params.get('customer') or None,
            meal_period=meal_period,
        )
        return Response(AdminProfitDashboardSerializer(payload).data)


class AdminProfitHistoryView(APIView):
    permission_classes = [IsVerifiedAdmin]
    pagination_class = AdminProfitPagination

    @extend_schema(
        tags=[ADMIN_PROFIT_TAG],
        operation_id='adminProfitHistory',
        summary='Admin Profit ledger history',
        description=(
            'Paginated immutable meal profit ledger rows. Filters use '
            '`service_date` for date range. Unsupported query params return 400.'
        ),
        parameters=[
            OpenApiParameter('start_date', str, description='YYYY-MM-DD'),
            OpenApiParameter('end_date', str, description='YYYY-MM-DD'),
            OpenApiParameter('package', str, description='Meal package public_id'),
            OpenApiParameter('customer', str, description='Customer public_id'),
            OpenApiParameter('meal_period', str, enum=['lunch', 'dinner']),
            OpenApiParameter('page', int),
            OpenApiParameter('page_size', int),
        ],
        responses={200: MealProfitTransactionSerializer(many=True)},
    )
    def get(self, request):
        try:
            params = {key: request.query_params.get(key) for key in request.query_params.keys()}
            qs = filter_history(params)
        except ValueError as exc:
            return Response(
                {
                    'success': False,
                    'message': str(exc),
                    'errors': {},
                    'error_code': 'UNSUPPORTED_FILTER',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = MealProfitTransactionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
