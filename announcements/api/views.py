from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters, mixins, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny

from user_management.api.permissions import IsVerifiedAdmin

from announcements.filters import AnnouncementFilter
from announcements.models import Announcement
from announcements.services import get_active_announcements

from .serializers import AnnouncementAdminSerializer, PublicAnnouncementSerializer


class AnnouncementPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50


class AdminAnnouncementPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


@extend_schema_view(
    list=extend_schema(
        tags=['Public Announcements'],
        summary='List currently active announcements',
        description=(
            'Unauthenticated. Returns announcements that are published and within '
            'their schedule window at request time (UTC). Ordered by priority '
            'descending, then newest first. publish_until is inclusive.'
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
        responses={200: PublicAnnouncementSerializer(many=True)},
    ),
)
class ActiveAnnouncementViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Public feed of currently active announcements."""

    serializer_class = PublicAnnouncementSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = AnnouncementPagination
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        return get_active_announcements()


@extend_schema_view(
    list=extend_schema(
        tags=['Admin Announcements'],
        summary='List announcements',
        description=(
            'Verified admin only. Returns all announcements including drafts and '
            'expired rows. Filter by is_published, type, severity, or search title/description.'
        ),
        parameters=[
            OpenApiParameter(
                name='is_published',
                type=bool,
                location=OpenApiParameter.QUERY,
                description='Filter by publish flag.',
            ),
            OpenApiParameter(
                name='type',
                type=str,
                location=OpenApiParameter.QUERY,
                description=(
                    'Filter by type (notice | offer | new_package | '
                    'maintenance | announcement).'
                ),
            ),
            OpenApiParameter(
                name='severity',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter by severity (info | warning | success | error).',
            ),
            OpenApiParameter(
                name='search',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Case-insensitive search across title and description.',
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
                    'Order by priority, publish_at, created_at, or updated_at. '
                    'Prefix with - for descending.'
                ),
            ),
        ],
        responses={200: AnnouncementAdminSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Admin Announcements'],
        summary='Retrieve announcement',
        responses={200: AnnouncementAdminSerializer},
    ),
    create=extend_schema(
        tags=['Admin Announcements'],
        summary='Create announcement',
        request={
            'application/json': AnnouncementAdminSerializer,
            'multipart/form-data': AnnouncementAdminSerializer,
        },
        responses={201: AnnouncementAdminSerializer},
    ),
    partial_update=extend_schema(
        tags=['Admin Announcements'],
        summary='Update announcement',
        request={
            'application/json': AnnouncementAdminSerializer,
            'multipart/form-data': AnnouncementAdminSerializer,
        },
        responses={200: AnnouncementAdminSerializer},
    ),
    destroy=extend_schema(
        tags=['Admin Announcements'],
        summary='Delete announcement',
    ),
)
class AnnouncementViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Verified-admin CRUD for announcements."""

    queryset = Announcement.objects.all()
    serializer_class = AnnouncementAdminSerializer
    permission_classes = [IsVerifiedAdmin]
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = AnnouncementFilter
    ordering_fields = ['priority', 'publish_at', 'created_at', 'updated_at']
    ordering = ['-priority', '-created_at']
    pagination_class = AdminAnnouncementPagination
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
