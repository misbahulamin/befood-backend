from csv import writer as csv_writer
from io import StringIO

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from referrals.api.serializers import (
    AdminManualAdjustmentSerializer,
    AdminReverseSerializer,
    ReferralCommissionSerializer,
    ReferralMeSerializer,
    ReferralProgramSettingsSerializer,
    ReferredUserSerializer,
    ValidateReferralCodeSerializer,
)
from referrals.models import ReferralCommission
from referrals.services.attribution import attribute_on_signup
from referrals.services.codes import ensure_referral_profile
from referrals.services.commission import (
    manual_adjust_referral_commission,
    reverse_referral_commission,
)
from referrals.services.settings import (
    get_referral_program_settings,
    update_referral_commission_percent,
)
from referrals.services.eligibility import ReferralError, validate_code_for_signup
from referrals.services.events import record_share, record_validation_event
from referrals.services.queries import (
    admin_analytics,
    admin_commissions_qs,
    admin_relationships_qs,
    customer_referral_summary,
    referrer_commissions_qs,
    referrer_relationships_qs,
)
from user_management.api.permissions import HasCustomerProfile, IsVerifiedAdmin
from user_management.models import CustomerProfile


class ReferralValidateThrottle(AnonRateThrottle):
    scope = 'referral_validate'

    def get_rate(self):
        from django.conf import settings

        return getattr(settings, 'REFERRAL_VALIDATE_RATE', '30/hour')


class ReferralPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ReferralMeView(APIView):
    permission_classes = [HasCustomerProfile]

    @extend_schema(tags=['Referrals'], responses={200: ReferralMeSerializer})
    def get(self, request):
        data = customer_referral_summary(request.user.customer_profile)
        return Response(ReferralMeSerializer(data).data)


class ReferralShareView(APIView):
    permission_classes = [HasCustomerProfile]

    @extend_schema(tags=['Referrals'], responses={200: ReferralMeSerializer})
    def post(self, request):
        profile = ensure_referral_profile(request.user.customer_profile)
        record_share(profile)
        data = customer_referral_summary(request.user.customer_profile)
        return Response(ReferralMeSerializer(data).data)


class ReferralReferredUsersView(APIView):
    permission_classes = [HasCustomerProfile]

    @extend_schema(tags=['Referrals'])
    def get(self, request):
        qs = referrer_relationships_qs(request.user.customer_profile)
        paginator = ReferralPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(ReferredUserSerializer(page, many=True).data)


class ReferralMyCommissionsView(APIView):
    permission_classes = [HasCustomerProfile]

    @extend_schema(tags=['Referrals'])
    def get(self, request):
        qs = referrer_commissions_qs(request.user.customer_profile)
        paginator = ReferralPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            ReferralCommissionSerializer(page, many=True).data
        )


