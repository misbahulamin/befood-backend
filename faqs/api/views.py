from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters, mixins, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from user_management.api.permissions import IsVerifiedAdmin

from faqs.filters import FaqQuestionFilter, FaqTypeFilter
from faqs.models import FaqQuestion, FaqType
from faqs.services import FaqTypeDeleteError, delete_faq_type, get_public_faq_catalog

from .serializers import (
    FaqQuestionAdminSerializer,
    FaqTypeAdminSerializer,
    PublicFaqTypeSerializer,
)


class AdminFaqPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


@extend_schema_view(
    list=extend_schema(
        tags=['Public FAQs'],
        summary='List public FAQ catalog',
        description=(
            'Unauthenticated. Returns active FAQ types that have at least one '
            'published question. Each type nests only published questions. '
            'Ordered by sort_order ascending.'
        ),
        responses={200: PublicFaqTypeSerializer(many=True)},
    ),
)
class PublicFaqCatalogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Public nested FAQ catalog for the website FAQ page."""

    serializer_class = PublicFaqTypeSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = None
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        return get_public_faq_catalog()


@extend_schema_view(
    list=extend_schema(
        tags=['Admin FAQ Types'],
        summary='List FAQ types',
        description=(
            'Verified admin only. Returns all FAQ types including inactive. '
            'Filter by is_active or search name.'
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
                description='Case-insensitive search on name.',
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
        responses={200: FaqTypeAdminSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Admin FAQ Types'],
        summary='Retrieve FAQ type',
        responses={200: FaqTypeAdminSerializer},
    ),
    create=extend_schema(
        tags=['Admin FAQ Types'],
        summary='Create FAQ type',
        request=FaqTypeAdminSerializer,
        responses={201: FaqTypeAdminSerializer},
    ),
    partial_update=extend_schema(
        tags=['Admin FAQ Types'],
        summary='Update FAQ type',
        request=FaqTypeAdminSerializer,
        responses={200: FaqTypeAdminSerializer},
    ),
    destroy=extend_schema(
        tags=['Admin FAQ Types'],
        summary='Delete FAQ type',
        description='Hard-deletes the type. Rejected with 409 if questions still exist.',
        responses={
            204: None,
            409: {'description': 'Type still has questions.'},
        },
    ),
)
class FaqTypeViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Verified-admin CRUD for FAQ types."""

    serializer_class = FaqTypeAdminSerializer
    permission_classes = [IsVerifiedAdmin]
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = FaqTypeFilter
    ordering_fields = ['sort_order', 'name', 'created_at', 'updated_at']
    ordering = ['sort_order', 'created_at']
    pagination_class = AdminFaqPagination
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return FaqType.objects.annotate(question_count=Count('questions'))

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            delete_faq_type(instance)
        except FaqTypeDeleteError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    list=extend_schema(
        tags=['Admin FAQ Questions'],
        summary='List FAQ questions',
        description=(
            'Verified admin only. Returns published and unpublished questions. '
            'Filter by type_public_id, is_published, or search question/answer.'
        ),
        parameters=[
            OpenApiParameter(
                name='type_public_id',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Filter by parent FAQ type public_id (UUID).',
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
                description='Case-insensitive search across question and answer.',
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
                description='Order by sort_order, created_at, updated_at.',
            ),
        ],
        responses={200: FaqQuestionAdminSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Admin FAQ Questions'],
        summary='Retrieve FAQ question',
        responses={200: FaqQuestionAdminSerializer},
    ),
    create=extend_schema(
        tags=['Admin FAQ Questions'],
        summary='Create FAQ question',
        request=FaqQuestionAdminSerializer,
        responses={201: FaqQuestionAdminSerializer},
    ),
    partial_update=extend_schema(
        tags=['Admin FAQ Questions'],
        summary='Update FAQ question',
        request=FaqQuestionAdminSerializer,
        responses={200: FaqQuestionAdminSerializer},
    ),
    destroy=extend_schema(
        tags=['Admin FAQ Questions'],
        summary='Delete FAQ question',
    ),
)
class FaqQuestionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Verified-admin CRUD for FAQ questions."""

    queryset = FaqQuestion.objects.select_related('type').all()
    serializer_class = FaqQuestionAdminSerializer
    permission_classes = [IsVerifiedAdmin]
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = FaqQuestionFilter
    ordering_fields = ['sort_order', 'created_at', 'updated_at']
    ordering = ['sort_order', 'created_at']
    pagination_class = AdminFaqPagination
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
