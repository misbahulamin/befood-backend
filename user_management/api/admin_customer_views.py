from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from user_management.api.admin_customer_serializers import (
    AdminCustomerActiveOrderSerializer,
    AdminCustomerActivitySerializer,
    AdminCustomerDetailSerializer,
    AdminCustomerListSerializer,
    AdminCustomerMealHistorySerializer,
    AdminCustomerOrderHistorySerializer,
    AdminCustomerWalletTransactionSerializer,
)
from user_management.api.permissions import IsVerifiedAdmin
from user_management.services.admin_customer import (
    MEAL_QUERY_ALLOWLIST,
    apply_customer_list_filters,
    build_active_order_payload,
    build_activity_events,
    customer_base_queryset,
    customer_deliveries_queryset,
    customer_orders_queryset,
    customer_wallet_transactions_queryset,
)


class AdminCustomerPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@extend_schema_view(
    list=extend_schema(
        tags=['Admin Customers'],
        summary='List customers',
        description=(
            'Verified admin only. Paginated customer directory with search and filters. '
            'Verification status maps to email verification (`is_email_verified`), not admin is_verified.'
        ),
        parameters=[
            OpenApiParameter(name='q', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='is_active', type=bool, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='is_email_verified', type=bool, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='has_active_order', type=bool, location=OpenApiParameter.QUERY),
            OpenApiParameter(
                name='meal_public_id',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter customers whose active order uses this meal package UUID.',
            ),
            OpenApiParameter(name='registered_from', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='registered_to', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(
                name='sort',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Allowlisted sort, default -date_joined.',
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=['Admin Customers'],
        summary='Customer detail / overview',
        responses={200: AdminCustomerDetailSerializer},
    ),
)
class AdminCustomerViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Admin SPA customer management (read-only)."""

    permission_classes = [IsVerifiedAdmin]
    pagination_class = AdminCustomerPagination
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        return customer_base_queryset()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AdminCustomerDetailSerializer
        return AdminCustomerListSerializer

    def list(self, request, *args, **kwargs):
        queryset = apply_customer_list_filters(self.get_queryset(), request.query_params)
        page = self.paginate_queryset(queryset)
        serializer = AdminCustomerListSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        tags=['Admin Customers'],
        summary='Active order for customer',
        responses={200: AdminCustomerActiveOrderSerializer},
    )
    @action(detail=True, methods=['get'], url_path='active-order')
    def active_order(self, request, public_id=None):
        customer = self.get_object()
        payload = {'active_order': build_active_order_payload(customer)}
        return Response(payload)

    @extend_schema(
        tags=['Admin Customers'],
        summary='Customer order history',
        responses={200: AdminCustomerOrderHistorySerializer(many=True)},
    )
    @action(detail=True, methods=['get'], url_path='orders')
    def orders(self, request, public_id=None):
        customer = self.get_object()
        queryset = customer_orders_queryset(customer)
        page = self.paginate_queryset(queryset)
        serializer = AdminCustomerOrderHistorySerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        tags=['Admin Customers'],
        summary='Customer meal / delivery history',
        parameters=[
            OpenApiParameter(name='status', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='meal_period', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='service_date_from', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='service_date_to', type=str, location=OpenApiParameter.QUERY),
        ],
        responses={200: AdminCustomerMealHistorySerializer(many=True)},
    )
    @action(detail=True, methods=['get'], url_path='meals')
    def meals(self, request, public_id=None):
        customer = self.get_object()
        queryset = customer_deliveries_queryset(customer, request.query_params)
        page = self.paginate_queryset(queryset)
        serializer = AdminCustomerMealHistorySerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        tags=['Admin Customers'],
        summary='Customer meal-off history',
        parameters=[
            OpenApiParameter(name='meal_period', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='service_date_from', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='service_date_to', type=str, location=OpenApiParameter.QUERY),
        ],
        responses={200: AdminCustomerMealHistorySerializer(many=True)},
    )
    @action(detail=True, methods=['get'], url_path='meal-offs')
    def meal_offs(self, request, public_id=None):
        customer = self.get_object()
        meal_off_allowlist = (MEAL_QUERY_ALLOWLIST - {'status'}) | frozenset(
            {'page', 'page_size'}
        )
        queryset = customer_deliveries_queryset(
            customer,
            request.query_params,
            meal_offs_only=True,
            param_allowlist=meal_off_allowlist,
        )
        page = self.paginate_queryset(queryset)
        serializer = AdminCustomerMealHistorySerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        tags=['Admin Customers'],
        summary='Customer wallet transaction history',
        responses={200: AdminCustomerWalletTransactionSerializer(many=True)},
    )
    @action(detail=True, methods=['get'], url_path='wallet-transactions')
    def wallet_transactions(self, request, public_id=None):
        customer = self.get_object()
        queryset = customer_wallet_transactions_queryset(customer)
        page = self.paginate_queryset(queryset)
        serializer = AdminCustomerWalletTransactionSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        tags=['Admin Customers'],
        summary='Composed customer activity feed',
        responses={200: AdminCustomerActivitySerializer(many=True)},
    )
    @action(detail=True, methods=['get'], url_path='activity')
    def activity(self, request, public_id=None):
        customer = self.get_object()
        events = build_activity_events(customer)
        page = self.paginate_queryset(events)
        serializer = AdminCustomerActivitySerializer(page, many=True)
        return self.get_paginated_response(serializer.data)