class ReferralValidateView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ReferralValidateThrottle]

    @extend_schema(tags=['Referrals'], request=ValidateReferralCodeSerializer)
    def post(self, request):
        serializer = ValidateReferralCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['referral_code']
        client_ip = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        try:
            profile = validate_code_for_signup(code)
        except ReferralError as exc:
            record_validation_event(
                code=code,
                is_valid=False,
                reason=exc.code,
                client_ip=client_ip,
                user_agent=user_agent,
            )
            return Response(
                {'detail': exc.message, 'code': exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record_validation_event(
            code=profile.code,
            is_valid=True,
            reason='OK',
            referrer=profile.customer,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        return Response(
            {
                'valid': True,
                'referral_code': profile.code,
                'referrer_public_id': str(profile.customer.public_id),
            }
        )


class AdminReferralProgramSettingsView(APIView):
    """Verified-admin GET/PATCH for live referral commission percent."""

    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=['Admin Referrals'],
        summary='Get referral program settings',
        description=(
            'Returns the live referral commission percent used for future accruals. '
            'Changing this value does not rewrite historical ReferralCommission rows.'
        ),
        responses={
            200: ReferralProgramSettingsSerializer,
            403: OpenApiResponse(description='Verified admin required'),
        },
        examples=[
            OpenApiExample(
                'Default settings',
                value={
                    'referral_commission_percent': '5.00',
                    'updated_at': '2026-09-11T00:00:00Z',
                },
                response_only=True,
            ),
        ],
    )
    def get(self, request):
        settings_obj = get_referral_program_settings()
        return Response(ReferralProgramSettingsSerializer(settings_obj).data)

    @extend_schema(
        tags=['Admin Referrals'],
        summary='Update referral program settings',
        description=(
            'Partially update referral_commission_percent (0–100, at most 2 decimal places). '
            'Applies only to future commission calculations.'
        ),
        request=ReferralProgramSettingsSerializer,
        responses={
            200: ReferralProgramSettingsSerializer,
            400: OpenApiResponse(description='Validation error'),
            403: OpenApiResponse(description='Verified admin required'),
        },
        examples=[
            OpenApiExample(
                'Update percent',
                value={'referral_commission_percent': '10.00'},
                request_only=True,
            ),
        ],
    )
    def patch(self, request):
        settings_obj = get_referral_program_settings()
        serializer = ReferralProgramSettingsSerializer(
            settings_obj, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        percent = serializer.validated_data.get('commission_percent')
        if percent is not None:
            settings_obj = update_referral_commission_percent(
                referral_commission_percent=percent
            )
        return Response(ReferralProgramSettingsSerializer(settings_obj).data)


class AdminReferralAnalyticsView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(tags=['Admin Referrals'])
    def get(self, request):
        data = admin_analytics(
            date_from=request.query_params.get('created_from'),
            date_to=request.query_params.get('created_to'),
        )
        # Convert decimals for JSON
        for key, value in list(data.items()):
            if hasattr(value, 'quantize'):
                data[key] = f'{value:.4f}' if 'rate' in key else f'{value:.2f}'
        return Response(data)


class AdminReferralRelationshipsView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(tags=['Admin Referrals'])
    def get(self, request):
        qs = admin_relationships_qs(
            filters={
                'referral_code': request.query_params.get('referral_code'),
                'referrer_public_id': request.query_params.get('referrer_public_id'),
                'referred_public_id': request.query_params.get('referred_public_id'),
                'created_from': request.query_params.get('created_from'),
                'created_to': request.query_params.get('created_to'),
            }
        )
        paginator = ReferralPagination()
        page = paginator.paginate_queryset(qs, request)
        payload = [
            {
                'public_id': str(row.public_id),
                'referrer_public_id': str(row.referrer.public_id),
                'referred_public_id': str(row.referred.public_id),
                'referral_code_used': row.referral_code_used,
                'source_client': row.source_client,
                'attributed_at': row.attributed_at,
            }
            for row in page
        ]
        return paginator.get_paginated_response(payload)


class AdminReferralCommissionsView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(tags=['Admin Referrals'])
    def get(self, request):
        qs = admin_commissions_qs(
            filters={
                'status': request.query_params.get('status'),
                'referral_code': request.query_params.get('referral_code'),
                'referrer_public_id': request.query_params.get('referrer_public_id'),
                'referred_public_id': request.query_params.get('referred_public_id'),
                'created_from': request.query_params.get('created_from'),
                'created_to': request.query_params.get('created_to'),
            }
        )
        paginator = ReferralPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            ReferralCommissionSerializer(page, many=True).data
        )


class AdminReferralCommissionsExportView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(tags=['Admin Referrals'])
    def get(self, request):
        qs = admin_commissions_qs(
            filters={
                'status': request.query_params.get('status'),
                'referral_code': request.query_params.get('referral_code'),
                'referrer_public_id': request.query_params.get('referrer_public_id'),
                'referred_public_id': request.query_params.get('referred_public_id'),
                'created_from': request.query_params.get('created_from'),
                'created_to': request.query_params.get('created_to'),
            }
        )
        buffer = StringIO()
        csv = csv_writer(buffer)
        csv.writerow(
            [
                'commission_public_id',
                'status',
                'referrer_public_id',
                'referred_public_id',
                'delivery_public_id',
                'meal_service_date',
                'meal_price',
                'commission_percent',
                'commission_amount',
                'admin_wallet_txn',
                'customer_wallet_txn',
                'created_at',
            ]
        )
        for row in qs.iterator():
            csv.writerow(
                [
                    str(row.public_id),
                    row.status,
                    str(row.referrer.public_id),
                    str(row.referred.public_id) if row.referred_id else '',
                    str(row.order_delivery.public_id) if row.order_delivery_id else '',
                    row.meal_service_date or '',
                    row.meal_price or '',
                    row.commission_percent,
                    row.commission_amount,
                    str(row.admin_wallet_transaction.public_id)
                    if row.admin_wallet_transaction_id
                    else '',
                    str(row.customer_wallet_transaction.public_id)
                    if row.customer_wallet_transaction_id
                    else '',
                    row.created_at.isoformat(),
                ]
            )
        response = HttpResponse(buffer.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="referral-commissions.csv"'
        return response


class AdminReferralCustomerDetailView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(tags=['Admin Referrals'])
    def get(self, request, public_id):
        customer = get_object_or_404(CustomerProfile, public_id=public_id)
        summary = customer_referral_summary(customer)
        referred_by = getattr(customer, 'referred_by_relationship', None)
        return Response(
            {
                'customer_public_id': str(customer.public_id),
                'referral': summary,
                'referred_by_public_id': (
                    str(referred_by.referrer.public_id) if referred_by else None
                ),
                'as_referrer_relationships': ReferralRelationshipCount(customer),
            }
        )


def ReferralRelationshipCount(customer):
    return referrer_relationships_qs(customer).count()


class AdminReferralReverseView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(tags=['Admin Referrals'], request=AdminReverseSerializer)
    def post(self, request, public_id):
        serializer = AdminReverseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        commission = get_object_or_404(ReferralCommission, public_id=public_id)
        try:
            updated = reverse_referral_commission(
                commission,
                reason=serializer.validated_data['reason'],
                actor=request.user,
            )
        except ReferralError as exc:
            http = (
                status.HTTP_422_UNPROCESSABLE_ENTITY
                if exc.code == 'REASON_REQUIRED'
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({'detail': exc.message, 'code': exc.code}, status=http)
        return Response(ReferralCommissionSerializer(updated).data)


class AdminReferralManualAdjustView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(tags=['Admin Referrals'], request=AdminManualAdjustmentSerializer)
    def post(self, request):
        serializer = AdminManualAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        referrer = get_object_or_404(
            CustomerProfile, public_id=data['referrer_public_id']
        )
        referred = None
        if data.get('referred_public_id'):
            referred = get_object_or_404(
                CustomerProfile, public_id=data['referred_public_id']
            )
        try:
            row = manual_adjust_referral_commission(
                referrer=referrer,
                amount=data['amount'],
                reason=data['reason'],
                actor=request.user,
                referred=referred,
            )
        except ReferralError as exc:
            http = (
                status.HTTP_422_UNPROCESSABLE_ENTITY
                if exc.code == 'REASON_REQUIRED'
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({'detail': exc.message, 'code': exc.code}, status=http)
        return Response(
            ReferralCommissionSerializer(row).data,
            status=status.HTTP_201_CREATED,
        )
