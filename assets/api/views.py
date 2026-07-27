from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters, mixins, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from user_management.api.permissions import IsVerifiedAdmin

from assets.filters import AssetCategoryFilter, PermanentAssetFilter
from assets.models import AssetCategory, PermanentAsset
from assets.services import (
    active_assets,
    active_categories,
    soft_deactivate_category,
    soft_retire_asset,
)

from .serializers import AssetCategorySerializer, PermanentAssetSerializer


class AdminAssetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


def _wants_inactive(request) -> bool:
    raw = request.query_params.get('include_inactive')
    if raw is None:
        return False
    return str(raw).lower() in ('1', 'true', 'yes')


@extend_schema_view(
    list=extend_schema(
        tags=['Admin Permanent Assets'],
        summary='List asset categories',
        description=(
            'Verified admin only. Permanent asset categories for kitchen/office '
            'equipment (non-consumable; not food inventory). Default list returns '
            'active categories only; pass include_inactive=true to include inactive.'
        ),
        parameters=[
            OpenApiParameter(
                name='is_active',
                type=bool,
                location=OpenApiParameter.QUERY,
                description='Filter by is_active.',
            ),
            OpenApiParameter(
                name='include_inactive',
                type=bool,
                location=OpenApiParameter.QUERY,
                description='When true, include inactive categories (default false).',
            ),
            OpenApiParameter(
                name='search',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Search name and description.',
            ),
            OpenApiParameter(
                name='page',
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page_size',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Page size (default 50, max 200).',
            ),
            OpenApiParameter(
                name='ordering',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Order by name, created_at, or updated_at. Prefix - for desc.',
            ),
        ],
        responses={200: AssetCategorySerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Admin Permanent Assets'],
        summary='Retrieve asset category',
        responses={200: AssetCategorySerializer},
    ),
    create=extend_schema(
        tags=['Admin Permanent Assets'],
        summary='Create asset category',
        request=AssetCategorySerializer,
        responses={201: AssetCategorySerializer},
    ),
    partial_update=extend_schema(
        tags=['Admin Permanent Assets'],
        summary='Update asset category',
        request=AssetCategorySerializer,
        responses={200: AssetCategorySerializer},
    ),
    destroy=extend_schema(
        tags=['Admin Permanent Assets'],
        summary='Soft-deactivate asset category',
        description='Sets is_active=false. Does not hard-delete.',
    ),
)
class AssetCategoryViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Verified-admin CRUD for permanent asset categories."""

    serializer_class = AssetCategorySerializer
    permission_classes = [IsVerifiedAdmin]
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = AssetCategoryFilter
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['name']
    pagination_class = AdminAssetPagination
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        include_inactive = _wants_inactive(self.request)
        # Explicit is_active filter overrides default active-only behavior.
        if 'is_active' in self.request.query_params:
            return AssetCategory.objects.all()
        return active_categories(include_inactive=include_inactive)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        soft_deactivate_category(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    list=extend_schema(
        tags=['Admin Permanent Assets'],
        summary='List permanent assets',
        description=(
            'Verified admin only. Permanent (non-consumable) kitchen/office assets. '
            'These records are independent of food inventory and meal costing — '
            'quantity never decreases through cooking. Default list returns active '
            'assets only; pass include_inactive=true for retired/inactive rows.'
        ),
        parameters=[
            OpenApiParameter(
                name='status',
                type=str,
                location=OpenApiParameter.QUERY,
                description=(
                    'Filter by status: in_service | under_maintenance | '
                    'retired | disposed.'
                ),
                enum=[c.value for c in PermanentAsset.Status],
            ),
            OpenApiParameter(
                name='category_public_id',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter by category public_id (UUID).',
            ),
            OpenApiParameter(
                name='outlet',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Filter by outlet integer PK.',
            ),
            OpenApiParameter(
                name='is_active',
                type=bool,
                location=OpenApiParameter.QUERY,
                description='Filter by is_active.',
            ),
            OpenApiParameter(
                name='include_inactive',
                type=bool,
                location=OpenApiParameter.QUERY,
                description='When true, include inactive assets (default false).',
            ),
            OpenApiParameter(
                name='search',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Search name, asset_tag, serial_number, brand, model.',
            ),
            OpenApiParameter(
                name='page',
                type=int,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='page_size',
                type=int,
                location=OpenApiParameter.QUERY,
                description='Page size (default 50, max 200).',
            ),
            OpenApiParameter(
                name='ordering',
                type=str,
                location=OpenApiParameter.QUERY,
                description=(
                    'Order by name, asset_tag, status, created_at, or updated_at. '
                    'Prefix - for descending.'
                ),
            ),
        ],
        responses={200: PermanentAssetSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Admin Permanent Assets'],
        summary='Retrieve permanent asset',
        description='Verified admin only. Non-consumable equipment record.',
        responses={200: PermanentAssetSerializer},
    ),
    create=extend_schema(
        tags=['Admin Permanent Assets'],
        summary='Create permanent asset',
        description=(
            'Register a permanent asset (refrigerator, burner, furniture, etc.). '
            'Not part of food inventory — never deducted by cooking.'
        ),
        request=PermanentAssetSerializer,
        responses={201: PermanentAssetSerializer},
    ),
    partial_update=extend_schema(
        tags=['Admin Permanent Assets'],
        summary='Update permanent asset',
        request=PermanentAssetSerializer,
        responses={200: PermanentAssetSerializer},
    ),
    destroy=extend_schema(
        tags=['Admin Permanent Assets'],
        summary='Soft-retire permanent asset',
        description=(
            'Sets is_active=false. If status was in_service or under_maintenance, '
            'status becomes retired. Row is retained for history.'
        ),
    ),
)
class PermanentAssetViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Verified-admin CRUD for permanent assets."""

    serializer_class = PermanentAssetSerializer
    permission_classes = [IsVerifiedAdmin]
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = PermanentAssetFilter
    ordering_fields = [
        'name',
        'asset_tag',
        'status',
        'created_at',
        'updated_at',
    ]
    ordering = ['name', 'asset_tag']
    pagination_class = AdminAssetPagination
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        include_inactive = _wants_inactive(self.request)
        if 'is_active' in self.request.query_params:
            return PermanentAsset.objects.select_related('category', 'outlet')
        return active_assets(include_inactive=include_inactive)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        soft_retire_asset(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
