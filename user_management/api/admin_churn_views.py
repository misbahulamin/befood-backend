from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from orders.models import ChurnFollowUp
from user_management.api.admin_churn_serializers import (
    ChurnFollowUpCreateSerializer,
    ChurnFollowUpSerializer,
    ChurnFollowUpUpdateSerializer,
)
from user_management.api.permissions import IsVerifiedAdmin
from user_management.models import CustomerProfile
from user_management.services.admin_customer import reject_unknown_query_params
from user_management.services.churn import (
    FOLLOW_UP_LIST_ALLOWLIST,
    build_churn_analytics,
    build_churn_customers_queryset,
    churn_customers_csv_response,
    serialize_churn_customer_row,
)


class ChurnPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminChurnCustomersView(APIView):
    permission_classes = [IsVerifiedAdmin]
    pagination_class = ChurnPagination

    @extend_schema(
        tags=['Admin Churn'],
        operation_id='adminChurnCustomersList',
        summary='List churned / lifecycle-filtered customers',
        description=(
            'Verified admin only. Defaults to lifecycle=unsubscribed. '
            'Pass format=csv for CSV download of the filtered set.'
        ),
        parameters=[
            OpenApiParameter(name='lifecycle', type=str, required=False),
            OpenApiParameter(name='churned_from', type=str, required=False),
            OpenApiParameter(name='churned_to', type=str, required=False),
            OpenApiParameter(name='cancel_reason', type=str, required=False),
            OpenApiParameter(name='package', type=str, required=False),
            OpenApiParameter(name='q', type=str, required=False),
            OpenApiParameter(name='sort', type=str, required=False),
            OpenApiParameter(name='format', type=str, required=False),
            OpenApiParameter(name='page', type=int, required=False),
            OpenApiParameter(name='page_size', type=int, required=False),
        ],
        responses={200: OpenApiResponse(description='Paginated customers or CSV')},
    )
    def get(self, request):
        qs = build_churn_customers_queryset(request.query_params)
        if (request.query_params.get('format') or '').strip().lower() == 'csv':
            return churn_customers_csv_response(qs, request=request)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        rows = [
            serialize_churn_customer_row(c, request=request) for c in page
        ]
        return paginator.get_paginated_response(rows)


class AdminChurnAnalyticsView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=['Admin Churn'],
        operation_id='adminChurnAnalytics',
        summary='Churn analytics for a date range',
        parameters=[
            OpenApiParameter(name='from', type=str, required=True),
            OpenApiParameter(name='to', type=str, required=True),
        ],
        responses={200: OpenApiResponse(description='Analytics payload')},
    )
    def get(self, request):
        payload = build_churn_analytics(request.query_params)
        return Response(payload)


class AdminChurnFollowUpViewSet(ViewSet):
    permission_classes = [IsVerifiedAdmin]
    lookup_field = 'public_id'
    pagination_class = ChurnPagination

    def get_object(self):
        return ChurnFollowUp.objects.select_related('customer', 'admin').get(
            public_id=self.kwargs['public_id'],
        )

    @extend_schema(
        tags=['Admin Churn'],
        operation_id='adminChurnFollowUpList',
        summary='List churn follow-ups',
    )
    def list(self, request):
        reject_unknown_query_params(request.query_params, FOLLOW_UP_LIST_ALLOWLIST)
        qs = ChurnFollowUp.objects.select_related('customer', 'admin').order_by(
            '-updated_at',
            '-pk',
        )
        customer_public_id = (request.query_params.get('customer_public_id') or '').strip()
        if customer_public_id:
            qs = qs.filter(customer__public_id=customer_public_id)
        status_filter = (request.query_params.get('status') or '').strip()
        if status_filter:
            qs = qs.filter(status=status_filter)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            ChurnFollowUpSerializer(page, many=True).data
        )

    @extend_schema(
        tags=['Admin Churn'],
        operation_id='adminChurnFollowUpCreate',
        summary='Create churn follow-up',
        request=ChurnFollowUpCreateSerializer,
        responses={201: ChurnFollowUpSerializer},
    )
    def create(self, request):
        serializer = ChurnFollowUpCreateSerializer(data=request.data or {})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        try:
            customer = CustomerProfile.objects.get(
                public_id=serializer.validated_data['customer_public_id'],
            )
        except CustomerProfile.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        row = ChurnFollowUp.objects.create(
            customer=customer,
            status=serializer.validated_data['status'],
            note=serializer.validated_data.get('note') or '',
            admin=request.user,
        )
        return Response(
            ChurnFollowUpSerializer(row).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=['Admin Churn'],
        operation_id='adminChurnFollowUpRetrieve',
        summary='Retrieve churn follow-up',
        responses={200: ChurnFollowUpSerializer},
    )
    def retrieve(self, request, public_id=None):
        try:
            row = self.get_object()
        except ChurnFollowUp.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ChurnFollowUpSerializer(row).data)

    @extend_schema(
        tags=['Admin Churn'],
        operation_id='adminChurnFollowUpUpdate',
        summary='Update churn follow-up',
        request=ChurnFollowUpUpdateSerializer,
        responses={200: ChurnFollowUpSerializer},
    )
    def partial_update(self, request, public_id=None):
        try:
            row = self.get_object()
        except ChurnFollowUp.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ChurnFollowUpUpdateSerializer(data=request.data or {}, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        data = serializer.validated_data
        update_fields = ['updated_at']
        if 'status' in data:
            row.status = data['status']
            update_fields.append('status')
        if 'note' in data:
            row.note = data['note']
            update_fields.append('note')
        row.admin = request.user
        update_fields.append('admin')
        row.save(update_fields=update_fields)
        return Response(ChurnFollowUpSerializer(row).data)
