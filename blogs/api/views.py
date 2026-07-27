from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from user_management.api.permissions import IsVerifiedAdmin

from blogs.filters import BlogArticleFilter, BlogCategoryFilter, PublicBlogArticleFilter
from blogs.models import BlogArticle, BlogCategory
from blogs.services import (
    DEFAULT_POPULAR_LIMIT,
    DEFAULT_RELATED_LIMIT,
    MAX_POPULAR_LIMIT,
    MAX_RELATED_LIMIT,
    get_popular_articles,
    get_public_article_queryset,
    get_related_articles,
    increment_article_views,
)

from .serializers import (
    BlogArticleAdminSerializer,
    BlogCategoryAdminSerializer,
    PublicBlogArticleCardSerializer,
    PublicBlogArticleDetailSerializer,
)


class AdminBlogPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class PublicBlogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50


@extend_schema_view(
    list=extend_schema(
        tags=['Admin Blog Categories'],
        summary='List blog categories',
        description=(
            'Verified admin only. Returns all blog categories including inactive. '
            'Filter by is_active or search name/slug.'
        ),
        parameters=[
            OpenApiParameter(
                name='is_active',
                type=bool,
                location=OpenApiParameter.QUERY,
                description='Filter by is_active.',
            ),
            OpenApiParameter(
                name='search',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Case-insensitive search on name or slug.',
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
                description='Order by sort_order, name, created_at, updated_at.',
            ),
        ],
        responses={200: BlogCategoryAdminSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Admin Blog Categories'],
        summary='Retrieve blog category',
        responses={200: BlogCategoryAdminSerializer},
    ),
    create=extend_schema(
        tags=['Admin Blog Categories'],
        summary='Create blog category',
        request=BlogCategoryAdminSerializer,
        responses={201: BlogCategoryAdminSerializer},
    ),
    partial_update=extend_schema(
        tags=['Admin Blog Categories'],
        summary='Update blog category',
        request=BlogCategoryAdminSerializer,
        responses={200: BlogCategoryAdminSerializer},
    ),
    destroy=extend_schema(
        tags=['Admin Blog Categories'],
        summary='Delete blog category',
        description=(
            'Hard-deletes the category. Articles that referenced it have '
            'category set to null (SET_NULL).'
        ),
        responses={204: None},
    ),
)
class BlogCategoryViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Verified-admin CRUD for blog categories."""

    queryset = BlogCategory.objects.all()
    serializer_class = BlogCategoryAdminSerializer
    permission_classes = [IsVerifiedAdmin]
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = BlogCategoryFilter
    ordering_fields = ['sort_order', 'name', 'created_at', 'updated_at']
    ordering = ['sort_order', 'created_at']
    pagination_class = AdminBlogPagination
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']


@extend_schema_view(
    list=extend_schema(
        tags=['Admin Blog Articles'],
        summary='List blog articles',
        description=(
            'Verified admin only. Returns published and draft articles. '
            'Filter by category_public_id, is_published, or search title/excerpt.'
        ),
        parameters=[
            OpenApiParameter(
                name='category_public_id',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter by category public_id (UUID).',
            ),
            OpenApiParameter(
                name='is_published',
                type=bool,
                location=OpenApiParameter.QUERY,
                description='Filter by publish flag.',
            ),
            OpenApiParameter(
                name='search',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Case-insensitive search across title and excerpt.',
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
                    'Order by published_at, created_at, updated_at, view_count, title. '
                    'Prefix with - for descending.'
                ),
            ),
        ],
        responses={200: BlogArticleAdminSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Admin Blog Articles'],
        summary='Retrieve blog article',
        responses={200: BlogArticleAdminSerializer},
    ),
    create=extend_schema(
        tags=['Admin Blog Articles'],
        summary='Create blog article',
        request={
            'application/json': BlogArticleAdminSerializer,
            'multipart/form-data': BlogArticleAdminSerializer,
        },
        responses={201: BlogArticleAdminSerializer},
    ),
    partial_update=extend_schema(
        tags=['Admin Blog Articles'],
        summary='Update blog article',
        request={
            'application/json': BlogArticleAdminSerializer,
            'multipart/form-data': BlogArticleAdminSerializer,
        },
        responses={200: BlogArticleAdminSerializer},
    ),
    destroy=extend_schema(
        tags=['Admin Blog Articles'],
        summary='Delete blog article',
    ),
)
class BlogArticleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Verified-admin CRUD for blog articles."""

    queryset = BlogArticle.objects.select_related('category', 'author').all()
    serializer_class = BlogArticleAdminSerializer
    permission_classes = [IsVerifiedAdmin]
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = BlogArticleFilter
    ordering_fields = [
        'published_at',
        'created_at',
        'updated_at',
        'view_count',
        'title',
    ]
    ordering = ['-created_at']
    pagination_class = AdminBlogPagination
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']


@extend_schema_view(
    list=extend_schema(
        tags=['Public Blogs'],
        summary='List published blog articles',
        description=(
            'Unauthenticated. Returns paginated published articles only. '
            'List items omit full content (card fields). Default order: '
            '-published_at. Optional filters: category (category public_id), q (title/excerpt).'
        ),
        parameters=[
            OpenApiParameter(
                name='category',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter by category public_id (UUID).',
            ),
            OpenApiParameter(
                name='q',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Case-insensitive search on title or excerpt.',
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
                description='Page size (default 20, max 50).',
            ),
        ],
        responses={200: PublicBlogArticleCardSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Public Blogs'],
        summary='Retrieve published blog article',
        description=(
            'Unauthenticated. Returns a published article including content. '
            'On success, atomically increments view_count by one. '
            'Unpublished or unknown articles return 404.'
        ),
        responses={200: PublicBlogArticleDetailSerializer},
    ),
)
class PublicBlogArticleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Public published blog list/detail plus popular and related actions."""

    permission_classes = [AllowAny]
    authentication_classes = []
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    filter_backends = [DjangoFilterBackend]
    filterset_class = PublicBlogArticleFilter
    pagination_class = PublicBlogPagination
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        return get_public_article_queryset()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PublicBlogArticleDetailSerializer
        return PublicBlogArticleCardSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        increment_article_views(instance)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @extend_schema(
        tags=['Public Blogs'],
        summary='List most popular published articles',
        description=(
            'Unauthenticated. Returns a non-paginated list of published articles '
            f'ordered by view_count descending. Default limit {DEFAULT_POPULAR_LIMIT}, '
            f'max {MAX_POPULAR_LIMIT} (clamped). Card payload only (no full content).'
        ),
        parameters=[
            OpenApiParameter(
                name='limit',
                type=int,
                location=OpenApiParameter.QUERY,
                description=(
                    f'Max results (default {DEFAULT_POPULAR_LIMIT}, '
                    f'max {MAX_POPULAR_LIMIT}; values above max are clamped).'
                ),
            ),
        ],
        responses={200: PublicBlogArticleCardSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='popular')
    def popular(self, request):
        articles = get_popular_articles(request.query_params.get('limit'))
        serializer = PublicBlogArticleCardSerializer(
            articles,
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    @extend_schema(
        tags=['Public Blogs'],
        summary='List related published articles',
        description=(
            'Unauthenticated. Suggests related published articles for the given '
            'published article. Prefers same category, then global backfill. '
            f'Default limit {DEFAULT_RELATED_LIMIT}, max {MAX_RELATED_LIMIT} (clamped). '
            'Source article must be published or 404.'
        ),
        parameters=[
            OpenApiParameter(
                name='limit',
                type=int,
                location=OpenApiParameter.QUERY,
                description=(
                    f'Max results (default {DEFAULT_RELATED_LIMIT}, '
                    f'max {MAX_RELATED_LIMIT}; values above max are clamped).'
                ),
            ),
        ],
        responses={200: PublicBlogArticleCardSerializer(many=True)},
    )
    @action(detail=True, methods=['get'], url_path='related')
    def related(self, request, public_id=None):
        article = self.get_object()
        related = get_related_articles(article, request.query_params.get('limit'))
        serializer = PublicBlogArticleCardSerializer(
            related,
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
