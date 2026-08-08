from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from admin_wallet.api.openapi import ADMIN_WALLET_TAG
from admin_wallet.api.serializers import (
    AdminWalletDashboardSerializer,
    AdminWalletSummarySerializer,
    AdminWalletTransactionSerializer,
    AuditLogSerializer,
    ExpenseSerializer,
    ManualDepositSerializer,
    WithdrawalSerializer,
)
from admin_wallet.models import AdminWalletAuditLog, AdminWalletTransaction
from admin_wallet.services.ledger import (
    AdminWalletError,
    InsufficientFundsError,
    InvalidAmountError,
    get_or_create_platform_wallet,
)
from admin_wallet.services.operations import manual_deposit, post_expense, withdraw
from admin_wallet.services.queries import (
    ALLOWED_TRANSACTION_FILTERS,
    dashboard_payload,
    filter_transactions,
    wallet_summary,
)
from orders.models import Order
from user_management.api.permissions import IsVerifiedAdmin
from user_management.models import CustomerProfile


class AdminWalletPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _error_response(exc: Exception, http_status=status.HTTP_400_BAD_REQUEST):
    code = getattr(exc, 'code', 'ADMIN_WALLET_ERROR')
    return Response(
        {
            'success': False,
            'message': str(exc),
            'errors': {},
            'error_code': code,
        },
        status=http_status,
    )


def _actor_admin(request):
    return getattr(request.user, 'admin_profile', None)


def _idempotency_key(request) -> str | None:
    key = request.headers.get('Idempotency-Key') or request.headers.get('idempotency-key')
    return key.strip() if key else None


class AdminWalletSummaryView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ADMIN_WALLET_TAG],
        operation_id='adminWalletSummary',
        summary='Admin Wallet summary',
        responses={200: AdminWalletSummarySerializer},
    )
    def get(self, request):
        data = wallet_summary()
        return Response(AdminWalletSummarySerializer(data).data)


class AdminWalletDashboardView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ADMIN_WALLET_TAG],
        operation_id='adminWalletDashboard',
        summary='Admin Wallet dashboard cards and recent transactions',
        responses={200: AdminWalletDashboardSerializer},
    )
    def get(self, request):
        payload = dashboard_payload()
        return Response(AdminWalletDashboardSerializer(payload).data)


