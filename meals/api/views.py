from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from permissions.base_permissions import HasGroupPermission

from ..filters import MealCategoryFilter
from ..models import MealCategory
from .serializers import MealCreateUpdateSerializer, MealDetailSerializer, MealListSerializer

MANAGER_GROUPS = ['ADMIN', 'OUTLET_MANAGER']
MEAL_TYPE_VALUES = [choice.value for choice in MealCategory.MealType]


@extend_schema_view(
    list=extend_schema(
        tags=['Meal Management'],
        summary='List meals',
        parameters=[
            OpenApiParameter(name='is_active', type=bool, description='Filter by active status'),
            OpenApiParameter(
                name='meal_type',
                type=str,
                description='Filter by meal type',
                enum=MEAL_TYPE_VALUES,
            ),
            OpenApiParameter(name='search', type=str, description='Search by meal name'),
        ],
        responses={200: MealListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Meal Management'],
        summary='Retrieve meal detail',
        description=(
            'Public meal detail includes pricing_status and current_cycle_offering '
            '(finalized menu servings, package total, per-meal rate) when available. '
            'Package price is published by cycle finalize — not set on create.'
        ),
        responses={200: MealDetailSerializer, 404: OpenApiResponse(description='Meal not found')},
    ),
    create=extend_schema(
        tags=['Meal Management'],
        summary='Create meal',
        description='Create a meal package without total_price. Price is published when a cycle plan is finalized.',
        request={'multipart/form-data': MealCreateUpdateSerializer},
        responses={
            201: MealDetailSerializer,
            400: OpenApiResponse(description='Validation error'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Manager permission required'),
        },
        examples=[
            OpenApiExample(
                'Create meal',
                value={
                    'meal_name': 'Chicken Rice Bowl',
                    'meal_type': 'daily',
                    'is_active': True,
                },
                request_only=True,
            )
        ],
    ),
    partial_update=extend_schema(
        tags=['Meal Management'],
        summary='Update meal',
        request={'multipart/form-data': MealCreateUpdateSerializer},
        responses={
            200: MealDetailSerializer,
            400: OpenApiResponse(description='Validation error'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Manager permission required'),
            404: OpenApiResponse(description='Meal not found'),
        },
    ),
    destroy=extend_schema(
        tags=['Meal Management'],
        summary='Soft delete meal',
        description='Sets is_active=False instead of permanently deleting the record.',
        responses={204: OpenApiResponse(description='Meal deactivated')},
    ),
)
class MealCategoryViewSet(viewsets.ModelViewSet):
    queryset = MealCategory.objects.all()
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = MealCategoryFilter
    ordering_fields = ['created_at', 'total_price', 'meal_name']
    ordering = ['-created_at']
    required_groups = MANAGER_GROUPS
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), HasGroupPermission()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action in ['list', 'retrieve'] and not self._is_manager():
            queryset = queryset.filter(is_active=True)
        return queryset

    def _is_manager(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return user.groups.filter(name__in=MANAGER_GROUPS).exists()

    def get_serializer_class(self):
        if self.action == 'list':
            return MealListSerializer
        if self.action == 'retrieve':
            return MealDetailSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return MealCreateUpdateSerializer
        return MealDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        detail = MealDetailSerializer(serializer.instance, context=self.get_serializer_context())
        headers = self.get_success_headers(detail.data)
        return Response(detail.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        detail = MealDetailSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(detail.data)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
