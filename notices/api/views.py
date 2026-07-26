from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters, mixins, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny

from user_management.api.permissions import IsVerifiedAdmin

from notices.filters import NoticeFilter
from notices.models import Notice
from notices.services import get_active_notices

from .serializers import NoticeAdminSerializer, PublicNoticeSerializer


class NoticePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50


class AdminNoticePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


@extend_schema_view(
    list=extend_schema(
        tags=['Public Notices'],
        summary='List currently active site notices',
        description=(
            'Unauthenticated. Returns notices that are published and within '
            'their schedule window at request time (UTC). Ordered by '
            'sort_order ascending, then newest schedule/create time.'
        ),
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
        responses={200: PublicNoticeSerializer(many=True)},
    ),
)
class ActiveNoticeViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Public feed of currently active site notices."""

    serializer_class = PublicNoticeSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = NoticePagination
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        return get_active_notices()


@extend_schema_view(
    list=extend_schema(
        tags=['Admin Notices'],
        summary='List site notices',
        description=(
            'Verified admin only. Returns all notices including drafts and '
            'expired rows. Filter by is_published, severity, or search titles/bodies.'
        ),
        parameters=[
            OpenApiParameter(
                name='is_published',
                type=bool,
                location=OpenApiParameter.QUERY,
                description='Filter by publish flag.',
            ),
            OpenApiParameter(
                name='severity',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter by severity (info | warning | critical).',
            ),
            OpenApiParameter(
                name='search',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Case-insensitive search across titles and bodies.',
            ),
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
                description='Page size (default 50, max 200).',
            ),
            OpenApiParameter(
                name='ordering',
                type=str,
                location=OpenApiParameter.QUERY,
                description=(
                    'Order by sort_order, publish_at, created_at, or updated_at. '
                    'Prefix with - for descending.'
                ),
            ),
        ],
        responses={200: NoticeAdminSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Admin Notices'],
        summary='Retrieve site notice',
        responses={200: NoticeAdminSerializer},
    ),
    create=extend_schema(
        tags=['Admin Notices'],
        summary='Create site notice',
        request=NoticeAdminSerializer,
        responses={201: NoticeAdminSerializer},
    ),
    partial_update=extend_schema(
        tags=['Admin Notices'],
        summary='Update site notice',
        request=NoticeAdminSerializer,
        responses={200: NoticeAdminSerializer},
    ),
    destroy=extend_schema(
        tags=['Admin Notices'],
        summary='Delete site notice',
    ),
)
class NoticeViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Verified-admin CRUD for site notices."""

    queryset = Notice.objects.all()
    serializer_class = NoticeAdminSerializer
    permission_classes = [IsVerifiedAdmin]
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = NoticeFilter
    ordering_fields = ['sort_order', 'publish_at', 'created_at', 'updated_at']
    ordering = ['sort_order', '-publish_at', '-created_at']
    pagination_class = AdminNoticePagination
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
