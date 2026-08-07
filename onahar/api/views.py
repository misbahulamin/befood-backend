from django.db.models import Sum
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from onahar.api.serializers import (
    AdminDistributionSerializer,
    AdminDistributionUpdateSerializer,
    AdminDistributionWriteSerializer,
    AuditLogSerializer,
    CustomerHistorySerializer,
    CustomerProgressSerializer,
    FundSummarySerializer,
    LeaderboardEntrySerializer,
    OnaharStatsSerializer,
    PrivacySerializer,
    PrivacyUpdateSerializer,
    PublicDistributionDetailSerializer,
    PublicDistributionListSerializer,
    PublicLedgerEntrySerializer,
    SettingsSerializer,
    SettingsUpdateSerializer,
    TargetHistorySerializer,
)
from onahar.models import (
    OnaharAuditLog,
    OnaharContribution,
    OnaharDistribution,
    OnaharFundLedgerEntry,
    OnaharMonthlyProgress,
    OnaharTargetHistory,
)
from onahar.services.contribution import OnaharError, update_contribution_target
from onahar.services.distribution import (
    OnaharDistributionError,
    attach_media,
    cancel_distribution,
    create_distribution,
    publish_distribution,
    update_draft_distribution,
)
from onahar.services.fund import fund_summary, get_or_create_settings
from onahar.services.privacy import get_or_create_privacy
from onahar.services.queries import (
    build_public_stats,
    customer_lifetime_stats,
    customer_ranking,
    get_or_open_current_progress,
    leaderboard_queryset,
    privacy_display_for_customer_id,
)
from orders.api.permissions import IsVerifiedCustomer
from user_management.api.permissions import IsVerifiedAdmin
from user_management.models import CustomerProfile


class OnaharPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# === Public ===


class OnaharStatsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=['Onahar Public'],
        summary='Public Onahar campaign statistics',
        responses={200: OnaharStatsSerializer},
    )
    def get(self, request):
        data = build_public_stats()
        return Response(OnaharStatsSerializer(data).data)


class OnaharLeaderboardView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=['Onahar Public'],
        summary='Public contributor leaderboard',
        responses={200: LeaderboardEntrySerializer(many=True)},
    )
    def get(self, request):
        paginator = OnaharPagination()
        rows = list(leaderboard_queryset())
        page = paginator.paginate_queryset(rows, request, view=self)
        offset = (paginator.page.number - 1) * paginator.get_page_size(request) if paginator.page else 0
        results = []
        for i, row in enumerate(page or []):
            results.append(
                {
                    'rank': offset + i + 1,
                    'display_name': privacy_display_for_customer_id(row['customer_id']),
                    'total_meals': row['total_meals'],
                }
            )
        return paginator.get_paginated_response(LeaderboardEntrySerializer(results, many=True).data)


class OnaharPublicLedgerView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=['Onahar Public'],
        summary='Public transparency ledger (contributions + distributions)',
        responses={200: PublicLedgerEntrySerializer(many=True)},
    )
    def get(self, request):
        entries = []
        for c in OnaharContribution.objects.select_related('customer__user').order_by('-created_at')[:500]:
            entries.append(
                {
                    'entry_side': 'contribution',
                    'occurred_at': c.created_at,
                    'meals': c.meals,
                    'display_name': privacy_display_for_customer_id(c.customer_id),
                    'location': None,
                    'campaign_public_id': None,
                    'campaign_title': None,
                    '_sort': c.created_at,
                }
            )
        for d in OnaharDistribution.objects.filter(
            status=OnaharDistribution.Status.PUBLISHED
        ).order_by('-published_at')[:500]:
            entries.append(
                {
                    'entry_side': 'distribution',
                    'occurred_at': d.published_at or d.created_at,
                    'meals': d.meals_distributed,
                    'display_name': None,
                    'location': d.location,
                    'campaign_public_id': d.public_id,
                    'campaign_title': d.title,
                    '_sort': d.published_at or d.created_at,
                }
            )
        entries.sort(key=lambda e: e['_sort'], reverse=True)
        for e in entries:
            e.pop('_sort', None)

        paginator = OnaharPagination()
        page = paginator.paginate_queryset(entries, request, view=self)
        return paginator.get_paginated_response(
            PublicLedgerEntrySerializer(page, many=True).data
        )


class OnaharPublicDistributionListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=['Onahar Public'],
        summary='List published Onahar distributions',
        responses={200: PublicDistributionListSerializer(many=True)},
    )
    def get(self, request):
        qs = (
            OnaharDistribution.objects.filter(status=OnaharDistribution.Status.PUBLISHED)
            .prefetch_related('media')
            .order_by('-distribution_date', '-published_at')
        )
        paginator = OnaharPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        ser = PublicDistributionListSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(ser.data)


class OnaharPublicDistributionDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=['Onahar Public'],
        summary='Published distribution detail',
        responses={
            200: PublicDistributionDetailSerializer,
            404: OpenApiResponse(description='Not found'),
        },
    )
    def get(self, request, public_id):
        try:
            dist = OnaharDistribution.objects.prefetch_related('media').get(
                public_id=public_id,
                status=OnaharDistribution.Status.PUBLISHED,
            )
        except OnaharDistribution.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        ser = PublicDistributionDetailSerializer(dist, context={'request': request})
        return Response(ser.data)


# === Customer ===


class OnaharMeView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=['Onahar Customer'],
        summary='Caller Onahar dashboard summary',
        responses={200: CustomerProgressSerializer},
    )
    def get(self, request):
        customer = request.user.customer_profile
        progress = get_or_open_current_progress(customer)
        lifetime = customer_lifetime_stats(customer)
        payload = {
            'year_month': progress.year_month,
            'current_points': progress.net_points,
            'target': progress.target_snapshot,
            'contributions_earned': progress.contributions_earned,
            'remaining_points': progress.remaining_points,
            'points_to_next_contribution': progress.points_to_next_contribution,
            'status': progress.status,
            'total_eligible_meals': lifetime['total_eligible_meals'],
            'total_onahar_meals_contributed': lifetime['total_onahar_meals_contributed'],
            'current_ranking': customer_ranking(customer),
        }
        return Response(CustomerProgressSerializer(payload).data)


class OnaharMeHistoryView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=['Onahar Customer'],
        summary='Caller monthly Onahar history',
        responses={200: CustomerHistorySerializer(many=True)},
    )
    def get(self, request):
        customer = request.user.customer_profile
        qs = OnaharMonthlyProgress.objects.filter(customer=customer).order_by('-year_month')
        paginator = OnaharPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(CustomerHistorySerializer(page, many=True).data)


class OnaharMePrivacyView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=['Onahar Customer'],
        summary='Get Onahar privacy preference',
        responses={200: PrivacySerializer},
    )
    def get(self, request):
        pref = get_or_create_privacy(request.user.customer_profile)
        return Response(PrivacySerializer(pref).data)

    @extend_schema(
        tags=['Onahar Customer'],
        summary='Update Onahar privacy preference',
        request=PrivacyUpdateSerializer,
        responses={200: PrivacySerializer, 400: OpenApiResponse(description='Validation error')},
    )
    def patch(self, request):
        ser = PrivacyUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        pref = get_or_create_privacy(request.user.customer_profile)
        pref.display_mode = ser.validated_data['display_mode']
        pref.save(update_fields=['display_mode', 'updated_at'])
        return Response(PrivacySerializer(pref).data)


# === Admin ===


