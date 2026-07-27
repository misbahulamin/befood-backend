from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.api.permissions import IsVerifiedCustomer
from wallet.models import WalletTransaction
from wallet.services.ledger import (
    IdempotencyConflictError,
    InsufficientFundsError,
    InvalidAmountError,
    ManualFundingDisabledError,
    WalletFrozenError,
    get_or_create_wallet,
    recharge_wallet,
    withdraw_wallet,
)

from .serializers import (
    FundingRequestSerializer,
    FundingResponseSerializer,
    WalletSerializer,
    WalletTransactionSerializer,
)


class WalletTransactionPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50


def _customer_profile(request):
    return getattr(request.user, 'customer_profile', None)


def _funding_error_response(exc):
    if isinstance(exc, IdempotencyConflictError):
        return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
    if isinstance(exc, (InvalidAmountError, InsufficientFundsError, WalletFrozenError)):
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, ManualFundingDisabledError):
        return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
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
        description='Paginated ledger for the caller\'s wallet, newest first.',
        parameters=[
            OpenApiParameter(
                name='page',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Page number (1-based).',
            ),
            OpenApiParameter(
                name='page_size',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Page size (default 20, max 50).',
            ),
        ],
        responses={200: WalletTransactionSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Customer Wallet'],
        summary='Get wallet transaction by public_id',
        description=(
            'Retrieve a single ledger row belonging to the caller\'s wallet. '
            'Foreign public_id values return 404.'
        ),
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
        summary='Recharge wallet (manual credit)',
        description=(
            'Credits the caller\'s wallet immediately with method=manual and status=completed. '
            'Optional Idempotency-Key header (or body field) prevents double-credit on retries. '
            'Clients must not send a payment gateway method; the server sets manual.'
        ),
        request=FundingRequestSerializer,
        parameters=[
            OpenApiParameter(
                name='Idempotency-Key',
                type=str,
                location=OpenApiParameter.HEADER,
                required=False,
                description='Optional idempotency key unique per wallet funding request.',
            ),
        ],
        responses={
            200: FundingResponseSerializer,
            400: OpenApiResponse(description='Invalid amount, frozen wallet, or insufficient funds'),
            401: OpenApiResponse(description='Unauthenticated'),
            403: OpenApiResponse(description='Manual funding disabled or not verified customer'),
            409: OpenApiResponse(description='Idempotency key reused with different amount'),
        },
        examples=[
            OpenApiExample(
                'Recharge 500',
                value={'amount': '500.00', 'note': 'Cash top-up'},
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
        serializer = FundingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = _resolve_idempotency_key(request, serializer.validated_data)
        try:
            wallet, txn = recharge_wallet(
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
        summary='Withdraw from wallet (manual debit)',
        description=(
            'Debits the caller\'s wallet immediately with method=manual and status=completed. '
            'This is a ledger balance reduction; real MFS/bank payout is a future payments change. '
            'Optional Idempotency-Key header (or body field) prevents double-debit on retries.'
        ),
        request=FundingRequestSerializer,
        parameters=[
            OpenApiParameter(
                name='Idempotency-Key',
                type=str,
                location=OpenApiParameter.HEADER,
                required=False,
                description='Optional idempotency key unique per wallet funding request.',
            ),
        ],
        responses={
            200: FundingResponseSerializer,
            400: OpenApiResponse(description='Invalid amount, frozen wallet, or insufficient funds'),
            401: OpenApiResponse(description='Unauthenticated'),
            403: OpenApiResponse(description='Manual funding disabled or not verified customer'),
            409: OpenApiResponse(description='Idempotency key reused with different amount'),
        },
        examples=[
            OpenApiExample(
                'Withdraw 500',
                value={'amount': '500.00', 'note': 'Balance reduction'},
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
        serializer = FundingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = _resolve_idempotency_key(request, serializer.validated_data)
        try:
            wallet, txn = withdraw_wallet(
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
        ) as exc:
            return _funding_error_response(exc)

        return Response(
            {
                'wallet': WalletSerializer(wallet).data,
                'transaction': WalletTransactionSerializer(txn).data,
            }
        )