class AdminWalletTransactionListView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ADMIN_WALLET_TAG],
        operation_id='adminWalletTransactionList',
        summary='List Admin Wallet transactions',
        parameters=[
            OpenApiParameter('date_from', str, description='YYYY-MM-DD'),
            OpenApiParameter('date_to', str, description='YYYY-MM-DD'),
            OpenApiParameter('direction', str, enum=['credit', 'debit']),
            OpenApiParameter('type', str, description='Transaction type or group (expense, refund)'),
            OpenApiParameter('method', str),
            OpenApiParameter('status', str),
            OpenApiParameter('q', str, description='Search public_id / order / customer'),
            OpenApiParameter('page', int),
            OpenApiParameter('page_size', int),
        ],
        responses={200: AdminWalletTransactionSerializer(many=True)},
    )
    def get(self, request):
        params = {k: v for k, v in request.query_params.items() if k in ALLOWED_TRANSACTION_FILTERS}
        # Reject unknown query keys (except DRF format)
        ignored = {'format'}
        unknown = set(request.query_params.keys()) - ALLOWED_TRANSACTION_FILTERS - ignored
        if unknown:
            return Response(
                {
                    'success': False,
                    'message': f'Unsupported filter(s): {", ".join(sorted(unknown))}',
                    'errors': {'filters': list(sorted(unknown))},
                    'error_code': 'UNSUPPORTED_FILTER',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        wallet = get_or_create_platform_wallet()
        try:
            qs = filter_transactions(wallet, params)
        except ValueError as exc:
            return Response(
                {
                    'success': False,
                    'message': str(exc),
                    'errors': {},
                    'error_code': 'INVALID_FILTER',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        paginator = AdminWalletPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        ser = AdminWalletTransactionSerializer(page, many=True)
        return paginator.get_paginated_response(ser.data)


class AdminWalletTransactionDetailView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ADMIN_WALLET_TAG],
        operation_id='adminWalletTransactionDetail',
        summary='Admin Wallet transaction detail',
        responses={
            200: AdminWalletTransactionSerializer,
            404: OpenApiResponse(description='Not found'),
        },
    )
    def get(self, request, public_id):
        wallet = get_or_create_platform_wallet()
        try:
            txn = AdminWalletTransaction.objects.select_related(
                'order',
                'order_delivery',
                'customer__user',
                'actor_admin__user',
            ).get(wallet=wallet, public_id=public_id)
        except AdminWalletTransaction.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'message': 'Transaction not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(AdminWalletTransactionSerializer(txn).data)


class AdminWalletDepositView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ADMIN_WALLET_TAG],
        operation_id='adminWalletDeposit',
        summary='Manual deposit into Admin Wallet',
        request=ManualDepositSerializer,
        responses={201: AdminWalletTransactionSerializer},
    )
    def post(self, request):
        ser = ManualDepositSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            txn = manual_deposit(
                ser.validated_data['amount'],
                reason=ser.validated_data['reason'],
                note=ser.validated_data.get('note') or '',
                actor_admin=_actor_admin(request),
                idempotency_key=_idempotency_key(request),
            )
        except (InvalidAmountError, AdminWalletError) as exc:
            return _error_response(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response(
            AdminWalletTransactionSerializer(txn).data,
            status=status.HTTP_201_CREATED,
        )


class AdminWalletWithdrawalView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ADMIN_WALLET_TAG],
        operation_id='adminWalletWithdrawal',
        summary='Withdraw from Admin Wallet',
        request=WithdrawalSerializer,
        responses={201: AdminWalletTransactionSerializer},
    )
    def post(self, request):
        ser = WithdrawalSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            txn = withdraw(
                ser.validated_data['amount'],
                reason=ser.validated_data['reason'],
                note=ser.validated_data.get('note') or '',
                actor_admin=_actor_admin(request),
                idempotency_key=_idempotency_key(request),
            )
        except InsufficientFundsError as exc:
            return _error_response(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)
        except (InvalidAmountError, AdminWalletError) as exc:
            return _error_response(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response(
            AdminWalletTransactionSerializer(txn).data,
            status=status.HTTP_201_CREATED,
        )


class AdminWalletExpenseView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ADMIN_WALLET_TAG],
        operation_id='adminWalletExpense',
        summary='Post a typed expense debit',
        request=ExpenseSerializer,
        responses={201: AdminWalletTransactionSerializer},
    )
    def post(self, request):
        ser = ExpenseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        order = None
        customer = None
        if data.get('order_public_id'):
            try:
                order = Order.objects.get(public_id=data['order_public_id'])
            except Order.DoesNotExist:
                return Response(
                    {
                        'success': False,
                        'message': 'Order not found.',
                        'errors': {'order_public_id': ['Not found.']},
                        'error_code': 'ORDER_NOT_FOUND',
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
        if data.get('customer_public_id'):
            try:
                customer = CustomerProfile.objects.get(public_id=data['customer_public_id'])
            except CustomerProfile.DoesNotExist:
                return Response(
                    {
                        'success': False,
                        'message': 'Customer not found.',
                        'errors': {'customer_public_id': ['Not found.']},
                        'error_code': 'CUSTOMER_NOT_FOUND',
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
        try:
            txn = post_expense(
                data['amount'],
                type=data['type'],
                reason=data['reason'],
                note=data.get('note') or '',
                reference=data.get('reference') or '',
                actor_admin=_actor_admin(request),
                order=order,
                customer=customer,
                idempotency_key=_idempotency_key(request),
            )
        except InsufficientFundsError as exc:
            return _error_response(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)
        except (InvalidAmountError, AdminWalletError) as exc:
            return _error_response(exc, status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response(
            AdminWalletTransactionSerializer(txn).data,
            status=status.HTTP_201_CREATED,
        )


class AdminWalletAuditLogListView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ADMIN_WALLET_TAG],
        operation_id='adminWalletAuditLogList',
        summary='List Admin Wallet audit logs',
        responses={200: AuditLogSerializer(many=True)},
    )
    def get(self, request):
        qs = AdminWalletAuditLog.objects.select_related(
            'actor_admin__user',
            'transaction',
        ).order_by('-created_at', '-id')
        paginator = AdminWalletPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(AuditLogSerializer(page, many=True).data)
