"""Verified-admin delivery-fee web APIs (global list + reports)."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from user_management.api.permissions import IsVerifiedAdmin
from user_management.models import CustomerProfile
from user_management.services.admin_people_search import build_customer_people_q
from wallet.api.delivery_fee_serializers import (
    DeliveryFeeLifetimeReportSerializer,
    DeliveryFeeMonthlyReportSerializer,
    DeliveryFeePaymentSerializer,
)
from wallet.models import DeliveryFeePayment
from wallet.services.delivery_fee import (
    DeliveryFeeError,
    DeliveryFeePeriodError,
    serialize_delivery_fee_payment,
)
from wallet.services.delivery_fee_reporting import (
    lifetime_delivery_fee_report,
    monthly_delivery_fee_report,
    parse_report_year_month,
)

DELIVERY_FEE_TAG = 'Admin Delivery Fees'
ALLOWED_PAYMENT_FILTERS = frozenset(
    {'year', 'month', 'customer', 'status', 'q', 'page', 'page_size'}
)


class DeliveryFeePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _unsupported_filters_response(query_params):
    unknown = [key for key in query_params.keys() if key not in ALLOWED_PAYMENT_FILTERS]
    if not unknown:
        return None
    return Response(
        {
            'success': False,
            'message': f'Unsupported filter(s): {", ".join(sorted(unknown))}',
            'errors': {'filters': unknown},
            'error_code': 'UNSUPPORTED_FILTER',
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


class DeliveryFeePaymentListView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[DELIVERY_FEE_TAG],
        operation_id='adminDeliveryFeePaymentList',
        summary='List delivery-fee payments',
        parameters=[
            OpenApiParameter(name='year', type=int, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='month', type=int, location=OpenApiParameter.QUERY),
            OpenApiParameter(
                name='customer',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Customer public_id (UUID)',
            ),
            OpenApiParameter(name='status', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='q', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='page', type=int, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='page_size', type=int, location=OpenApiParameter.QUERY),
        ],
        responses={
            200: DeliveryFeePaymentSerializer(many=True),
            400: OpenApiResponse(description='Unsupported filter'),
            401: OpenApiResponse(description='Unauthenticated'),
            403: OpenApiResponse(description='Forbidden'),
        },
    )
    def get(self, request):
        bad = _unsupported_filters_response(request.query_params)
        if bad is not None:
            return bad

        qs = DeliveryFeePayment.objects.select_related(
            'customer__user',
            'deducted_by_admin__user',
            'wallet_transaction',
        ).order_by('-payment_year', '-payment_month', '-created_at', '-id')

        year = request.query_params.get('year')
        month = request.query_params.get('month')
        if year is not None:
            try:
                qs = qs.filter(payment_year=int(year))
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'year must be an integer.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if month is not None:
            try:
                qs = qs.filter(payment_month=int(month))
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'month must be an integer.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        customer_pid = (request.query_params.get('customer') or '').strip()
        if customer_pid:
            try:
                customer = CustomerProfile.objects.get(public_id=customer_pid)
            except (CustomerProfile.DoesNotExist, ValueError):
                return Response(
                    {'detail': 'Customer not found.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            qs = qs.filter(customer=customer)

        status_filter = (request.query_params.get('status') or '').strip()
        if status_filter:
            if status_filter not in DeliveryFeePayment.Status.values:
                return Response(
                    {'detail': 'Invalid status filter.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(status=status_filter)

        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(build_customer_people_q(q, customer_prefix='customer__'))

        paginator = DeliveryFeePagination()
        page = paginator.paginate_queryset(qs, request)
        payload = [serialize_delivery_fee_payment(p) for p in page]
        return paginator.get_paginated_response(payload)


class DeliveryFeeMonthlyReportView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[DELIVERY_FEE_TAG],
        operation_id='adminDeliveryFeeMonthlyReport',
        summary='Monthly delivery-fee collection report',
        parameters=[
            OpenApiParameter(name='year', type=int, location=OpenApiParameter.QUERY, required=True),
            OpenApiParameter(name='month', type=int, location=OpenApiParameter.QUERY, required=True),
        ],
        responses={
            200: DeliveryFeeMonthlyReportSerializer,
            400: OpenApiResponse(description='Invalid year/month'),
            401: OpenApiResponse(description='Unauthenticated'),
            403: OpenApiResponse(description='Forbidden'),
        },
    )
    def get(self, request):
        try:
            month, year = parse_report_year_month(request.query_params)
            payload = monthly_delivery_fee_report(year=year, month=month)
        except (DeliveryFeePeriodError, DeliveryFeeError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)


class DeliveryFeeLifetimeReportView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[DELIVERY_FEE_TAG],
        operation_id='adminDeliveryFeeLifetimeReport',
        summary='Lifetime delivery-fee collection report',
        responses={
            200: DeliveryFeeLifetimeReportSerializer,
            401: OpenApiResponse(description='Unauthenticated'),
            403: OpenApiResponse(description='Forbidden'),
        },
    )
    def get(self, request):
        return Response(lifetime_delivery_fee_report())