class OnaharAdminSettingsView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(tags=['Onahar Admin'], summary='Get Onahar settings', responses={200: SettingsSerializer})
    def get(self, request):
        s = get_or_create_settings()
        return Response(
            SettingsSerializer(
                {
                    'contribution_target': s.contribution_target,
                    'total_contributed_meals': s.total_contributed_meals,
                    'total_distributed_meals': s.total_distributed_meals,
                    'available_meals': s.available_meals,
                    'updated_at': s.updated_at,
                }
            ).data
        )

    @extend_schema(
        tags=['Onahar Admin'],
        summary='Update contribution target',
        request=SettingsUpdateSerializer,
        responses={200: SettingsSerializer, 400: OpenApiResponse(description='Invalid target')},
    )
    def patch(self, request):
        ser = SettingsUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            update_contribution_target(ser.validated_data['contribution_target'], actor=request.user)
        except OnaharError as exc:
            return Response({'detail': str(exc), 'error_code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        s = get_or_create_settings()
        return Response(
            SettingsSerializer(
                {
                    'contribution_target': s.contribution_target,
                    'total_contributed_meals': s.total_contributed_meals,
                    'total_distributed_meals': s.total_distributed_meals,
                    'available_meals': s.available_meals,
                    'updated_at': s.updated_at,
                }
            ).data
        )


class OnaharAdminTargetHistoryView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=['Onahar Admin'],
        summary='List contribution target change history',
        responses={200: TargetHistorySerializer(many=True)},
    )
    def get(self, request):
        qs = OnaharTargetHistory.objects.select_related('changed_by').all()
        paginator = OnaharPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(TargetHistorySerializer(page, many=True).data)


class OnaharAdminDistributionListCreateView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=['Onahar Admin'],
        summary='List all distributions',
        parameters=[
            OpenApiParameter(name='status', required=False, type=str),
        ],
        responses={200: AdminDistributionSerializer(many=True)},
    )
    def get(self, request):
        qs = OnaharDistribution.objects.prefetch_related('media').all()
        status_filter = request.query_params.get('status')
        if status_filter:
            if status_filter not in OnaharDistribution.Status.values:
                return Response(
                    {'detail': 'Invalid status filter.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(status=status_filter)
        paginator = OnaharPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            AdminDistributionSerializer(page, many=True, context={'request': request}).data
        )

    @extend_schema(
        tags=['Onahar Admin'],
        summary='Create draft distribution',
        request=AdminDistributionWriteSerializer,
        responses={201: AdminDistributionSerializer},
    )
    def post(self, request):
        ser = AdminDistributionWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        dist = create_distribution(data=ser.validated_data, actor=request.user)
        return Response(
            AdminDistributionSerializer(dist, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class OnaharAdminDistributionDetailView(APIView):
    permission_classes = [IsVerifiedAdmin]

    def _get(self, public_id):
        return OnaharDistribution.objects.prefetch_related('media').get(public_id=public_id)

    @extend_schema(tags=['Onahar Admin'], summary='Distribution detail', responses={200: AdminDistributionSerializer})
    def get(self, request, public_id):
        try:
            dist = self._get(public_id)
        except OnaharDistribution.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AdminDistributionSerializer(dist, context={'request': request}).data)

    @extend_schema(
        tags=['Onahar Admin'],
        summary='Update draft distribution',
        request=AdminDistributionUpdateSerializer,
        responses={200: AdminDistributionSerializer},
    )
    def patch(self, request, public_id):
        try:
            dist = self._get(public_id)
        except OnaharDistribution.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        ser = AdminDistributionUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        try:
            dist = update_draft_distribution(dist, data=ser.validated_data, actor=request.user)
        except OnaharDistributionError as exc:
            return Response({'detail': str(exc), 'error_code': exc.code}, status=status.HTTP_409_CONFLICT)
        return Response(AdminDistributionSerializer(dist, context={'request': request}).data)


class OnaharAdminDistributionPublishView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(tags=['Onahar Admin'], summary='Publish distribution (debit fund)', responses={200: AdminDistributionSerializer})
    def post(self, request, public_id):
        try:
            dist = OnaharDistribution.objects.get(public_id=public_id)
        except OnaharDistribution.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            dist = publish_distribution(dist, actor=request.user)
        except OnaharDistributionError as exc:
            code = status.HTTP_409_CONFLICT if exc.code == 'INSUFFICIENT_ONAHAR_FUND' else status.HTTP_400_BAD_REQUEST
            return Response({'detail': str(exc), 'error_code': exc.code}, status=code)
        return Response(AdminDistributionSerializer(dist, context={'request': request}).data)


class OnaharAdminDistributionCancelView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(tags=['Onahar Admin'], summary='Cancel distribution (restore fund if published)', responses={200: AdminDistributionSerializer})
    def post(self, request, public_id):
        try:
            dist = OnaharDistribution.objects.get(public_id=public_id)
        except OnaharDistribution.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            dist = cancel_distribution(dist, actor=request.user)
        except OnaharDistributionError as exc:
            return Response({'detail': str(exc), 'error_code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminDistributionSerializer(dist, context={'request': request}).data)


class OnaharAdminDistributionMediaView(APIView):
    permission_classes = [IsVerifiedAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(tags=['Onahar Admin'], summary='Upload distribution media', responses={201: AdminDistributionSerializer})
    def post(self, request, public_id):
        try:
            dist = OnaharDistribution.objects.get(public_id=public_id)
        except OnaharDistribution.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        image = request.FILES.get('image')
        if not image:
            return Response({'detail': 'image file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            attach_media(
                dist,
                image=image,
                actor=request.user,
                caption=request.data.get('caption', ''),
                sort_order=int(request.data.get('sort_order') or 0),
            )
        except OnaharDistributionError as exc:
            return Response({'detail': str(exc), 'error_code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        dist.refresh_from_db()
        dist = OnaharDistribution.objects.prefetch_related('media').get(pk=dist.pk)
        return Response(
            AdminDistributionSerializer(dist, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class OnaharAdminFundView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(tags=['Onahar Admin'], summary='Onahar fund summary', responses={200: FundSummarySerializer})
    def get(self, request):
        return Response(FundSummarySerializer(fund_summary()).data)


class OnaharAdminAuditLogView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=['Onahar Admin'],
        summary='Onahar audit log',
        parameters=[OpenApiParameter(name='action', required=False, type=str)],
        responses={200: AuditLogSerializer(many=True)},
    )
    def get(self, request):
        qs = OnaharAuditLog.objects.select_related('actor').all()
        action = request.query_params.get('action')
        if action:
            qs = qs.filter(action=action)
        paginator = OnaharPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(AuditLogSerializer(page, many=True).data)
