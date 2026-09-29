from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle

from user_management.api.permissions import IsVerifiedAdmin

from sliders.models import HomeSlider

from .serializers import AdminSliderSerializer, PublicSliderSerializer


class AdminSliderPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


@extend_schema_view(
    list=extend_schema(tags=['Admin Sliders'], summary='List sliders'),
    retrieve=extend_schema(tags=['Admin Sliders'], summary='Retrieve slider'),
    create=extend_schema(tags=['Admin Sliders'], summary='Create slider'),
    partial_update=extend_schema(tags=['Admin Sliders'], summary='Update slider'),
    destroy=extend_schema(tags=['Admin Sliders'], summary='Delete slider'),
)
class AdminSliderViewSet(viewsets.ModelViewSet):
    queryset = HomeSlider.objects.all()
    serializer_class = AdminSliderSerializer
    permission_classes = [IsVerifiedAdmin]
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    pagination_class = AdminSliderPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = HomeSlider.objects.all()
        is_active = self.request.query_params.get('is_active')
        if is_active is None:
            return qs
        value = str(is_active).lower()
        if value in ('true', '1'):
            return qs.filter(is_active=True)
        if value in ('false', '0'):
            return qs.filter(is_active=False)
        return qs


@extend_schema_view(
    list=extend_schema(
        tags=['Public Sliders'],
        summary='List active home sliders',
        description=(
            'Unauthenticated. Active-only, ordered by priority ascending, '
            'then oldest first. No pagination.'
        ),
        responses={200: PublicSliderSerializer(many=True)},
    ),
)
class PublicSliderViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = PublicSliderSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle]
    pagination_class = None
    http_method_names = ['get', 'head', 'options']

    def get_queryset(self):
        return HomeSlider.objects.filter(is_active=True).order_by(
            'priority', 'created_at', 'id',
        )

    @method_decorator(cache_control(public=True, max_age=300))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
