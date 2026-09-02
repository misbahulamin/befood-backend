from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.api.permissions import IsVerifiedCustomer
from wallet.models import WalletTransaction
from wallet.services.funding import (
    DuplicateProviderRefError,
    FundingRequestConflictError,
    approve_recharge,
    approve_withdraw,
    reject_recharge,
    reject_withdraw,
    request_recharge,
    request_withdraw,
)
from wallet.services.ledger import (
    IdempotencyConflictError,
    InsufficientFundsError,
    InvalidAmountError,
    ManualFundingDisabledError,
    PendingTransactionError,
    PlatformFloatError,
    WalletFrozenError,
    get_or_create_wallet,
)

from .serializers import (
    FundingRejectSerializer,
    FundingResponseSerializer,
    RechargeRequestSerializer,
    WalletSerializer,
    WalletTransactionSerializer,
    WithdrawRequestSerializer,
)


class WalletTransactionPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50


def _customer_profile(request):
    return getattr(request.user, 'customer_profile', None)


def _funding_error_response(exc):
    if isinstance(
        exc,
        (
            IdempotencyConflictError,
            PlatformFloatError,
            DuplicateProviderRefError,
            FundingRequestConflictError,
        ),
    ):
        return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
    if isinstance(exc, (InvalidAmountError, InsufficientFundsError, WalletFrozenError)):
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, ManualFundingDisabledError):
        return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, PendingTransactionError):
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _resolve_idempotency_key(request, validated_data):
    header_key = request.headers.get('Idempotency-Key') or request.META.get('HTTP_IDEMPOTENCY_KEY')
    body_key = validated_data.get('idempotency_key')
    return header_key or body_key or None


class WalletDetailView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=['Customer Wallet'],
        summary='Get caller wallet summary',
        description=(
            'Returns the authenticated verified customer\'s wallet. '
            'Creates an active BDT wallet with balance 0.00 on first access. '
            'Includes admin-configured thresholds: min_wallet_balance_to_order '
            '(subscribe floor), low_balance_reminder_threshold, and meal_stop_threshold. '
            'Clients must use public_id, never the integer primary key.'
        ),
        responses={
            200: WalletSerializer,
            401: OpenApiResponse(description='Unauthenticated'),
            403: OpenApiResponse(description='Not a verified customer'),
        },
    )
    def get(self, request):
        profile = _customer_profile(request)
        if profile is None:
            return Response(
                {'detail': 'Customer profile is required.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        wallet = get_or_create_wallet(profile)
        return Response(WalletSerializer(wallet).data)


class WalletTransactionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsVerifiedCustomer]
    serializer_class = WalletTransactionSerializer
    pagination_class = WalletTransactionPagination
    lookup_field = 'public_id'
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        profile = _customer_profile(self.request)
        if profile is None:
            return WalletTransaction.objects.none()
        wallet = get_or_create_wallet(profile)
        return WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')

    @extend_schema(
        tags=['Customer Wallet'],
        summary='List wallet transactions',
        parameters=[
            OpenApiParameter(name='page', type=int, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='page_size', type=int, location=OpenApiParameter.QUERY),
        ],
        responses={200: WalletTransactionSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Customer Wallet'],
        summary='Get wallet transaction by public_id',
        responses={
            200: WalletTransactionSerializer,
            404: OpenApiResponse(description='Transaction not found for this wallet'),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class WalletRechargeView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=['Customer Wallet'],
        summary='Submit wallet recharge request (manual verification)',
        description=(
            'Creates a pending recharge request. Balance is NOT credited until a verified '
            'admin approves. Requires payment_method (bkash|nagad|bank) and transaction_id. '
            'Optional Idempotency-Key prevents duplicate creates on retries.'
        ),
        request=RechargeRequestSerializer,
        parameters=[
            OpenApiParameter(
                name='Idempotency-Key',
                type=str,
                location=OpenApiParameter.HEADER,
                required=False,
            ),
        ],
        responses={
            200: FundingResponseSerializer,
            400: OpenApiResponse(description='Invalid amount/method/transaction_id or frozen wallet'),
            401: OpenApiResponse(description='Unauthenticated'),
            403: OpenApiResponse(description='Manual funding disabled or not verified customer'),
            409: OpenApiResponse(
                description='Idempotency conflict or duplicate provider transaction id'
            ),
        },
        examples=[
            OpenApiExample(
                'Recharge via bKash',
                value={
                    'amount': '500.00',
                    'payment_method': 'bkash',
                    'transaction_id': 'TX123456',
                    'note': 'Sent from personal bKash',
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        profile = _customer_profile(request)
        if profile is None:
            return Response(
                {'detail': 'Customer profile is required.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = RechargeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = _resolve_idempotency_key(request, serializer.validated_data)
        try:
            wallet, txn, _created = request_recharge(
                profile,
                serializer.validated_data['amount'],
                payment_method=serializer.validated_data['payment_method'],
                transaction_id=serializer.validated_data['transaction_id'],
                note=serializer.validated_data.get('note') or '',
                idempotency_key=idempotency_key,
            )
        except (
            IdempotencyConflictError,
            DuplicateProviderRefError,
            InvalidAmountError,
            InsufficientFundsError,
            WalletFrozenError,
            ManualFundingDisabledError,
            PlatformFloatError,
        ) as exc:
            return _funding_error_response(exc)

        return Response(
            {
                'wallet': WalletSerializer(wallet).data,
                'transaction': WalletTransactionSerializer(txn).data,
            }
        )


class WalletWithdrawView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=['Customer Wallet'],
        summary='Submit wallet withdraw request (manual verification)',
        description=(
            'Creates a pending withdraw with method=manual and immediately reserves '
            '(debits) spendable balance. Admin Wallet custody is debited only on approve. '
            'Reject restores the reservation.'
        ),
        request=WithdrawRequestSerializer,
        parameters=[
            OpenApiParameter(
                name='Idempotency-Key',
                type=str,
                location=OpenApiParameter.HEADER,
                required=False,
            ),
        ],
        responses={
            200: FundingResponseSerializer,
            400: OpenApiResponse(description='Invalid amount, insufficient balance, or frozen wallet'),
            401: OpenApiResponse(description='Unauthenticated'),
            403: OpenApiResponse(description='Manual funding disabled or not verified customer'),
            409: OpenApiResponse(description='Idempotency key conflict'),
        },
        examples=[
            OpenApiExample(
                'Withdraw 500',
                value={'amount': '500.00'},
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        profile = _customer_profile(request)
        if profile is None:
            return Response(
                {'detail': 'Customer profile is required.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = WithdrawRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = _resolve_idempotency_key(request, serializer.validated_data)
        try:
            wallet, txn, _created = request_withdraw(
                profile,
                serializer.validated_data['amount'],
                note=serializer.validated_data.get('note') or '',
                idempotency_key=idempotency_key,
            )
        except (
            IdempotencyConflictError,
            InvalidAmountError,
            InsufficientFundsError,
            WalletFrozenError,
            ManualFundingDisabledError,
            PlatformFloatError,
        ) as exc:
            return _funding_error_response(exc)

        return Response(
            {
                'wallet': WalletSerializer(wallet).data,
                'transaction': WalletTransactionSerializer(txn).data,
            }
        )
