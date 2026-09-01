from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from user_management.api.permissions import IsVerifiedAdmin
from wallet.api.serializers import (
    AdminFundingRequestSerializer,
    FundingRejectSerializer,
)
from wallet.api.views import _funding_error_response
from wallet.models import WalletTransaction
from wallet.services.funding import (
    FundingRequestConflictError,
    approve_recharge,
    approve_withdraw,
    reject_recharge,
    reject_withdraw,
)
from wallet.services.ledger import (
    PendingTransactionError,
    PlatformFloatError,
)


class AdminFundingPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminFundingRequestViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Verified-admin funding review queue.

    Not gated by WALLET_MANUAL_FUNDING_ENABLED so pending withdraws remain resolvable.
    """

    permission_classes = [IsVerifiedAdmin]
    serializer_class = AdminFundingRequestSerializer
    pagination_class = AdminFundingPagination
    lookup_field = 'public_id'
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = (
            WalletTransaction.objects.filter(
                type__in=[
                    WalletTransaction.Type.RECHARGE,
                    WalletTransaction.Type.WITHDRAW,
                ]
            )
            .select_related('wallet__customer__user', 'reviewed_by')
            .order_by('-created_at')
        )
        txn_type = self.request.query_params.get('type')
        if txn_type in {
            WalletTransaction.Type.RECHARGE,
            WalletTransaction.Type.WITHDRAW,
        }:
            qs = qs.filter(type=txn_type)
        status_filter = self.request.query_params.get('status')
        if status_filter in {
            WalletTransaction.Status.PENDING,
            WalletTransaction.Status.COMPLETED,
            WalletTransaction.Status.FAILED,
        }:
            qs = qs.filter(status=status_filter)
        return qs

    @extend_schema(
        tags=['Admin Wallet Funding Review'],
        summary='List customer funding requests',
        parameters=[
            OpenApiParameter(name='type', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='status', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='page', type=int, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='page_size', type=int, location=OpenApiParameter.QUERY),
        ],
        responses={
            200: AdminFundingRequestSerializer(many=True),
            401: OpenApiResponse(description='Unauthenticated'),
            403: OpenApiResponse(description='Not a verified admin'),
        },
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Admin Wallet Funding Review'],
        summary='Get funding request detail',
        responses={
            200: AdminFundingRequestSerializer,
            404: OpenApiResponse(description='Not found'),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Admin Wallet Funding Review'],
        summary='Approve pending funding request',
        request=None,
        responses={
            200: AdminFundingRequestSerializer,
            409: OpenApiResponse(
                description='Already processed, or Admin Wallet float insufficient for withdraw'
            ),
            404: OpenApiResponse(description='Not found'),
        },
    )
    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, public_id=None):
        txn = self.get_object()
        try:
            if txn.type == WalletTransaction.Type.RECHARGE:
                txn = approve_recharge(txn, reviewed_by=request.user)
            elif txn.type == WalletTransaction.Type.WITHDRAW:
                txn = approve_withdraw(txn, reviewed_by=request.user)
            else:
                return Response(
                    {'detail': 'Unsupported funding type.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (
            FundingRequestConflictError,
            PlatformFloatError,
            PendingTransactionError,
        ) as exc:
            return _funding_error_response(exc)
        txn = (
            WalletTransaction.objects.select_related(
                'wallet__customer__user',
                'reviewed_by',
            ).get(pk=txn.pk)
        )
        return Response(AdminFundingRequestSerializer(txn).data)

    @extend_schema(
        tags=['Admin Wallet Funding Review'],
        summary='Reject pending funding request',
        request=FundingRejectSerializer,
        responses={
            200: AdminFundingRequestSerializer,
            409: OpenApiResponse(description='Already processed'),
            404: OpenApiResponse(description='Not found'),
        },
    )
    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, public_id=None):
        txn = self.get_object()
        serializer = FundingRejectSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get('reason') or ''
        try:
            if txn.type == WalletTransaction.Type.RECHARGE:
                txn = reject_recharge(txn, reviewed_by=request.user, reason=reason)
            elif txn.type == WalletTransaction.Type.WITHDRAW:
                txn = reject_withdraw(txn, reviewed_by=request.user, reason=reason)
            else:
                return Response(
                    {'detail': 'Unsupported funding type.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (FundingRequestConflictError, PendingTransactionError) as exc:
            return _funding_error_response(exc)
        txn = (
            WalletTransaction.objects.select_related(
                'wallet__customer__user',
                'reviewed_by',
            ).get(pk=txn.pk)
        )
        return Response(AdminFundingRequestSerializer(txn).data)
